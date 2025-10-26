from datetime import datetime, timezone

import peewee

db = peewee.SqliteDatabase("feed_database.db")


class BaseModel(peewee.Model):
    class Meta:
        database = db


class Post(BaseModel):
    author = peewee.CharField(index=True)
    uri = peewee.CharField(index=True)
    cid = peewee.CharField()
    text = peewee.TextField()
    reply_parent = peewee.CharField(null=True, default=None)
    reply_root = peewee.CharField(null=True, default=None)
    created_at = peewee.DateTimeField()
    indexed_at = peewee.DateTimeField(default=datetime.now(timezone.utc))


class Like(BaseModel):
    author = peewee.CharField(index=True)
    uri = peewee.CharField(index=True)
    cid = peewee.CharField()
    created_at = peewee.DateTimeField()
    indexed_at = peewee.DateTimeField(default=datetime.now(timezone.utc))


class Repost(BaseModel):
    author = peewee.CharField(index=True)
    uri = peewee.CharField(index=True)
    cid = peewee.CharField()
    created_at = peewee.DateTimeField()
    indexed_at = peewee.DateTimeField(default=datetime.now(timezone.utc))


class Follow(BaseModel):
    author = peewee.CharField(index=True)
    subject = peewee.CharField(index=True)
    uri = peewee.CharField(index=True)
    created_at = peewee.DateTimeField()
    indexed_at = peewee.DateTimeField(default=datetime.now(timezone.utc))


class FirehoseSubscriptionState(BaseModel):
    service = peewee.CharField(unique=True)
    cursor = peewee.BigIntegerField()


if db.is_closed():
    db.connect()
    db.create_tables([Post, Like, Repost, Follow, FirehoseSubscriptionState])
