from functools import wraps
import hashlib
import hmac
import math

from flask import current_app, g, jsonify, request

from fishtank.models.user import TOKEN_LIFETIME, AuthToken

# The web ui keeps its login in a cookie that scripts cannot read, api clients send "Authorization: Bearer <token>"
SESSION_COOKIE = 'fishtank_session'
# readable by the ui, which sends it back in CSRF_HEADER with every change it makes, see check_csrf
CSRF_COOKIE = 'fishtank_csrf'
CSRF_HEADER = 'X-CSRF-Token'
SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS')
# logging in and registering ignore the session cookie, so an expired cookie cannot keep anyone from logging in again
LOGIN_ENDPOINTS = ('auth.login', 'auth.register')


# Raised anywhere in a request, answered as {'status': 'error', 'message': ...} with the given http status
# field names the request field that is wrong, so a form can show the message next to it
# headers are added to the answer, e.g. Retry-After
class ApiError(Exception):
    def __init__(self, message, status_code=400, field=None, headers=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.field = field
        self.headers = headers or {}


def success(status_code=200, **body):
    return jsonify({'status': 'success', **body}), status_code


def error_response(message, status_code, field=None, headers=None):
    body = {'status': 'error', 'message': message}
    if field is not None:
        body['field'] = field
    response = jsonify(body)
    response.status_code = status_code
    if status_code == 401:
        response.headers['WWW-Authenticate'] = 'Bearer'
    response.headers.extend(headers or {})
    return response


# Answers 429 when the rate limit is used up for this key, the {} in message becomes the wait, e.g. "15 minutes"
def check_rate_limit(rate_limit, key, message):
    seconds = rate_limit.retry_after(key)
    if seconds:
        minutes = math.ceil(seconds / 60)
        wait = 'a minute' if minutes <= 1 else '{} minutes'.format(minutes)
        raise ApiError(message.format(wait), 429, headers={'Retry-After': str(seconds)})


# the address the request comes from, behind a proxy create_app trusts its X-Forwarded-For (FISHTANK_PROXIES)
def client_ip():
    return request.remote_addr or 'unknown'


# the json object sent with the request, an empty body counts as an empty object when allowed
def json_body(allow_empty=False):
    if allow_empty and not request.get_data():
        return {}
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ApiError('please send a json object')
    return payload


def reject_unknown_fields(payload, allowed):
    for field in payload:
        if field not in allowed:
            raise ApiError('{} is not a known field'.format(field), field=field)


# whole numbers only, json true and false would otherwise pass as 1 and 0
def is_integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


# The csrf token belongs to one login token, so it cannot be made up without knowing the login token,
# and knowing it does not tell the login token. Nothing more needs to be stored
def csrf_token_for(token):
    return hashlib.sha256(('csrf:' + token).encode('utf-8')).hexdigest()


# Browsers send cookies with requests that other sites start, a form on another site could post to the api
# as the logged in user. Only the ui can read the csrf cookie, so only the ui can send its value back
def check_csrf(token):
    if request.method in SAFE_METHODS:
        return
    sent = request.headers.get(CSRF_HEADER, '')
    if not hmac.compare_digest(sent, csrf_token_for(token)):
        raise ApiError('This request is missing its csrf token, please reload the page', 403)


def set_session_cookies(response, token):
    secure = current_app.config['FISHTANK_SECURE_COOKIES']
    max_age = int(TOKEN_LIFETIME.total_seconds())
    response.set_cookie(SESSION_COOKIE, token, max_age=max_age, path='/fishtank_api', secure=secure,
                        httponly=True, samesite='Lax')
    # the ui reads it on every page, so its path is the whole site
    response.set_cookie(CSRF_COOKIE, csrf_token_for(token), max_age=max_age, path='/', secure=secure,
                        httponly=False, samesite='Lax')


def clear_session_cookies(response):
    secure = current_app.config['FISHTANK_SECURE_COOKIES']
    response.delete_cookie(SESSION_COOKIE, path='/fishtank_api', secure=secure, httponly=True, samesite='Lax')
    response.delete_cookie(CSRF_COOKIE, path='/', secure=secure, samesite='Lax')


# A request is from a visitor unless it carries "Authorization: Bearer <token>" or the session cookie
# A token that is wrong or expired is refused instead of quietly treating the request as a visitor's,
# a refused cookie is removed with the answer, so the next request is a visitor's
def load_current_user():
    g.user = None
    g.token = None
    g.clear_session = False
    header = request.headers.get('Authorization')
    if header is not None:
        scheme, _, token = header.partition(' ')
        token = token.strip()
        if scheme.lower() != 'bearer' or not token:
            raise ApiError('Authorization header must be "Bearer <token>"', 401)
        record = AuthToken.find_valid(token)
        if record is None:
            raise ApiError('Login token is invalid or expired, please log in again', 401)
    else:
        token = request.cookies.get(SESSION_COOKIE)
        if not token or request.endpoint in LOGIN_ENDPOINTS:
            return
        record = AuthToken.find_valid(token)
        if record is None:
            g.clear_session = True
            raise ApiError('Your login has expired, please log in again', 401)
        check_csrf(token)
    g.user = record.user
    g.token = record


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if g.user is None:
            raise ApiError('Please log in first', 401)
        return view(*args, **kwargs)
    return wrapper


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if g.user is None:
            raise ApiError('Please log in first', 401)
        if not g.user.is_admin():
            raise ApiError('Only admins can do this', 403)
        return view(*args, **kwargs)
    return wrapper
