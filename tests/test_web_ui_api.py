import gzip
import os
import shutil
import tempfile
import unittest
from unittest import mock

from fishtank import app as app_module
from fishtank.models.fish import Fish
from fishtank.simulation.fishtank import Fishtank
from tests.api_test_case import ApiTestCase
from tests.test_accounts import NEW_FISH

# Tests for what the web ui needs from the api: field names on errors, which fish can join a fishtank,
# retiring fish, fishtank counts for admins, compressed json and serving the built ui
# Run from the project root: python -m unittest tests.test_web_ui_api -v


class FieldErrorTest(ApiTestCase):

    def test_validation_errors_name_their_field(self):
        admin = self.register_admin()
        cases = [({'scientific_name': None}, 'scientific_name'), ({'minimum_ph': 'acidic'}, 'minimum_ph'),
                 ({'minimum_ph': 8.0}, 'minimum_ph'), ({'minimum_size': None, 'maximum_size': None}, 'minimum_size'),
                 ({'retired': True}, 'retired'), ({'colour': 'blue'}, 'colour'),
                 ({'scientific_name': 'Corydoras acrensis'}, 'scientific_name')]
        for overrides, field in cases:
            with self.subTest(overrides=overrides):
                response = self.call('POST', '/fish', dict(NEW_FISH, **overrides), token=admin)
                self.assertIn(response.status_code, (400, 409))
                self.assertEqual(response.get_json()['field'], field)

    def test_registration_errors_name_their_field(self):
        for payload, field in (({'username': 'a', 'password': 'correct horse'}, 'username'),
                               ({'username': 'alice', 'password': 'short'}, 'password')):
            with self.subTest(field=field):
                self.assertEqual(self.call('POST', '/auth/register', payload, expected_status=400).get_json()['field'], field)
        self.register('alice')
        response = self.call('POST', '/auth/register', {'username': 'alice', 'password': 'correct horse'}, expected_status=409)
        self.assertEqual(response.get_json()['field'], 'username')

    def test_other_errors_have_no_field(self):
        self.assertNotIn('field', self.call('GET', '/fishtanks/nope', expected_status=404).get_json())


class CompatibleFishTest(ApiTestCase):

    def setUp(self):
        super().setUp()
        self.peaceful = Fish.get(Fish.scientific_name == 'Corydoras acrensis')
        self.aggressive = Fish.get(Fish.scientific_name == 'Cynotilapia afra')
        self.unknown = Fish.get(Fish.scientific_name == 'Ameca splendens')

    def compatible(self, key, token=None):
        response = self.call('GET', '/fishtanks/{}/compatible'.format(key), token=token, expected_status=200).get_json()
        return set(response['compatible']), {entry['id']: entry['reason'] for entry in response['incompatible']}

    def test_every_fish_fits_an_empty_tank(self):
        compatible, incompatible = self.compatible(self.new_tank())
        self.assertEqual(compatible, {fish.id for fish in Fish.select()})
        self.assertEqual(incompatible, {})

    def test_answer_matches_adding_each_fish(self):
        key = self.new_tank()
        self.operate('add', key, [self.peaceful.id])
        compatible, incompatible = self.compatible(key)
        self.assertEqual(compatible | set(incompatible), {fish.id for fish in Fish.select()})
        self.assertIn(self.peaceful.id, compatible)
        self.assertIn('Cynotilapia afra', incompatible[self.aggressive.id])
        self.assertIn(self.unknown.id, incompatible)
        # spot check a spread of fish against the real add
        for fish_id in sorted(compatible)[::97] + sorted(incompatible)[::97]:
            with self.subTest(fish_id=fish_id):
                trial = self.new_tank()
                self.operate('add', trial, [self.peaceful.id])
                status = self.operate('add', trial, [fish_id]).status_code
                self.assertEqual(status, 200 if fish_id in compatible else 422)

    def test_saved_tanks_stay_private(self):
        key = self.new_tank(self.register('alice'))
        self.call('GET', '/fishtanks/{}/compatible'.format(key), expected_status=404)

    def test_check_can_add_leaves_the_tank_unchanged(self):
        tank = Fishtank(fish_map={})
        tank.add_fish(self.peaceful)
        tank.check_can_add(self.peaceful)
        self.assertEqual(tank.fish_map, {self.peaceful.scientific_name: 1})


