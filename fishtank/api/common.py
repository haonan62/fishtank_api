from functools import wraps

from flask import g, jsonify, request

from fishtank.models.user import AuthToken


# Raised anywhere in a request, answered as {'status': 'error', 'message': ...} with the given http status
class ApiError(Exception):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def success(status_code=200, **body):
    return jsonify({'status': 'success', **body}), status_code


def error_response(message, status_code):
    response = jsonify({'status': 'error', 'message': message})
    response.status_code = status_code
    if status_code == 401:
        response.headers['WWW-Authenticate'] = 'Bearer'
    return response


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
            raise ApiError('{} is not a known field'.format(field))


# whole numbers only, json true and false would otherwise pass as 1 and 0
def is_integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


# A request is from a visitor unless it carries "Authorization: Bearer <token>"
# A token that is wrong or expired is refused instead of quietly treating the request as a visitor's
def load_current_user():
    g.user = None
    g.token = None
    header = request.headers.get('Authorization')
    if header is None:
        return
    scheme, _, token = header.partition(' ')
    token = token.strip()
    if scheme.lower() != 'bearer' or not token:
        raise ApiError('Authorization header must be "Bearer <token>"', 401)
    record = AuthToken.find_valid(token)
    if record is None:
        raise ApiError('Login token is invalid or expired, please log in again', 401)
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
