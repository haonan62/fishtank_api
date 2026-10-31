import time
import unittest
from unittest import mock

from fishtank.api import fishtanks as fishtanks_api
from fishtank.models.fish import Fish, FishPicture
from fishtank.simulation.fishtank import Fishtank
from fishtank.simulation.suggestions import rank_companions
from tests.api_test_case import ApiTestCase
from tests.test_fishtank import FishPoolTestCase, make_fish

# Tests for suggesting companions: the budget of Fishtank.find_largest_group, the order of rank_companions
# and GET /fishtanks/<key>/suggestions
# Run from the project root: python -m unittest tests.test_suggestions -v


# seven fish whose best group (Alpha, Bravo, Echo) is not the first group the search grows (Delta, Golf)
def first_group_is_not_the_best():
    return [make_fish('Alpha', temperature=(24, 25), ph=(6.2, 6.3)),
            make_fish('Bravo', temperature=(24, 26), ph=(6.3, 6.5)),
            make_fish('Charlie', temperature=(23, 24), ph=(6.8, 6.8)),
            make_fish('Delta', temperature=(23, 23), ph=(6.7, 7.1)),
            make_fish('Echo', temperature=(25, 27), ph=(6.0, 6.4)),
            make_fish('Foxtrot', temperature=(24, 25), ph=(6.8, 6.9)),
            make_fish('Golf', temperature=(22, 24), ph=(6.4, 6.7))]


class SearchBudgetTest(FishPoolTestCase):

    def assert_gets_along(self, pool, species):
        by_name = {fish.scientific_name: fish for fish in pool}
        tank = Fishtank()
        for name in species:
            tank.add_fish(by_name[name])
        for name in reversed(species):
            tank.remove_fish(by_name[name])

    def test_without_budget_the_search_is_complete(self):
        self.use_pool(first_group_is_not_the_best())
        self.assertEqual(Fishtank().find_largest_group(), (['Alpha', 'Bravo', 'Echo'], True))

    def test_spent_steps_answer_the_group_found_so_far(self):
        pool = first_group_is_not_the_best()
        self.use_pool(pool)
        search = Fishtank().find_largest_group(max_steps=1)
        self.assertFalse(search.complete)
        self.assertEqual(search.species, ['Delta', 'Golf'])
        self.assert_gets_along(pool, search.species)

    def test_a_budget_large_enough_finds_the_best_group(self):
        self.use_pool(first_group_is_not_the_best())
        self.assertEqual(Fishtank().find_largest_group(max_steps=1000, time_limit=60), (['Alpha', 'Bravo', 'Echo'], True))

    def test_no_time_still_answers_a_group(self):
        pool = first_group_is_not_the_best()
        self.use_pool(pool)
        search = Fishtank().find_largest_group(time_limit=0)
        self.assertFalse(search.complete)
        self.assertEqual(len(search.species), 1)

    def test_time_running_out_while_pairs_are_checked_searches_the_checked_fish(self):
        pool = first_group_is_not_the_best()
        self.use_pool(pool)
        # the clock moves one second per look, the deadline passes after three rows of pairs are checked
        clock = iter(range(1000))
        with mock.patch('fishtank.simulation.fishtank.time.monotonic', side_effect=lambda: next(clock)):
            search = Fishtank().find_largest_group(time_limit=2.5)
        self.assertFalse(search.complete)
        self.assertTrue(set(search.species) <= {'Alpha', 'Bravo', 'Charlie'})
        self.assert_gets_along(pool, search.species)

    def test_v3_takes_the_same_budget(self):
        self.use_pool(first_group_is_not_the_best())
        self.assertEqual(Fishtank().maximize_diversity_given_fish_v3(max_steps=1), ['Delta', 'Golf'])

    def test_retired_fish_are_never_in_the_group(self):
        retired = make_fish('Bravo')
        retired.retired_at = '2026-01-01 00:00:00'
        self.use_pool([make_fish('Alpha'), retired, make_fish('Charlie')])
        self.assertEqual(Fishtank().maximize_diversity_given_fish_v3(), ['Alpha', 'Charlie'])

    def test_a_short_budget_on_the_whole_database_answers_quickly(self):
        started = time.monotonic()
        search = Fishtank().find_largest_group(time_limit=0.2)
        self.assertLess(time.monotonic() - started, 1.5)
        self.assertFalse(search.complete)
        self.assertGreater(len(search.species), 0)


