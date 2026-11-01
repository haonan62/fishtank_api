import csv
import io
import unittest

from fishtank.models.fish import Fish, FishPicture
from fishtank.models.review import AuditEvent, TemperamentSuggestion
from fishtank.models.user import User
from tests.api_test_case import ApiTestCase
from tests.test_accounts import NEW_FISH

# Tests for clearing the review backlog: suggestions from users, the catalogue as csv, and the audit log
# Run from the project root: python -m unittest tests.test_review -v

SUGGESTION = {'in_species_temperament': 'peaceful', 'cross_species_temperament': 'peaceful', 'minimum_size': 5,
              'maximum_size': 8}


class ReviewTestCase(ApiTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.register_admin()
        self.user = self.register('alice')
        self.unknown = Fish.get(Fish.scientific_name == 'Ameca splendens')
        self.known = Fish.get(Fish.scientific_name == 'Corydoras acrensis')

    def suggest(self, payload=None, fish=None, token=None, expected_status=201):
        return self.call('POST', '/fish/{}/suggestions'.format((fish or self.unknown).id), payload or SUGGESTION,
                         token=token or self.user, expected_status=expected_status).get_json()

    def events(self, **query):
        path = '/audit' + ('?' + '&'.join('{}={}'.format(k, v) for k, v in query.items()) if query else '')
        return self.call('GET', path, token=self.admin, expected_status=200).get_json()['events']


class SuggestionTest(ReviewTestCase):

    def test_user_suggests_and_admin_approves(self):
        suggestion = self.suggest(dict(SUGGESTION, minimum_group_size=6, note='  kept them for years  '))['suggestion']
        self.assertEqual((suggestion['status'], suggestion['username'], suggestion['note'], suggestion['minimum_group_size']),
                         ('pending', 'alice', 'kept them for years', 6))
        listed = self.call('GET', '/suggestions', token=self.admin).get_json()
        self.assertEqual((listed['pending'], [s['id'] for s in listed['suggestions']]), (1, [suggestion['id']]))
        answer = self.call('POST', '/suggestions/{}/approve'.format(suggestion['id']), token=self.admin, expected_status=200).get_json()
        self.assertEqual((answer['fish']['cross_species_temperament'], answer['fish']['maximum_size'], answer['fish']['minimum_group_size'],
                          answer['fish']['group_size_source']), ('peaceful', 8, 6, 'manual entry'))
        self.assertEqual(answer['suggestion']['reviewed_by'], 'admin')
        # the fish is no longer kept alone
        key = self.new_tank()
        self.assertEqual(self.operate('add', key, [self.unknown.id, self.unknown.id]).status_code, 200)
        [event] = self.events()
        self.assertEqual((event['action'], event['username'], event['details']['suggested_by']), ('suggestion.approve', 'admin', 'alice'))
        self.assertEqual(event['details']['changes']['cross_species_temperament'], {'from': 'unknown', 'to': 'peaceful'})

    def test_reject(self):
        suggestion = self.suggest()['suggestion']
        rejected = self.call('POST', '/suggestions/{}/reject'.format(suggestion['id']), token=self.admin, expected_status=200).get_json()
        self.assertEqual(rejected['suggestion']['status'], 'rejected')
        self.assertEqual(Fish.get_by_id(self.unknown.id).cross_species_temperament, 'unknown')
        self.call('POST', '/suggestions/{}/approve'.format(suggestion['id']), token=self.admin, expected_status=409)
        self.assertEqual(self.events()[0]['action'], 'suggestion.reject')
        self.assertEqual(self.call('GET', '/suggestions?status=rejected', token=self.admin).get_json()['suggestions'][0]['id'],
                         suggestion['id'])

    def test_suggestions_are_checked_like_admin_changes(self):
        cases = [({'minimum_size': None, 'maximum_size': None}, 'minimum_size'), ({'minimum_size': 9}, 'minimum_size'),
                 ({'cross_species_temperament': 'unknown'}, 'cross_species_temperament'),
                 ({'in_species_temperament': 'aggressive/territorial', 'minimum_group_size': 6}, 'minimum_group_size'),
                 ({'note': 'x' * 501}, 'note'), ({'scientific_name': 'Renamed'}, 'scientific_name')]
        for changes, field in cases:
            with self.subTest(changes=changes):
                self.assertEqual(self.suggest(dict(SUGGESTION, **changes), expected_status=400)['field'], field)
        self.assertEqual(TemperamentSuggestion.select().count(), 0)

    def test_only_logged_in_users_and_unknown_fish(self):
        self.call('POST', '/fish/{}/suggestions'.format(self.unknown.id), SUGGESTION, expected_status=401)
        self.suggest(fish=self.known, expected_status=409)
        self.call('POST', '/fish/{}/retire'.format(self.unknown.id), token=self.admin)
        self.suggest(expected_status=409)

    def test_a_newer_suggestion_replaces_the_pending_one(self):
        self.suggest()
        second = self.suggest(dict(SUGGESTION, maximum_size=10))['suggestion']
        self.assertEqual([s.id for s in TemperamentSuggestion.select()], [second['id']])
        self.suggest(token=self.register('bob'))
        self.assertEqual(TemperamentSuggestion.select().count(), 2)

    def test_only_admins_review(self):
        suggestion = self.suggest()['suggestion']
        for path in ('/suggestions/{}/approve', '/suggestions/{}/reject'):
            self.call('POST', path.format(suggestion['id']), token=self.user, expected_status=403)
        self.call('GET', '/suggestions', token=self.user, expected_status=403)
        self.call('POST', '/suggestions/999999/approve', token=self.admin, expected_status=404)

    def test_approval_checks_again(self):
        suggestion = self.suggest(dict(SUGGESTION, minimum_group_size=6))['suggestion']
        # the fish was changed since, a group no longer fits its temperament
        self.call('PATCH', '/fish/{}'.format(self.unknown.id), {'in_species_temperament': 'aggressive/territorial'}, token=self.admin)
        TemperamentSuggestion.update(in_species_temperament='aggressive/territorial').execute()
        answer = self.call('POST', '/suggestions/{}/approve'.format(suggestion['id']), token=self.admin, expected_status=400).get_json()
        self.assertEqual(answer['field'], 'minimum_group_size')
        self.assertEqual(TemperamentSuggestion.get_by_id(suggestion['id']).status, 'pending')


class CsvTest(ReviewTestCase):

    def export(self, query=''):
        response = self.client.get('/fishtank_api/fish/export.csv' + query, headers={'Authorization': 'Bearer ' + self.admin})
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response.headers['Content-Disposition'])
        return list(csv.DictReader(io.StringIO(response.data.decode())))

    def upload(self, text, dry_run=False, token=None):
        return self.client.post('/fishtank_api/fish/import' + ('?dry_run=true' if dry_run else ''), data=text.encode(),
                                headers={'Authorization': 'Bearer ' + (token or self.admin), 'Content-Type': 'text/csv'})

    def test_export(self):
        rows = self.export()
        self.assertEqual(len(rows), Fish.select().count())
        self.assertEqual(list(rows[0])[:3], ['id', 'scientific_name', 'common_name'])
        review = self.export('?review=true')
        self.assertTrue(all(row['cross_species_temperament'] == 'unknown' or row['in_species_temperament'] == 'unknown' for row in review))
        self.assertIn(str(self.unknown.id), [row['id'] for row in review])
        neon = next(row for row in rows if row['scientific_name'] == 'Paracheirodon innesi')
        self.assertEqual((neon['minimum_group_size'], neon['reproduce_method']), ('6', 'Spawning'))

    def test_export_round_trips_without_changes(self):
        output = io.StringIO()
        rows = self.export()
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
        result = self.upload(output.getvalue(), dry_run=True).get_json()
        self.assertEqual((result['errors'], result['changed']), (0, 0))

    def test_dry_run_then_apply(self):
        text = 'id,cross_species_temperament,in_species_temperament,minimum_size,maximum_size\n{},peaceful,peaceful,5,8\n'.format(self.unknown.id)
        checked = self.upload(text, dry_run=True).get_json()
        self.assertEqual((checked['changed'], checked['errors'], checked['applied']), (1, 0, False))
        self.assertEqual(checked['rows'][0]['changes']['maximum_size'], {'from': None, 'to': 8})
        self.assertEqual(Fish.get_by_id(self.unknown.id).cross_species_temperament, 'unknown')
        applied = self.upload(text).get_json()
        self.assertTrue(applied['applied'])
        self.assertEqual(Fish.get_by_id(self.unknown.id).size_max, 8)
        self.assertEqual([event['action'] for event in self.events()], ['fish.import', 'fish.update'])
        self.assertEqual(self.events()[1]['details']['via'], 'import')

    def test_one_bad_row_changes_nothing(self):
        text = ('id,common_name,minimum_ph\n'
                '{},Renamed,\n'
                '{},Also renamed,6.5\n'.format(self.known.id, self.unknown.id))
        result = self.upload(text).get_json()
        self.assertEqual((result['applied'], result['errors']), (False, 1))
        bad = next(row for row in result['rows'] if row['error'])
        self.assertEqual((bad['row'], bad['field']), (2, 'minimum_ph'))
        self.assertNotEqual(Fish.get_by_id(self.unknown.id).common_name, 'Also renamed')
        self.assertEqual(self.events(), [])

    def test_row_errors(self):
        text = 'id,common_name\nabc,x\n999999,x\n{0},x\n{0},y\n{1},x,extra\n'.format(self.known.id, self.unknown.id)
        rows = self.upload(text, dry_run=True).get_json()['rows']
        self.assertEqual([(row['row'], row['field']) for row in rows], [(2, 'id'), (3, 'id'), (4, None), (5, 'id'), (6, None)])
        self.assertIn('more cells', rows[4]['error'])

    def test_file_errors(self):
        for text, status in (('common_name\nx\n', 400), ('id,colour\n1,blue\n', 400), ('id,id\n1,1\n', 400)):
            with self.subTest(text=text):
                self.assertEqual(self.upload(text).status_code, status)
        self.assertEqual(self.upload(b'\xff\xfe'.decode('latin-1')).status_code, 400)

    def test_two_rows_cannot_take_one_name(self):
        text = 'id,scientific_name\n{},Testus duplicatus\n{},Testus duplicatus\n'.format(self.known.id, self.unknown.id)
        self.assertEqual(self.upload(text).status_code, 409)
        self.assertEqual(Fish.select().where(Fish.scientific_name == 'Testus duplicatus').count(), 0)

    def test_only_admins(self):
        self.assertEqual(self.client.get('/fishtank_api/fish/export.csv', headers={'Authorization': 'Bearer ' + self.user}).status_code, 403)
        self.assertEqual(self.upload('id\n1\n', token=self.user).status_code, 403)


