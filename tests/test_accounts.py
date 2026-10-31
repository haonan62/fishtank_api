from datetime import timedelta
import unittest

from fishtank.db import utcnow
from fishtank.models.fish import Fish, FishPicture
from fishtank.models.fishtank_record import FishtankRecord
from fishtank.models.user import AuthToken, User
from tests.api_test_case import ApiTestCase

# Tests for users, roles, saved fishtanks and the admin fish api
# Run from the project root: python -m unittest tests.test_accounts -v

# a fish with every field the api asks for, aggressive to smaller fish so it needs a size
NEW_FISH = {
    'scientific_name': 'Testus maximus', 'common_name': 'Test fish', 'family_name': 'Testidae',
    'minimum_size': 3, 'maximum_size': 6, 'minimum_ph': 6.5, 'maximum_ph': 7.5,
    'minimum_water_hardness': 5, 'maximum_water_hardness': 15, 'minimum_temperature': 22, 'maximum_temperature': 26,
    'reproduce_method': 'Spawning', 'origin': 'South America', 'in_species_temperament': 'peaceful',
    'cross_species_temperament': 'aggressive to smaller', 'fishtank_position': 'Middle levels',
}


class AuthTest(ApiTestCase):

    def test_register_logs_in_as_user(self):
        response = self.call('POST', '/auth/register', {'username': 'alice', 'password': 'correct horse'},
                             expected_status=201).get_json()
        self.assertEqual((response['user']['username'], response['user']['role']), ('alice', 'user'))
        me = self.call('GET', '/auth/me', token=response['token'], expected_status=200).get_json()['user']
        self.assertEqual(me['username'], 'alice')

    def test_password_and_token_are_not_stored_in_plain_text(self):
        token = self.register('alice', 'correct horse')
        user = User.get(User.username == 'alice')
        self.assertNotIn('correct horse', user.password_hash)
        self.assertFalse(AuthToken.select().where(AuthToken.token_hash == token).exists())
        self.assertNotIn('password', self.call('GET', '/auth/me', token=token).get_json()['user'])

    def test_usernames_are_unique_ignoring_case(self):
        self.register('alice')
        self.call('POST', '/auth/register', {'username': 'Alice', 'password': 'another one'}, expected_status=409)

    def test_bad_credentials_are_rejected_at_registration(self):
        for payload in ({'username': 'al', 'password': 'correct horse'}, {'username': 'alice bob', 'password': 'correct horse'},
                        {'username': 'alice', 'password': 'short'}, {'username': 'alice', 'password': 12345678},
                        {'username': 'alice'}, {'username': 'alice', 'password': 'correct horse', 'role': 'admin'}):
            with self.subTest(payload=payload):
                self.call('POST', '/auth/register', payload, expected_status=400)
        self.assertEqual(User.select().count(), 0)

    def test_login_with_right_and_wrong_password(self):
        self.register('alice', 'correct horse')
        token = self.call('POST', '/auth/login', {'username': 'ALICE', 'password': 'correct horse'},
                          expected_status=200).get_json()['token']
        self.call('GET', '/auth/me', token=token, expected_status=200)
        for payload in ({'username': 'alice', 'password': 'wrong horse'}, {'username': 'bob', 'password': 'correct horse'}):
            with self.subTest(payload=payload):
                response = self.call('POST', '/auth/login', payload, expected_status=401)
                self.assertEqual(response.get_json()['message'], 'wrong username or password')

    def test_logout_ends_only_that_token(self):
        first = self.register('alice', 'correct horse')
        second = self.call('POST', '/auth/login', {'username': 'alice', 'password': 'correct horse'}).get_json()['token']
        self.call('POST', '/auth/logout', token=first, expected_status=200)
        self.call('GET', '/auth/me', token=first, expected_status=401)
        self.call('GET', '/auth/me', token=second, expected_status=200)

    def test_expired_or_wrong_tokens_are_refused(self):
        token = self.register('alice')
        AuthToken.update(expires_at=utcnow() - timedelta(seconds=1)).execute()
        response = self.call('GET', '/auth/me', token=token, expected_status=401)
        self.assertEqual(response.headers['WWW-Authenticate'], 'Bearer')
        self.assertEqual(AuthToken.select().count(), 0)
        # a wrong token is not quietly treated as a visitor
        self.call('POST', '/fishtanks', token='not-a-token', expected_status=401)
        response = self.client.post('/fishtank_api/fishtanks', headers={'Authorization': 'Basic abc'})
        self.assertEqual(response.status_code, 401)

    def test_visitors_have_no_me(self):
        self.call('GET', '/auth/me', expected_status=401)
        self.call('POST', '/auth/logout', expected_status=401)


