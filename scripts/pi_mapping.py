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


# ------------------------------------------------------------------ PI Builder sheet (staging, NOT import-tested)
# Header names follow what the vendor workbooks show (data/pi_builder_reference.json). Element properties are
# unprefixed (Template, Description); attribute properties carry the Attribute prefix (AttributeType, ...).
PI_SHEET_COLS = ["Selected(x)", "Parent", "Name", "ObjectType", "Description", "Template",
                 "AttributeType", "AttributeDefaultUOM", "AttributeDataReference", "AttributeConfigString"]
SHEET_SCHEMA_VERSION = 2
NOT_IMPORT_TESTED = ("NOT import-tested: these files have never been published to a licensed PI AF server. "
                     "They follow the vendor-published PI Builder conventions read offline "
                     "(data/pi_builder_reference.json).")
# Model spelling -> the AF default UOM database abbreviation, where a vendor-published AF export shows it.
VENDOR_UOM = {"degC": "\u00b0C"}
# Units with no vendor-published AF abbreviation in the sources read. Never assumed to exist: they are written to
# custom_uoms.csv with a definition, and a site either creates them or replaces them with its own equivalent.
CUSTOM_UOMS = {
    "kg/h": {"class": "Mass Flow Rate", "new_class": False, "name": "kilogram per hour", "reference": "kg/s",
             "factor": 1 / 3600, "offset": 0.0,
             "note": "Exact conversion. The AF default UOM database may already have kg/h; if so, use it and "
                     "skip this row."},
    "kPa g": {"class": "Gauge Pressure (custom)", "new_class": True, "name": "kilopascal gauge", "reference": "",
              "factor": "", "offset": "",
              "note": "Gauge pressure kept in its own class with no conversion: converting to absolute needs the "
                      "local atmospheric pressure. A site with a gauge-pressure convention should map to that."},
    "kscmh": {"class": "Standard Volume Flow Rate (custom)", "new_class": True,
              "name": "thousand standard cubic meter per hour", "reference": "", "factor": "", "offset": "",
              "note": "Tennessee Eastman unit. Volume at standard conditions, so not convertible to actual m3/h by "
                      "a fixed factor; kept in its own class with no conversion."},
    "mol%": {"class": "Ratio", "new_class": False, "name": "mole percent", "reference": "%", "factor": 1.0,
             "offset": 0.0, "note": "Numerically equal to percent; the separate unit keeps 'mole' visible."},
}
CUSTOM_UOM_COLS = ["uom_class", "new_class", "name", "abbreviation", "reference_uom", "factor", "offset",
                   "used_by_attributes", "note"]
DESCRIPTION_COLS = ["attribute_path", "description"]


def af_uom(uom):
    return VENDOR_UOM.get(uom, uom)


def is_placeholder_reference(config):
    return "placeholder" in (config or "").lower()


def sheet_text(rows):
    """The PI Builder staging sheet. Attribute descriptions are not written: no vendor sheet shows the attribute
    description column header, so they go to attribute_descriptions.csv instead (descriptions_text)."""
    out = [r[:4] + ["" if r[3] == "Attribute" else r[4]] + r[5:] for r in rows]
    return pi_csv_text(PI_SHEET_COLS, out)


def descriptions_text(rows):
    return pi_csv_text(DESCRIPTION_COLS, [[f"{r[1]}|{r[2]}", r[4]] for r in rows if r[3] == "Attribute" and r[4]])


def custom_uoms_text(rows):
    used = {}
    for r in rows:
        if r[3] == "Attribute" and r[7] in CUSTOM_UOMS:
            used[r[7]] = used.get(r[7], 0) + 1
    body = [[d["class"], "yes" if d["new_class"] else "no", d["name"], u, d["reference"],
             "" if d["factor"] == "" else repr(d["factor"]), "" if d["offset"] == "" else repr(d["offset"]),
             used[u], d["note"]] for u, d in CUSTOM_UOMS.items() if u in used]
    return pi_csv_text(CUSTOM_UOM_COLS, body)


