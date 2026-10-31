import os
import shutil
import sqlite3
import tempfile
import unittest
from unittest import mock

from fishtank import fishbase_import
from tests.test_migrations import LEGACY_SCHEMA, LEGACY_ROWS

# Tests for fishbase_import.py, on a small legacy database and hand written FishBase rows, no parquet files needed
# Run from the project root: python -m unittest tests.test_import -v

# our fish besides LEGACY_ROWS: one FishBase renamed, one whose old name is a synonym of two FishBase species,
# and two whose old names are synonyms of the same FishBase species
EXTRA_LEGACY_NAMES = ['Archocentrus nigrofasciatus', 'Puntius ambiguus', 'Old name a', 'Old name b']


def species(code, name, fresh=1, aquarium='commercial', family_code=1, common_name='Common'):
    genus, epithet = name.split(' ', 1)
    return {'SpecCode': code, 'Genus': genus, 'Species': epithet, 'FBname': common_name, 'FamCode': family_code,
            'Fresh': fresh, 'Aquarium': aquarium}


def stock(code, temperature=(22.0, 26.0), ph=(6.5, 7.5), hardness=(5.0, 15.0), level='species in general', stock_code=None):
    return {'SpecCode': code, 'StockCode': code if stock_code is None else stock_code, 'Level': level,
            'TempMin': temperature[0], 'TempMax': temperature[1], 'pHMin': ph[0], 'pHMax': ph[1],
            'dHMin': hardness[0], 'dHMax': hardness[1]}


def synonym(code, name):
    genus, epithet = name.split(' ', 1)
    return {'SpecCode': code, 'SynGenus': genus, 'SynSpecies': epithet}


def picture(code, name, copyright_text='free use', picture_type='photo', life_stage='unsexed', type_specimen=None,
            public_domain=False, author='Ott, G.', preferred=False, rank=None):
    return {'SpecCode': float(code), 'PicName': name, 'PictureType': picture_type, 'PicType': type_specimen,
            'LifeStage': life_stage, 'Copyright': copyright_text, 'PublicDomain': public_domain, 'AuthName': author,
            'PicPreferred': preferred, 'Rank': rank}


def fishbase_tables():
    return {
        'species': [
            species(100, 'Ameca splendens', common_name='Butterfly splitfin'),
            species(101, 'Aphyocharax erythrurus', aquarium='highly commercial', family_code=2, common_name=None),
            species(102, 'Marinus fishus', fresh=0),
            species(103, 'Rarely kept', aquarium='never/rarely'),
            species(104, 'Missing hardness'),
            species(105, 'Typo ph'),
            species(106, 'Unknown family', family_code=999),
            species(107, 'Corydoras adolfoi'),
            species(108, 'Amatitlania nigrofasciata'),
            species(109, 'Pethia one'),
            species(110, 'Pethia two'),
            species(111, 'Claimed twice'),
        ],
        'stocks': [
            stock(100, temperature=(22.5, 27.5), ph=(6.0500001907348633, 8.0), hardness=(4.2, 19.8)),
            stock(101, temperature=(10.0, 12.0), level='wild stock/population', stock_code=1),
            stock(101, temperature=(24.0, 28.0), stock_code=2),
            stock(102), stock(103),
            stock(104, hardness=(5.0, None)),
            stock(105, ph=(6.5, 82.0)),
            stock(106), stock(107), stock(108), stock(109), stock(110), stock(111),
        ],
        'synonyms': [
            synonym(108, 'Archocentrus nigrofasciatus'),
            synonym(109, 'Puntius ambiguus'), synonym(110, 'Puntius ambiguus'),
            synonym(111, 'Old name a'), synonym(111, 'Old name b'),
        ],
        'families': [{'FamCode': 1, 'Family': 'Goodeidae'}, {'FamCode': 2, 'Family': 'Characidae'}],
        'picturesmain': [
            picture(100, 'Amspl_u0.jpg', 'non-commercial use', preferred=True, rank=1),
            picture(100, 'Amspl_u1.jpg', ' Free  Use ', picture_type='aquarium photo', life_stage='male'),
            picture(100, 'Amspl_u2.jpg', 'permission required'),
            picture(100, 'Amspl_u3.jpg', None, picture_type='public aquarium', public_domain=True),
            picture(100, 'Amspl_u4.jpg', 'non-conmmercial use'),
            picture(100, 'Amspl_u5.gif', picture_type='b/w drawing'),
            picture(100, 'Amspl_j0.jpg', life_stage='juvenile'),
            picture(100, 'Amspl_h0.jpg', type_specimen='holotype'),
            picture(100, 'Amspl_u0.jpg', 'non-commercial use'),
            picture(107, 'Coado_u0.jpg', author=None),
            picture(102, 'Mafis_u0.jpg'),
        ],
    }


