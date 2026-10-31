import math
import os
import sqlite3
import sys

from fishtank import migrations

# Adds freshwater aquarium fish from a FishBase release to a copy of the fish database, the source file is never changed
# FishBase data is licensed under CC BY-NC 4.0, see the Acknowledgments in README.md
# The tables are the parquet files of a FishBase release, as published for rfishbase on
# https://huggingface.co/datasets/cboettig/fishbase (data/fb/v25.04/parquet), reading them needs pyarrow
# Usage: python -m fishtank.fishbase_import <folder with the parquet files> data/fish.db data/fish_imported.db
#
# - only species sold in the aquarium trade, living in freshwater, with all six water parameters are added
# - species we already have are recognised by scientific name, also when FishBase lists our name as a synonym
# - FishBase has no temperament, so new fish get an unknown temperament and are kept apart from every other species
# - pictures are linked, not stored, for fish of both sources, only photos of adult fish whose licence allows reuse

FISHBASE_RELEASE = '25.04'
DATA_SOURCE = 'FishBase ' + FISHBASE_RELEASE
PICTURE_URL = 'https://www.fishbase.se/images/species/{}'
SUMMARY_URL = 'https://www.fishbase.se/summary/{}'

AQUARIUM_TRADE = {'commercial', 'highly commercial'}
# photos of whole live fish, drawings, stamps, radiographs and close ups of details are left out
PHOTO_TYPES = {'photo', 'underwater photo', 'aquarium photo', 'public aquarium', "Randall's tank photos"}
ADULT_LIFE_STAGES = {'unsexed', 'male', 'female', 'terminal phase'}
# FishBase: photos and drawings with CC-BY or CC-BY-NC copyrights can be used without further permission
REUSABLE_LICENCES = {'free use', 'non-commercial use'}

TABLE_COLUMNS = {
    'species': ['SpecCode', 'Genus', 'Species', 'FBname', 'FamCode', 'Fresh', 'Aquarium'],
    'stocks': ['SpecCode', 'StockCode', 'Level', 'TempMin', 'TempMax', 'pHMin', 'pHMax', 'dHMin', 'dHMax'],
    'synonyms': ['SpecCode', 'SynGenus', 'SynSpecies'],
    'families': ['FamCode', 'Family'],
    'picturesmain': ['SpecCode', 'PicName', 'PictureType', 'PicType', 'LifeStage', 'Copyright', 'PublicDomain',
                     'AuthName', 'PicPreferred', 'Rank'],
}


def is_missing(value):
    return value is None or (isinstance(value, float) and math.isnan(value))


def scientific_name_of(genus, species):
    if is_missing(genus) or is_missing(species):
        return None
    return '{} {}'.format(genus.strip(), species.strip())


# returns the licence of a picture when it may be reused, None otherwise
# spelling variants such as 'non-conmmercial use' are not trusted, those pictures are left out
def reusable_licence(copyright_text, public_domain):
    if public_domain is True:
        return 'public domain'
    if is_missing(copyright_text):
        return None
    licence = ' '.join(copyright_text.lower().split())
    if licence in REUSABLE_LICENCES:
        return licence
    return None


# returns (temperature_min, temperature_max, ph_min, ph_max, water_hardness_min, water_hardness_max) or None
# our temperature and hardness are whole numbers, fractions are rounded inwards so a range never grows
# FishBase keeps ph as a 32 bit float (4.9 reads as 4.900000095), two decimals remove that noise
def water_parameters(stock):
    values = [stock[key] for key in ('TempMin', 'TempMax', 'pHMin', 'pHMax', 'dHMin', 'dHMax')]
    if any(is_missing(value) for value in values):
        return None
    temperature_min, temperature_max = int(math.ceil(values[0])), int(math.floor(values[1]))
    ph_min, ph_max = round(float(values[2]), 2), round(float(values[3]), 2)
    water_hardness_min, water_hardness_max = int(math.ceil(values[4])), int(math.floor(values[5]))
    if temperature_min > temperature_max or ph_min > ph_max or water_hardness_min > water_hardness_max:
        return None
    if ph_min < 0 or ph_max > 14 or water_hardness_min < 0:
        return None
    return temperature_min, temperature_max, ph_min, ph_max, water_hardness_min, water_hardness_max


# FishBase may describe a species in several stocks, the stock for the species in general comes first
def choose_water_parameters(stocks):
    ordered = sorted(stocks, key=lambda stock: (str(stock['Level']).lower() != 'species in general',
                                                0 if is_missing(stock['StockCode']) else stock['StockCode']))
    for stock in ordered:
        parameters = water_parameters(stock)
        if parameters is not None:
            return parameters
    return None


# Works out which FishBase species we already have
# Returns the species codes to record on our fish, by scientific name, and every code that belongs to one of our fish
# A synonym that points to more than one species, or a code claimed by more than one of our fish, is not recorded,
# but its codes still count as ours, so none of them is added again
def match_existing_fish(existing_names, species_rows, synonym_rows):
    code_by_name = {}
    for row in species_rows:
        name = scientific_name_of(row['Genus'], row['Species'])
        if name is not None:
            code_by_name[name] = row['SpecCode']
    codes_by_synonym = {}
    for row in synonym_rows:
        name = scientific_name_of(row['SynGenus'], row['SynSpecies'])
        if name is not None and not is_missing(row['SpecCode']):
            codes_by_synonym.setdefault(name, set()).add(int(row['SpecCode']))

    known_codes = set()
    candidate_code_by_name = {}
    for name in existing_names:
        if name in code_by_name:
            codes = {code_by_name[name]}
        else:
            codes = codes_by_synonym.get(name, set())
        known_codes |= codes
        if len(codes) == 1:
            candidate_code_by_name[name] = next(iter(codes))

    claims = {}
    for code in candidate_code_by_name.values():
        claims[code] = claims.get(code, 0) + 1
    code_to_record = {name: code for name, code in candidate_code_by_name.items() if claims[code] == 1}
    return code_to_record, known_codes


