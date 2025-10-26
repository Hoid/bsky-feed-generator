import datetime
from collections import defaultdict

from atproto import models

from server import config
from server.database import Follow, Like, Post, Repost, db
from server.logger import logger
from server.utils import get_author_from_uri


def is_archive_post(record: "models.AppBskyFeedPost.Record") -> bool:
    # Sometimes users will import old posts from Twitter/X which con flood a feed with
    # old posts. Unfortunately, the only way to test for this is to look an old
    # created_at date. However, there are other reasons why a post might have an old
    # date, such as firehose or firehose consumer outages. It is up to you, the feed
    # creator to weigh the pros and cons, and optionally include this function in
    # your filter conditions, and adjust the threshold to your liking.
    #
    # See https://github.com/MarshalX/bluesky-feed-generator/pull/21

    archived_threshold = datetime.timedelta(days=7)
    created_at = datetime.datetime.fromisoformat(record.created_at)
    now = datetime.datetime.now(datetime.UTC)

    return now - created_at > archived_threshold


def should_ignore_post(created_post: dict) -> bool:
    record = created_post["record"]
    uri = created_post["uri"]

    if config.IGNORE_ARCHIVED_POSTS and is_archive_post(record):
        logger.debug(f"Ignoring archived post: {uri}")
        return True

    if config.IGNORE_REPLY_POSTS and record.reply:
        logger.debug(f"Ignoring reply post: {uri}")
        return True

    return False


def operations_callback(ops: defaultdict) -> None:
    # Here we can filter, process, run ML classification, etc.
    # After our feed alg we can save posts into our DB
    # Also, we should process deleted posts to remove them from our DB and keep it in sync

    # Create posts
    posts_to_create = []
    for created_post in ops[models.ids.AppBskyFeedPost]["created"]:
        author = get_author_from_uri(created_post["uri"])
        record = created_post["record"]

        is_post_with_images = isinstance(record.embed, models.AppBskyEmbedImages.Main)
        is_post_with_video = isinstance(record.embed, models.AppBskyEmbedVideo.Main)
        inlined_text = record.text.replace("\n", " ")

        # print all texts just as demo that data stream works
        logger.debug(
            f"NEW POST "
            f"[CREATED_AT={record.created_at}]"
            f"[AUTHOR={author}]"
            f"[WITH_IMAGE={is_post_with_images}]"
            f"[WITH_VIDEO={is_post_with_video}]"
            f": {inlined_text}"
        )

        if should_ignore_post(created_post):
            continue

        reply_root = reply_parent = None
        if record.reply:
            reply_root = record.reply.root.uri
            reply_parent = record.reply.parent.uri

        post_dict = {
            "created_at": record.created_at,
            "author": author,
            "uri": created_post["uri"],
            "cid": created_post["cid"],
            "text": record.text,
            "reply_parent": reply_parent,
            "reply_root": reply_root,
        }
        posts_to_create.append(post_dict)

    # Create likes
    likes_to_create = []
    for like in ops[models.ids.AppBskyFeedLike]["created"]:
        like_dict = {
            "created_at": like["record"]["created_at"],
            "author": like["author"],
            "uri": like["record"]["subject"]["uri"],
            "cid": like["record"]["subject"]["cid"],
        }
        likes_to_create.append(like_dict)

    # Create reposts
    reposts_to_create = []
    for repost in ops[models.ids.AppBskyFeedRepost]["created"]:
        repost_dict = {
            "created_at": repost["record"]["created_at"],
            "author": repost["author"],
            "uri": repost["record"]["subject"]["uri"],
            "cid": repost["record"]["subject"]["cid"],
        }
        reposts_to_create.append(repost_dict)

    # Create follows
    follows_to_create = []
    for follow in ops[models.ids.AppBskyGraphFollow]["created"]:
        follow_dict = {
            "created_at": follow["record"]["created_at"],
            "author": follow["author"],
            "subject": follow["record"]["subject"],
        }
        follows_to_create.append(follow_dict)

    # Create follows in db
    if follows_to_create:
        with db.atomic():
            for follow_dict in follows_to_create:
                Follow.create(**follow_dict)
        logger.debug(f"Follows indexed: {len(follows_to_create)}")

    # Create posts in db
    if posts_to_create:
        with db.atomic():
            for post_dict in posts_to_create:
                Post.create(**post_dict)
        logger.debug(f"Posts indexed: {len(posts_to_create)}")

    # Create likes in db
    if likes_to_create:
        with db.atomic():
            for like_dict in likes_to_create:
                Like.create(**like_dict)
        logger.debug(f"Likes indexed: {len(likes_to_create)}")

    # Create reposts in db
    if reposts_to_create:
        with db.atomic():
            for repost_dict in reposts_to_create:
                Repost.create(**repost_dict)
        logger.debug(f"Reposts indexed: {len(reposts_to_create)}")

    # Delete posts in db
    posts_to_delete = ops[models.ids.AppBskyFeedPost]["deleted"]
    if posts_to_delete:
        post_uris_to_delete = [post["uri"] for post in posts_to_delete]
        Post.delete().where(Post.uri.in_(post_uris_to_delete))
        logger.debug(f"Posts deleted: {len(post_uris_to_delete)}")

    # Delete follows in db
    follows_to_delete = ops[models.ids.AppBskyGraphFollow]["deleted"]
    follow_uris = []
    if follows_to_delete:
        for follow in follows_to_delete:
            follow_uris.append(follow["uri"])
        Follow.delete().where(
            Follow.uri.in_(follow_uris)
        )
        logger.debug(f"Follows deleted: {len(follows_to_delete)}")

    # Delete likes in db
    likes_to_delete = ops[models.ids.AppBskyFeedLike]["deleted"]
    like_uris = []
    if likes_to_delete:
        for like in likes_to_delete:
            like_uris.append(like["uri"])
        Like.delete().where(
            Like.uri.in_(like_uris)
        )
        logger.debug(f"Likes deleted: {len(likes_to_delete)}")

    # Delete reposts in db
    reposts_to_delete = ops[models.ids.AppBskyFeedRepost]["deleted"]
    repost_uris = []
    if reposts_to_delete:
        for repost in reposts_to_delete:
            repost_uris.append(repost["uri"])
        Repost.delete().where(
            Repost.uri.in_(repost_uris)
        )
        logger.debug(f"Reposts deleted: {len(reposts_to_delete)}")