class ImportTest(unittest.TestCase):

    def setUp(self):
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory)
        self.source_path = os.path.join(directory, 'legacy.db')
        self.target_path = os.path.join(directory, 'imported.db')
        connection = sqlite3.connect(self.source_path)
        connection.execute(LEGACY_SCHEMA)
        rows = LEGACY_ROWS + [(name,) + LEGACY_ROWS[0][1:] for name in EXTRA_LEGACY_NAMES]
        connection.executemany('INSERT INTO fish VALUES ({})'.format(', '.join(['?'] * len(rows[0]))), rows)
        connection.commit()
        connection.close()
        self.legacy_count = len(rows)

    def run_import(self, tables=None, source_path=None, target_path=None):
        return fishbase_import.import_tables(tables or fishbase_tables(), source_path or self.source_path,
                                             target_path or self.target_path)

    def query(self, sql, parameters=(), path=None):
        connection = sqlite3.connect(path or self.target_path)
        try:
            return connection.execute(sql, parameters).fetchall()
        finally:
            connection.close()

    def fish_by_name(self, path=None):
        connection = sqlite3.connect(path or self.target_path)
        connection.row_factory = sqlite3.Row
        try:
            return {row['scientific_name']: dict(row) for row in connection.execute('SELECT * FROM fish')}
        finally:
            connection.close()

    def test_adds_freshwater_aquarium_species_with_unknown_temperament(self):
        self.run_import()
        fish = self.fish_by_name()
        self.assertEqual(fish['Ameca splendens'], {
            'id': self.legacy_count + 1, 'scientific_name': 'Ameca splendens', 'common_name': 'Butterfly splitfin',
            'family_name': 'Goodeidae', 'size_min': None, 'size_max': None, 'ph_min': 6.05, 'ph_max': 8.0,
            'water_hardness_min': 5, 'water_hardness_max': 19, 'temperature_min': 23, 'temperature_max': 27,
            'reproduce_method': None, 'origin': None, 'in_species_temperament': 'unknown',
            'cross_species_temperament': 'unknown', 'fishtank_position': None, 'fishbase_spec_code': 100,
            'data_source': 'FishBase 25.04', 'retired_at': None})
        self.assertEqual((fish['Aphyocharax erythrurus']['common_name'], fish['Aphyocharax erythrurus']['family_name']),
                         (None, 'Characidae'))

    def test_new_fish_get_the_next_ids_in_scientific_name_order(self):
        self.run_import()
        self.assertEqual(self.query("SELECT id, scientific_name FROM fish WHERE data_source = 'FishBase 25.04' ORDER BY id"),
                         [(self.legacy_count + 1, 'Ameca splendens'), (self.legacy_count + 2, 'Aphyocharax erythrurus')])

    def test_skips_species_that_cannot_be_described_or_are_not_aquarium_fish(self):
        self.run_import()
        fish = self.fish_by_name()
        for name in ('Marinus fishus', 'Rarely kept', 'Missing hardness', 'Typo ph', 'Unknown family'):
            with self.subTest(fish=name):
                self.assertNotIn(name, fish)
        self.assertEqual(len(fish), self.legacy_count + 2)

    def test_recognises_our_fish_by_name_and_by_synonym(self):
        self.run_import()
        fish = self.fish_by_name()
        self.assertEqual(fish['Corydoras adolfoi']['fishbase_spec_code'], 107)
        self.assertEqual(fish['Archocentrus nigrofasciatus']['fishbase_spec_code'], 108)
        self.assertNotIn('Amatitlania nigrofasciata', fish)
        self.assertEqual(fish['Corydoras adolfoi']['data_source'], 'aqua-fish.net')

    def test_ambiguous_matches_are_neither_recorded_nor_imported(self):
        self.run_import()
        fish = self.fish_by_name()
        for name in ('Puntius ambiguus', 'Old name a', 'Old name b'):
            with self.subTest(ours=name):
                self.assertIsNone(fish[name]['fishbase_spec_code'])
        for name in ('Pethia one', 'Pethia two', 'Claimed twice'):
            with self.subTest(fishbase=name):
                self.assertNotIn(name, fish)

    def test_our_fish_keep_their_values(self):
        before = self.fish_by_name(self.source_path)
        self.run_import()
        after = self.fish_by_name()
        for name, row in before.items():
            with self.subTest(fish=name):
                self.assertEqual({column: after[name][column] for column in row}, row)

    def test_prefers_the_stock_for_the_species_in_general(self):
        self.run_import()
        fish = self.fish_by_name()['Aphyocharax erythrurus']
        self.assertEqual((fish['temperature_min'], fish['temperature_max']), (24, 28))

    def test_links_only_reusable_photos_of_adult_fish(self):
        self.run_import()
        pictures = self.query('SELECT f.scientific_name, p.url, p.author, p.licence, p.source_url FROM fish_picture p JOIN fish f ON f.id = p.fish_id')
        images = 'https://www.fishbase.se/images/species/'
        self.assertEqual(sorted(pictures), sorted([
            ('Ameca splendens', images + 'Amspl_u0.jpg', 'Ott, G.', 'non-commercial use', 'https://www.fishbase.se/summary/100'),
            ('Ameca splendens', images + 'Amspl_u1.jpg', 'Ott, G.', 'free use', 'https://www.fishbase.se/summary/100'),
            ('Ameca splendens', images + 'Amspl_u3.jpg', 'Ott, G.', 'public domain', 'https://www.fishbase.se/summary/100'),
            ('Corydoras adolfoi', images + 'Coado_u0.jpg', None, 'free use', 'https://www.fishbase.se/summary/107'),
        ]))

    def test_reports_what_was_added(self):
        self.assertEqual(self.run_import(), {'recorded_codes': 2, 'new_fish': 2, 'new_pictures': 4})

    def test_importing_again_adds_nothing(self):
        self.run_import()
        again_path = self.target_path + '.again'
        self.assertEqual(self.run_import(source_path=self.target_path, target_path=again_path),
                         {'recorded_codes': 0, 'new_fish': 0, 'new_pictures': 0})
        self.assertEqual(self.fish_by_name(again_path), self.fish_by_name())
        self.assertEqual(self.query('SELECT * FROM fish_picture ORDER BY id', path=again_path),
                         self.query('SELECT * FROM fish_picture ORDER BY id'))

    def test_source_is_never_changed(self):
        with open(self.source_path, 'rb') as source_file:
            before = source_file.read()
        self.run_import()
        with open(self.source_path, 'rb') as source_file:
            self.assertEqual(source_file.read(), before)

    def test_failed_import_adds_nothing(self):
        with mock.patch.object(fishbase_import, 'select_pictures', side_effect=RuntimeError('pictures failed')):
            with self.assertRaises(RuntimeError):
                self.run_import()
        self.assertEqual(self.query('SELECT count(*), count(fishbase_spec_code) FROM fish'), [(self.legacy_count, 0)])
        self.assertEqual(self.query('SELECT count(*) FROM fish_picture'), [(0,)])


