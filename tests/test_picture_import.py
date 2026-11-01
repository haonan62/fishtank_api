import os
import shutil
import sqlite3
import tempfile
import unittest
from unittest import mock

from fishtank import migrations, picture_import
from fishtank.db import SEED_DATABASE
from fishtank.models.fish import FishPicture

# Tests for fishtank/picture_import.py, without the network: the lookups are replaced by fixed answers
# Run from the project root: python -m unittest tests.test_picture_import -v


def picture(url, source='Wikimedia Commons', licence='CC BY-SA 4.0', author='Jane Doe'):
    return {'url': url, 'source_url': url + '/page', 'licence': licence, 'author': author, 'source': source}


class LicenceTest(unittest.TestCase):

    def test_commons_licences(self):
        for licence in ('CC BY-SA 3.0', 'CC BY 4.0', 'CC BY 2.0 de', 'CC0', 'Public domain', 'GFDL 1.2', 'No restrictions'):
            with self.subTest(licence=licence):
                self.assertTrue(picture_import.reusable_commons_licence(licence))
        for licence in ('Fair use', 'CC BY-NC 4.0', 'All rights reserved', None):
            with self.subTest(licence=licence):
                self.assertFalse(picture_import.reusable_commons_licence(licence))

    def test_creative_commons_urls(self):
        cases = {
            'http://creativecommons.org/licenses/by-nc/4.0/legalcode': 'CC BY-NC 4.0',
            'https://creativecommons.org/licenses/by-sa/3.0/': 'CC BY-SA 3.0',
            'https://creativecommons.org/publicdomain/zero/1.0/': 'CC0',
            'http://creativecommons.org/publicdomain/mark/1.0/': 'Public domain',
            'https://creativecommons.org/licenses/sampling/1.0/': None,
            'All rights reserved': None,
            None: None,
        }
        for url, licence in cases.items():
            with self.subTest(url=url):
                self.assertEqual(picture_import.creative_commons_licence(url), licence)

    def test_inaturalist_photos_need_a_licence(self):
        photo = {'id': 7, 'license_code': 'cc-by-nc', 'medium_url': 'https://example.org/7/medium.jpg',
                 'attribution': '(c) Jane Doe, some rights reserved (CC BY-NC)'}
        self.assertEqual(picture_import.inaturalist_photo(photo), {
            'url': 'https://example.org/7/medium.jpg', 'source_url': 'https://www.inaturalist.org/photos/7',
            'licence': 'CC BY-NC', 'author': 'Jane Doe', 'source': 'iNaturalist'})
        self.assertIsNone(picture_import.inaturalist_photo(dict(photo, license_code=None)))
        square = dict(photo, medium_url=None, url='https://example.org/7/square.jpg')
        self.assertEqual(picture_import.inaturalist_photo(square)['url'], 'https://example.org/7/medium.jpg')

    def test_commons_addresses_lose_their_tracking(self):
        self.assertEqual(picture_import.without_query('https://thumb.wikimedia.org/a/960px-A.jpg?utm_source=commons.wikimedia.org'),
                         'https://thumb.wikimedia.org/a/960px-A.jpg')
        self.assertEqual(picture_import.without_query('https://upload.wikimedia.org/a.jpg'), 'https://upload.wikimedia.org/a.jpg')

    def test_authors_and_file_names(self):
        self.assertEqual(picture_import.inaturalist_author('Jane Doe, no rights reserved (CC0)'), 'Jane Doe')
        self.assertEqual(picture_import.plain_text('<a href="x">Jane</a> &amp; Joe'), 'Jane & Joe')
        self.assertEqual(picture_import.commons_file_name('http://commons.wikimedia.org/wiki/Special:FilePath/Neon%20Tetra_1.jpg'),
                         'Neon Tetra 1.jpg')


class FetchTest(unittest.TestCase):

    def test_order_of_sources(self):
        names = ['Alpha', 'Beta', 'Gamma', 'Delta']
        commons = {'a.jpg': picture('https://commons/a'), 'a2.jpg': None}
        with mock.patch.object(picture_import, 'fish_without_pictures', return_value=names), \
                mock.patch.object(picture_import, 'wikidata_images', return_value={'Alpha': ['a.jpg', 'a2.jpg'], 'Beta': ['a2.jpg']}), \
                mock.patch.object(picture_import, 'commons_pictures', return_value=commons), \
                mock.patch.object(picture_import, 'fallback_pictures', side_effect=lambda name: {
                    'Beta': [picture('https://inat/b', 'iNaturalist')], 'Gamma': [picture('https://broken/g', 'GBIF')]}.get(name, [])), \
                mock.patch.object(picture_import, 'loads_as_image', side_effect=lambda url: 'broken' not in url), \
                mock.patch('sys.stderr'):
            found = picture_import.fetch('unused.db')
        # Alpha from Commons (its unlicensed image left out), Beta from the fallback,
        # Gamma's picture does not load, Delta has none
        self.assertEqual({name: [p['url'] for p in pictures] for name, pictures in found.items()},
                         {'Alpha': ['https://commons/a'], 'Beta': ['https://inat/b']})


