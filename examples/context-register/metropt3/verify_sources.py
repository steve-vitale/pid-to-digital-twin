"""Verify original hashes/CSV observations. --pdf-text explicitly adds optional PDF text checks.

Never reads source_key.json, answer proposals or generated context. PDF table layout also requires visual review.
"""
import argparse
from collections import Counter
import csv
from datetime import datetime
import json
from pathlib import Path
import re
from prepare_sources import DEFAULT_SOURCE, PACKET, verify_file

CSV_NAME = 'MetroPT3(AirCompressor).csv'
PDF_NAME = 'Data Description_Metro.pdf'
HEADER = ['', 'timestamp', 'TP2', 'TP3', 'H1', 'DV_pressure', 'Reservoirs', 'Oil_temperature',
          'Motor_current', 'COMP', 'DV_eletric', 'Towers', 'MPG', 'LPS', 'Pressure_switch', 'Oil_level', 'Caudal_impulses']


def csv_profile(path):
    gaps = Counter()
    first, last, previous, count = [], None, None, 0
    with path.open(encoding='utf-8', newline='') as stream:
        rows = csv.reader(stream)
        assert next(rows) == HEADER, 'CSV column identities/order changed'
        for line, row in enumerate(rows, 2):
            assert len(row) == 17, f'CSV physical line {line}: field count changed'
            instant = datetime.fromisoformat(row[1])
            assert instant.tzinfo is None, f'CSV physical line {line}: unexpected explicit timezone'
            if previous is not None:
                gap = (instant - previous).total_seconds()
                assert gap > 0 and gap.is_integer(), f'CSV physical line {line}: nonincreasing/subsecond timestamp'
                gaps[int(gap)] += 1
            if len(first) < 4:
                first.append(row)
            previous, last, count = instant, row, count + 1
    assert count == 1516948 and first[0][1] == '2020-02-01 00:00:00'
    assert last[1] == '2020-09-01 03:59:50'
    assert [r[1] for r in first] == ['2020-02-01 00:00:00', '2020-02-01 00:00:10',
                                   '2020-02-01 00:00:19', '2020-02-01 00:00:29']
    assert first[0][7:11] == ['53.60000000000001', '0.04', '1.0', '0.0']
    # The total number of gaps is odd, so this order statistic is the exact median.
    middle, accumulated, median = (sum(gaps.values()) + 1) // 2, 0, None
    for gap, occurrences in sorted(gaps.items()):
        accumulated += occurrences
        if accumulated >= middle:
            median = gap
            break
    assert (min(gaps), median, max(gaps)) == (8, 10, 172918)
    return {'data_rows': count, 'fields': len(HEADER), 'first_timestamp': first[0][1], 'last_timestamp': last[1],
            'gap_seconds_min_median_max': [min(gaps), median, max(gaps)], 'first_four_rows': first,
            'limits': 'Released-file observations; no acquisition/downsampling explanation, timezone or healthy-state labels inferred.'}


def pdf_text_checks(path):
    try:
        import pymupdf
    except ImportError as error:
        raise ValueError('--pdf-text needs PyMuPDF; see requirements-render.txt. No PDF check was performed.') from error
    with pymupdf.open(path) as doc:
        assert len(doc) == 3
        pages = [re.sub(r'\s+', ' ', p.get_text()).strip() for p in doc]
    assert '15169480' in pages[0] and 'logged at 1Hz' in pages[0]
    assert '15169480 data points collected at 1Hz' in pages[1]
    assert pages[1].index('6. Motor Current (A)') < pages[1].index('7. Oil Temperature')
    assert 'active when there is no air intake' in pages[1]
    assert 'either turned off or operating in an offloaded state' in pages[1]
    assert 'active when the compressor is functioning under load' in pages[2]
    table = pages[2].split('Failure Information:', 1)[1]
    assert re.findall(r'#\d', table) == ['#1', '#1', '#3', '#4']
    for text in ['4/18/2020 0:00', '4/18/2020 23:59', '5/29/2020 23:30', '5/30/2020 6:00',
                 '6/5/2020 10:00', '6/7/2020 14:30', '7/15/2020 14:30', '7/15/2020 19:00',
                 'Maintenance on 30Apr at 12:00', 'Maintenance on 8Jun at 16:00', 'Maintenance on 16Jul at 00:00']:
        assert text in table, text
    return 'Three original pages: rate/population, analogue ordering, electrical definitions, printed failure IDs/times/notes. Table layout needs separate visual review.'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--pdf-text', action='store_true')
    args = parser.parse_args()
    try:
        pins = json.loads((PACKET / 'originals.json').read_text(encoding='utf-8'))
        for name, pin in pins['members'].items():
            verify_file(args.source_root / name, pin)
        result = csv_profile(args.source_root / CSV_NAME)
        result['pdf_check'] = pdf_text_checks(args.source_root / PDF_NAME) if args.pdf_text else 'NOT RUN: use --pdf-text for optional text checks; separate visual review remains necessary.'
    except (OSError, ValueError, AssertionError) as error:
        parser.exit(2, f'MetroPT source verification: {error}\nPrepare the actual originals first; a derived key is not a substitute.\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
