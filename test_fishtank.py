import unittest
from unittest import mock

from models.fish import Fish
from models.fish_error import FishError
from models.fishtank import Fishtank

# Tests for Fishtank.maximize_diversity_given_fish_v3
# Given the fish already in the tank, the method returns the largest group of new species that can live
# with every fish in the tank and with each other, as a sorted list of scientific names
# Two species only count as compatible when coexist_together passes in both directions
#
# Run from the project root: python -m unittest test_fishtank -v
# Name the module explicitly, plain discovery would also import test.py, which runs a long script


# Builds an unsaved fish, every attribute defaults to the same comfortable values
# so that each test only spells out the attributes it is about
def make_fish(scientific_name, temperature=(22, 26), ph=(6.5, 7.5), water_hardness=(5, 15), size=(5, 6),
              cross_species_temperament='peaceful', in_species_temperament='peaceful'):
    return Fish(scientific_name=scientific_name, common_name=scientific_name, family_name='Testidae',
                size_min=size[0], size_max=size[1], ph_min=ph[0], ph_max=ph[1],
                water_hardness_min=water_hardness[0], water_hardness_max=water_hardness[1],
                temperature_min=temperature[0], temperature_max=temperature[1],
                reproduce_method='egg layer', origin='Test', in_species_temperament=in_species_temperament,
                cross_species_temperament=cross_species_temperament, fishtank_position='middle')


# (attribute, default range used by make_fish, smallest step in the data, range wide enough to cover any test fish)
RANGE_ATTRIBUTES = [
    ('temperature', (22, 26), 1, (10, 40)),
    ('ph', (6.5, 7.5), 0.1, (4.0, 9.0)),
    ('water_hardness', (5, 15), 1, (1, 30)),
]


class FishPoolTestCase(unittest.TestCase):

    # replaces the fish database with the given fish for the rest of the test
    def use_pool(self, fish_list):
        patcher = mock.patch('models.fishdao.all_fish_list', list(fish_list))
        patcher.start()
        self.addCleanup(patcher.stop)

    def tank_with(self, fish_list):
        tank = Fishtank(size=(100, 100, 30))
        for sample in fish_list:
            tank.add_fish(sample)
        return tank

    # puts the residents in a tank, makes residents and candidates the whole database, and solves
    def solve(self, residents, candidates):
        self.use_pool(list(residents) + list(candidates))
        return self.tank_with(residents).maximize_diversity_given_fish_v3()