# Returns the new fish, in scientific name order so the same release always gets the same ids
def select_new_fish(species_rows, stock_rows, family_rows, existing_names, known_codes):
    stocks_by_code = {}
    for stock in stock_rows:
        stocks_by_code.setdefault(stock['SpecCode'], []).append(stock)
    family_by_code = {row['FamCode']: row['Family'] for row in family_rows}

    new_fish = []
    for row in species_rows:
        name = scientific_name_of(row['Genus'], row['Species'])
        if name is None or name in existing_names or row['SpecCode'] in known_codes:
            continue
        if not row['Fresh'] or row['Aquarium'] not in AQUARIUM_TRADE:
            continue
        family_name = family_by_code.get(row['FamCode'])
        parameters = choose_water_parameters(stocks_by_code.get(row['SpecCode'], []))
        if is_missing(family_name) or parameters is None:
            continue
        temperature_min, temperature_max, ph_min, ph_max, water_hardness_min, water_hardness_max = parameters
        new_fish.append({
            'scientific_name': name,
            'common_name': None if is_missing(row['FBname']) else row['FBname'],
            'family_name': family_name,
            'ph_min': ph_min,
            'ph_max': ph_max,
            'water_hardness_min': water_hardness_min,
            'water_hardness_max': water_hardness_max,
            'temperature_min': temperature_min,
            'temperature_max': temperature_max,
            'in_species_temperament': 'unknown',
            'cross_species_temperament': 'unknown',
            'fishbase_spec_code': int(row['SpecCode']),
            'data_source': DATA_SOURCE,
        })
    return sorted(new_fish, key=lambda fish: fish['scientific_name'])


# Returns the pictures to link for our fish, preferred pictures first
def select_pictures(picture_rows, fish_id_by_code):
    pictures = []
    seen_urls = set()
    ordered = sorted(picture_rows, key=lambda row: (row['PicPreferred'] is not True,
                                                    99 if is_missing(row['Rank']) else row['Rank'], str(row['PicName'])))
    for row in ordered:
        fish_id = fish_id_by_code.get(row['SpecCode'])
        licence = reusable_licence(row['Copyright'], row['PublicDomain'])
        if fish_id is None or licence is None or is_missing(row['PicName']):
            continue
        if row['PictureType'] not in PHOTO_TYPES or row['LifeStage'] not in ADULT_LIFE_STAGES or not is_missing(row['PicType']):
            continue
        url = PICTURE_URL.format(row['PicName'].strip())
        if url in seen_urls:
            continue
        seen_urls.add(url)
        pictures.append({
            'fish_id': fish_id,
            'url': url,
            'author': None if is_missing(row['AuthName']) else row['AuthName'].strip(),
            'licence': licence,
            'source_url': SUMMARY_URL.format(int(row['SpecCode'])),
        })
    return pictures


def read_fishbase_tables(directory):
    import pyarrow.parquet
    return {name: pyarrow.parquet.read_table(os.path.join(directory, name + '.parquet'), columns=columns).to_pylist()
            for name, columns in TABLE_COLUMNS.items()}


# Copies the source to the target at the latest schema version, then adds the fish and pictures in one transaction
# Running it again on an imported database adds nothing
def import_tables(tables, source_path, target_path):
    migrations.migrate(source_path, target_path)
    connection = sqlite3.connect(target_path, isolation_level=None)
    try:
        connection.execute('BEGIN')
        try:
            existing_names = {row[0] for row in connection.execute('SELECT scientific_name FROM fish')}
            code_to_record, known_codes = match_existing_fish(existing_names, tables['species'], tables['synonyms'])
            recorded = 0
            for name, code in sorted(code_to_record.items()):
                recorded += connection.execute('UPDATE fish SET fishbase_spec_code = ? WHERE scientific_name = ? AND fishbase_spec_code IS NULL',
                                               (code, name)).rowcount

            new_fish = select_new_fish(tables['species'], tables['stocks'], tables['families'], existing_names, known_codes)
            for fish in new_fish:
                columns = sorted(fish)
                connection.execute('INSERT INTO fish ({}) VALUES ({})'.format(', '.join(columns), ', '.join(['?'] * len(columns))),
                                   [fish[column] for column in columns])

            fish_id_by_code = dict(connection.execute('SELECT fishbase_spec_code, id FROM fish WHERE fishbase_spec_code IS NOT NULL'))
            added_pictures = 0
            for picture in select_pictures(tables['picturesmain'], fish_id_by_code):
                added_pictures += connection.execute('INSERT OR IGNORE INTO fish_picture (fish_id, url, author, licence, source_url) VALUES (?, ?, ?, ?, ?)',
                                                     (picture['fish_id'], picture['url'], picture['author'], picture['licence'], picture['source_url'])).rowcount
            connection.execute('COMMIT')
        except Exception:
            connection.execute('ROLLBACK')
            raise
    finally:
        connection.close()
    return {'recorded_codes': recorded, 'new_fish': len(new_fish), 'new_pictures': added_pictures}


if __name__ == '__main__':
    if len(sys.argv) != 4:
        print('Usage: python -m fishtank.fishbase_import <folder with the parquet files> <source database> <target database>')
        sys.exit(1)
    print(import_tables(read_fishbase_tables(sys.argv[1]), sys.argv[2], sys.argv[3]))
