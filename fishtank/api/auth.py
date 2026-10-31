import re

from flask import Blueprint, g
from peewee import IntegrityError

from fishtank.api.common import ApiError, json_body, login_required, reject_unknown_fields, success
from fishtank.db import database, to_iso
from fishtank.models.user import AuthToken, User

blueprint = Blueprint('auth', __name__)

USERNAME_PATTERN = re.compile(r'^[A-Za-z0-9_.-]{3,32}$')
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128


# returns (field, error message), or None when the username and password can be used
def check_new_credentials(username, password):
    if not isinstance(username, str) or not USERNAME_PATTERN.match(username):
        return 'username', 'username must be 3 to 32 letters, digits, dots, dashes or underscores'
    if not isinstance(password, str) or not PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH:
        return 'password', 'password must be {} to {} characters'.format(PASSWORD_MIN_LENGTH, PASSWORD_MAX_LENGTH)
    return None


def logged_in(user, status_code=200):
    token, record = AuthToken.issue(user)
    return success(status_code, user=user.to_dic(), token=token, expires_at=to_iso(record.expires_at))


# everyone registers as a user, admins are made with "flask --app fishtank create-admin" or by another admin
@blueprint.route('/auth/register', methods=['POST'])
def register():
    payload = json_body()
    reject_unknown_fields(payload, {'username', 'password'})
    username, password = payload.get('username'), payload.get('password')
    problem = check_new_credentials(username, password)
    if problem is not None:
        raise ApiError(problem[1], field=problem[0])
    try:
        with database.atomic():
            user = User.create_with_password(username, password)
    except IntegrityError:
        raise ApiError('username {} is already taken'.format(username), 409, field='username')
    return logged_in(user, 201)


@blueprint.route('/auth/login', methods=['POST'])
def login():
    payload = json_body()
    username, password = payload.get('username'), payload.get('password')
    if not isinstance(username, str) or not isinstance(password, str):
        raise ApiError('please provide username and password')
    user = User.authenticate(username, password)
    if user is None:
        raise ApiError('wrong username or password', 401)
    return logged_in(user)


# ends the login of this token only, other devices stay logged in
@blueprint.route('/auth/logout', methods=['POST'])
@login_required
def logout():
    g.token.delete_instance()
    return success(message='logged out')


@blueprint.route('/auth/me')
@login_required
def me():
    return success(user=g.user.to_dic())
