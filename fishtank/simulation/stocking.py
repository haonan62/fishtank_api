# How crowded a fishtank is, and what its fish would miss: the company of their own kind, or room to swim
# These are rules of thumb that warn, they never stop a fish from being added

# gravel, decoration and the gap below the rim take part of the water
NET_VOLUME_SHARE = 0.85
# one inch of adult fish per US gallon, the best known stocking rule, as cm per litre
FISH_CM_PER_LITRE = 2.54 / 3.785
# a tank from this share of its capacity on is nearly full, above all of it overstocked
NEARLY_FULL_SHARE = 0.8
# a fish needs a tank at least this many times its adult length to swim and turn
SWIM_ROOM_LENGTHS = 4

LEVEL_EMPTY = 'empty'
LEVEL_COMFORTABLE = 'comfortable'
LEVEL_NEARLY_FULL = 'nearly full'
LEVEL_OVERSTOCKED = 'overstocked'


def display_name(fish):
    return fish.common_name or fish.scientific_name


def stocking_level(share, has_fish):
    if not has_fish:
        return LEVEL_EMPTY
    if share > 1:
        return LEVEL_OVERSTOCKED
    if share >= NEARLY_FULL_SHARE:
        return LEVEL_NEARLY_FULL
    return LEVEL_COMFORTABLE


# size is (length, width, height) in cm, residents a list of (fish, count)
# Fish without a known adult size are not counted, the answer says how many those are
def assess_stocking(size, residents):
    length, width, height = size
    litres = length * width * height / 1000
    net_litres = litres * NET_VOLUME_SHARE
    capacity_cm = net_litres * FISH_CM_PER_LITRE
    fish_cm = sum(count * fish.size_max for fish, count in residents if fish.size_max is not None)
    uncounted = sum(count for fish, count in residents if fish.size_max is None)
    share = fish_cm / capacity_cm if capacity_cm else 0
    return {
        'litres': round(litres, 1),
        'net_litres': round(net_litres, 1),
        'capacity_cm': round(capacity_cm, 1),
        'fish_cm': fish_cm,
        'share': round(share, 3),
        'level': stocking_level(share, any(count for _, count in residents)),
        'uncounted_fish': uncounted,
    }


# Warnings about the fishtank as a whole and about single species, most pressing first
def tank_warnings(size, residents, stocking):
    warnings = []
    if stocking['level'] == LEVEL_OVERSTOCKED:
        warnings.append({
            'kind': 'overstocked',
            'message': 'The tank is overstocked: {:.0f} cm of adult fish in {:.0f} litres of water, '
                       'about {:.0f} cm is comfortable'.format(stocking['fish_cm'], stocking['net_litres'],
                                                              stocking['capacity_cm']),
        })
    for fish, count in residents:
        if fish.minimum_group_size is not None and count < fish.minimum_group_size:
            warnings.append({
                'kind': 'group',
                'fish_id': fish.id,
                'count': count,
                'minimum': fish.minimum_group_size,
                'message': '{} is a schooling fish, keep at least {} together (the tank has {})'.format(
                    display_name(fish), fish.minimum_group_size, count),
            })
    length = size[0]
    for fish, count in residents:
        if fish.size_max is not None and length < SWIM_ROOM_LENGTHS * fish.size_max:
            warnings.append({
                'kind': 'room',
                'fish_id': fish.id,
                'minimum_length': SWIM_ROOM_LENGTHS * fish.size_max,
                'message': '{} grows to {} cm, a tank at least {} cm long gives it room to swim'.format(
                    display_name(fish), fish.size_max, SWIM_ROOM_LENGTHS * fish.size_max),
            })
    return warnings
