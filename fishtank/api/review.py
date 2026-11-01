import csv
import io
import re

from flask import Blueprint, Response, g, request
from peewee import IntegrityError

from fishtank.api.common import (ApiError, admin_required, check_rate_limit, is_integer, json_body, login_required,
                                 reject_unknown_fields, success)
from fishtank.api.fish import (FISH_FIELDS, INTEGER, NUMBER, apply_fish_fields, find_fish, fish_fields_from_payload,
                               fish_for_api, fishtank_counts, save_fish)
from fishtank.db import database, utcnow
from fishtank.models.fish import UNKNOWN_TEMPERAMENT, Fish
from fishtank.models.rate_limit import SUGGESTIONS_PER_USER
from fishtank.models.review import (STATUS_APPROVED, STATUS_PENDING, STATUS_REJECTED, AuditEvent,
                                    TemperamentSuggestion)

# Clearing the review backlog: users suggest what admins have not filled in yet, admins edit many fish at once
# as a spreadsheet, and every change admins make is in the audit log
blueprint = Blueprint('review', __name__)

SUGGESTION_FIELDS = {'in_species_temperament', 'cross_species_temperament', 'minimum_size', 'maximum_size',
                     'minimum_group_size', 'note'}
NOTE_MAX_LENGTH = 500
CSV_MAX_BYTES = 2 * 1024 * 1024
CSV_MAX_ROWS = 5000
AUDIT_PAGE_SIZE = 50
AUDIT_PAGE_MAX = 200


def suggestion_for_api(suggestion):
    fish = suggestion.fish
    return {**suggestion.to_dic(), 'fish': {'id': fish.id, 'scientific_name': fish.scientific_name,
                                            'common_name': fish.common_name, 'retired': fish.is_retired(),
                                            'in_species_temperament': fish.in_species_temperament,
                                            'cross_species_temperament': fish.cross_species_temperament}}


# --- suggestions from users ---

# A logged in user suggests the temperament of a fish that has none yet, with the size it needs once it has one
# body: {"in_species_temperament", "cross_species_temperament", "minimum_size", "maximum_size",
#        "minimum_group_size" (optional), "note" (optional)}
# The values are checked as an admin's change would be, a user's newer suggestion for the fish replaces their pending one
@blueprint.route('/fish/<int:fish_id>/suggestions', methods=['POST'])
@login_required
def suggest_temperament(fish_id):
    payload = json_body()
    reject_unknown_fields(payload, SUGGESTION_FIELDS)
    fish = find_fish(fish_id)
    if fish.is_retired():
        raise ApiError('{} is retired'.format(fish.scientific_name), 409)
    if fish.cross_species_temperament != UNKNOWN_TEMPERAMENT and fish.in_species_temperament != UNKNOWN_TEMPERAMENT:
        raise ApiError('the temperament of {} is already known'.format(fish.scientific_name), 409)
    for name in ('in_species_temperament', 'cross_species_temperament'):
        if payload.get(name) == UNKNOWN_TEMPERAMENT:
            raise ApiError('please suggest a known temperament', field=name)
    note = payload.get('note')
    if note is not None and (not isinstance(note, str) or len(note.strip()) > NOTE_MAX_LENGTH):
        raise ApiError('note must be text of at most {} characters'.format(NOTE_MAX_LENGTH), field='note')

    values = {name: payload.get(name) for name in SUGGESTION_FIELDS - {'note'}}
    # the same rules as an admin's change: ranges, a size once the temperament is known, groups only when peaceful
    fields = fish_fields_from_payload(values, fish)
    check_rate_limit(SUGGESTIONS_PER_USER, str(g.user.id), 'You have made a lot of suggestions in a short time, '
                                                           'please try again in {}')
    with database.atomic():
        TemperamentSuggestion.delete().where((TemperamentSuggestion.fish == fish) & (TemperamentSuggestion.user == g.user) &
                                             (TemperamentSuggestion.status == STATUS_PENDING)).execute()
        suggestion = TemperamentSuggestion.create(
            fish=fish, user=g.user, in_species_temperament=fields['in_species_temperament'],
            cross_species_temperament=fields['cross_species_temperament'], size_min=fields['size_min'],
            size_max=fields['size_max'], minimum_group_size=fields['minimum_group_size'],
            note=note.strip() if note and note.strip() else None)
        SUGGESTIONS_PER_USER.hit(str(g.user.id))
    return success(201, suggestion=suggestion_for_api(suggestion))