class FallbackTest(unittest.TestCase):

    def run_fallbacks(self, inaturalist=None, gbif=(None, None), gbif_picture=None, commons=None):
        calls = []
        def record(name, answer):
            def call(argument):
                calls.append((name, argument))
                return answer(argument) if callable(answer) else answer
            return call
        with mock.patch.object(picture_import, 'inaturalist_picture', side_effect=record('inaturalist', inaturalist)), \
                mock.patch.object(picture_import, 'gbif_species', side_effect=record('gbif_species', gbif)), \
                mock.patch.object(picture_import, 'gbif_picture', side_effect=record('gbif_picture', gbif_picture)), \
                mock.patch.object(picture_import, 'commons_search_picture', side_effect=record('commons', commons)), \
                mock.patch('time.sleep'):
            return picture_import.fallback_pictures('Puntius tetrazona'), calls

    def test_inaturalist_first(self):
        found, calls = self.run_fallbacks(inaturalist=picture('https://inat/1', 'iNaturalist'))
        self.assertEqual(([p['url'] for p in found], calls), (['https://inat/1'], [('inaturalist', ['Puntius tetrazona'])]))

    def test_renamed_species_is_looked_up_under_its_accepted_name(self):
        found, calls = self.run_fallbacks(inaturalist=lambda names: picture('https://inat/2') if names == ['Puntigrus tetrazona'] else None,
                                          gbif=(8214163, 'Puntigrus tetrazona'))
        self.assertEqual(found[0]['url'], 'https://inat/2')
        self.assertEqual([call[0] for call in calls], ['inaturalist', 'gbif_species', 'inaturalist'])

    def test_then_gbif_then_commons_search(self):
        found, calls = self.run_fallbacks(gbif=(8214163, 'Puntigrus tetrazona'), gbif_picture=picture('https://gbif/3', 'GBIF'))
        self.assertEqual(found[0]['url'], 'https://gbif/3')
        found, calls = self.run_fallbacks(gbif=(8214163, 'Puntigrus tetrazona'), commons=lambda name: picture('https://commons/4') if name == 'Puntigrus tetrazona' else None)
        self.assertEqual(found[0]['url'], 'https://commons/4')
        self.assertEqual([call for call in calls if call[0] == 'commons'], [('commons', 'Puntius tetrazona'), ('commons', 'Puntigrus tetrazona')])

    def test_nothing_found(self):
        self.assertEqual(self.run_fallbacks()[0], [])

    def test_commons_search_keeps_files_named_after_the_species(self):
        search = {'query': {'search': [{'title': 'File:Map of rivers.png'}, {'title': 'File:Puntius tetrazona male.JPG'},
                                       {'title': 'File:Puntius tetrazona.svg'}]}}
        with mock.patch.object(picture_import, 'get_json', return_value=search), \
                mock.patch.object(picture_import, 'commons_pictures', return_value={'Puntius tetrazona male.JPG': picture('https://commons/5')}) as lookup, \
                mock.patch('time.sleep'):
            self.assertEqual(picture_import.commons_search_picture('Puntius tetrazona')['url'], 'https://commons/5')
        lookup.assert_called_once_with(['Puntius tetrazona male.JPG'])


class InaturalistTest(unittest.TestCase):

    def test_species_found_under_an_older_name(self):
        photo = {'id': 9, 'license_code': 'cc-by-nc', 'medium_url': 'https://example.org/9/medium.jpg', 'attribution': '(c) Ann'}
        answers = [{'results': [{'id': 1, 'name': 'Corydoras arcuatusii'},
                                {'id': 2, 'name': 'Brochis arcuata', 'matched_term': 'Corydoras arcuatus', 'default_photo': photo}]}]
        with mock.patch.object(picture_import, 'get_json', side_effect=answers), mock.patch('time.sleep'):
            found = picture_import.inaturalist_picture(['Corydoras arcuatus'])
        self.assertEqual(found['url'], 'https://example.org/9/medium.jpg')

    def test_a_similar_name_is_not_enough(self):
        answers = [{'results': [{'id': 1, 'name': 'Corydoras arcuatusii', 'matched_term': 'Corydoras arcuatusii'}]}]
        with mock.patch.object(picture_import, 'get_json', side_effect=answers), mock.patch('time.sleep'):
            self.assertIsNone(picture_import.inaturalist_picture(['Corydoras arcuatus']))


