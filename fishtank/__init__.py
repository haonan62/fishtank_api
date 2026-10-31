import os

from flask import Flask
from werkzeug.exceptions import HTTPException

from fishtank.api import auth, fish, fishtanks, users
from fishtank.api.common import ApiError, error_response, load_current_user
from fishtank.cli import register_commands
from fishtank.db import DEFAULT_APP_DATABASE, database, prepare_database, use_database

API_PREFIX = '/fishtank_api'


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
        return error_response(error.message, error.status_code)

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        return error_response(error.description, error.code)

    register_commands(app)
    return app