class AuditTest(ReviewTestCase):

    def test_fish_changes_are_recorded(self):
        created = self.call('POST', '/fish', NEW_FISH, token=self.admin, expected_status=201).get_json()['fish']
        self.call('PATCH', '/fish/{}'.format(created['id']), {'common_name': 'Renamed', 'family_name': 'Testidae'}, token=self.admin)
        self.call('POST', '/fish/{}/retire'.format(created['id']), token=self.admin)
        self.call('POST', '/fish/{}/restore'.format(created['id']), token=self.admin)
        self.call('DELETE', '/fish/{}'.format(created['id']), token=self.admin)
        events = self.events(fish_id=created['id'])
        self.assertEqual([event['action'] for event in events], ['fish.delete', 'fish.restore', 'fish.retire', 'fish.update', 'fish.create'])
        # unchanged fields are not listed
        self.assertEqual(events[3]['details']['changes'], {'common_name': {'from': 'Test fish', 'to': 'Renamed'}})

    def test_nothing_recorded_when_nothing_changes(self):
        self.call('PATCH', '/fish/{}'.format(self.known.id), {'common_name': self.known.common_name}, token=self.admin)
        self.assertEqual(self.events(), [])

    def test_role_changes_are_recorded(self):
        alice = User.get(User.username == 'alice')
        self.call('PATCH', '/users/{}'.format(alice.id), {'role': 'admin'}, token=self.admin)
        [event] = self.events()
        self.assertEqual((event['action'], event['target_user_id'], event['details']), ('user.role', alice.id,
                                                                                          {'username': 'alice', 'from': 'user', 'to': 'admin'}))

    def test_paging_and_access(self):
        for index in range(5):
            AuditEvent.record(None, 'fish.update', fish_id=1, details={'n': index})
        first = self.call('GET', '/audit?limit=2', token=self.admin).get_json()
        self.assertEqual(([e['details']['n'] for e in first['events']], first['more']), ([4, 3], True))
        rest = self.call('GET', '/audit?limit=10&before={}'.format(first['events'][-1]['id']), token=self.admin).get_json()
        self.assertEqual(([e['details']['n'] for e in rest['events']], rest['more']), ([2, 1, 0], False))
        self.assertIsNone(first['events'][0]['username'])
        self.call('GET', '/audit', token=self.user, expected_status=403)
        self.call('GET', '/audit?limit=x', token=self.admin, expected_status=400)



