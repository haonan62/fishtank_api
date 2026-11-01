import math

from flask import Blueprint, g, request
from peewee import IntegrityError, fn

from fishtank.api.common import ApiError, admin_required, is_integer, json_body, reject_unknown_fields, success
from fishtank.db import database, utcnow
from fishtank.models.fish import (CROSS_SPECIES_TEMPERAMENTS, IN_SPECIES_TEMPERAMENTS, PICTURE_SOURCE_FISHBASE,
                                  UNKNOWN_TEMPERAMENT, Fish, FishPicture)
from fishtank.models.fishtank_record import FishtankFish, FishtankRecord
from fishtank.models.review import AuditEvent

blueprint = Blueprint('fish', __name__)

TEXT = 'text'
INTEGER = 'integer'
NUMBER = 'number'

# the fields of a fish as the api names them (the names of Fish.to_dic): (model field, kind, required)
# a kind can also be the tuple of allowed values
FISH_FIELDS = {
    'scientific_name': ('scientific_name', TEXT, True),
    'common_name': ('common_name', TEXT, False),
    'family_name': ('family_name', TEXT, True),
    'minimum_size': ('size_min', INTEGER, False),
    'maximum_size': ('size_max', INTEGER, False),
    'minimum_ph': ('ph_min', NUMBER, True),
    'maximum_ph': ('ph_max', NUMBER, True),
    'minimum_water_hardness': ('water_hardness_min', INTEGER, True),
    'maximum_water_hardness': ('water_hardness_max', INTEGER, True),
    'minimum_temperature': ('temperature_min', INTEGER, True),
    'maximum_temperature': ('temperature_max', INTEGER, True),
    'reproduce_method': ('reproduce_method', TEXT, False),
    'origin': ('origin', TEXT, False),
    'in_species_temperament': ('in_species_temperament', IN_SPECIES_TEMPERAMENTS, True),
    'cross_species_temperament': ('cross_species_temperament', CROSS_SPECIES_TEMPERAMENTS, True),
    'fishtank_position': ('fishtank_position', TEXT, False),
    'fishbase_spec_code': ('fishbase_spec_code', INTEGER, False),
    'minimum_group_size': ('minimum_group_size', INTEGER, False),
    'data_source': ('data_source', TEXT, True),
}
# worked out by the api, pictures come from the FishBase import, retire and restore have their own endpoints
READ_ONLY_FIELDS = {'id', 'fishbase_url', 'pictures', 'retired', 'fishtank_count', 'group_size_source'}
DEFAULT_DATA_SOURCE = 'manual entry'
# a group size an admin sets is theirs, the curated starting values say 'Fishtank list'
MANUAL_GROUP_SIZE_SOURCE = 'manual entry'
GROUP_SIZE_RANGE = (2, 50)
TEXT_MAX_LENGTH = 100

# (minimum, maximum, lowest allowed, highest allowed), None means no limit
RANGES = [
    ('minimum_size', 'maximum_size', 1, None),
    ('minimum_ph', 'maximum_ph', 0, 14),
    ('minimum_water_hardness', 'maximum_water_hardness', 0, None),
    ('minimum_temperature', 'maximum_temperature', 0, 45),
]


def read_field(api_name, value):
    _, kind, required = FISH_FIELDS[api_name]
    if value is None:
        if required:
            raise ApiError('{} is required'.format(api_name), field=api_name)
        return None
    if kind == TEXT:
        if not isinstance(value, str) or len(value.strip()) > TEXT_MAX_LENGTH:
            raise ApiError('{} must be text of at most {} characters'.format(api_name, TEXT_MAX_LENGTH), field=api_name)
        value = value.strip()
        if not value:
            if required:
                raise ApiError('{} is required'.format(api_name), field=api_name)
            return None
        return value
    if kind == INTEGER:
        if not is_integer(value):
            raise ApiError('{} must be a whole number'.format(api_name), field=api_name)
        return value
    if kind == NUMBER:
        # python's json also reads NaN and Infinity, which no range check would catch
        if not (is_integer(value) or (isinstance(value, float) and math.isfinite(value))):
            raise ApiError('{} must be a number'.format(api_name), field=api_name)
        return float(value)
    if value not in kind:
        raise ApiError('{} must be one of: {}'.format(api_name, ', '.join(kind)), field=api_name)
    return value