class RankCompanionsTest(unittest.TestCase):

    def fish(self, scientific_name, fish_id, common_name='a name', **ranges):
        fish = make_fish(scientific_name, **ranges)
        fish.id = fish_id
        fish.common_name = common_name
        return fish

    def names(self, residents, group, pictured_ids=frozenset()):
        return [fish.scientific_name for fish in rank_companions(residents, group, pictured_ids)]

    def test_picture_and_common_name_come_first(self):
        group = [self.fish('Alpha', 1, common_name=None), self.fish('Bravo', 2), self.fish('Charlie', 3),
                 self.fish('Delta', 4, common_name='')]
        self.assertEqual(self.names([], group, {3}), ['Charlie', 'Bravo', 'Alpha', 'Delta'])

    def test_wider_overlap_with_the_tank_water_ranks_higher(self):
        resident = self.fish('Resident', 0, temperature=(20, 30))
        group = [self.fish('Narrow', 1, temperature=(29, 34)), self.fish('Wide', 2, temperature=(18, 32)),
                 self.fish('Half', 3, temperature=(25, 35))]
        self.assertEqual(self.names([resident], group), ['Wide', 'Half', 'Narrow'])

    def test_empty_tank_prefers_fish_that_take_wide_ranges(self):
        group = [self.fish('Narrow', 1, ph=(7.0, 7.1)), self.fish('Wide', 2, ph=(6.0, 8.0))]
        self.assertEqual(self.names([], group), ['Wide', 'Narrow'])

    def test_ties_go_by_scientific_name(self):
        group = [self.fish('Charlie', 1), self.fish('Alpha', 2), self.fish('Bravo', 3)]
        self.assertEqual(self.names([], group), ['Alpha', 'Bravo', 'Charlie'])

    def test_water_residents_no_longer_agree_on_ranks_nothing(self):
        residents = [self.fish('Warm', 0, temperature=(28, 30)), self.fish('Cool', 9, temperature=(20, 22))]
        self.assertEqual(self.names(residents, [self.fish('Bravo', 1), self.fish('Alpha', 2)]), ['Alpha', 'Bravo'])

    def test_empty_group(self):
        self.assertEqual(rank_companions([], [], set()), [])