def import_steps_text(rows):
    templates = sum(r[3] == "ElementTemplate" for r in rows)
    attrs = [r for r in rows if r[3] == "Attribute"]
    held = sum(r[0] != "x" for r in attrs)
    custom = sorted({r[7] for r in attrs if r[7] in CUSTOM_UOMS})
    return "\n".join([
        "PI AF staging files: how to use them",
        "",
        NOT_IMPORT_TESTED,
        "Use only a separately authorized, isolated AF database. Nothing here connects to PI or creates PI points.",
        "",
        "Files:",
        "  pi_builder_af.csv           PI Builder sheet (schema v%d): element templates, elements, attributes."
        % SHEET_SCHEMA_VERSION,
        "  custom_uoms.csv             units this sheet uses that a default AF UOM database may not have.",
        "  attribute_descriptions.csv  attribute descriptions (not in the sheet: that column header is unconfirmed).",
        "",
        "Order:",
        "  1. Units: in PI Builder, Library > Units of Measure > Find UOM Classes, and compare with custom_uoms.csv"
        + (" (%s)." % ", ".join(custom) if custom else " (none needed)."),
        "     For each row: if the site already has an equivalent unit, replace the abbreviation in",
        "     pi_builder_af.csv; otherwise create it (a new class where new_class = yes) before step 3.",
        ("  2. Element templates: select only the %d ElementTemplate rows and Publish (Edit Mode: Create Only)."
         % templates) if templates else "  2. Element templates: none in this sheet; skip.",
        "  3. Elements and attributes: select the remaining x rows and Publish (Create Only).",
        "     %d of %d attributes are not selected because their PI point reference is a placeholder." % (held, len(attrs)),
        "     Leave them out until a reviewed mapping replaces the placeholder (scripts/map_pi_points.py).",
        "  4. Check in PI System Explorer: counts, paths, that each mapped attribute resolves to its point, types",
        "     and UOMs; read back values with timestamps and quality; export to XML as evidence (docs/PI_MAPPING.md).",
        ""])


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
    return {'status': 'OFFLINE STAGING ONLY; ' + NOT_IMPORT_TESTED,
            'model_id': model.get('meta', {}).get('model_id'),
            'sheet_schema': {
                'version': SHEET_SCHEMA_VERSION, 'file': 'pi_builder_af.csv', 'columns': PI_SHEET_COLS,
                'status': NOT_IMPORT_TESTED,
                'changes_from_v1': ['AttributeValueType header replaced by the documented AttributeType',
                                    'vendor UOM abbreviations where known (degC written in the degree-sign form)',
                                    'units without vendor evidence defined in custom_uoms.csv, never assumed',
                                    'element templates defined as ElementTemplate rows ahead of the elements',
                                    'attribute descriptions moved to attribute_descriptions.csv',
                                    'placeholder PI point rows left unselected so PI Builder will not publish them'],
                'vendor_sources': 'data/pi_builder_reference.json',
                'remaining_contract_checks': [
                    'Compare the header row and row conventions with a sheet retrieved from the installed PI Builder version.',
                    'Confirm every unit in custom_uoms.csv against the site UOM database, or create it.',
                    'Verify every supplied AF value type and UOM against the installed system and source point.']},
            'mapped': snapshot(model), 'unmapped_asset_ids': report['unmapped_asset_ids'],
            'review_status': 'User-supplied reviewer attestations only; archive, point, AF type and UOM compatibility NOT independently verified',
            'attributes': [{'asset_id': x['id'], 'parent': r[1], 'name': r[2], 'selected': r[0] == 'x',
                            'value_type': r[6], 'uom': r[7], 'config_string': r[9],
                            'status': 'reviewed mapping; native verification pending' if 'pi_point' in x
                            else 'blocked callout' if x.get('reviewed_valve_association')
                            else 'unmapped placeholder (row not selected; excluded from publish)'}
                           for x, r in zip([x for x in model['instruments']
                                            if (x.get('ops_review') or {}).get('status') != 'rejected'],
                                           [r for r in rows if r[3] == 'Attribute'])],
            'expected_element_rows': sum(r[3] == 'Element' for r in rows),
            'expected_template_rows': sum(r[3] == 'ElementTemplate' for r in rows),
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
