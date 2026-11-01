import html
import json
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request

from fishtank import migrations

# Finds pictures for the fish that have none and adds them to a copy of the fish database, the source file is never changed
# Two steps, so the lookup can be checked before anything is written:
#   python -m fishtank.picture_import fetch data/fish.db pictures.json
#   python -m fishtank.picture_import apply pictures.json data/fish.db data/fish_with_pictures.db
#
# A fish gets the first of these that has a picture whose licence allows showing it with a credit:
# 1. the images its Wikidata species item (matched by scientific name, P225) names as its image (P18),
#    hosted by Wikimedia Commons, with author and licence from Commons
# 2. its iNaturalist species: the default photo, another photo of the species, or a research grade observation's photo
#    a renamed species is found under the name GBIF accepts for it
# 3. images GBIF has of the species or of its occurrences, from museums and other collections
# 4. a photo on Wikimedia Commons whose file name has the scientific name in it, for species no item points to
# Pictures are linked, not stored, every one keeps its author, licence and the page it comes from,
# and is only kept when it loads as an image

WIKIDATA_SPARQL = 'https://query.wikidata.org/sparql'
COMMONS_API = 'https://commons.wikimedia.org/w/api.php'
INATURALIST_TAXA = 'https://api.inaturalist.org/v1/taxa'
INATURALIST_OBSERVATIONS = 'https://api.inaturalist.org/v1/observations'
INATURALIST_PHOTO_PAGE = 'https://www.inaturalist.org/photos/{}'
GBIF_MATCH = 'https://api.gbif.org/v1/species/match'
GBIF_SPECIES = 'https://api.gbif.org/v1/species/{}'
GBIF_OCCURRENCES = 'https://api.gbif.org/v1/occurrence/search'
GBIF_OCCURRENCE_PAGE = 'https://www.gbif.org/occurrence/{}'
USER_AGENT = 'FishtankPictureImport/1.0 (https://github.com/haonan62/fishtank_api)'
THUMBNAIL_WIDTH = 800
# the most images of one fish taken from Wikidata
MAX_PICTURES_PER_FISH = 3

SOURCE_COMMONS = 'Wikimedia Commons'
SOURCE_INATURALIST = 'iNaturalist'
SOURCE_GBIF = 'GBIF'

# licences on Commons that allow showing a picture with a credit and a link to its page
REUSABLE_COMMONS_PATTERNS = [r'^CC0', r'^Public domain', r'^PD', r'^CC BY(-SA)? ', r'^CC BY(-SA)?$', r'^GFDL',
                             r'^No restrictions$', r'^Copyrighted free use$', r'^Attribution$']
# iNaturalist licence codes and how they are written, a photo without a code is all rights reserved and left out
INATURALIST_LICENCES = {
    'cc0': 'CC0', 'pd': 'Public domain', 'cc-by': 'CC BY', 'cc-by-sa': 'CC BY-SA', 'cc-by-nc': 'CC BY-NC',
    'cc-by-nc-sa': 'CC BY-NC-SA', 'cc-by-nd': 'CC BY-ND', 'cc-by-nc-nd': 'CC BY-NC-ND',
}
INATURALIST_LICENCE_FILTER = ','.join(code for code in INATURALIST_LICENCES if code != 'pd')


# 'http://creativecommons.org/licenses/by-nc/4.0/legalcode' -> 'CC BY-NC 4.0', None for anything else
def creative_commons_licence(url):
    if not url:
        return None
    if re.search(r'creativecommons\.org/publicdomain/(zero|mark)', url):
        return 'CC0' if 'zero' in url else 'Public domain'
    match = re.search(r'creativecommons\.org/licenses/([a-z-]+)/([0-9.]+)', url)
    if not match or match.group(1) not in ('by', 'by-sa', 'by-nc', 'by-nc-sa', 'by-nd', 'by-nc-nd'):
        return None
    return 'CC {} {}'.format(match.group(1).upper(), match.group(2))


def reusable_commons_licence(licence):
    return licence is not None and any(re.match(pattern, licence) for pattern in REUSABLE_COMMONS_PATTERNS)


# 'http://commons.wikimedia.org/wiki/Special:FilePath/Neon%20Tetra.jpg' -> 'Neon Tetra.jpg'
def commons_file_name(url):
    return urllib.parse.unquote(url.rsplit('/', 1)[1]).replace('_', ' ')


# Commons adds tracking parameters (utm_source...) to its thumbnail addresses, the image loads without them
def without_query(url):
    return url.split('?', 1)[0] if url else url


def plain_text(value):
    if value is None:
        return None
    text = ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', value)).split())
    return text or None


# '(c) Jane Doe, some rights reserved (CC BY-NC)' -> 'Jane Doe', the author as iNaturalist credits them
def inaturalist_author(attribution):
    if not attribution:
        return None
    match = re.match(r'^\s*(?:\(c\)|©)?\s*(.*?),\s*(?:some|all|no) rights reserved', attribution, re.IGNORECASE)
    author = match.group(1) if match else attribution
    return author.strip() or None


