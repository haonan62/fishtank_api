import gzip
import os

from flask import Flask, abort, request, send_from_directory
from werkzeug.exceptions import HTTPException
from werkzeug.security import safe_join

from fishtank.api import auth, fish, fishtanks, users
from fishtank.api.common import ApiError, error_response, load_current_user
from fishtank.cli import register_commands
from fishtank.db import DEFAULT_APP_DATABASE, database, prepare_database, use_database

API_PREFIX = '/fishtank_api'

# the web ui, built with "npm run build" in frontend/
FRONTEND_DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frontend', 'dist')
# vite puts a hash in the name of every built asset, so they can be cached for good
ASSET_MAX_AGE = 365 * 24 * 3600
GZIP_MIN_SIZE = 1024


# The database is FISHTANK_DATABASE when set, instance/fishtank.db otherwise
# Run with "flask --app fishtank run --debug", or in production with gunicorn "fishtank:create_app()"
def create_app(database_path=None):
    database_path = database_path or os.environ.get('FISHTANK_DATABASE') or DEFAULT_APP_DATABASE
    prepare_database(database_path)
    use_database(database_path)

    app = Flask(__name__)

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
        return error_response(error.message, error.status_code, error.field)

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        return error_response(error.description, error.code)

    @app.after_request
    def compress_json(response):
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