class NormalCasesTest(FishPoolTestCase):

    def test_returns_every_candidate_when_all_get_along(self):
        result = self.solve([make_fish('Resident')],
                            [make_fish('Charlie'), make_fish('Alpha'), make_fish('Bravo')])
        self.assertEqual(result, ['Alpha', 'Bravo', 'Charlie'])

    def test_never_returns_species_already_in_tank(self):
        result = self.solve([make_fish('Resident one'), make_fish('Resident two')], [make_fish('Alpha')])
        self.assertEqual(result, ['Alpha'])

    def test_returns_empty_list_when_no_candidate_fits(self):
        result = self.solve([make_fish('Resident')],
                            [make_fish('Alpha', temperature=(30, 32)), make_fish('Bravo', temperature=(28, 34))])
        self.assertEqual(result, [])

    def test_returns_empty_list_when_tank_already_holds_every_species(self):
        result = self.solve([make_fish('Resident one'), make_fish('Resident two')], [])
        self.assertEqual(result, [])

    def test_finds_largest_group_rather_than_first_fit(self):
        # Alpha sorts first but conflicts with the other three, which get along with each other
        result = self.solve([make_fish('Resident', temperature=(20, 30))],
                            [make_fish('Alpha', temperature=(20, 21)), make_fish('Bravo', temperature=(25, 30)),
                             make_fish('Charlie', temperature=(25, 30)), make_fish('Delta', temperature=(25, 30))])
        self.assertEqual(result, ['Bravo', 'Charlie', 'Delta'])

    def test_finds_largest_group_when_best_connected_candidate_is_a_trap(self):
        # Hub gets along with six candidates (three pairs that conflict with each other), so the best group with
        # Hub has three species. The four Pack fish only get along with each other, but four beats three
        candidates = [make_fish('Hub', temperature=(14, 30))]
        for name, temperature in [('Pair a', (15, 16)), ('Pair b', (18, 19)), ('Pair c', (21, 22))]:
            candidates.append(make_fish(name + '1', temperature=temperature))
            candidates.append(make_fish(name + '2', temperature=temperature))
        for name in ['Pack p', 'Pack q', 'Pack r', 'Pack s']:
            candidates.append(make_fish(name, temperature=(10, 12)))
        result = self.solve([make_fish('Resident', temperature=(10, 30))], candidates)
        self.assertEqual(result, ['Pack p', 'Pack q', 'Pack r', 'Pack s'])

    def test_empty_tank_returns_largest_group_from_whole_database(self):
        result = self.solve([], [make_fish('Alpha', temperature=(20, 21)), make_fish('Bravo', temperature=(25, 30)),
                                 make_fish('Charlie', temperature=(25, 30))])
        self.assertEqual(result, ['Bravo', 'Charlie'])

    def test_result_does_not_depend_on_database_order(self):
        residents = [make_fish('Resident', temperature=(20, 30))]
        candidates = [make_fish('Alpha', temperature=(20, 25)), make_fish('Bravo', temperature=(26, 30)),
                      make_fish('Charlie', temperature=(24, 27)), make_fish('Delta', temperature=(22, 26))]
        forward = self.solve(residents, candidates)
        backward = self.solve(list(reversed(residents)), list(reversed(candidates)))
        self.assertEqual(forward, backward)

    def test_repeated_calls_agree_and_leave_tank_unchanged(self):
        self.use_pool([make_fish('Resident'), make_fish('Alpha'), make_fish('Bravo', temperature=(30, 32))])
        tank = self.tank_with([make_fish('Resident')])
        tank.add_fish(make_fish('Resident'))
        before = (dict(tank.fish_map), tank.status, tank.size)

        first = tank.maximize_diversity_given_fish_v3()
        second = tank.maximize_diversity_given_fish_v3()

        self.assertEqual(first, ['Alpha'])
        self.assertEqual(second, first)
        self.assertEqual((tank.fish_map, tank.status, tank.size), before)

    def test_every_returned_fish_can_be_added_in_either_order(self):
        residents = [make_fish('Resident', size=(20, 22))]
        candidates = [make_fish('Alpha', size=(10, 12), cross_species_temperament='aggressive to smaller'),
                      make_fish('Bravo', size=(13, 15), cross_species_temperament='aggressive to smaller'),
                      make_fish('Charlie', size=(12, 14)), make_fish('Delta', size=(15, 18)),
                      make_fish('Echo', temperature=(10, 12))]
        result = self.solve(residents, candidates)
        all_fish = {sample.scientific_name: sample for sample in candidates}
        # Bravo may attack Alpha and Charlie, Echo cannot share the resident's temperature
        self.assertEqual(result, ['Alpha', 'Charlie', 'Delta'])

        for order in (result, list(reversed(result))):
            with self.subTest(order=order):
                tank = self.tank_with(residents)
                for name in order:
                    tank.add_fish(all_fish[name])
                expected_map = {'Resident': 1}
                expected_map.update({name: 1 for name in result})
                self.assertEqual(tank.fish_map, expected_map)


class RangeBoundaryTest(FishPoolTestCase):

    def test_ranges_touching_a_resident_are_compatible(self):
        for attribute, (low, high), step, _ in RANGE_ATTRIBUTES:
            for side, candidate_range in [('above', (high, high + 2)), ('below', (low - 2, low))]:
                with self.subTest(attribute=attribute, side=side):
                    result = self.solve([make_fish('Resident')], [make_fish('Alpha', **{attribute: candidate_range})])
                    self.assertEqual(result, ['Alpha'])

    def test_ranges_one_step_away_from_a_resident_are_incompatible(self):
        for attribute, (low, high), step, _ in RANGE_ATTRIBUTES:
            for side, candidate_range in [('above', (high + step, high + 2)), ('below', (low - 2, low - step))]:
                with self.subTest(attribute=attribute, side=side):
                    result = self.solve([make_fish('Resident')], [make_fish('Alpha', **{attribute: candidate_range})])
                    self.assertEqual(result, [])

    def test_ranges_touching_between_candidates_are_compatible(self):
        for attribute, (low, high), step, wide_range in RANGE_ATTRIBUTES:
            with self.subTest(attribute=attribute):
                result = self.solve([make_fish('Resident', **{attribute: wide_range})],
                                    [make_fish('Alpha'), make_fish('Bravo', **{attribute: (high, high + 2)})])
                self.assertEqual(result, ['Alpha', 'Bravo'])

    def test_ranges_one_step_apart_between_candidates_keep_only_one(self):
        for attribute, (low, high), step, wide_range in RANGE_ATTRIBUTES:
            with self.subTest(attribute=attribute):
                result = self.solve([make_fish('Resident', **{attribute: wide_range})],
                                    [make_fish('Alpha'), make_fish('Bravo', **{attribute: (high + step, high + 2)})])
                self.assertIn(result, [['Alpha'], ['Bravo']])


