from datetime import timedelta
import hashlib
import secrets

from peewee import *
from werkzeug.security import check_password_hash, generate_password_hash

from fishtank.db import BaseModel, to_iso, utcnow

ROLE_USER = 'user'
ROLE_ADMIN = 'admin'
ROLES = (ROLE_USER, ROLE_ADMIN)

TOKEN_LIFETIME = timedelta(days=30)

# checked against when a username does not exist, so a wrong username takes as long as a wrong password
_UNUSED_PASSWORD_HASH = generate_password_hash(secrets.token_hex(16))


# Visitors without an account can still create and simulate fishtanks, a user keeps their fishtanks,
# an admin also adds, changes and removes fish
class User(BaseModel):
    id = AutoField()
    username = CharField(unique=True)
    password_hash = TextField()
    role = CharField(default=ROLE_USER)
    created_at = DateTimeField(default=utcnow)

    class Meta:
        table_name = 'user'

    @classmethod
    def create_with_password(cls, username, password, role=ROLE_USER):
        return cls.create(username=username, password_hash=generate_password_hash(password), role=role)

    # returns the user when the password is right, None otherwise
    @classmethod
    def authenticate(cls, username, password):
        user = cls.get_or_none(cls.username == username)
        if user is None:
            check_password_hash(_UNUSED_PASSWORD_HASH, password)
            return None
        if not check_password_hash(user.password_hash, password):
            return None
        return user

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def is_admin(self):
        return self.role == ROLE_ADMIN

    def to_dic(self):
        return {
            'id': self.id,
            'username': self.username,
            'role': self.role,
            'created_at': to_iso(self.created_at)
        }


def hash_token(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


# A login token is handed to the user once, only its hash is stored
class AuthToken(BaseModel):
    id = AutoField()
    user = ForeignKeyField(User, backref='tokens', column_name='user_id', on_delete='CASCADE')
    token_hash = CharField(unique=True)
    created_at = DateTimeField(default=utcnow)
    expires_at = DateTimeField()

    class Meta:
        table_name = 'auth_token'

    # returns the new token in plain text together with its record
    @classmethod
    def issue(cls, user):
        token = secrets.token_urlsafe(32)
        record = cls.create(user=user, token_hash=hash_token(token), expires_at=utcnow() + TOKEN_LIFETIME)
        return token, record

    # returns the token record when the token is valid, expired tokens are removed on the way
    @classmethod
    def find_valid(cls, token):
        record = cls.get_or_none(cls.token_hash == hash_token(token))
        if record is None:
            return None
        if record.expires_at <= utcnow():
            record.delete_instance()
            return None
        return record