def get_json(url, params):
    request = urllib.request.Request(url + '?' + urllib.parse.urlencode(params),
                                     headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def fish_without_pictures(database_path):
    connection = sqlite3.connect(database_path)
    try:
        return [row[0] for row in connection.execute(
            'SELECT scientific_name FROM fish WHERE id NOT IN (SELECT fish_id FROM fish_picture) ORDER BY scientific_name')]
    finally:
        connection.close()


# scientific name -> Commons file names of its Wikidata image (P18)
def wikidata_images(names, batch_size=150):
    images = {}
    for start in range(0, len(names), batch_size):
        values = ' '.join(json.dumps(name) for name in names[start:start + batch_size])
        query = 'SELECT ?name ?image WHERE { VALUES ?name { %s } ?item wdt:P225 ?name . ?item wdt:P18 ?image }' % values
        for row in get_json(WIKIDATA_SPARQL, {'query': query, 'format': 'json'})['results']['bindings']:
            files = images.setdefault(row['name']['value'], [])
            name = commons_file_name(row['image']['value'])
            if name not in files:
                files.append(name)
        time.sleep(1)
    return images


# Commons file name -> picture, or None when its licence does not allow it
def commons_pictures(file_names, batch_size=40):
    pictures = {}
    for start in range(0, len(file_names), batch_size):
        params = {'action': 'query', 'format': 'json', 'formatversion': 2, 'prop': 'imageinfo',
                  'titles': '|'.join('File:' + name for name in file_names[start:start + batch_size]),
                  'iiprop': 'url|extmetadata', 'iiurlwidth': THUMBNAIL_WIDTH,
                  'iiextmetadatafilter': 'LicenseShortName|Artist'}
        for page in get_json(COMMONS_API, params)['query']['pages']:
            if 'imageinfo' not in page:
                continue
            info = page['imageinfo'][0]
            metadata = info.get('extmetadata', {})
            licence = plain_text(metadata.get('LicenseShortName', {}).get('value'))
            pictures[page['title'][len('File:'):]] = {
                'url': without_query(info['thumburl']), 'source_url': info['descriptionurl'], 'licence': licence,
                'author': plain_text(metadata.get('Artist', {}).get('value')), 'source': SOURCE_COMMONS,
            } if reusable_commons_licence(licence) and info.get('thumburl') else None
        time.sleep(0.5)
    return pictures


def inaturalist_photo(photo):
    licence = photo and INATURALIST_LICENCES.get(photo.get('license_code'))
    url = photo and (photo.get('medium_url') or (photo.get('url') or '').replace('/square.', '/medium.'))
    if not licence or not url:
        return None
    return {'url': url, 'source_url': INATURALIST_PHOTO_PAGE.format(photo['id']), 'licence': licence,
            'author': inaturalist_author(photo.get('attribution')), 'source': SOURCE_INATURALIST}


# A licensed photo of the iNaturalist species with exactly one of these names, as its name or as an older name of it
# (most Corydoras moved to Hoplisoma, Brochis and others in 2024): its default photo, one of its other photos,
# or the photo of a research grade observation
def inaturalist_picture(names):
    for name in names:
        taxa = get_json(INATURALIST_TAXA, {'q': name, 'rank': 'species', 'per_page': 5})['results']
        time.sleep(1)
        taxon = next((entry for entry in taxa if entry.get('name') == name), None) or \
            next((entry for entry in taxa if (entry.get('matched_term') or '').lower() == name.lower()), None)
        if taxon is None:
            continue
        picture = inaturalist_photo(taxon.get('default_photo'))
        if picture:
            return picture
        details = get_json(INATURALIST_TAXA + '/{}'.format(taxon['id']), {})['results']
        time.sleep(1)
        for taxon_photo in (details[0].get('taxon_photos') or []) if details else []:
            picture = inaturalist_photo(taxon_photo.get('photo'))
            if picture:
                return picture
        observations = get_json(INATURALIST_OBSERVATIONS, {
            'taxon_id': taxon['id'], 'photo_license': INATURALIST_LICENCE_FILTER, 'quality_grade': 'research',
            'photos': 'true', 'order_by': 'votes', 'per_page': 3})['results']
        time.sleep(1)
        for observation in observations:
            for photo in observation.get('photos') or []:
                picture = inaturalist_photo(photo)
                if picture:
                    return picture
    return None


# GBIF's species key for the name, and the name it accepts for the species when ours is an old one
def gbif_species(name):
    match = get_json(GBIF_MATCH, {'name': name, 'kingdom': 'Animalia', 'strict': 'true'})
    if match.get('matchType') not in ('EXACT', 'FUZZY') or 'usageKey' not in match:
        return None, None
    key = match.get('acceptedUsageKey') or match['usageKey']
    accepted = match.get('canonicalName')
    if match.get('acceptedUsageKey'):
        accepted = get_json(GBIF_SPECIES.format(key), {}).get('canonicalName')
    return key, accepted


# a licensed image GBIF has of the species, from an occurrence (a specimen or an observation) with its page
def gbif_picture(species_key):
    occurrences = get_json(GBIF_OCCURRENCES, {'taxonKey': species_key, 'mediaType': 'StillImage', 'limit': 20})['results']
    for occurrence in occurrences:
        for media in occurrence.get('media') or []:
            licence = creative_commons_licence(media.get('license'))
            if media.get('type') == 'StillImage' and licence and (media.get('identifier') or '').startswith('https://'):
                return {'url': media['identifier'], 'licence': licence, 'source': SOURCE_GBIF,
                        'source_url': media.get('references') or GBIF_OCCURRENCE_PAGE.format(occurrence['key']),
                        'author': plain_text(media.get('creator') or media.get('rightsHolder') or occurrence.get('recordedBy'))}
    return None


# A Commons file whose name has the scientific name in it, the search also finds files that only mention it
def commons_search_picture(name):
    answer = get_json(COMMONS_API, {'action': 'query', 'format': 'json', 'formatversion': 2, 'list': 'search',
                                    'srnamespace': 6, 'srlimit': 20, 'srsearch': '"{}"'.format(name)})
    time.sleep(0.5)
    files = [hit['title'][len('File:'):] for hit in answer['query']['search']
             if name.lower() in hit['title'].lower() and re.search(r'\.(jpe?g|png)$', hit['title'], re.IGNORECASE)]
    if not files:
        return None
    pictures = commons_pictures(files[:10])
    return next((pictures[file] for file in files if pictures.get(file)), None)


# a picture is only kept when its url answers with an image, some collections do not let others link to them
def loads_as_image(url):
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Range': 'bytes=0-1023'})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.headers.get_content_maintype() == 'image'
    except Exception:
        return False


# scientific name -> pictures, for every fish of the database without a picture
def fetch(database_path):
    names = fish_without_pictures(database_path)
    images = wikidata_images(names)
    commons = commons_pictures(sorted({file for files in images.values() for file in files}))
    found = {}
    for name in names:
        pictures = [commons[file] for file in images.get(name, []) if commons.get(file)][:MAX_PICTURES_PER_FISH]
        if not pictures:
            pictures = [picture for picture in fallback_pictures(name) if picture]
        pictures = [picture for picture in pictures if loads_as_image(picture['url'])]
        if pictures:
            found[name] = pictures
        print('{} {}'.format('+' if pictures else '-', name), file=sys.stderr, flush=True)
    return found


def fallback_pictures(name):
    picture = inaturalist_picture([name])
    if picture:
        return [picture]
    species_key, accepted = gbif_species(name)
    time.sleep(0.5)
    if accepted and accepted != name:
        picture = inaturalist_picture([accepted])
        if picture:
            return [picture]
    if species_key:
        picture = gbif_picture(species_key)
        time.sleep(0.5)
        if picture:
            return [picture]
    for search_name in dict.fromkeys(name for name in (name, accepted) if name):
        picture = commons_search_picture(search_name)
        if picture:
            return [picture]
    return []


# Adds the fetched pictures to a copy of the database, only for fish that still have no picture
def apply(pictures_by_name, source_path, target_path):
    migrations.migrate(source_path, target_path)
    connection = sqlite3.connect(target_path, isolation_level=None)
    try:
        connection.execute('BEGIN')
        added = 0
        fish_ids = dict(connection.execute(
            'SELECT scientific_name, id FROM fish WHERE id NOT IN (SELECT fish_id FROM fish_picture)'))
        known_urls = {row[0] for row in connection.execute('SELECT url FROM fish_picture')}
        for name, pictures in sorted(pictures_by_name.items()):
            if name not in fish_ids:
                continue
            for picture in pictures:
                if picture['url'] in known_urls:
                    continue
                connection.execute('INSERT INTO fish_picture (fish_id, url, author, licence, source_url, source) '
                                   'VALUES (?, ?, ?, ?, ?, ?)',
                                   (fish_ids[name], picture['url'], picture['author'], picture['licence'],
                                    picture['source_url'], picture['source']))
                known_urls.add(picture['url'])
                added += 1
        connection.execute('COMMIT')
        missing = connection.execute('SELECT count(*) FROM fish WHERE id NOT IN (SELECT fish_id FROM fish_picture)').fetchone()[0]
        return added, missing
    except Exception:
        connection.execute('ROLLBACK')
        raise
    finally:
        connection.close()


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == 'fetch':
        with open(sys.argv[3], 'w') as output:
            json.dump(fetch(sys.argv[2]), output, indent=1, sort_keys=True)
        print('Wrote {}'.format(sys.argv[3]))
    elif len(sys.argv) == 5 and sys.argv[1] == 'apply':
        with open(sys.argv[2]) as lookup:
            added, missing = apply(json.load(lookup), sys.argv[3], sys.argv[4])
        print('Added {} pictures, {} fish still have none'.format(added, missing))
    else:
        print('Usage: python -m fishtank.picture_import fetch <database> <pictures.json>\n'
              '       python -m fishtank.picture_import apply <pictures.json> <source database> <target database>')
        sys.exit(1)
