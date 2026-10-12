"""Offline, deliberately narrow PI mapping contract; no PI client or native import.

pi_point is separate from OPC data_point. Unknown PI/AF types are rejected instead
of coerced. These exports remain PI Builder-style staging CSVs until reconciled in
an authorized isolated AF database using its native import/export format.
"""
import copy
import csv
import io

FIELDS = ('asset_id', 'archive', 'point', 'value_type', 'uom', 'reviewed_by', 'review_note')
VALUE_TYPES = {'Double', 'Single', 'Int32', 'Int16', 'String'}
UNKNOWN = {'unknown', 'tbd', 'todo', 'placeholder', 'null', 'none', '?'}


def clean_text(value, field, allow_empty=False):
    if not isinstance(value, str) or value != value.strip():
        raise ValueError(f'{field}: expected trimmed text')
    if not value and not allow_empty:
        raise ValueError(f'{field}: required')
    if value.lower() in UNKNOWN or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError(f'{field}: unknown or control-character data')
    if value.lstrip().startswith(('=', '+', '-', '@')):
        raise ValueError(f'{field}: spreadsheet formula-like text is not allowed')
    return value


def validate_point(mapping):
    required = set(FIELDS) - {'asset_id'}
    if not isinstance(mapping, dict) or set(mapping) != required:
        raise ValueError('pi_point: exact archive, point, value_type, uom, reviewed_by, review_note fields required')
    for key, value in mapping.items():
        clean_text(value, key, allow_empty=key == 'uom')
    if mapping['value_type'] not in VALUE_TYPES:
        raise ValueError('value_type: unsupported/unknown AF type; review required')
    # This bounded contract supports simple archive/point references only. Reject
    # AF config delimiters/macros rather than invent an escaping convention.
    for key in ('archive', 'point'):
        if any(c in mapping[key] for c in '\\/;|%"\'[]{}?*'):
            raise ValueError(f'{key}: unsupported PI config delimiter or macro')
        if 'placeholder' in mapping[key].lower():
            raise ValueError(f'{key}: placeholder is not a reviewed mapping')
    return mapping


def mapping_config(mapping):
    validate_point(mapping)
    return '\\\\' + mapping['archive'] + '\\' + mapping['point']


def snapshot(model):
    return {x['id']: copy.deepcopy(x['pi_point']) for x in model['instruments'] if 'pi_point' in x}


def plan_mapping(model, rows, replace_all=False):
    before = snapshot(model)
    errors, assignments, seen, ids = [], {}, set(), {}
    for group in ('units', 'line_items', 'streams', 'systems', 'offpage_connectors', 'final_elements'):
        for asset in model.get(group, []):
            if 'pi_point' in asset:
                errors.append({'asset_id': asset.get('id'), 'reason': 'pi_point is supported only on instruments'})
    for x in model['instruments']:
        if x['id'] in ids:
            errors.append({'asset_id': x['id'], 'reason': 'duplicate model asset_id'})
        ids[x['id']] = x
        if 'pi_point' in x:
            try:
                validate_point(x['pi_point'])
                if x.get('reviewed_valve_association') or (x.get('ops_review') or {}).get('status') == 'rejected':
                    raise ValueError('blocked callout/rejected instrument has PI mapping')
            except ValueError as exc:
                errors.append({'asset_id': x['id'], 'reason': str(exc)})
    for n, row in enumerate(rows, 2):
        try:
            if set(row) != set(FIELDS):
                raise ValueError('CSV columns must exactly match ' + ','.join(FIELDS))
            identity = clean_text(row['asset_id'], 'asset_id')
            if identity in seen:
                raise ValueError('duplicate target row')
            seen.add(identity)
            if identity not in ids:
                raise ValueError('unknown explicit asset_id; no tag fallback')
            target = ids[identity]
            if target.get('reviewed_valve_association'):
                raise ValueError('valve callout: signal requires separate review; mapping blocked')
            if (target.get('ops_review') or {}).get('status') == 'rejected':
                raise ValueError('rejected instrument')
            mapping = {k: row[k] for k in FIELDS if k != 'asset_id'}
            assignments[identity] = copy.deepcopy(validate_point(mapping))
        except (ValueError, TypeError) as exc:
            errors.append({'row': n, 'reason': str(exc)})
    proposed = copy.deepcopy(model)
    if not errors:
        for x in proposed['instruments']:
            if replace_all:
                x.pop('pi_point', None)
            if x['id'] in assignments:
                x['pi_point'] = assignments[x['id']]
    after = snapshot(proposed)
    changes = [{'asset_id': k, 'before': before.get(k), 'after': after.get(k),
                'kind': 'added' if k not in before else 'removed' if k not in after else 'changed'}
               for k in sorted(before.keys() | after.keys()) if before.get(k) != after.get(k)]
    return proposed, {'valid': not errors, 'errors': errors, 'mode': 'replace-all' if replace_all else 'partial',
                      'mappings_before': before, 'mappings_after': after, 'mapping_changes': changes,
                      'unmapped_asset_ids': [x['id'] for x in proposed['instruments'] if 'pi_point' not in x]}


