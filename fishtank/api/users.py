from flask import Blueprint

from fishtank.api.common import ApiError, admin_required, json_body, reject_unknown_fields, success
from fishtank.db import database
from fishtank.models.user import ROLE_ADMIN, ROLES, User

blueprint = Blueprint('users', __name__)


class LastAdminError(Exception):
    pass


# changes the role of a user, there is always at least one admin left
def change_role(user, role):
    with database.atomic('IMMEDIATE'):
        if user.role == ROLE_ADMIN and role != ROLE_ADMIN and \
                User.select().where(User.role == ROLE_ADMIN).count() <= 1:
            raise LastAdminError('{} is the last admin'.format(user.username))
        user.role = role
        user.save()


# removes a user, their login tokens and fishtanks go with them (on delete cascade),
# there is always at least one admin left
def delete_user(user):
    with database.atomic('IMMEDIATE'):
        if user.role == ROLE_ADMIN and User.select().where(User.role == ROLE_ADMIN).count() <= 1:
            raise LastAdminError('{} is the last admin'.format(user.username))
        User.delete().where(User.id == user.id).execute()


@blueprint.route('/users')
@admin_required
def list_users():
    return success(users=[user.to_dic() for user in User.select().order_by(User.id)])


# body: {"role": "user" or "admin"}
@blueprint.route('/users/<int:user_id>', methods=['PATCH'])
@admin_required
def update_user(user_id):
    payload = json_body()
    reject_unknown_fields(payload, {'role'})
    if payload.get('role') not in ROLES:
        raise ApiError('role must be one of: {}'.format(', '.join(ROLES)))
    user = User.get_or_none(User.id == user_id)
    if user is None:
        raise ApiError('no such user', 404)
    try:
        change_role(user, payload['role'])
    except LastAdminError as e:
        raise ApiError(str(e), 409)
    return success(user=user.to_dic())