# ?status=pending (default), approved, rejected or all, oldest first for pending, newest first otherwise
@blueprint.route('/suggestions')
@admin_required
def list_suggestions():
    status = request.args.get('status', STATUS_PENDING)
    if status not in (STATUS_PENDING, STATUS_APPROVED, STATUS_REJECTED, 'all'):
        raise ApiError('status must be pending, approved, rejected or all', field='status')
    query = TemperamentSuggestion.select(TemperamentSuggestion, Fish).join(Fish)
    if status != 'all':
        query = query.where(TemperamentSuggestion.status == status)
    order = TemperamentSuggestion.id.asc() if status == STATUS_PENDING else TemperamentSuggestion.id.desc()
    pending = TemperamentSuggestion.select().where(TemperamentSuggestion.status == STATUS_PENDING).count()
    return success(suggestions=[suggestion_for_api(suggestion) for suggestion in query.order_by(order).limit(500)],
                   pending=pending)


def find_pending_suggestion(suggestion_id):
    suggestion = TemperamentSuggestion.get_or_none(TemperamentSuggestion.id == suggestion_id)
    if suggestion is None:
        raise ApiError('no such suggestion', 404)
    if suggestion.status != STATUS_PENDING:
        raise ApiError('this suggestion was already {}'.format(suggestion.status), 409)
    return suggestion


# Copies the suggested values onto the fish, checked again, the fish may have changed since
@blueprint.route('/suggestions/<int:suggestion_id>/approve', methods=['POST'])
@admin_required
def approve_suggestion(suggestion_id):
    with database.atomic():
        suggestion = find_pending_suggestion(suggestion_id)
        fish = suggestion.fish
        changes = apply_fish_fields(fish, fish_fields_from_payload(suggestion.fish_values(), fish))
        save_fish(fish)
        suggestion.status = STATUS_APPROVED
        suggestion.reviewed_by = g.user
        suggestion.reviewed_at = utcnow()
        suggestion.save()
        AuditEvent.record(g.user, 'suggestion.approve', fish_id=fish.id,
                          details={'suggestion_id': suggestion.id, 'suggested_by': suggestion.to_dic()['username'],
                                   'changes': changes})
    return success(suggestion=suggestion_for_api(suggestion), fish=fish_for_api(fish, fishtank_counts()))


@blueprint.route('/suggestions/<int:suggestion_id>/reject', methods=['POST'])
@admin_required
def reject_suggestion(suggestion_id):
    with database.atomic():
        suggestion = find_pending_suggestion(suggestion_id)
        suggestion.status = STATUS_REJECTED
        suggestion.reviewed_by = g.user
        suggestion.reviewed_at = utcnow()
        suggestion.save()
        AuditEvent.record(g.user, 'suggestion.reject', fish_id=suggestion.fish_id,
                          details={'suggestion_id': suggestion.id, 'suggested_by': suggestion.to_dic()['username']})
    return success(suggestion=suggestion_for_api(suggestion))


# --- the catalogue as a spreadsheet ---

CSV_COLUMNS = ['id'] + list(FISH_FIELDS)


# Every fish with the fields admins can change, ?review=true for the fish whose temperament is not known yet
# Retired fish are included, they may still need their facts corrected
@blueprint.route('/fish/export.csv')
@admin_required
def export_fish():
    query = Fish.select().order_by(Fish.id)
    if request.args.get('review') == 'true':
        query = query.where(Fish.retired_at.is_null() & ((Fish.cross_species_temperament == UNKNOWN_TEMPERAMENT) |
                                                         (Fish.in_species_temperament == UNKNOWN_TEMPERAMENT)))
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_COLUMNS)
    for fish in query:
        writer.writerow([fish.id] + [csv_value(getattr(fish, FISH_FIELDS[name][0])) for name in FISH_FIELDS])
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment; filename="fish.csv"'})


def csv_value(value):
    return '' if value is None else value


# a cell as the api reads a json value: empty is null, numbers become numbers when they look like one,
# anything else is passed on as text, so the usual checks name the field that is wrong
def cell_value(name, text):
    text = text.strip()
    if text == '':
        return None
    kind = FISH_FIELDS[name][1]
    if kind == INTEGER and re.fullmatch(r'-?\d+', text):
        return int(text)
    if kind == NUMBER and re.fullmatch(r'-?\d+(\.\d+)?', text):
        return float(text)
    return text