def pi_csv_text(header, rows):
    """CSV quoting handles commas/quotes; neutralize spreadsheet formulas in labels.

    Mapping address fields are rejected earlier, never silently rewritten.
    Leading controls/whitespace cannot disguise a formula in free-text cells.
    """
    def safe(value):
        if isinstance(value, str) and (value.lstrip().startswith(('=', '+', '-', '@'))
                                       or any(ord(c) < 32 for c in value)):
            return "'" + value
        return value
    stream = io.StringIO(newline='')
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(header)
    writer.writerows([[safe(v) for v in row] for row in rows])
    return '\ufeff' + stream.getvalue()


def reconciliation(model, rows):
    _, report = plan_mapping(model, [])
    if not report['valid']:
        raise ValueError('Invalid PI mappings: ' + str(report['errors']))
    return {'status': 'OFFLINE STAGING ONLY; native PI Builder import NOT tested',
            'model_id': model.get('meta', {}).get('model_id'),
            'candidate_schema': {
                'version': 1, 'file': 'pi_builder_UNVALIDATED_candidate_v1.csv',
                'status': 'UNVALIDATED candidate; not native-import-ready',
                'only_legacy_migration': 'AttributeValueType header renamed to AttributeType; same row data',
                'vendor_source': 'https://osicdn.blob.core.windows.net/learningcontent/Online%20Course%20Workbooks/Asset%20Framework_Beyond%20the%20Basics_Workbook.pdf',
                'vendor_pages': [34, 85, 86, 92],
                'remaining_contract_checks': [
                    'Retrieve sample rows from the installed PI Builder version before import.',
                    'Verify complete header names, including Parent, Name, ObjectType, Template and AttributeDataReference.',
                    'Verify element/attribute row identity, parent paths and version-specific row conventions.',
                    'Verify every supplied AF value type and UOM against the installed system and source point.']},
            'mapped': snapshot(model), 'unmapped_asset_ids': report['unmapped_asset_ids'],
            'review_status': 'User-supplied reviewer attestations only; archive, point, AF type and UOM compatibility NOT independently verified',
            'attributes': [{'asset_id': x['id'], 'parent': r[1], 'name': r[2],
                            'value_type': r[6], 'uom': r[7], 'config_string': r[9],
                            'status': 'reviewed mapping; native verification pending' if 'pi_point' in x
                            else 'blocked callout' if x.get('reviewed_valve_association') else 'unmapped placeholder'}
                           for x, r in zip([x for x in model['instruments']
                                            if (x.get('ops_review') or {}).get('status') != 'rejected'],
                                           [r for r in rows if r[3] == 'Attribute'])],
            'expected_element_rows': sum(r[3] == 'Element' for r in rows),
            'expected_attribute_rows': sum(r[3] == 'Attribute' for r in rows),
            'checklist': [
                'Obtain approval before any native import or plant/PI connection.',
                'Export a sample from the installed PI Builder version; reconcile its actual column contract with this staging CSV.',
                'Verify every reviewed archive and point exists, permissions, AF type and UOM compatibility; no points are created by this workflow.',
                'Exclude all unresolved placeholders from native import; no placeholder is evidence of an available signal.',
                'Use a separately authorized isolated AF database; back up existing elements before making changes.',
                'Compare imported paths, names, element/attribute counts, references, types and UOMs against this file and the staging CSV.',
                'Read back every mapped attribute; record timestamp, quality, value, source point and reviewer evidence; reject bad or stale values.',
                'Record native errors and differences and resolve them before any operational-use decision.',
                'Formula-like free-text CSV cells have an apostrophe prefix; review labels before native import.']}