class SavedFishtankTest(ApiTestCase):

    def setUp(self):
        super().setUp()
        self.peaceful_id = Fish.get(Fish.scientific_name == 'Corydoras acrensis').id
        self.other_peaceful_id = Fish.get(Fish.scientific_name == 'Corydoras adolfoi').id
        self.alice = self.register('alice')
        self.bob = self.register('bob')

    def test_user_tanks_are_saved_and_listed(self):
        key = self.new_tank(self.alice, {'name': 'Living room'})
        self.operate('add', key, [self.peaceful_id, self.peaceful_id], token=self.alice)
        tanks = self.call('GET', '/fishtanks', token=self.alice, expected_status=200).get_json()['fishtanks']
        self.assertEqual([(tank['key'], tank['name'], tank['saved'], tank['expires_at']) for tank in tanks],
                         [(key, 'Living room', True, None)])
        self.assertEqual(self.fish_in_tank(key, self.alice), {self.peaceful_id: 2})
        self.assertEqual(self.call('GET', '/fishtanks', token=self.bob).get_json()['fishtanks'], [])

    def test_saved_tanks_survive_logging_in_again(self):
        key = self.new_tank(self.alice)
        self.operate('add', key, [self.peaceful_id], token=self.alice)
        self.call('POST', '/auth/logout', token=self.alice)
        token = self.call('POST', '/auth/login', {'username': 'alice', 'password': 'correct horse'}).get_json()['token']
        self.assertEqual(self.fish_in_tank(key, token), {self.peaceful_id: 1})

    def test_only_the_owner_can_use_a_saved_tank(self):
        key = self.new_tank(self.alice)
        for token in (self.bob, None):
            with self.subTest(token=token):
                self.call('GET', '/fishtanks/' + key, token=token, expected_status=404)
                self.assertEqual(self.operate('add', key, [self.peaceful_id], token=token).status_code, 404)
                self.call('PATCH', '/fishtanks/' + key, {'name': 'mine now'}, token=token, expected_status=404)
                self.call('DELETE', '/fishtanks/' + key, token=token, expected_status=404)
        self.call('POST', '/fishtanks/{}/save'.format(key), token=self.bob, expected_status=404)
        self.assertEqual(self.fish_in_tank(key, self.alice), {})

    def test_visitors_cannot_list_tanks(self):
        self.call('GET', '/fishtanks', expected_status=401)

    def test_owner_changes_name_and_size(self):
        key = self.new_tank(self.alice)
        tank = self.call('PATCH', '/fishtanks/' + key, {'name': 'Office', 'size': {'length': 80, 'width': 35, 'height': 45}},
                         token=self.alice, expected_status=200).get_json()['fishtank']
        self.assertEqual((tank['name'], tank['size']), ('Office', {'length': 80, 'width': 35, 'height': 45}))
        tank = self.call('PATCH', '/fishtanks/' + key, {'name': None}, token=self.alice, expected_status=200).get_json()['fishtank']
        self.assertIsNone(tank['name'])
        self.call('PATCH', '/fishtanks/' + key, {'size': {'length': -1, 'width': 35, 'height': 45}}, token=self.alice,
                  expected_status=400)

    def test_owner_removes_a_tank(self):
        key = self.new_tank(self.alice)
        self.operate('add', key, [self.peaceful_id], token=self.alice)
        self.call('DELETE', '/fishtanks/' + key, token=self.alice, expected_status=200)
        self.call('GET', '/fishtanks/' + key, token=self.alice, expected_status=404)

    def test_user_saves_a_tank_built_as_visitor(self):
        key = self.new_tank()
        self.operate('add', key, [self.peaceful_id])
        self.call('POST', '/fishtanks/{}/save'.format(key), expected_status=401)
        tank = self.call('POST', '/fishtanks/{}/save'.format(key), token=self.alice, expected_status=200).get_json()['fishtank']
        self.assertEqual((tank['saved'], tank['expires_at']), (True, None))
        self.call('GET', '/fishtanks/' + key, expected_status=404)
        self.assertEqual(self.fish_in_tank(key, self.alice), {self.peaceful_id: 1})
        # saving again changes nothing
        self.call('POST', '/fishtanks/{}/save'.format(key), token=self.alice, expected_status=200)

    def test_visitor_tanks_expire_and_are_cleaned_up(self):
        key = self.new_tank()
        saved_key = self.new_tank(self.alice)
        FishtankRecord.update(expires_at=utcnow() - timedelta(seconds=1)).where(FishtankRecord.key == key).execute()
        self.call('GET', '/fishtanks/' + key, expected_status=404)
        self.new_tank()
        self.assertFalse(FishtankRecord.select().where(FishtankRecord.key == key).exists())
        self.call('GET', '/fishtanks/' + saved_key, token=self.alice, expected_status=200)

    def test_changes_keep_a_visitor_tank_alive(self):
        key = self.new_tank()
        soon = utcnow() + timedelta(minutes=1)
        FishtankRecord.update(expires_at=soon).where(FishtankRecord.key == key).execute()
        self.operate('add', key, [self.peaceful_id])
        self.assertGreater(FishtankRecord.get(FishtankRecord.key == key).expires_at, soon + timedelta(hours=23))

    def test_tank_keeps_a_renamed_fish(self):
        key = self.new_tank(self.alice)
        self.operate('add', key, [self.peaceful_id], token=self.alice)
        Fish.update(scientific_name='Corydoras renamed').where(Fish.id == self.peaceful_id).execute()
        tank = self.call('GET', '/fishtanks/' + key, token=self.alice).get_json()['fishtank']
        self.assertEqual([(entry['id'], entry['scientific_name']) for entry in tank['fish']],
                         [(self.peaceful_id, 'Corydoras renamed')])
        self.assertEqual(self.operate('add', key, [self.other_peaceful_id], token=self.alice).status_code, 200)

    def test_removing_a_user_removes_their_tanks(self):
        key = self.new_tank(self.alice)
        self.operate('add', key, [self.peaceful_id], token=self.alice)
        User.get(User.username == 'alice').delete_instance()
        self.assertFalse(FishtankRecord.select().where(FishtankRecord.key == key).exists())