class RetireFishTest(ApiTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.register_admin()
        self.fish = Fish.get(Fish.scientific_name == 'Corydoras acrensis')

    def retire(self, token=None, expected_status=200):
        return self.call('POST', '/fish/{}/retire'.format(self.fish.id), token=token or self.admin,
                         expected_status=expected_status).get_json()

    def catalogue_ids(self, token=None, query=''):
        return {fish['id'] for fish in self.call('GET', '/fish' + query, token=token, expected_status=200).get_json()['fish']}

    def test_retired_fish_leaves_the_catalogue(self):
        self.assertTrue(self.retire()['fish']['retired'])
        self.assertNotIn(self.fish.id, self.catalogue_ids())
        groups = self.call('GET', '/fish?group_by=family').get_json()['fish_by_family']
        self.assertNotIn(self.fish.id, [fish['id'] for family in groups.values() for fish in family])
        # it can still be looked up, fishtanks may keep it
        self.assertTrue(self.call('GET', '/fish/{}'.format(self.fish.id), expected_status=200).get_json()['fish']['retired'])

    def test_only_admins_see_retired_fish(self):
        self.retire()
        self.assertIn(self.fish.id, self.catalogue_ids(self.admin, '?include_retired=true'))
        self.call('GET', '/fish?include_retired=true', expected_status=403)
        self.call('GET', '/fish?include_retired=true', token=self.register('alice'), expected_status=403)

    def test_retired_fish_cannot_be_added_but_stays_in_tanks(self):
        key = self.new_tank()
        self.operate('add', key, [self.fish.id])
        self.retire()
        response = self.operate('add', key, [self.fish.id])
        self.assertEqual(response.status_code, 409)
        self.assertIn('retired', response.get_json()['message'])
        self.assertEqual(self.fish_in_tank(key), {self.fish.id: 1})
        compatible = self.call('GET', '/fishtanks/{}/compatible'.format(key)).get_json()
        self.assertNotIn(self.fish.id, compatible['compatible'] + [entry['id'] for entry in compatible['incompatible']])
        self.assertEqual(self.operate('remove', key, [self.fish.id]).status_code, 200)

    def test_restore_brings_it_back(self):
        self.retire()
        restored = self.call('POST', '/fish/{}/restore'.format(self.fish.id), token=self.admin, expected_status=200).get_json()
        self.assertFalse(restored['fish']['retired'])
        self.assertIn(self.fish.id, self.catalogue_ids())
        # retiring or restoring twice changes nothing
        self.call('POST', '/fish/{}/restore'.format(self.fish.id), token=self.admin, expected_status=200)
        self.retire()
        self.retire()

    def test_only_admins_retire_and_restore(self):
        user = self.register('alice')
        for action in ('retire', 'restore'):
            with self.subTest(action=action):
                self.call('POST', '/fish/{}/{}'.format(self.fish.id, action), expected_status=401)
                self.call('POST', '/fish/{}/{}'.format(self.fish.id, action), token=user, expected_status=403)
        self.call('POST', '/fish/999999/retire', token=self.admin, expected_status=404)

    def test_admins_see_how_many_tanks_keep_a_fish(self):
        user = self.register('alice')
        for token in (user, None):
            key = self.new_tank(token)
            self.operate('add', key, [self.fish.id, self.fish.id], token=token)
        listed = {fish['id']: fish for fish in self.call('GET', '/fish', token=self.admin).get_json()['fish']}
        self.assertEqual(listed[self.fish.id]['fishtank_count'], 2)
        self.assertEqual(self.call('GET', '/fish/{}'.format(self.fish.id), token=self.admin).get_json()['fish']['fishtank_count'], 2)
        self.assertNotIn('fishtank_count', self.call('GET', '/fish/{}'.format(self.fish.id), token=user).get_json()['fish'])


class CompressionTest(ApiTestCase):

    def test_large_json_is_gzipped_when_asked(self):
        response = self.client.get('/fishtank_api/fish', headers={'Accept-Encoding': 'gzip, deflate'})
        self.assertEqual(response.headers['Content-Encoding'], 'gzip')
        self.assertIn('Accept-Encoding', response.headers['Vary'])
        self.assertIn(b'"scientific_name"', gzip.decompress(response.data))
        self.assertLess(len(response.data), 100000)

    def test_not_gzipped_unless_asked_or_small(self):
        self.assertNotIn('Content-Encoding', self.client.get('/fishtank_api/fish').headers)
        small = self.client.get('/fishtank_api/fishtanks/nope', headers={'Accept-Encoding': 'gzip'})
        self.assertNotIn('Content-Encoding', small.headers)


class FrontendServingTest(ApiTestCase):

    def setUp(self):
        super().setUp()
        self.dist = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dist)
        os.makedirs(os.path.join(self.dist, 'assets'))
        with open(os.path.join(self.dist, 'index.html'), 'w') as index:
            index.write('<!doctype html><div id="root"></div>')
        with open(os.path.join(self.dist, 'assets', 'app-1234.js'), 'w') as asset:
            asset.write('console.log(1)')
        patcher = mock.patch.object(app_module, 'FRONTEND_DIST', self.dist)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_ui_routes_get_index_html(self):
        for path in ('/', '/fish', '/tanks/abc', '/admin/fish/12'):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn(b'id="root"', response.data)
                # index.html names the current assets, so it is checked with the server every time
                self.assertIn(response.headers['Cache-Control'], ('no-cache', 'max-age=0', 'no-cache, max-age=0'))

    def test_assets_are_served_and_cached(self):
        response = self.client.get('/assets/app-1234.js')
        self.assertEqual(response.status_code, 200)
        self.assertIn('max-age=31536000', response.headers['Cache-Control'])

    def test_api_paths_stay_json(self):
        for path in ('/fishtank_api/nope', '/fishtank_api/fishtanks/nope'):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.get_json()['status'], 'error')

    def test_files_outside_the_build_are_not_served(self):
        response = self.client.get('/../pyproject.toml')
        self.assertNotIn(b'[project]', response.data)
        response = self.client.get('/assets/%2e%2e/%2e%2e/pyproject.toml')
        self.assertNotIn(b'[project]', response.data)

    def test_missing_build_says_how_to_build(self):
        os.remove(os.path.join(self.dist, 'index.html'))
        response = self.client.get('/')
        self.assertEqual(response.status_code, 404)
        self.assertIn('npm run build', response.get_json()['message'])


if __name__ == '__main__':
    unittest.main()
