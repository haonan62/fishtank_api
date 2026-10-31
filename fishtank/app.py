import gzip
import os

from flask import Flask, abort, g, request, send_from_directory
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import safe_join

from fishtank.api import auth, fish, fishtanks, users
from fishtank.api.common import ApiError, clear_session_cookies, error_response, load_current_user
from fishtank.cli import register_commands
from fishtank.db import DEFAULT_APP_DATABASE, database, prepare_database, use_database

API_PREFIX = '/fishtank_api'

# the web ui, built with "npm run build" in frontend/
FRONTEND_DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frontend', 'dist')
# vite puts a hash in the name of every built asset, so they can be cached for good
ASSET_MAX_AGE = 365 * 24 * 3600
GZIP_MIN_SIZE = 1024

# The built ui only loads its own files and the Google Fonts stylesheet, fish pictures are hosted by FishBase
# React sets inline styles through the dom, which a policy without 'unsafe-inline' still allows
CONTENT_SECURITY_POLICY = '; '.join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data: https://www.fishbase.se",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])
SECURITY_HEADERS = {
    'Content-Security-Policy': CONTENT_SECURITY_POLICY,
    'X-Content-Type-Options': 'nosniff',
    # fishtank keys are in the urls of the ui, other sites only learn which site a visitor comes from
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    # for browsers that do not know frame-ancestors
    'X-Frame-Options': 'DENY',
}
HSTS = 'max-age=31536000'


# The database is FISHTANK_DATABASE when set, instance/fishtank.db otherwise
# Run with "flask --app fishtank run --debug", or in production with gunicorn "fishtank:create_app()"
# FISHTANK_SECURE_COOKIES=0 lets the login cookie work over plain http, for local use only
# FISHTANK_PROXIES is the number of proxies in front of the app (e.g. 1 for nginx), whose X-Forwarded-For and
# X-Forwarded-Proto are then trusted, so rate limits count the address of the visitor instead of the proxy's
def create_app(database_path=None):
    database_path = database_path or os.environ.get('FISHTANK_DATABASE') or DEFAULT_APP_DATABASE
    prepare_database(database_path)
    use_database(database_path)

    app = Flask(__name__)
    app.config['FISHTANK_SECURE_COOKIES'] = os.environ.get('FISHTANK_SECURE_COOKIES', '1') != '0'
    proxies = int(os.environ.get('FISHTANK_PROXIES', '0'))
    if proxies:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=proxies, x_proto=proxies)

    @app.route(API_PREFIX)
    def api_root():
        return 'Welcome to fishtank api'

    for module in (auth, fish, fishtanks, users):
        app.register_blueprint(module.blueprint, url_prefix=API_PREFIX)

    @app.before_request
    def open_database_and_find_user():
        database.connect(reuse_if_open=True)
        load_current_user()

    @app.teardown_request
    def close_database(exception):
        if not database.is_closed():
            database.close()

    @app.errorhandler(ApiError)
    def handle_api_error(error):
        return error_response(error.message, error.status_code, error.field, error.headers)

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        return error_response(error.description, error.code)

    @app.after_request
    def finish_response(response):
        if g.get('clear_session'):
            clear_session_cookies(response)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        if request.is_secure:
            response.headers.setdefault('Strict-Transport-Security', HSTS)
        return gzip_json(response)

    register_frontend(app)
    register_commands(app)
    return app


# The fish catalogue is 650 KB of json and 50 KB gzipped, files are left to the web server in production
def gzip_json(response):
    if response.direct_passthrough or response.mimetype != 'application/json' or \
            'gzip' not in request.headers.get('Accept-Encoding', '') or 'Content-Encoding' in response.headers:
        return response
    data = response.get_data()
    if len(data) < GZIP_MIN_SIZE:
        return response
    response.set_data(gzip.compress(data, compresslevel=6))
    response.headers['Content-Encoding'] = 'gzip'
    response.vary.add('Accept-Encoding')
    return response


# Every path outside the api is the web ui: a built file when there is one, index.html otherwise,
# so the ui's own routes such as /tanks/<key> work when opened directly
def register_frontend(app):
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def frontend(path):
        if path == API_PREFIX.strip('/') or path.startswith(API_PREFIX.strip('/') + '/'):
            abort(404)
        if not os.path.isfile(os.path.join(FRONTEND_DIST, 'index.html')):
            abort(404, description='The web ui is not built yet, run "npm run build" in frontend/')
        file_path = safe_join(FRONTEND_DIST, path) if path else None
        if file_path is not None and os.path.isfile(file_path):
            max_age = ASSET_MAX_AGE if path.startswith('assets/') else 0
            return send_from_directory(FRONTEND_DIST, path, max_age=max_age)
        return send_from_directory(FRONTEND_DIST, 'index.html', max_age=0)