def read_csv():
    if request.content_length is not None and request.content_length > CSV_MAX_BYTES:
        raise ApiError('the file is larger than {} MB'.format(CSV_MAX_BYTES // (1024 * 1024)), 413)
    try:
        text = request.get_data(as_text=False).decode('utf-8-sig')
    except UnicodeDecodeError:
        raise ApiError('the file must be utf-8 text')
    reader = csv.DictReader(io.StringIO(text))
    header = reader.fieldnames or []
    if 'id' not in header:
        raise ApiError('the first row must name the columns, with an id column')
    for name in header:
        if name not in CSV_COLUMNS:
            raise ApiError('{} is not a column that can be imported'.format(name), field=name)
    if len(set(header)) != len(header):
        raise ApiError('a column is named twice')
    rows = list(reader)
    if len(rows) > CSV_MAX_ROWS:
        raise ApiError('at most {} rows at once'.format(CSV_MAX_ROWS))
    return header, rows


# Checks every row of the uploaded csv against the same rules as a change through the api
# Only the columns in the file change, an empty cell clears an optional field
# Returns one entry per row, with the changes or the error, and the fish with their changes applied
def check_rows(header, rows):
    results = []
    changed = []
    seen = set()
    for number, row in enumerate(rows, start=2):
        entry = {'row': number, 'id': None, 'scientific_name': None, 'changes': {}, 'error': None, 'field': None}
        results.append(entry)
        if None in row:
            entry['error'] = 'this row has more cells than the header has columns'
            continue
        raw_id = (row.get('id') or '').strip()
        if not re.fullmatch(r'\d+', raw_id):
            entry['error'], entry['field'] = 'id must be the number of an existing fish', 'id'
            continue
        entry['id'] = int(raw_id)
        if entry['id'] in seen:
            entry['error'], entry['field'] = 'this fish is in the file twice', 'id'
            continue
        seen.add(entry['id'])
        fish = Fish.get_or_none(Fish.id == entry['id'])
        if fish is None:
            entry['error'], entry['field'] = 'no fish has id {}'.format(entry['id']), 'id'
            continue
        entry['scientific_name'] = fish.scientific_name
        payload = {name: cell_value(name, row[name] or '') for name in header if name != 'id'}
        try:
            fields = fish_fields_from_payload(payload, fish)
        except ApiError as error:
            entry['error'], entry['field'] = error.message, error.field
            continue
        entry['changes'] = apply_fish_fields(fish, fields)
        if entry['changes']:
            changed.append((fish, entry))
    return results, changed


# body: the csv file as text/csv. ?dry_run=true only checks it and shows what would change
# Without it every row is applied in one go, or none when any row has an error
@blueprint.route('/fish/import', methods=['POST'])
@admin_required
def import_fish():
    header, rows = read_csv()
    results, changed = check_rows(header, rows)
    errors = [entry for entry in results if entry['error']]
    summary = {'rows': results, 'changed': len(changed), 'errors': len(errors), 'applied': False}
    if request.args.get('dry_run') == 'true' or errors or not changed:
        return success(**summary)
    try:
        with database.atomic():
            for fish, entry in changed:
                fish.save()
                AuditEvent.record(g.user, 'fish.update', fish_id=fish.id, details={'changes': entry['changes'], 'via': 'import'})
            AuditEvent.record(g.user, 'fish.import', details={'rows': len(rows), 'changed': len(changed)})
    except IntegrityError:
        raise ApiError('two rows give the same scientific name or FishBase species code', 409)
    summary['applied'] = True
    return success(**summary)


# --- the audit log ---

# newest first, ?fish_id= for one fish, ?before= (an event id) for the next page, ?limit= up to 200
@blueprint.route('/audit')
@admin_required
def list_audit_events():
    query = AuditEvent.select().order_by(AuditEvent.id.desc())
    for name in ('fish_id', 'before', 'limit'):
        value = request.args.get(name)
        if value is not None and not value.isdigit():
            raise ApiError('{} must be a whole number'.format(name), field=name)
    if request.args.get('fish_id'):
        query = query.where(AuditEvent.fish_id == int(request.args['fish_id']))
    if request.args.get('before'):
        query = query.where(AuditEvent.id < int(request.args['before']))
    limit = min(int(request.args.get('limit') or AUDIT_PAGE_SIZE), AUDIT_PAGE_MAX)
    events = list(query.limit(limit + 1))
    return success(events=[event.to_dic() for event in events[:limit]], more=len(events) > limit)