PICTURE = {'url': 'https://example.org/fish.jpg', 'source_url': 'https://example.org/fish', 'licence': 'CC BY 4.0',
           'source': 'Flickr', 'author': 'Jane Doe'}


class PictureTest(ReviewTestCase):

    def without_picture(self):
        return Fish.select().where(Fish.id.not_in(FishPicture.select(FishPicture.fish))).order_by(Fish.id).first()

    def add(self, fish, payload=None, token=None, expected_status=201):
        return self.call('POST', '/fish/{}/pictures'.format(fish.id), payload or PICTURE, token=token or self.admin,
                         expected_status=expected_status).get_json()

    def test_admin_adds_a_picture_to_a_fish_without_one(self):
        fish = self.without_picture()
        answer = self.add(fish)
        self.assertEqual(answer['picture']['credit'], 'Jane Doe, CC BY 4.0, via Flickr')
        self.assertEqual([p['url'] for p in answer['fish']['pictures']], ['https://example.org/fish.jpg'])
        # everyone sees it first in the catalogue
        shown = self.call('GET', '/fish/{}'.format(fish.id)).get_json()['fish']['pictures']
        self.assertEqual(shown[0]['source'], 'Flickr')
        [event] = self.events(fish_id=fish.id)
        self.assertEqual((event['action'], event['details']['picture']['url']), ('picture.add', 'https://example.org/fish.jpg'))

    def test_a_fish_keeps_its_pictures_in_the_order_they_came(self):
        fish = FishPicture.select().first().fish
        before = [p['id'] for p in self.call('GET', '/fish/{}'.format(fish.id)).get_json()['fish']['pictures']]
        added = self.add(fish)['picture']
        after = [p['id'] for p in self.call('GET', '/fish/{}'.format(fish.id)).get_json()['fish']['pictures']]
        self.assertEqual(after, before + [added['id']])

    def test_invalid_pictures(self):
        fish = self.without_picture()
        cases = [({'url': 'http://example.org/a.jpg'}, 'url'), ({'url': 'https://example.org/a b.jpg'}, 'url'),
                 ({'source_url': None}, 'source_url'), ({'licence': ' '}, 'licence'), ({'source': None}, 'source'),
                 ({'source': 'FishBase'}, 'source'), ({'author': 5}, 'author'), ({'caption': 'x'}, 'caption'),
                 ({'url': 'https://' + 'x' * 1000}, 'url')]
        for changes, field in cases:
            with self.subTest(changes=changes):
                self.assertEqual(self.add(fish, dict(PICTURE, **changes), expected_status=400)['field'], field)
        existing = FishPicture.select().first()
        self.assertEqual(self.add(fish, dict(PICTURE, url=existing.url), expected_status=409)['field'], 'url')
        self.assertFalse(FishPicture.select().where(FishPicture.fish == fish).exists())

    def test_admin_removes_a_picture(self):
        fish = self.without_picture()
        picture = self.add(fish)['picture']
        answer = self.call('DELETE', '/fish/{}/pictures/{}'.format(fish.id, picture['id']), token=self.admin,
                           expected_status=200).get_json()
        self.assertEqual(answer['fish']['pictures'], [])
        self.assertEqual([e['action'] for e in self.events(fish_id=fish.id)], ['picture.remove', 'picture.add'])
        self.call('DELETE', '/fish/{}/pictures/{}'.format(fish.id, picture['id']), token=self.admin, expected_status=404)
        # a picture is only removed through its own fish
        other = FishPicture.select().first()
        self.call('DELETE', '/fish/{}/pictures/{}'.format(fish.id, other.id), token=self.admin, expected_status=404)

    def test_only_admins(self):
        fish = self.without_picture()
        self.add(fish, token=self.user, expected_status=403)
        self.call('POST', '/fish/{}/pictures'.format(fish.id), PICTURE, expected_status=401)
        picture = FishPicture.select().first()
        self.call('DELETE', '/fish/{}/pictures/{}'.format(picture.fish_id, picture.id), token=self.user, expected_status=403)


if __name__ == '__main__':
    unittest.main()
