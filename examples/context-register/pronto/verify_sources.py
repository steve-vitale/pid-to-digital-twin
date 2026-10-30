"""Check the example's key against pinned originals, without writing any source file.

XLSX/TSV checks and hashes use the standard library. PDF text checks additionally
use pypdf when installed. The Figure 1 claim requires separate visual review.
This checks a coding-agent transcription, not current plant truth or human approval.
"""
import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}


def xlsx_cells(path, sheet):
    with zipfile.ZipFile(path) as z:
        shared = []
        if 'xl/sharedStrings.xml' in z.namelist():
            root = ET.fromstring(z.read('xl/sharedStrings.xml'))
            shared = [''.join(n.itertext()) for n in root]
        wb = ET.fromstring(z.read('xl/workbook.xml'))
        rid = next(s.attrib['{' + NS['r'] + '}id'] for s in wb.findall('m:sheets/m:sheet', NS)
                   if s.attrib['name'] == sheet)
        rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        target = next(r.attrib['Target'] for r in rels if r.attrib['Id'] == rid)
        name = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/' + target)
        root = ET.fromstring(z.read(name))
        result = {}
        for cell in root.findall('.//m:sheetData/m:row/m:c', NS):
            typ = cell.attrib.get('t', 'n')
            val = cell.find('m:v', NS)
            text = '' if val is None else val.text or ''
            if typ == 's':
                value = shared[int(text)]
            elif typ == 'inlineStr':
                value = ''.join(cell.find('m:is', NS).itertext())
            elif typ == 'b':
                value = text == '1'
            elif typ == 'n' and text:
                value = float(text)
            else:
                value = text
            result[cell.attrib['r']] = value
        return result


def same_cell(got, expected):
    if isinstance(expected, dict):
        if not isinstance(got, (float, int)):
            return False
        stamp = dt.datetime(1899, 12, 30) + dt.timedelta(days=got)
        if 'time' in expected:
            return stamp.time().replace(microsecond=0).isoformat() == expected['time']
        return stamp.replace(microsecond=0).isoformat() == expected['datetime']
    if isinstance(expected, (float, int)):
        return isinstance(got, (float, int)) and abs(got - expected) < 1e-12
    return got == expected


def verify(source_root, key_path):
    key = json.loads(key_path.read_text(encoding='utf-8'))
    docs = {d['id']: d for d in key['documents']}
    failures, unavailable, visual, verified = [], [], [], []
    paths = {}
    for docid, doc in docs.items():
        path = source_root / doc['path']
        if not path.is_file():
            unavailable.append(docid + ': original missing; run both documented fetch commands')
            continue
        if hashlib.sha256(path.read_bytes()).hexdigest() != doc['sha256']:
            failures.append(docid + ': raw-byte SHA-256 mismatch')
            continue
        paths[docid] = path
    pdfs, sheets, records = {}, {}, {}
    norm = lambda s: re.sub(r'\s+', ' ', s).strip()
    for fact in key['facts']:
        fid, docid, check = fact['id'], fact['document_id'], fact['check']
        if docid not in paths:
            continue
        if fact['raw_sha256'] != docs[docid]['sha256']:
            failures.append(fid + ': key hash does not match manifest')
            continue
        path = paths[docid]
        kind = check['kind']
        if kind == 'xlsx_cells':
            k = (docid, check['sheet'])
            if k not in sheets:
                sheets[k] = xlsx_cells(path, check['sheet'])
            errors = [cell for cell, expected in check['cells'].items()
                      if not same_cell(sheets[k].get(cell), expected)]
            if errors:
                failures.append(fid + ': cells differ: ' + ', '.join(errors))
                continue
        elif kind == 'tsv_record':
            if docid not in records:
                records[docid] = list(csv.reader(io.StringIO(path.read_text(encoding='utf-8-sig')), delimiter='\t'))
            rows = records[docid]
            row = rows[check['line'] - 1]
            record = dict(zip(rows[0], row))
            if row[0] != check['record'] or any(record.get(k) != v for k, v in check['fields'].items()):
                failures.append(fid + ': record/physical-line/field mismatch')
                continue
        elif kind == 'pdf_text':
            try:
                import pypdf
            except ImportError:
                unavailable.append(fid + ': pypdf unavailable for PDF text check (raw hash checked)')
                continue
            if docid not in pdfs:
                pdfs[docid] = pypdf.PdfReader(path)
            text = norm(pdfs[docid].pages[check['page'] - 1].extract_text())
            if not all(norm(s) in text for s in check['contains']):
                failures.append(fid + ': page text does not contain expected table/phrase')
                continue
        elif kind == 'pdf_figure':
            visual.append(fid + ': ' + fact['locator'])
            continue
        else:
            failures.append(fid + ': unsupported check kind')
            continue
        verified.append(fid)
    return {'schema': 'pronto-context-source-check-1', 'original_hashes_verified': len(paths),
            'facts_automatically_verified': len(verified), 'fact_ids': verified,
            'failures': failures, 'unavailable': unavailable, 'visual_review_required': visual,
            'note': 'Automatic checks do not count as independent human review, operational truth or sign-off.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-root', type=Path, default=Path('data/external'))
    p.add_argument('--key', type=Path, default=Path(__file__).with_name('source_key.json'))
    args = p.parse_args()
    result = verify(args.source_root, args.key)
    print(json.dumps(result, indent=2))
    return 1 if result['failures'] else 2 if result['unavailable'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