# Checks a whole fish, given by api names, so the rules hold after a partial change as well
def check_fish(values):
    for minimum_name, maximum_name, lowest, highest in RANGES:
        minimum, maximum = values[minimum_name], values[maximum_name]
        if (minimum is None) != (maximum is None):
            raise ApiError('{} and {} must be given together'.format(minimum_name, maximum_name), field=minimum_name)
        if minimum is None:
            continue
        if minimum > maximum:
            raise ApiError('{} cannot be larger than {}'.format(minimum_name, maximum_name), field=minimum_name)
        if (lowest is not None and minimum < lowest) or (highest is not None and maximum > highest):
            raise ApiError('{} and {} must lie between {} and {}'.format(
                minimum_name, maximum_name, lowest, highest if highest is not None else 'any'), field=minimum_name)
    # live_peacefully_with compares sizes once a temperament is known
    if values['cross_species_temperament'] != UNKNOWN_TEMPERAMENT and values['minimum_size'] is None:
        raise ApiError('a fish with a known cross_species_temperament needs minimum_size and maximum_size',
                       field='minimum_size')
    group_size = values['minimum_group_size']
    if group_size is not None:
        if not GROUP_SIZE_RANGE[0] <= group_size <= GROUP_SIZE_RANGE[1]:
            raise ApiError('minimum_group_size must lie between {} and {}'.format(*GROUP_SIZE_RANGE),
                           field='minimum_group_size')
        # the simulation keeps a second fish of a species only when it is peaceful with its own kind
        if values['in_species_temperament'] != 'peaceful' or values['cross_species_temperament'] == UNKNOWN_TEMPERAMENT:
            raise ApiError('only a fish that is peaceful with its own kind and others can be kept in a group, '
                           'clear minimum_group_size or change its temperament', field='minimum_group_size')


# Returns the model fields to store, from the payload on top of the current values of the fish (None for a new fish)
def fish_fields_from_payload(payload, fish=None):
    for api_name in payload:
        if api_name in READ_ONLY_FIELDS:
            raise ApiError('{} cannot be changed'.format(api_name), field=api_name)
        if api_name not in FISH_FIELDS:
            raise ApiError('{} is not a known field'.format(api_name), field=api_name)

    values = {}
    for api_name, (model_field, _, required) in FISH_FIELDS.items():
        if api_name in payload:
            values[api_name] = read_field(api_name, payload[api_name])
        elif fish is not None:
            values[api_name] = getattr(fish, model_field)
        elif api_name == 'data_source':
            values[api_name] = DEFAULT_DATA_SOURCE
        else:
            values[api_name] = read_field(api_name, None)
    check_fish(values)

    fish_id = fish.id if fish is not None else None
    if Fish.select().where((Fish.scientific_name == values['scientific_name']) & (Fish.id != fish_id)).exists():
        raise ApiError('a fish named {} already exists'.format(values['scientific_name']), 409, field='scientific_name')
    if values['fishbase_spec_code'] is not None and Fish.select().where(
            (Fish.fishbase_spec_code == values['fishbase_spec_code']) & (Fish.id != fish_id)).exists():
        raise ApiError('a fish with FishBase species code {} already exists'.format(values['fishbase_spec_code']), 409,
                       field='fishbase_spec_code')
    fields = {FISH_FIELDS[api_name][0]: value for api_name, value in values.items()}
    if 'minimum_group_size' in payload and (fish is None or values['minimum_group_size'] != fish.minimum_group_size):
        fields['group_size_source'] = MANUAL_GROUP_SIZE_SOURCE if values['minimum_group_size'] is not None else None
    return fields


# model field -> api name, for the audit log
API_NAMES = {model_field: api_name for api_name, (model_field, _, _) in FISH_FIELDS.items()}
API_NAMES['group_size_source'] = 'group_size_source'


