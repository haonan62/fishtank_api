import math

from flask import Blueprint, request
from peewee import IntegrityError

from fishtank.api.common import ApiError, admin_required, is_integer, json_body, success
from fishtank.db import database
from fishtank.models.fish import CROSS_SPECIES_TEMPERAMENTS, IN_SPECIES_TEMPERAMENTS, UNKNOWN_TEMPERAMENT, Fish, FishPicture
from fishtank.simulation.fishdao import Fishdao
from fishtank.models.fishtank_record import FishtankFish, FishtankRecord

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
    'data_source': ('data_source', TEXT, True),
}
# worked out by the api, pictures come from the FishBase import
READ_ONLY_FIELDS = {'id', 'fishbase_url', 'pictures'}
DEFAULT_DATA_SOURCE = 'manual entry'
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
            raise ApiError('{} is required'.format(api_name))
        return None
    if kind == TEXT:
        if not isinstance(value, str) or len(value.strip()) > TEXT_MAX_LENGTH:
            raise ApiError('{} must be text of at most {} characters'.format(api_name, TEXT_MAX_LENGTH))
        value = value.strip()
        if not value:
            if required:
                raise ApiError('{} is required'.format(api_name))
            return None
        return value
    if kind == INTEGER:
        if not is_integer(value):
            raise ApiError('{} must be a whole number'.format(api_name))
        return value
    if kind == NUMBER:
        # python's json also reads NaN and Infinity, which no range check would catch
        if not (is_integer(value) or (isinstance(value, float) and math.isfinite(value))):
            raise ApiError('{} must be a number'.format(api_name))
        return float(value)
    if value not in kind:
        raise ApiError('{} must be one of: {}'.format(api_name, ', '.join(kind)))
    return value


# Checks a whole fish, given by api names, so the rules hold after a partial change as well
def check_fish(values):
    for minimum_name, maximum_name, lowest, highest in RANGES:
        minimum, maximum = values[minimum_name], values[maximum_name]
        if (minimum is None) != (maximum is None):
            raise ApiError('{} and {} must be given together'.format(minimum_name, maximum_name))
        if minimum is None:
            continue
        if minimum > maximum:
            raise ApiError('{} cannot be larger than {}'.format(minimum_name, maximum_name))
        if (lowest is not None and minimum < lowest) or (highest is not None and maximum > highest):
            raise ApiError('{} and {} must lie between {} and {}'.format(
                minimum_name, maximum_name, lowest, highest if highest is not None else 'any'))
    # live_peacefully_with compares sizes once a temperament is known
    if values['cross_species_temperament'] != UNKNOWN_TEMPERAMENT and values['minimum_size'] is None:
        raise ApiError('a fish with a known cross_species_temperament needs minimum_size and maximum_size')


# Returns the model fields to store, from the payload on top of the current values of the fish (None for a new fish)
def fish_fields_from_payload(payload, fish=None):
    for api_name in payload:
        if api_name in READ_ONLY_FIELDS:
            raise ApiError('{} cannot be changed'.format(api_name))
        if api_name not in FISH_FIELDS:
            raise ApiError('{} is not a known field'.format(api_name))

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
        raise ApiError('a fish named {} already exists'.format(values['scientific_name']), 409)
    if values['fishbase_spec_code'] is not None and Fish.select().where(
            (Fish.fishbase_spec_code == values['fishbase_spec_code']) & (Fish.id != fish_id)).exists():
        raise ApiError('a fish with FishBase species code {} already exists'.format(values['fishbase_spec_code']), 409)
    return {FISH_FIELDS[api_name][0]: value for api_name, value in values.items()}


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


# every fish, by id, or grouped by family with ?group_by=family
@blueprint.route('/fish')
def list_fish():
    group_by = request.args.get('group_by')
    if group_by == 'family':
        return success(fish_by_family=Fishdao().get_all_fish_group_by_family_for_api())
    if group_by is not None:
        raise ApiError('fish can only be grouped by family')
    return success(fish=[fish.to_dic() for fish in Fish.select().order_by(Fish.id)])


@blueprint.route('/fish/<int:fish_id>')
def get_fish(fish_id):
    return success(fish=find_fish(fish_id).to_dic())


@blueprint.route('/fish', methods=['POST'])
@admin_required
def create_fish():
    fish = Fish(**fish_fields_from_payload(json_body()))
    save_fish(fish)
    return success(201, fish=fish.to_dic())


# changes only the fields that are sent, fishtanks keep the fish even if it no longer fits in with the others
@blueprint.route('/fish/<int:fish_id>', methods=['PATCH'])
@admin_required
def update_fish(fish_id):
    fish = find_fish(fish_id)
    for model_field, value in fish_fields_from_payload(json_body(), fish).items():
        setattr(fish, model_field, value)
    save_fish(fish)
    return success(fish=fish.to_dic())


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
    return success(message='fish removed', id=fish_id)
