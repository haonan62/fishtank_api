import re

from flask import Blueprint, g
from peewee import IntegrityError

from fishtank.api.common import (ApiError, check_rate_limit, clear_session_cookies, client_ip, json_body,
                                 login_required, reject_unknown_fields, set_session_cookies, success)
from fishtank.api.users import LastAdminError, delete_user
from fishtank.db import database, to_iso
from fishtank.models.rate_limit import FAILED_LOGINS_PER_IP, FAILED_LOGINS_PER_USERNAME, REGISTRATIONS_PER_IP
from fishtank.models.user import AuthToken, User

blueprint = Blueprint('auth', __name__)

USERNAME_PATTERN = re.compile(r'^[A-Za-z0-9_.-]{3,32}$')
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128


# returns (field, error message), or None when the username and password can be used
def check_new_credentials(username, password):
    if not isinstance(username, str) or not USERNAME_PATTERN.match(username):
        return 'username', 'username must be 3 to 32 letters, digits, dots, dashes or underscores'
    problem = check_new_password(password)
    if problem is not None:
        return 'password', problem
    return None


def check_new_password(password):
    if not isinstance(password, str) or not PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH:
        return 'password must be {} to {} characters'.format(PASSWORD_MIN_LENGTH, PASSWORD_MAX_LENGTH)
    return None


# The token is in the answer for api clients, the web ui uses the session cookie instead
def logged_in(user, status_code=200):
    token, record = AuthToken.issue(user)
    response, status_code = success(status_code, user=user.to_dic(), token=token, expires_at=to_iso(record.expires_at))
    set_session_cookies(response, token)
    return response, status_code


# usernames are unique ignoring case, so are their rate limits
def username_key(username):
    return username.lower()


def check_login_limits(username):
    message = 'Too many failed logins, please try again in {}'
    check_rate_limit(FAILED_LOGINS_PER_USERNAME, username_key(username), message)
    check_rate_limit(FAILED_LOGINS_PER_IP, client_ip(), message)


def count_failed_login(username):
    FAILED_LOGINS_PER_USERNAME.hit(username_key(username))
    FAILED_LOGINS_PER_IP.hit(client_ip())


# Changing the password or removing the account asks for the password again,
# wrong guesses count as failed logins, so a stolen session cannot be used to find the password
def confirm_password(payload, field):
    password = payload.get(field)
    if not isinstance(password, str) or not password:
        raise ApiError('please enter your password', field=field)
    check_login_limits(g.user.username)
    if User.authenticate(g.user.username, password) is None:
        count_failed_login(g.user.username)
        raise ApiError('the password is not right', 403, field=field)


# everyone registers as a user, admins are made with "flask --app fishtank create-admin" or by another admin
@blueprint.route('/auth/register', methods=['POST'])
def register():
    payload = json_body()
    reject_unknown_fields(payload, {'username', 'password'})
    username, password = payload.get('username'), payload.get('password')
    problem = check_new_credentials(username, password)
    if problem is not None:
        raise ApiError(problem[1], field=problem[0])
    check_rate_limit(REGISTRATIONS_PER_IP, client_ip(),
                     'Too many new accounts from your network, please try again in {}')
    try:
        with database.atomic():
            user = User.create_with_password(username, password)
    except IntegrityError:
        raise ApiError('username {} is already taken'.format(username), 409, field='username')
    REGISTRATIONS_PER_IP.hit(client_ip())
    return logged_in(user, 201)


@blueprint.route('/auth/login', methods=['POST'])
def login():
    payload = json_body()
    username, password = payload.get('username'), payload.get('password')
    if not isinstance(username, str) or not isinstance(password, str):
        raise ApiError('please provide username and password')
    # checked before the password, so the right password is no use once the limit is reached
    check_login_limits(username)
    user = User.authenticate(username, password)
    if user is None:
        count_failed_login(username)
        raise ApiError('wrong username or password', 401)
    FAILED_LOGINS_PER_USERNAME.reset(username_key(username))
    return logged_in(user)


# ends the login of this token only, other devices stay logged in
@blueprint.route('/auth/logout', methods=['POST'])
@login_required
def logout():
    g.token.delete_instance()
    response, status_code = success(message='logged out')
    clear_session_cookies(response)
    return response, status_code


@blueprint.route('/auth/me')
@login_required
def me():
    return success(user=g.user.to_dic())


# body: {"current_password": ..., "new_password": ...}
# every other login of the user ends, the login of this request stays
@blueprint.route('/auth/password', methods=['POST'])
@login_required
def change_password():
    payload = json_body()
    reject_unknown_fields(payload, {'current_password', 'new_password'})
    confirm_password(payload, 'current_password')
    new_password = payload.get('new_password')
    problem = check_new_password(new_password)
    if problem is not None:
        raise ApiError('new ' + problem, field='new_password')
    with database.atomic():
        g.user.set_password(new_password)
        g.user.save()
        AuthToken.delete().where((AuthToken.user == g.user) & (AuthToken.id != g.token.id)).execute()
    return success(user=g.user.to_dic(), message='password changed')


# removes the account with its logins and fishtanks, body: {"password": ...}
@blueprint.route('/auth/me', methods=['DELETE'])
@login_required
def delete_account():
    payload = json_body()
    reject_unknown_fields(payload, {'password'})
    confirm_password(payload, 'password')
    try:
        delete_user(g.user)
    except LastAdminError as e:
        raise ApiError('{}, make another user an admin first'.format(e), 409)
    response, status_code = success(message='account removed')
    clear_session_cookies(response)
    return response, status_code
