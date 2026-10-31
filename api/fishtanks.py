from flask import Blueprint, g

from api.common import ApiError, is_integer, json_body, login_required, reject_unknown_fields, success
from models.database import database
from models.fish import Fish
from models.fish_error import FishError
from models.fishtank_record import DEFAULT_SIZE, FishtankRecord

blueprint = Blueprint('fishtanks', __name__)

NAME_MAX_LENGTH = 100
SIZE_DIMENSIONS = ('length', 'width', 'height')
SIZE_MAX = 10000


def find_fishtank(key):
    record = FishtankRecord.find_for(key, g.user)
    if record is None:
        raise ApiError('no such fishtank', 404)
    return record


def read_name(payload):
    name = payload['name']
    if name is None:
        return None
    if not isinstance(name, str) or len(name.strip()) > NAME_MAX_LENGTH:
        raise ApiError('name must be text of at most {} characters'.format(NAME_MAX_LENGTH))
    return name.strip() or None


def read_size(payload):
    size = payload['size']
    if not isinstance(size, dict) or set(size) != set(SIZE_DIMENSIONS) or \
            not all(is_integer(size[dimension]) and 0 < size[dimension] <= SIZE_MAX for dimension in SIZE_DIMENSIONS):
        raise ApiError('size must be {{"length", "width", "height"}}, whole numbers from 1 to {}'.format(SIZE_MAX))
    return tuple(size[dimension] for dimension in SIZE_DIMENSIONS)


# A visitor's fishtank is kept for a day after its last change, a logged in user's fishtank is saved
# body (optional): {"name": text, "size": {"length", "width", "height"}}
@blueprint.route('/fishtanks', methods=['POST'])
def create_fishtank():
    payload = json_body(allow_empty=True)
    reject_unknown_fields(payload, {'name', 'size'})
    name = read_name(payload) if 'name' in payload else None
    size = read_size(payload) if 'size' in payload else DEFAULT_SIZE
    FishtankRecord.remove_expired()
    record = FishtankRecord.create_for(g.user, name=name, size=size)
    return success(201, fishtank=record.to_dic())


# the saved fishtanks of the logged in user, latest change first
@blueprint.route('/fishtanks')
@login_required
def list_fishtanks():
    records = (FishtankRecord.select().where(FishtankRecord.owner == g.user)
               .order_by(FishtankRecord.updated_at.desc(), FishtankRecord.id.desc()))
    return success(fishtanks=[record.to_dic() for record in records])


@blueprint.route('/fishtanks/<key>')
def get_fishtank(key):
    return success(fishtank=find_fishtank(key).to_dic())


# changes the name or size of a fishtank, body: {"name": text or null, "size": {"length", "width", "height"}}
@blueprint.route('/fishtanks/<key>', methods=['PATCH'])
def update_fishtank(key):
    payload = json_body()
    reject_unknown_fields(payload, {'name', 'size'})
    with database.atomic():
        record = find_fishtank(key)
        if 'name' in payload:
            record.name = read_name(payload)
        if 'size' in payload:
            record.length, record.width, record.height = read_size(payload)
        record.touch()
        record.save()
    return success(fishtank=record.to_dic())


@blueprint.route('/fishtanks/<key>', methods=['DELETE'])
def delete_fishtank(key):
    find_fishtank(key).delete_instance()
    return success(message='fishtank removed', key=key)


# A logged in user keeps a visitor's fishtank, e.g. one they built before logging in
@blueprint.route('/fishtanks/<key>/save', methods=['POST'])
@login_required
def save_fishtank(key):
    with database.atomic():
        record = find_fishtank(key)
        if not record.is_saved():
            record.save_for(g.user)
            record.touch()
            record.save()
    return success(fishtank=record.to_dic())


# Adds or removes a group of fish, the fishtank only changes when every fish can be added or removed
# body: {"fish": list of fish ids}, the same id twice means two fish
@blueprint.route('/fishtanks/<key>/<any(add, remove):action>', methods=['POST'])
def operate_fishtank(key, action):
    payload = json_body()
    reject_unknown_fields(payload, {'fish'})
    fish_ids = payload.get('fish')
    if not isinstance(fish_ids, list):
        raise ApiError('please provide a list of fish ids in array')
    for fish_id in fish_ids:
        if not is_integer(fish_id):
            raise ApiError('{} is not a valid fish id'.format(fish_id))

    # immediate, so two changes to the same fishtank at once cannot overwrite each other
    with database.atomic('IMMEDIATE'):
        record = find_fishtank(key)
        fish_by_id = {fish.id: fish for fish in Fish.select().where(Fish.id.in_(fish_ids))}
        for fish_id in fish_ids:
            if fish_id not in fish_by_id:
                raise ApiError('{} does not exist in database'.format(fish_id), 404)

        fishtank = record.to_fishtank()
        try:
            for fish_id in fish_ids:
                if action == 'add':
                    fishtank.add_fish(fish_by_id[fish_id])
                else:
                    fishtank.remove_fish(fish_by_id[fish_id])
        except FishError as e:
            # the alarm: these fish cannot live together, the fishtank stays as it was
            raise ApiError(str(e), 422)

        record.store_fish(fishtank)
        record.touch()
        record.save()
    return success(fishtank=record.to_dic())
