import unittest

import app
from models.fish import Fish

# Tests for the http api, which identifies fish by id
# Run from the project root: python -m unittest test_api -v


class ApiTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.peaceful_id = Fish.get(Fish.scientific_name == 'Corydoras acrensis').id
        cls.other_peaceful_id = Fish.get(Fish.scientific_name == 'Corydoras adolfoi').id
        cls.aggressive_id = Fish.get(Fish.scientific_name == 'Cynotilapia afra').id
        cls.unknown_temperament_id = Fish.get(Fish.scientific_name == 'Ameca splendens').id
        cls.all_ids = sorted(fish.id for fish in Fish.select())

    def setUp(self):
        app.fishtank_map.clear()
        self.addCleanup(app.fishtank_map.clear)
        self.client = app.app.test_client()

    def new_tank(self):
        response = self.client.get('/fishtank_api/initialize_new_fishtank').get_json()
        self.assertEqual(response['status'], 'success')
        return response['fishtank_number']

    def operate(self, action, tank_number, fish):
        return self.client.post('/fishtank_api/fishtank_operation?action=' + action,
                                json={'fishtank_no': tank_number, 'fish': fish}).get_json()

    # adding nothing changes nothing and reports the tank as it is
    def fish_in_tank(self, tank_number):
        return self.operate('add', tank_number, [])['current_fishtank']['Fish']

    def test_fish_groups_include_every_id(self):
        groups = self.client.get('/fishtank_api/get_fish_by_group').get_json()
        all_fish = [fish for family in groups.values() for fish in family]
        self.assertEqual(sorted(fish['id'] for fish in all_fish), self.all_ids)
        self.assertEqual(self.all_ids, list(range(1, len(self.all_ids) + 1)))
        for fish in all_fish:
            self.assertEqual(Fish.get_by_id(fish['id']).scientific_name, fish['scientific_name'])

    def test_fish_groups_link_pictures_and_fishbase_pages(self):
        groups = self.client.get('/fishtank_api/get_fish_by_group').get_json()
        all_fish = {fish['id']: fish for family in groups.values() for fish in family}
        new_fish = all_fish[self.unknown_temperament_id]
        self.assertEqual((new_fish['data_source'], new_fish['cross_species_temperament'], new_fish['minimum_size']),
                         ('FishBase 25.04', 'unknown', None))
        self.assertTrue(new_fish['fishbase_url'].startswith('https://www.fishbase.se/summary/'))
        pictures = [picture for fish in all_fish.values() for picture in fish['pictures']]
        self.assertTrue(pictures)
        for picture in pictures:
            self.assertTrue(picture['url'].startswith('https://www.fishbase.se/images/species/'))
            self.assertTrue(picture['credit'].endswith('from FishBase'))
            self.assertIn(picture['licence'], ('free use', 'non-commercial use', 'public domain'))

    def test_fish_of_unknown_temperament_lives_alone(self):
        tank = self.new_tank()
        response = self.operate('add', tank, [self.unknown_temperament_id])
        self.assertEqual(response['current_fishtank']['Fish'], str({self.unknown_temperament_id: 1}))
        for other_id in (self.peaceful_id, self.unknown_temperament_id):
            with self.subTest(other_id=other_id):
                self.assertEqual(self.operate('add', tank, [other_id])['status'], 'error')
        self.assertEqual(self.fish_in_tank(tank), str({self.unknown_temperament_id: 1}))

    def test_fish_of_unknown_temperament_cannot_join_other_species(self):
        tank = self.new_tank()
        self.operate('add', tank, [self.peaceful_id])
        self.assertEqual(self.operate('add', tank, [self.unknown_temperament_id])['status'], 'error')
        self.assertEqual(self.fish_in_tank(tank), str({self.peaceful_id: 1}))

    def test_new_tank_is_empty(self):
        response = self.client.get('/fishtank_api/initialize_new_fishtank').get_json()
        self.assertEqual(response['fishtank']['Fish'], '{}')

    def test_add_fish_by_id_reports_ids(self):
        tank = self.new_tank()
        response = self.operate('add', tank, [self.peaceful_id, self.other_peaceful_id])
        self.assertEqual(response['status'], 'success')
        self.assertEqual(response['current_fishtank']['Fish'], str({self.peaceful_id: 1, self.other_peaceful_id: 1}))

    def test_adding_the_same_id_twice_counts_two_fish(self):
        tank = self.new_tank()
        response = self.operate('add', tank, [self.peaceful_id, self.peaceful_id])
        self.assertEqual(response['current_fishtank']['Fish'], str({self.peaceful_id: 2}))

    def test_remove_fish_by_id(self):
        tank = self.new_tank()
        self.operate('add', tank, [self.peaceful_id, self.peaceful_id, self.other_peaceful_id])
        response = self.operate('remove', tank, [self.peaceful_id, self.other_peaceful_id])
        self.assertEqual(response['status'], 'success')
        self.assertEqual(response['current_fishtank']['Fish'], str({self.peaceful_id: 1}))

    def test_removing_a_fish_that_is_not_in_the_tank_is_an_error(self):
        tank = self.new_tank()
        self.operate('add', tank, [self.peaceful_id])
        response = self.operate('remove', tank, [self.other_peaceful_id])
        self.assertEqual(response['status'], 'error')
        self.assertEqual(self.fish_in_tank(tank), str({self.peaceful_id: 1}))

    def test_incompatible_fish_is_rejected_and_tank_is_unchanged(self):
        tank = self.new_tank()
        self.operate('add', tank, [self.peaceful_id])
        response = self.operate('add', tank, [self.aggressive_id])
        self.assertEqual(response['status'], 'error')
        self.assertEqual(self.fish_in_tank(tank), str({self.peaceful_id: 1}))

    def test_unknown_ids_are_rejected(self):
        tank = self.new_tank()
        for unknown_id in (0, -1, self.all_ids[-1] + 1, 999999):
            with self.subTest(fish_id=unknown_id):
                response = self.operate('add', tank, [unknown_id])
                self.assertEqual(response, {'status': 'error', 'message': '{} does not exist in database'.format(unknown_id)})
        self.assertEqual(self.fish_in_tank(tank), '{}')

    def test_values_that_are_not_ids_are_rejected(self):
        tank = self.new_tank()
        for value in ('Corydoras acrensis', str(self.peaceful_id), float(self.peaceful_id), True, None, [self.peaceful_id]):
            with self.subTest(value=value):
                for action in ('add', 'remove'):
                    response = self.operate(action, tank, [value])
                    self.assertEqual(response, {'status': 'error', 'message': '{} is not a valid fish id'.format(value)})
        self.assertEqual(self.fish_in_tank(tank), '{}')

    def test_one_bad_id_rejects_the_whole_request(self):
        tank = self.new_tank()
        for bad_value in (999999, 'Corydoras adolfoi'):
            with self.subTest(value=bad_value):
                response = self.operate('add', tank, [self.peaceful_id, bad_value])
                self.assertEqual(response['status'], 'error')
        self.assertEqual(self.fish_in_tank(tank), '{}')


if __name__ == '__main__':
    unittest.main()
