import os

import click
from flask import Flask
from werkzeug.exceptions import HTTPException

import migrate_db
from api import auth, fish, fishtanks, users
from api.common import ApiError, error_response, load_current_user
from api.users import LastAdminError, change_role
from models.database import DEFAULT_APP_DATABASE, SEED_DATABASE, database, use_database
from models.user import ROLE_ADMIN, ROLES, User

API_PREFIX = '/fishtank_api'


# The app works on its own database, made from the committed data/fish.db the first time it starts
# and brought to the latest schema every time after
def prepare_database(path):
    if os.path.exists(path):
        migrate_db.upgrade(path)
    else:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        migrate_db.migrate(SEED_DATABASE, path)


# The database is FISHTANK_DATABASE when set, instance/fishtank.db otherwise
# Run with "python app.py", or in production with gunicorn "app:create_app()"
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


# "flask --app app create-admin <username>" makes the first admin, admins can then promote other users
def register_commands(app):
    @app.cli.command('create-admin')
    @click.argument('username')
    @click.password_option()
    def create_admin(username, password):
        problem = auth.check_new_credentials(username, password)
        if problem is not None:
            raise click.ClickException(problem)
        if User.get_or_none(User.username == username) is not None:
            raise click.ClickException('{} already exists, use "flask --app app set-role {} admin"'.format(username, username))
        User.create_with_password(username, password, role=ROLE_ADMIN)
        click.echo('{} is now an admin'.format(username))

    @app.cli.command('set-role')
    @click.argument('username')
    @click.argument('role', type=click.Choice(ROLES))
    def set_role(username, role):
        user = User.get_or_none(User.username == username)
        if user is None:
            raise click.ClickException('no such user: {}'.format(username))
        try:
            change_role(user, role)
        except LastAdminError as e:
            raise click.ClickException(str(e))
        click.echo('{} is now {}'.format(user.username, role))


if __name__ == '__main__':
    create_app().run(debug=True)
