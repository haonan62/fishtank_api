import os
import shutil
import tempfile
import unittest

from app import create_app
from models.database import SEED_DATABASE, use_database
from models.fish import Fish
from models.user import ROLE_ADMIN, User

# Tests for the http api, which identifies fish by id
# Every test runs the app on its own copy of data/fish.db
# Run from the project root: python -m unittest test_api -v

PREFIX = '/fishtank_api'


class ApiTestCase(unittest.TestCase):

    def setUp(self):
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory)
        self.app = create_app(os.path.join(directory, 'fishtank.db'))
        # other test modules read the committed database
        self.addCleanup(use_database, SEED_DATABASE)
        self.client = self.app.test_client()

    def call(self, method, path, json=None, token=None, expected_status=None):
        headers = {'Authorization': 'Bearer ' + token} if token else {}
        response = self.client.open(PREFIX + path, method=method, json=json, headers=headers)
        if expected_status is not None:
            self.assertEqual(response.status_code, expected_status, response.get_json())
        return response

    def register(self, username='alice', password='correct horse'):
        return self.call('POST', '/auth/register', {'username': username, 'password': password},
                         expected_status=201).get_json()['token']

    def register_admin(self, username='admin'):
        token = self.register(username)
        User.update(role=ROLE_ADMIN).where(User.username == username).execute()
        return token

    def new_tank(self, token=None, json=None):
        response = self.call('POST', '/fishtanks', json, token=token, expected_status=201).get_json()
        return response['fishtank']['key']

    def operate(self, action, tank_key, fish, token=None):
        return self.call('POST', '/fishtanks/{}/{}'.format(tank_key, action), {'fish': fish}, token=token)

    def fish_in_tank(self, tank_key, token=None):
        tank = self.call('GET', '/fishtanks/' + tank_key, token=token, expected_status=200).get_json()['fishtank']
        return {entry['id']: entry['count'] for entry in tank['fish']}


