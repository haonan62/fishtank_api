from datetime import timedelta
import math

from peewee import *

from fishtank.db import BaseModel, database, utcnow


# One counted attempt, see RateLimit
class RateLimitHit(BaseModel):
    id = AutoField()
    bucket = CharField()
    key = CharField()
    created_at = DateTimeField(default=utcnow)

    class Meta:
        table_name = 'rate_limit_hit'


# At most `limit` attempts per key within a sliding window, e.g. 5 failed logins per username in 15 minutes
# The attempts live in the database, so every worker process of the app counts the same attempts
class RateLimit:
    def __init__(self, bucket, limit, window):
        self.bucket = bucket
        self.limit = limit
        self.window = window

    def _recent(self, key):
        return RateLimitHit.select().where((RateLimitHit.bucket == self.bucket) & (RateLimitHit.key == key) &
                                           (RateLimitHit.created_at > utcnow() - self.window))

    # seconds until the next attempt is allowed, 0 when one is allowed now
    def retry_after(self, key):
        recent = self._recent(key)
        if recent.count() < self.limit:
            return 0
        # the oldest attempts leave the window first, one more is allowed once enough of them have left
        freed_by = recent.order_by(RateLimitHit.created_at.desc()).offset(self.limit - 1).first()
        wait = (freed_by.created_at + self.window - utcnow()).total_seconds()
        return max(1, math.ceil(wait))

    # counts an attempt, attempts older than the window are removed on the way
    def hit(self, key):
        with database.atomic():
            RateLimitHit.delete().where((RateLimitHit.bucket == self.bucket) & (RateLimitHit.key == key) &
                                        (RateLimitHit.created_at <= utcnow() - self.window)).execute()
            RateLimitHit.create(bucket=self.bucket, key=key, created_at=utcnow())

    def reset(self, key):
        RateLimitHit.delete().where((RateLimitHit.bucket == self.bucket) & (RateLimitHit.key == key)).execute()


# Failed logins are limited per username, so one account cannot be guessed at from many addresses,
# and per ip address, so one address cannot try many accounts. Wrong passwords given to change the password
# or delete the account count as failed logins too
FAILED_LOGINS_PER_USERNAME = RateLimit('failed_login_username', 5, timedelta(minutes=15))
FAILED_LOGINS_PER_IP = RateLimit('failed_login_ip', 20, timedelta(minutes=15))
REGISTRATIONS_PER_IP = RateLimit('register_ip', 10, timedelta(hours=1))
# visitors need no account to create fishtanks, which would otherwise let one script fill the database
VISITOR_TANKS_PER_IP = RateLimit('visitor_tank_ip', 30, timedelta(hours=1))