class TemperamentTest(FishPoolTestCase):

    def test_cross_species_temperament_combinations(self):
        cases = [
            ('peaceful', 'peaceful', True),
            ('aggressive/territorial', 'peaceful', False),
            ('peaceful', 'aggressive/territorial', False),
            ('aggressive/territorial', 'aggressive/territorial', False),
            ('aggressive/territorial', 'aggressive to smaller', False),
            ('aggressive to smaller', 'aggressive/territorial', False),
        ]
        for resident_temperament, candidate_temperament, compatible in cases:
            with self.subTest(resident=resident_temperament, candidate=candidate_temperament):
                result = self.solve([make_fish('Resident', cross_species_temperament=resident_temperament)],
                                    [make_fish('Alpha', cross_species_temperament=candidate_temperament)])
                self.assertEqual(result, ['Alpha'] if compatible else [])

    def test_aggressive_to_smaller_size_boundary(self):
        # the aggressor's largest size is 12, prey of minimum size 12 is safe, prey of minimum size 11 is not
        cases = [((12, 14), True), ((11, 14), False)]
        for prey_size, compatible in cases:
            aggressor = make_fish('Aggressor', size=(10, 12), cross_species_temperament='aggressive to smaller')
            prey = make_fish('Prey', size=prey_size)
            expected = ['Aggressor', 'Prey'] if compatible else None
            with self.subTest(prey_size=prey_size, aggressor='in tank'):
                self.assertEqual(self.solve([aggressor], [prey]), ['Prey'] if compatible else [])
            with self.subTest(prey_size=prey_size, aggressor='candidate'):
                self.assertEqual(self.solve([prey], [aggressor]), ['Aggressor'] if compatible else [])
            with self.subTest(prey_size=prey_size, aggressor='both candidates'):
                result = self.solve([make_fish('Resident', size=(20, 22))], [aggressor, prey])
                if compatible:
                    self.assertEqual(result, expected)
                else:
                    self.assertIn(result, [['Aggressor'], ['Prey']])

    def test_two_aggressive_to_smaller_fish_must_pass_both_ways(self):
        # Small.coexist_together(Large) passes because only Small's size is checked,
        # Large.coexist_together(Small) fails because Large may attack Small, so they are incompatible
        small = make_fish('Small', size=(10, 12), cross_species_temperament='aggressive to smaller')
        large = make_fish('Large', size=(13, 15), cross_species_temperament='aggressive to smaller')
        with self.subTest(in_tank='Small'):
            self.assertEqual(self.solve([small], [large]), [])
        with self.subTest(in_tank='Large'):
            self.assertEqual(self.solve([large], [small]), [])
        with self.subTest(in_tank='neither'):
            result = self.solve([make_fish('Resident', size=(15, 20))], [small, large])
            self.assertIn(result, [['Large'], ['Small']])

    def test_two_aggressive_to_smaller_fish_of_identical_size_get_along(self):
        result = self.solve([make_fish('Resident', size=(10, 20))],
                            [make_fish('Alpha', size=(10, 10), cross_species_temperament='aggressive to smaller'),
                             make_fish('Bravo', size=(10, 10), cross_species_temperament='aggressive to smaller')])
        self.assertEqual(result, ['Alpha', 'Bravo'])

    def test_in_species_temperament_does_not_block_one_new_species(self):
        # only one fish of each new species is added, add_fish only checks in-species temperament from the second fish
        result = self.solve([make_fish('Resident')],
                            [make_fish('Alpha', in_species_temperament='aggressive/territorial')])
        self.assertEqual(result, ['Alpha'])