# Sets the fields on the fish and returns what changed, by api name: {name: {'from': old, 'to': new}}
def apply_fish_fields(fish, fields):
    changes = {}
    for model_field, value in fields.items():
        old = getattr(fish, model_field)
        if old != value:
            changes[API_NAMES[model_field]] = {'from': old, 'to': value}
        setattr(fish, model_field, value)
    return changes


def find_fish(fish_id):
    fish = Fish.get_or_none(Fish.id == fish_id)
    if fish is None:
        raise ApiError('{} does not exist in database'.format(fish_id), 404)
    return fish


def save_fish(fish):
    try:
        with database.atomic():
            fish.save()
    except IntegrityError:
        # another admin was faster with the same scientific name or species code
        raise ApiError('a fish with this scientific name or FishBase species code already exists', 409)


# the number of fishtanks each fish lives in, by fish id, for admins deciding to retire or remove a fish
def fishtank_counts():
    FishtankRecord.remove_expired()
    rows = FishtankFish.select(FishtankFish.fish, fn.COUNT(FishtankFish.fishtank).alias('count')).group_by(FishtankFish.fish)
    return {row.fish_id: row.count for row in rows}


def fish_for_api(fish, counts=None):
    dic = fish.to_dic()
    if counts is not None:
        dic['fishtank_count'] = counts.get(fish.id, 0)
    return dic


def is_admin():
    return g.user is not None and g.user.is_admin()


# every fish in the catalogue, by id, or grouped by family with ?group_by=family
# admins also see retired fish with ?include_retired=true, and every fish carries its fishtank_count for them
@blueprint.route('/fish')
def list_fish():
    group_by = request.args.get('group_by')
    include_retired = request.args.get('include_retired') == 'true'
    if include_retired and not is_admin():
        raise ApiError('Only admins can see retired fish', 403)
    if group_by not in (None, 'family'):
        raise ApiError('fish can only be grouped by family')

    query = Fish.select().order_by(Fish.id)
    if not include_retired:
        query = query.where(Fish.retired_at.is_null())
    counts = fishtank_counts() if is_admin() else None
    all_fish = [fish_for_api(fish, counts) for fish in query]
    if group_by == 'family':
        fish_by_family = {}
        for fish in all_fish:
            fish_by_family.setdefault(fish['family_name'], []).append(fish)
        return success(fish_by_family=fish_by_family)
    return success(fish=all_fish)


# a retired fish can still be looked up, fishtanks may keep it
@blueprint.route('/fish/<int:fish_id>')
def get_fish(fish_id):
    counts = fishtank_counts() if is_admin() else None
    return success(fish=fish_for_api(find_fish(fish_id), counts))


@blueprint.route('/fish', methods=['POST'])
@admin_required
def create_fish():
    fish = Fish(**fish_fields_from_payload(json_body()))
    with database.atomic():
        save_fish(fish)
        AuditEvent.record(g.user, 'fish.create', fish_id=fish.id, details={'scientific_name': fish.scientific_name})
    return success(201, fish=fish_for_api(fish, fishtank_counts()))


# changes only the fields that are sent, fishtanks keep the fish even if it no longer fits in with the others
@blueprint.route('/fish/<int:fish_id>', methods=['PATCH'])
@admin_required
def update_fish(fish_id):
    fish = find_fish(fish_id)
    changes = apply_fish_fields(fish, fish_fields_from_payload(json_body(), fish))
    with database.atomic():
        save_fish(fish)
        if changes:
            AuditEvent.record(g.user, 'fish.update', fish_id=fish.id, details={'changes': changes})
    return success(fish=fish_for_api(fish, fishtank_counts()))


# a fish living in a fishtank cannot be removed, its pictures are removed with it
@blueprint.route('/fish/<int:fish_id>', methods=['DELETE'])
@admin_required
def delete_fish(fish_id):
    FishtankRecord.remove_expired()
    with database.atomic():
        fish = find_fish(fish_id)
        fishtank_count = FishtankFish.select().where(FishtankFish.fish == fish).count()
        if fishtank_count:
            raise ApiError('{} lives in {} fishtank(s) and cannot be removed'.format(
                fish.scientific_name, fishtank_count), 409)
        FishPicture.delete().where(FishPicture.fish == fish).execute()
        fish.delete_instance()
        AuditEvent.record(g.user, 'fish.delete', fish_id=fish_id, details={'scientific_name': fish.scientific_name})
    return success(message='fish removed', id=fish_id)


