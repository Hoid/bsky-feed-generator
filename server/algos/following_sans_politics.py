from datetime import datetime
from typing import Optional

from server import config
from server.database import Follow, Post

uri = config.FEED_URI
CURSOR_EOF = "eof"


def handler(cursor: Optional[str], limit: int, requester_did: str | None = None) -> dict:
    following = Follow.select('subject').where(Follow.author == requester_did).dicts()
    following_dids: list[str] = [follow['subject'] for follow in following]

    posts_by_following = (
        Post.select()
        .where(Post.author.in_(following_dids))
        .order_by(Post.cid.desc())
        .order_by(Post.indexed_at.desc())
        .limit(limit)
    )

    if cursor:
        if cursor == CURSOR_EOF:
            return {"cursor": CURSOR_EOF, "feed": []}
        cursor_parts = cursor.split("::")
        if len(cursor_parts) != 2:
            raise ValueError("Malformed cursor")

        indexed_at, cid = cursor_parts
        indexed_at = datetime.fromtimestamp(int(indexed_at) / 1000)
        posts_by_following = posts_by_following.where(
            ((Post.indexed_at == indexed_at) & (Post.cid < cid))
            | (Post.indexed_at < indexed_at)
        )

    feed = [{"post": post.uri} for post in posts_by_following]

    cursor = CURSOR_EOF
    last_post = posts_by_following[-1] if posts_by_following else None
    if last_post:
        cursor = f"{int(last_post.indexed_at.timestamp() * 1000)}::{last_post.cid}"

    return {"cursor": cursor, "feed": feed}