class SuggestionsApiTest(ApiTestCase):

    def setUp(self):
        super().setUp()
        self.neon = Fish.get(Fish.scientific_name == 'Paracheirodon innesi')

    def suggestions(self, key, query='', token=None):
        return self.call('GET', '/fishtanks/{}/suggestions{}'.format(key, query), token=token,
                         expected_status=200).get_json()

    def neon_tank(self, token=None):
        key = self.new_tank(token)
        self.operate('add', key, [self.neon.id, self.neon.id], token=token)
        return key

    def test_answers_a_ranked_part_of_the_largest_group(self):
        answer = self.suggestions(self.neon_tank())
        self.assertEqual(len(answer['suggestions']), 12)
        self.assertEqual(len(set(answer['suggestions'])), 12)
        self.assertNotIn(self.neon.id, answer['suggestions'])
        self.assertEqual(answer['group_size'], 55)
        self.assertTrue(answer['complete'])
        # the same as the search, best first
        expected = Fishtank(fish_map={self.neon.scientific_name: 2}).maximize_diversity_given_fish_v3()
        by_id = {fish.id: fish for fish in Fish.select()}
        self.assertTrue({by_id[fish_id].scientific_name for fish_id in answer['suggestions']} <= set(expected))
        # 11 fish of the group have a picture and a common name, they come first, then fish with a common name
        pictured = {picture.fish_id for picture in FishPicture.select()}
        has_picture = [fish_id in pictured for fish_id in answer['suggestions']]
        self.assertEqual(has_picture, [True] * 11 + [False])
        self.assertTrue(all(by_id[fish_id].common_name for fish_id in answer['suggestions']))

    def test_every_suggested_fish_can_be_added_at_once(self):
        key = self.neon_tank()
        suggested = self.suggestions(key, '?limit=50')['suggestions']
        self.assertEqual(len(suggested), 50)
        self.operate('add', key, suggested)
        self.assertEqual(self.fish_in_tank(key), {self.neon.id: 2, **{fish_id: 1 for fish_id in suggested}})

    def test_every_suggested_fish_can_be_added_one_by_one_in_any_order(self):
        key = self.neon_tank()
        suggested = self.suggestions(key)['suggestions']
        for order in (suggested, list(reversed(suggested))):
            with self.subTest(first=order[0]):
                trial = self.neon_tank()
                for fish_id in order:
                    self.assertEqual(self.operate('add', trial, [fish_id]).status_code, 200)

    def test_shorter_lists_are_the_start_of_longer_ones(self):
        key = self.neon_tank()
        three = self.suggestions(key, '?limit=3')['suggestions']
        self.assertEqual(three, self.suggestions(key)['suggestions'][:3])

    def test_empty_tank_searches_the_whole_catalogue(self):
        key = self.new_tank()
        answer = self.suggestions(key)
        self.assertEqual(answer['group_size'], 427)
        self.assertTrue(answer['complete'])
        self.operate('add', key, answer['suggestions'])
        self.assertEqual(len(self.fish_in_tank(key)), 12)

    def test_suggestions_follow_the_tank(self):
        key = self.neon_tank()
        first = self.suggestions(key)['suggestions'][0]
        self.operate('add', key, [first])
        answer = self.suggestions(key)
        self.assertNotIn(first, answer['suggestions'])
        self.assertEqual(answer['group_size'], 54)

    def test_retired_fish_are_not_suggested(self):
        key = self.neon_tank()
        first = self.suggestions(key)['suggestions'][0]
        self.call('POST', '/fish/{}/retire'.format(first), token=self.register_admin(), expected_status=200)
        answer = self.suggestions(key, '?limit=50')
        self.assertNotIn(first, answer['suggestions'])

    def test_a_tank_nobody_can_join(self):
        key = self.new_tank()
        self.operate('add', key, [Fish.get(Fish.scientific_name == 'Ameca splendens').id])
        self.assertEqual(self.suggestions(key), {'status': 'success', 'suggestions': [], 'group_size': 0,
                                                 'complete': True})

    def test_limit_must_be_from_1_to_50(self):
        key = self.new_tank()
        for limit in ('0', '51', '-1', 'ten', '2.5', ''):
            with self.subTest(limit=limit):
                response = self.call('GET', '/fishtanks/{}/suggestions?limit={}'.format(key, limit), expected_status=400)
                self.assertEqual(response.get_json()['field'], 'limit')

    def test_same_access_as_the_fishtank(self):
        alice = self.register('alice')
        key = self.neon_tank(alice)
        self.assertEqual(self.suggestions(key, token=alice)['group_size'], 55)
        self.call('GET', '/fishtanks/{}/suggestions'.format(key), expected_status=404)
        self.call('GET', '/fishtanks/{}/suggestions'.format(key), token=self.register('bob'), expected_status=404)
        self.call('GET', '/fishtanks/nope/suggestions', expected_status=404)

    def test_out_of_time_still_answers_fish_that_can_join(self):
        key = self.neon_tank()
        with mock.patch.object(fishtanks_api, 'SUGGESTION_TIME_LIMIT', 0):
            answer = self.suggestions(key)
        self.assertFalse(answer['complete'])
        self.assertGreater(answer['group_size'], 0)
        self.assertEqual(self.operate('add', key, answer['suggestions']).status_code, 200)


if __name__ == '__main__':
    unittest.main()