class MultipleConditionsTest(FishPoolTestCase):

    def test_candidate_failing_any_condition_is_excluded(self):
        cases = [
            ('nothing', {}, ['Alpha']),
            ('temperature', {'temperature': (30, 32)}, []),
            ('ph', {'ph': (8.0, 8.5)}, []),
            ('water_hardness', {'water_hardness': (20, 25)}, []),
            ('temperament', {'cross_species_temperament': 'aggressive/territorial'}, []),
            ('temperature and ph', {'temperature': (30, 32), 'ph': (8.0, 8.5)}, []),
            ('every condition', {'temperature': (30, 32), 'ph': (8.0, 8.5), 'water_hardness': (20, 25),
                                 'cross_species_temperament': 'aggressive/territorial'}, []),
        ]
        for failing, attributes, expected in cases:
            with self.subTest(failing=failing):
                self.assertEqual(self.solve([make_fish('Resident')], [make_fish('Alpha', **attributes)]), expected)

    def test_candidate_must_suit_every_fish_already_in_tank(self):
        # Alpha suits the first resident but not the second, Bravo suits both
        result = self.solve([make_fish('Resident one', temperature=(20, 30)), make_fish('Resident two', temperature=(20, 25))],
                            [make_fish('Alpha', temperature=(26, 30)), make_fish('Bravo', temperature=(24, 30))])
        self.assertEqual(result, ['Bravo'])

    def test_conditions_combine_across_candidates(self):
        # every candidate suits the resident, but Bravo clashes with each of the others: with Alpha and Delta on ph,
        # and with Charlie on temperament (their ph ranges touch at 7.0), so the largest group is Alpha, Charlie and Delta
        resident = make_fish('Resident', temperature=(20, 30), ph=(6.0, 8.0), size=(30, 40))
        candidates = [make_fish('Alpha', ph=(6.0, 6.5)),
                      make_fish('Bravo', ph=(7.0, 8.0), size=(20, 25), cross_species_temperament='aggressive to smaller'),
                      make_fish('Charlie', ph=(6.0, 7.0)),
                      make_fish('Delta', ph=(6.2, 6.8))]
        self.assertEqual(self.solve([resident], candidates), ['Alpha', 'Charlie', 'Delta'])


class RealDatabaseTest(unittest.TestCase):
    # the expected sizes were found by an exact search over data/fish.db, any smaller answer is not the maximum

    @classmethod
    def setUpClass(cls):
        cls.residents = [Fish.get(Fish.scientific_name == 'Corydoras acrensis'),
                         Fish.get(Fish.scientific_name == 'Corydoras adolfoi')]
        cls.seeded_tank = Fishtank(size=(100, 100, 30))
        for sample in cls.residents:
            cls.seeded_tank.add_fish(sample)
        cls.seeded_result = cls.seeded_tank.maximize_diversity_given_fish_v3()
        cls.empty_result = Fishtank(size=(100, 100, 30)).maximize_diversity_given_fish_v3()
        cls.all_fish = {sample.scientific_name: sample for sample in Fish.select()}

    def assert_all_compatible_both_ways(self, fish_list):
        for i, first in enumerate(fish_list):
            for second in fish_list[i + 1:]:
                for a, b in ((first, second), (second, first)):
                    try:
                        a.coexist_together(b)
                    except FishError as e:
                        self.fail(str(e))

    def test_seeded_tank_finds_maximum_number_of_new_species(self):
        self.assertEqual(len(self.seeded_result), 425)
        self.assertEqual(self.seeded_result, sorted(set(self.seeded_result)))
        self.assertFalse({'Corydoras acrensis', 'Corydoras adolfoi'} & set(self.seeded_result))

    def test_empty_tank_finds_maximum_number_of_species(self):
        self.assertEqual(len(self.empty_result), 427)
        self.assertEqual(self.empty_result, sorted(set(self.empty_result)))

    def test_seeded_result_gets_along_with_tank_and_itself(self):
        self.assert_all_compatible_both_ways(self.residents + [self.all_fish[name] for name in self.seeded_result])

    def test_empty_tank_result_gets_along_with_itself(self):
        self.assert_all_compatible_both_ways([self.all_fish[name] for name in self.empty_result])

    def test_seeded_result_can_be_added_in_either_order(self):
        for order in (self.seeded_result, list(reversed(self.seeded_result))):
            with self.subTest(first=order[0]):
                tank = self.seeded_tank.copy()
                for name in order:
                    tank.add_fish(self.all_fish[name])
                self.assertEqual(len(tank.fish_map), 2 + 425)

    def test_seeded_tank_is_left_unchanged(self):
        self.assertEqual(self.seeded_tank.fish_map, {'Corydoras acrensis': 1, 'Corydoras adolfoi': 1})


if __name__ == '__main__':
    unittest.main()