class WaterParametersTest(unittest.TestCase):

    def test_boundaries(self):
        cases = [
            ('typical', stock(1), (22, 26, 6.5, 7.5, 5, 15)),
            ('ph at both ends of the scale', stock(1, ph=(0.0, 14.0)), (22, 26, 0.0, 14.0, 5, 15)),
            ('ph above 14', stock(1, ph=(6.5, 14.01)), None),
            ('negative ph', stock(1, ph=(-0.1, 7.0)), None),
            ('negative hardness', stock(1, hardness=(-1.0, 10.0)), None),
            ('single value ranges', stock(1, temperature=(24.0, 24.0), ph=(7.0, 7.0), hardness=(8.0, 8.0)), (24, 24, 7.0, 7.0, 8, 8)),
            ('minimum above maximum', stock(1, temperature=(27.0, 26.0)), None),
            ('fractions rounded inwards', stock(1, temperature=(22.1, 26.9), hardness=(4.5, 15.5)), (23, 26, 6.5, 7.5, 5, 15)),
            ('rounding empties the range', stock(1, temperature=(22.4, 22.6)), None),
            ('missing value', stock(1, ph=(None, 7.5)), None),
            ('not a number', stock(1, temperature=(float('nan'), 26.0)), None),
        ]
        for description, row, expected in cases:
            with self.subTest(description):
                self.assertEqual(fishbase_import.water_parameters(row), expected)


class ReusableLicenceTest(unittest.TestCase):

    def test_licences(self):
        cases = [
            ('free use', False, 'free use'),
            ('Non-Commercial  Use', False, 'non-commercial use'),
            (None, True, 'public domain'),
            ('permission required', True, 'public domain'),
            ('permission required', False, None),
            ('non-com0mercial use', False, None),
            (None, False, None),
            ('', False, None),
        ]
        for copyright_text, public_domain, expected in cases:
            with self.subTest(copyright=copyright_text, public_domain=public_domain):
                self.assertEqual(fishbase_import.reusable_licence(copyright_text, public_domain), expected)


if __name__ == '__main__':
    unittest.main()