# A retired fish leaves the catalogue and cannot be added to a fishtank anymore, fishtanks that keep it are not changed
@blueprint.route('/fish/<int:fish_id>/retire', methods=['POST'])
@admin_required
def retire_fish(fish_id):
    fish = find_fish(fish_id)
    if not fish.is_retired():
        with database.atomic():
            fish.retired_at = utcnow()
            fish.save()
            AuditEvent.record(g.user, 'fish.retire', fish_id=fish.id)
    return success(fish=fish_for_api(fish, fishtank_counts()))


@blueprint.route('/fish/<int:fish_id>/restore', methods=['POST'])
@admin_required
def restore_fish(fish_id):
    fish = find_fish(fish_id)
    if fish.is_retired():
        with database.atomic():
            fish.retired_at = None
            fish.save()
            AuditEvent.record(g.user, 'fish.restore', fish_id=fish.id)
    return success(fish=fish_for_api(fish, fishtank_counts()))


PICTURE_FIELDS = {'url', 'source_url', 'author', 'licence', 'source'}
PICTURE_TEXT_MAX_LENGTH = 200
PICTURE_URL_MAX_LENGTH = 1000


def read_picture_text(payload, name, required, max_length=PICTURE_TEXT_MAX_LENGTH):
    value = payload.get(name)
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise ApiError('{} is required'.format(name), field=name)
        return None
    if not isinstance(value, str) or len(value.strip()) > max_length:
        raise ApiError('{} must be text of at most {} characters'.format(name, max_length), field=name)
    return value.strip()


def read_picture_url(payload, name):
    url = read_picture_text(payload, name, True, PICTURE_URL_MAX_LENGTH)
    if not url.startswith('https://') or any(character.isspace() for character in url):
        raise ApiError('{} must be an https:// address'.format(name), field=name)
    return url


# An admin links a picture they found, for a fish without one or one more, it is shown with its credit:
# "author, licence, via source" and a link to its page. Only link pictures whose licence allows showing them
# body: {"url": the image, "source_url": its page, "licence", "source": where it is from, "author" (optional)}
@blueprint.route('/fish/<int:fish_id>/pictures', methods=['POST'])
@admin_required
def add_picture(fish_id):
    payload = json_body()
    reject_unknown_fields(payload, PICTURE_FIELDS)
    fish = find_fish(fish_id)
    values = {'url': read_picture_url(payload, 'url'), 'source_url': read_picture_url(payload, 'source_url'),
              'licence': read_picture_text(payload, 'licence', True), 'source': read_picture_text(payload, 'source', True),
              'author': read_picture_text(payload, 'author', False)}
    if values['source'] == PICTURE_SOURCE_FISHBASE:
        raise ApiError('FishBase pictures come from the FishBase import, please name the site you found it on',
                       field='source')
    if FishPicture.select().where(FishPicture.url == values['url']).exists():
        raise ApiError('this picture is already linked to a fish', 409, field='url')
    try:
        with database.atomic():
            picture = FishPicture.create(fish=fish, **values)
            AuditEvent.record(g.user, 'picture.add', fish_id=fish.id, details={'picture': picture.to_dic()})
    except IntegrityError:
        raise ApiError('this picture is already linked to a fish', 409, field='url')
    return success(201, picture=picture.to_dic(), fish=fish_for_api(fish, fishtank_counts()))


@blueprint.route('/fish/<int:fish_id>/pictures/<int:picture_id>', methods=['DELETE'])
@admin_required
def remove_picture(fish_id, picture_id):
    fish = find_fish(fish_id)
    picture = FishPicture.get_or_none((FishPicture.id == picture_id) & (FishPicture.fish == fish))
    if picture is None:
        raise ApiError('no such picture', 404)
    with database.atomic():
        details = {'picture': picture.to_dic()}
        picture.delete_instance()
        AuditEvent.record(g.user, 'picture.remove', fish_id=fish.id, details=details)
    return success(fish=fish_for_api(fish, fishtank_counts()))