class AdminFishTest(ApiTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.register_admin()
        self.user = self.register('alice')

    def create(self, overrides=None, expected_status=201):
        payload = dict(NEW_FISH, **(overrides or {}))
        return self.call('POST', '/fish', payload, token=self.admin, expected_status=expected_status).get_json()

    def test_admin_creates_a_fish_for_everyone(self):
        fish = self.create()['fish']
        self.assertEqual((fish['scientific_name'], fish['data_source'], fish['pictures'], fish['fishbase_url']),
                         ('Testus maximus', 'manual entry', [], None))
        self.assertGreater(fish['id'], 1040)
        listed = self.call('GET', '/fish', token=self.admin).get_json()['fish']
        self.assertIn(fish, listed)
        groups = self.call('GET', '/fish?group_by=family').get_json()['fish_by_family']
        self.assertEqual([entry['id'] for entry in groups['Testidae']], [fish['id']])
        # and it can be put in a fishtank straight away
        key = self.new_tank()
        self.assertEqual(self.operate('add', key, [fish['id']]).status_code, 200)

    def test_only_admins_change_fish(self):
        fish = Fish.get(Fish.scientific_name == 'Corydoras acrensis')
        for token, status in ((None, 401), (self.user, 403)):
            with self.subTest(token=token):
                self.call('POST', '/fish', NEW_FISH, token=token, expected_status=status)
                self.call('PATCH', '/fish/{}'.format(fish.id), {'common_name': 'x'}, token=token, expected_status=status)
                self.call('DELETE', '/fish/{}'.format(fish.id), token=token, expected_status=status)
        self.assertFalse(Fish.select().where(Fish.scientific_name == 'Testus maximus').exists())
        self.assertEqual(Fish.get_by_id(fish.id).common_name, fish.common_name)

    def test_invalid_fish_are_rejected(self):
        cases = [
            {'scientific_name': None}, {'scientific_name': '  '}, {'family_name': 7},
            {'minimum_ph': 'acidic'}, {'minimum_temperature': 22.5}, {'minimum_water_hardness': True},
            {'minimum_ph': 8.0}, {'minimum_size': None}, {'minimum_ph': -1.0}, {'maximum_temperature': 99},
            {'cross_species_temperament': 'grumpy'}, {'in_species_temperament': 'aggressive to smaller'},
            {'minimum_size': None, 'maximum_size': None}, {'scientific_name': 'x' * 101},
            {'id': 5}, {'pictures': []}, {'colour': 'blue'},
        ]
        for overrides in cases:
            with self.subTest(overrides=overrides):
                self.create(overrides, expected_status=400)
        self.call('POST', '/fish', [NEW_FISH], token=self.admin, expected_status=400)
        for number in ('NaN', 'Infinity'):
            with self.subTest(number=number):
                body = '{"minimum_ph": %s, "scientific_name": "Testus maximus"}' % number
                response = self.client.patch('/fishtank_api/fish/1', data=body, content_type='application/json',
                                             headers={'Authorization': 'Bearer ' + self.admin})
                self.assertEqual(response.status_code, 400, response.get_json())
        self.assertFalse(Fish.select().where(Fish.family_name == 'Testidae').exists())

    def test_fish_of_unknown_temperament_needs_no_size(self):
        fish = self.create({'minimum_size': None, 'maximum_size': None, 'cross_species_temperament': 'unknown',
                            'in_species_temperament': 'unknown', 'reproduce_method': None, 'origin': ''})['fish']
        self.assertEqual((fish['minimum_size'], fish['origin']), (None, None))

    def test_names_and_species_codes_stay_unique(self):
        self.create({'fishbase_spec_code': 123456789})
        self.create({'scientific_name': 'Corydoras acrensis'}, expected_status=409)
        self.create({'scientific_name': 'Testus minimus', 'fishbase_spec_code': 123456789}, expected_status=409)

    def test_admin_changes_some_fields(self):
        fish = self.create()['fish']
        changed = self.call('PATCH', '/fish/{}'.format(fish['id']), {'common_name': 'Renamed', 'maximum_size': 8},
                            token=self.admin, expected_status=200).get_json()['fish']
        self.assertEqual((changed['common_name'], changed['maximum_size'], changed['minimum_size']), ('Renamed', 8, 3))
        # the rules hold for the whole fish after the change
        self.call('PATCH', '/fish/{}'.format(fish['id']), {'minimum_size': 9}, token=self.admin, expected_status=400)
        self.call('PATCH', '/fish/{}'.format(fish['id']), {'scientific_name': 'Corydoras adolfoi'}, token=self.admin,
                  expected_status=409)
        self.call('PATCH', '/fish/999999', {'common_name': 'x'}, token=self.admin, expected_status=404)
        self.assertEqual(Fish.get_by_id(fish['id']).size_min, 3)

    def test_admin_changes_an_existing_fish(self):
        fish_id = Fish.get(Fish.scientific_name == 'Ameca splendens').id
        changed = self.call('PATCH', '/fish/{}'.format(fish_id),
                            {'in_species_temperament': 'peaceful', 'cross_species_temperament': 'peaceful',
                             'minimum_size': 8, 'maximum_size': 12}, token=self.admin, expected_status=200).get_json()['fish']
        self.assertEqual(changed['cross_species_temperament'], 'peaceful')
        self.assertEqual(changed['data_source'], 'FishBase 25.04')
        # the simulation sees the change straight away
        key = self.new_tank()
        self.assertEqual(self.operate('add', key, [fish_id, fish_id]).status_code, 200)

    def test_admin_removes_a_fish_with_its_pictures(self):
        fish_id = FishPicture.select().get().fish_id
        self.call('DELETE', '/fish/{}'.format(fish_id), token=self.admin, expected_status=200)
        self.assertIsNone(Fish.get_or_none(Fish.id == fish_id))
        self.assertFalse(FishPicture.select().where(FishPicture.fish == fish_id).exists())
        self.call('GET', '/fish/{}'.format(fish_id), expected_status=404)
        self.call('DELETE', '/fish/{}'.format(fish_id), token=self.admin, expected_status=404)

    def test_fish_in_a_tank_cannot_be_removed(self):
        fish_id = Fish.get(Fish.scientific_name == 'Corydoras acrensis').id
        key = self.new_tank(self.user)
        self.operate('add', key, [fish_id], token=self.user)
        response = self.call('DELETE', '/fish/{}'.format(fish_id), token=self.admin, expected_status=409)
        self.assertIn('1 fishtank', response.get_json()['message'])
        self.operate('remove', key, [fish_id], token=self.user)
        self.call('DELETE', '/fish/{}'.format(fish_id), token=self.admin, expected_status=200)

    def test_fish_only_in_expired_visitor_tanks_can_be_removed(self):
        fish_id = Fish.get(Fish.scientific_name == 'Corydoras acrensis').id
        key = self.new_tank()
        self.operate('add', key, [fish_id])
        FishtankRecord.update(expires_at=utcnow() - timedelta(seconds=1)).execute()
        self.call('DELETE', '/fish/{}'.format(fish_id), token=self.admin, expected_status=200)


class AdminUserTest(ApiTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.register_admin()
        self.user = self.register('alice')
        self.alice_id = User.get(User.username == 'alice').id
        self.admin_id = User.get(User.username == 'admin').id

    def test_only_admins_list_users(self):
        users = self.call('GET', '/users', token=self.admin, expected_status=200).get_json()['users']
        self.assertEqual([(user['username'], user['role']) for user in users], [('admin', 'admin'), ('alice', 'user')])
        self.call('GET', '/users', token=self.user, expected_status=403)
        self.call('GET', '/users', expected_status=401)

    def test_admin_promotes_a_user(self):
        self.call('PATCH', '/users/{}'.format(self.alice_id), {'role': 'admin'}, token=self.user, expected_status=403)
        self.call('PATCH', '/users/{}'.format(self.alice_id), {'role': 'admin'}, token=self.admin, expected_status=200)
        self.call('POST', '/fish', NEW_FISH, token=self.user, expected_status=201)
        self.call('PATCH', '/users/{}'.format(self.alice_id), {'role': 'owner'}, token=self.admin, expected_status=400)
        self.call('PATCH', '/users/999999', {'role': 'user'}, token=self.admin, expected_status=404)

    def test_last_admin_cannot_step_down(self):
        self.call('PATCH', '/users/{}'.format(self.admin_id), {'role': 'user'}, token=self.admin, expected_status=409)
        self.call('PATCH', '/users/{}'.format(self.alice_id), {'role': 'admin'}, token=self.admin, expected_status=200)
        self.call('PATCH', '/users/{}'.format(self.admin_id), {'role': 'user'}, token=self.admin, expected_status=200)
        # a demoted admin loses admin rights at once
        self.call('GET', '/users', token=self.admin, expected_status=403)


class CommandTest(ApiTestCase):

    def test_create_admin_and_set_role(self):
        runner = self.app.test_cli_runner()
        result = runner.invoke(args=['create-admin', 'root'], input='correct horse\ncorrect horse\n')
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue(User.get(User.username == 'root').is_admin())
        result = runner.invoke(args=['create-admin', 'root'], input='correct horse\ncorrect horse\n')
        self.assertNotEqual(result.exit_code, 0)
        self.register('alice')
        self.assertEqual(runner.invoke(args=['set-role', 'alice', 'admin']).exit_code, 0)
        self.assertTrue(User.get(User.username == 'alice').is_admin())
        self.assertEqual(runner.invoke(args=['set-role', 'root', 'user']).exit_code, 0)
        self.assertNotEqual(runner.invoke(args=['set-role', 'alice', 'user']).exit_code, 0)
        self.assertNotEqual(runner.invoke(args=['set-role', 'nobody', 'user']).exit_code, 0)


if __name__ == '__main__':
    unittest.main()