class ApiTest(ApiTestCase):

    @classmethod
    def setUpClass(cls):
        cls.peaceful_id = Fish.get(Fish.scientific_name == 'Corydoras acrensis').id
        cls.other_peaceful_id = Fish.get(Fish.scientific_name == 'Corydoras adolfoi').id
        cls.aggressive_id = Fish.get(Fish.scientific_name == 'Cynotilapia afra').id
        cls.unknown_temperament_id = Fish.get(Fish.scientific_name == 'Ameca splendens').id
        cls.all_ids = sorted(fish.id for fish in Fish.select())

    def fish_groups(self):
        return self.call('GET', '/fish?group_by=family', expected_status=200).get_json()['fish_by_family']

    def test_fish_groups_include_every_id(self):
        groups = self.fish_groups()
        all_fish = [fish for family in groups.values() for fish in family]
        self.assertEqual(sorted(fish['id'] for fish in all_fish), self.all_ids)
        self.assertEqual(self.all_ids, list(range(1, len(self.all_ids) + 1)))
        for fish in all_fish:
            self.assertEqual(Fish.get_by_id(fish['id']).scientific_name, fish['scientific_name'])

    def test_fish_groups_link_pictures_and_fishbase_pages(self):
        groups = self.fish_groups()
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

    def test_fish_list_is_by_id(self):
        fish = self.call('GET', '/fish', expected_status=200).get_json()['fish']
        self.assertEqual([entry['id'] for entry in fish], self.all_ids)
        one = self.call('GET', '/fish/{}'.format(self.peaceful_id), expected_status=200).get_json()['fish']
        self.assertEqual(one['scientific_name'], 'Corydoras acrensis')
        self.call('GET', '/fish/999999', expected_status=404)
        self.call('GET', '/fish?group_by=origin', expected_status=400)

    def test_fish_of_unknown_temperament_lives_alone(self):
        tank = self.new_tank()
        self.assertEqual(self.operate('add', tank, [self.unknown_temperament_id]).status_code, 200)
        self.assertEqual(self.fish_in_tank(tank), {self.unknown_temperament_id: 1})
        for other_id in (self.peaceful_id, self.unknown_temperament_id):
            with self.subTest(other_id=other_id):
                self.assertEqual(self.operate('add', tank, [other_id]).status_code, 422)
        self.assertEqual(self.fish_in_tank(tank), {self.unknown_temperament_id: 1})

    def test_fish_of_unknown_temperament_cannot_join_other_species(self):
        tank = self.new_tank()
        self.operate('add', tank, [self.peaceful_id])
        self.assertEqual(self.operate('add', tank, [self.unknown_temperament_id]).status_code, 422)
        self.assertEqual(self.fish_in_tank(tank), {self.peaceful_id: 1})

    def test_new_tank_is_empty_and_expires(self):
        tank = self.call('POST', '/fishtanks', expected_status=201).get_json()['fishtank']
        self.assertEqual(tank['fish'], [])
        self.assertEqual(tank['size'], {'length': 100, 'width': 100, 'height': 30})
        self.assertFalse(tank['saved'])
        self.assertIsNotNone(tank['expires_at'])

    def test_new_tank_takes_name_and_size(self):
        tank = self.call('POST', '/fishtanks', {'name': ' Living room ', 'size': {'length': 60, 'width': 30, 'height': 40}},
                         expected_status=201).get_json()['fishtank']
        self.assertEqual((tank['name'], tank['size']), ('Living room', {'length': 60, 'width': 30, 'height': 40}))
        for payload in ({'size': {'length': 60, 'width': 30}}, {'size': {'length': 0, 'width': 30, 'height': 40}},
                        {'size': [60, 30, 40]}, {'name': 5}, {'colour': 'blue'}):
            with self.subTest(payload=payload):
                self.call('POST', '/fishtanks', payload, expected_status=400)

    def test_tank_keys_cannot_be_guessed(self):
        keys = {self.new_tank() for _ in range(3)}
        self.assertEqual(len(keys), 3)
        for key in keys:
            self.assertGreaterEqual(len(key), 43)

    def test_unknown_tank_is_not_found(self):
        self.call('GET', '/fishtanks/nope', expected_status=404)
        self.assertEqual(self.operate('add', 'nope', [self.peaceful_id]).status_code, 404)

    def test_visitor_can_remove_a_tank(self):
        tank = self.new_tank()
        self.call('DELETE', '/fishtanks/' + tank, expected_status=200)
        self.call('GET', '/fishtanks/' + tank, expected_status=404)

    def test_add_fish_by_id_reports_ids(self):
        tank = self.new_tank()
        response = self.operate('add', tank, [self.peaceful_id, self.other_peaceful_id])
        self.assertEqual(response.status_code, 200)
        self.assertEqual([entry['id'] for entry in response.get_json()['fishtank']['fish']],
                         sorted([self.peaceful_id, self.other_peaceful_id]))
        self.assertEqual(self.fish_in_tank(tank), {self.peaceful_id: 1, self.other_peaceful_id: 1})

    def test_adding_the_same_id_twice_counts_two_fish(self):
        tank = self.new_tank()
        self.operate('add', tank, [self.peaceful_id, self.peaceful_id])
        self.assertEqual(self.fish_in_tank(tank), {self.peaceful_id: 2})

    def test_remove_fish_by_id(self):
        tank = self.new_tank()
        self.operate('add', tank, [self.peaceful_id, self.peaceful_id, self.other_peaceful_id])
        response = self.operate('remove', tank, [self.peaceful_id, self.other_peaceful_id])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.fish_in_tank(tank), {self.peaceful_id: 1})

    def test_removing_a_fish_that_is_not_in_the_tank_is_an_error(self):
        tank = self.new_tank()
        self.operate('add', tank, [self.peaceful_id])
        response = self.operate('remove', tank, [self.other_peaceful_id])
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.fish_in_tank(tank), {self.peaceful_id: 1})

    def test_incompatible_fish_is_rejected_and_tank_is_unchanged(self):
        tank = self.new_tank()
        self.operate('add', tank, [self.peaceful_id])
        response = self.operate('add', tank, [self.aggressive_id])
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()['status'], 'error')
        self.assertIn('Cynotilapia afra', response.get_json()['message'])
        self.assertEqual(self.fish_in_tank(tank), {self.peaceful_id: 1})

    def test_unknown_ids_are_rejected(self):
        tank = self.new_tank()
        for unknown_id in (0, -1, self.all_ids[-1] + 1, 999999):
            with self.subTest(fish_id=unknown_id):
                response = self.operate('add', tank, [unknown_id])
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.get_json(), {'status': 'error', 'message': '{} does not exist in database'.format(unknown_id)})
        self.assertEqual(self.fish_in_tank(tank), {})

    def test_values_that_are_not_ids_are_rejected(self):
        tank = self.new_tank()
        for value in ('Corydoras acrensis', str(self.peaceful_id), float(self.peaceful_id), True, None, [self.peaceful_id]):
            with self.subTest(value=value):
                for action in ('add', 'remove'):
                    response = self.operate(action, tank, [value])
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.get_json(), {'status': 'error', 'message': '{} is not a valid fish id'.format(value)})
        self.assertEqual(self.fish_in_tank(tank), {})

    def test_one_bad_id_rejects_the_whole_request(self):
        tank = self.new_tank()
        for bad_value in (999999, 'Corydoras adolfoi'):
            with self.subTest(value=bad_value):
                response = self.operate('add', tank, [self.peaceful_id, bad_value])
                self.assertEqual(response.get_json()['status'], 'error')
        self.assertEqual(self.fish_in_tank(tank), {})

    def test_requests_that_are_not_json_objects_are_rejected(self):
        tank = self.new_tank()
        for payload in ([self.peaceful_id], {'fish': self.peaceful_id}, None):
            with self.subTest(payload=payload):
                self.assertEqual(self.call('POST', '/fishtanks/{}/add'.format(tank), payload).status_code, 400)


if __name__ == '__main__':
    unittest.main()
