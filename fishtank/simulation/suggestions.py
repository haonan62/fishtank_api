# Orders a group of companions, e.g. the largest group from Fishtank.find_largest_group, so the first few are the
# ones most worth showing. Any part of such a group can still be added together, so a short list keeps that promise
#
# A fish with a picture and a common name ranks first, then a fish with one of them, among those the fish whose water
# ranges cover more of the tank's water rank higher.
# The tank's water is the range every resident is happy with. An empty tank has no water yet, the span of the whole
# group stands in for it, so fish that take a wide range of water rank higher

# (minimum attribute, maximum attribute) of each water condition
WATER_RANGES = [('temperature_min', 'temperature_max'), ('ph_min', 'ph_max'),
                ('water_hardness_min', 'water_hardness_max')]


def water_window(fish_list, common):
    # common: the range every fish shares, otherwise the span from the lowest minimum to the highest maximum
    window = []
    for minimum, maximum in WATER_RANGES:
        lows = [getattr(fish, minimum) for fish in fish_list]
        highs = [getattr(fish, maximum) for fish in fish_list]
        window.append((max(lows), min(highs)) if common else (min(lows), max(highs)))
    return window


# how much of the window the fish covers, from 0 to 1, averaged over the water conditions
def water_overlap(fish, window):
    shares = []
    for (minimum, maximum), (low, high) in zip(WATER_RANGES, window):
        width = high - low
        if width <= 0:
            # the window is one value (or residents no longer agree), it tells the fish apart by nothing
            shares.append(1.0)
            continue
        covered = min(high, getattr(fish, maximum)) - max(low, getattr(fish, minimum))
        shares.append(max(0.0, covered) / width)
    return sum(shares) / len(shares)


# residents: the fish in the tank, group: the companions to order, pictured_ids: the ids of fish with a picture
# answers the group as a list, best first, ties by scientific name so the order is always the same
def rank_companions(residents, group, pictured_ids):
    if not group:
        return []
    window = water_window(residents, common=True) if residents else water_window(group, common=False)

    def order(fish):
        shown_well = (fish.id in pictured_ids) + bool(fish.common_name)
        return -shown_well, -water_overlap(fish, window), fish.scientific_name

    return sorted(group, key=order)
