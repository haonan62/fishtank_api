import click

from fishtank.api.auth import check_new_credentials
from fishtank.api.users import LastAdminError, change_role
from fishtank.models.user import ROLE_ADMIN, ROLES, User


# "flask --app fishtank create-admin <username>" makes the first admin, admins can then promote other users
def register_commands(app):
    @app.cli.command('create-admin')
    @click.argument('username')
    @click.password_option()
    def create_admin(username, password):
        problem = check_new_credentials(username, password)
        if problem is not None:
            raise click.ClickException(problem[1])
        if User.get_or_none(User.username == username) is not None:
            raise click.ClickException('{} already exists, use "flask --app fishtank set-role {} admin"'.format(username, username))
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