class ApplyTest(unittest.TestCase):

    def setUp(self):
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory)
        self.target = os.path.join(directory, 'with_pictures.db')
        connection = sqlite3.connect(SEED_DATABASE)
        self.without = connection.execute('SELECT scientific_name FROM fish WHERE id NOT IN (SELECT fish_id FROM fish_picture) '
                                          'ORDER BY id LIMIT 2').fetchall()
        self.with_picture = connection.execute('SELECT f.scientific_name, count(*) FROM fish f JOIN fish_picture p '
                                               'ON p.fish_id = f.id GROUP BY f.id LIMIT 1').fetchone()
        self.missing_before = connection.execute('SELECT count(*) FROM fish WHERE id NOT IN (SELECT fish_id FROM fish_picture)').fetchone()[0]
        connection.close()

    def read(self, sql, parameters=()):
        connection = sqlite3.connect(self.target)
        try:
            return connection.execute(sql, parameters).fetchall()
        finally:
            connection.close()

    def test_adds_pictures_to_fish_without_any(self):
        first, second = self.without[0][0], self.without[1][0]
        lookup = {first: [picture('https://example.org/1.jpg'), picture('https://example.org/2.jpg', 'iNaturalist', 'CC BY-NC')],
                  second: [picture('https://example.org/3.jpg', 'GBIF', 'CC BY 4.0', None)],
                  # a fish that has pictures keeps only those, an unknown name is passed over
                  self.with_picture[0]: [picture('https://example.org/4.jpg')], 'Nonexistus nemo': [picture('https://example.org/5.jpg')]}
        added, missing = picture_import.apply(lookup, SEED_DATABASE, self.target)
        self.assertEqual((added, missing), (3, self.missing_before - 2))
        rows = self.read('SELECT f.scientific_name, p.url, p.author, p.licence, p.source FROM fish_picture p JOIN fish f '
                         'ON f.id = p.fish_id WHERE p.url LIKE ? ORDER BY p.url', ('https://example.org/%',))
        self.assertEqual(rows, [(first, 'https://example.org/1.jpg', 'Jane Doe', 'CC BY-SA 4.0', 'Wikimedia Commons'),
                                (first, 'https://example.org/2.jpg', 'Jane Doe', 'CC BY-NC', 'iNaturalist'),
                                (second, 'https://example.org/3.jpg', None, 'CC BY 4.0', 'GBIF')])
        self.assertEqual(self.read('PRAGMA user_version'), [(migrations.LATEST_VERSION,)])

    def test_a_url_is_only_used_once(self):
        first, second = self.without[0][0], self.without[1][0]
        added, _ = picture_import.apply({first: [picture('https://example.org/same.jpg')],
                                         second: [picture('https://example.org/same.jpg')]}, SEED_DATABASE, self.target)
        self.assertEqual(added, 1)

    def test_source_is_never_changed(self):
        with open(SEED_DATABASE, 'rb') as seed:
            before = seed.read()
        picture_import.apply({self.without[0][0]: [picture('https://example.org/1.jpg')]}, SEED_DATABASE, self.target)
        with open(SEED_DATABASE, 'rb') as seed:
            self.assertEqual(seed.read(), before)


class CreditTest(unittest.TestCase):

    def test_credit_follows_the_source(self):
        self.assertEqual(FishPicture(author='Jane', source='FishBase', licence='free use').credit(), 'Jane, from FishBase')
        self.assertEqual(FishPicture(author=None, source='FishBase', licence='free use').credit(), 'from FishBase')
        self.assertEqual(FishPicture(author='Jane', source='Wikimedia Commons', licence='CC BY-SA 3.0').credit(),
                         'Jane, CC BY-SA 3.0, via Wikimedia Commons')
        self.assertEqual(FishPicture(author=None, source='GBIF', licence='CC BY 4.0').credit(), 'Unknown author, CC BY 4.0, via GBIF')


if __name__ == '__main__':
    unittest.main()
