"""Apply explicit, reviewed PI mappings locally; dry-run writes nothing.

python scripts/map_pi_points.py plant_model.json reviewed_pi.csv --dry-run
CSV columns: asset_id,archive,point,value_type,uom,reviewed_by,review_note
Empty uom explicitly means no UOM. No archive/point/type is inferred from a tag.
Partial updates preserve other PI mappings; --replace-all removes omitted PI
mappings and restores their export placeholders. OPC mappings are never changed.
"""
import argparse
import csv
import json
import os
import sys
from pathlib import Path
import tempfile
from pi_mapping import FIELDS, plan_mapping


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON key: {key}')
        result[key] = value
    return result


def nonfinite(value):
    raise ValueError(f'nonfinite JSON number: {value}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('model', type=Path)
    parser.add_argument('mapping_csv', type=Path)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--replace-all', action='store_true')
    args = parser.parse_args()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(newline='\n')  # a redirected report is LF on every OS
    try:
        original = args.model.read_text(encoding='utf-8')
        model = json.loads(original, object_pairs_hook=strict_object, parse_constant=nonfinite)
        if model.get('meta', {}).get('model_kind') != 'extracted_twin':
            raise ValueError('Only extracted_twin models are supported; TE seed references are separate')
        with args.mapping_csv.open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream, strict=True)
            if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)) or set(reader.fieldnames) != set(FIELDS):
                raise ValueError('CSV requires exactly these unique columns: ' + ','.join(FIELDS))
            rows = list(reader)
        from generate import validate_twin
        issues = validate_twin(model)
        if issues:
            raise ValueError('Invalid model: ' + '; '.join(issues))
        updated, report = plan_mapping(model, rows, args.replace_all)
        report['dry_run'] = args.dry_run
        print(json.dumps(report, indent=2, ensure_ascii=True))
        if not report['valid']:
            return 1
        if not args.dry_run:
            # Same-directory replace avoids leaving a half-written model. Check
            # for an intervening edit before replacement; no exports are written.
            temp = None
            try:
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=args.model.parent, delete=False) as stream:
                    temp = Path(stream.name)
                    stream.write(json.dumps(updated, indent=2, ensure_ascii=False) + '\n')
                if args.model.read_text(encoding='utf-8') != original:
                    raise ValueError('Model changed during planning; rerun against current model')
                os.replace(temp, args.model)
            finally:
                if temp and temp.exists():
                    temp.unlink()
        return 0
    except (ValueError, OSError, KeyError, TypeError, csv.Error) as exc:
        parser.exit(2, f'PI mapping rejected; no model update: {exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
