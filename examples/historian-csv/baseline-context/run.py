"""Reproduce a fixed PRONTO baseline-choice diagnostic, not a new detector or site adapter.

Stdlib only, offline. Read pinned originals; execute the existing band CLI twelve
times. --check compares both reports with committed records; --out needs a fresh
destination. No source, model, criterion or company-state changes are made.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import fetch_corpus as fc
import corpus_adapters as ca


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_day(day, source_root, pins):
    base = source_root / ('pronto/zip' if day == '3' else 'pronto-more/PRONTO benchmark case study')
    raw_name = fc.PRONTO_RAW if day == '3' else ca.PRONTO_DAYS[day]['raw']
    if day == '3':
        raw_name = 'C2 Air Leakage/Test5/Process Data/' + raw_name
    merged_name = ca.PRONTO_MERGED.format(day=day)
    selected = [merged_name, raw_name]
    expected = fc.SOURCES['pronto']['members'] if day == '3' else pins['pronto-more']
    sources = []
    for name in selected:
        path, pin = base / name, expected[name]
        size = pin.get('size', pin.get('bytes'))
        if path.stat().st_size != size or fingerprint(path) != pin['sha256']:
            raise ValueError(f'day {day}: pinned original differs: {name}')
        sources.append({'day': day, 'member': name, 'bytes': size, 'sha256': pin['sha256']})
    merged = fc.read_rows((base / merged_name).read_text(encoding='utf-8-sig'))
    raw = fc.read_rows((base / raw_name).read_text(encoding='utf-8-sig'))
    header, data = merged[0], merged[1:]
    if header[-1] != 'Fault':
        raise ValueError(f'day {day}: last column is not Fault')
    desc, raw_data, raw_times = fc.raw_export_times(raw)
    offset = fc.align_offset(header, data, desc, raw_data)
    times = raw_times[offset:offset + len(data)]
    columns = list(fc.PRONTO_PROCESS_COLUMNS)
    pick = [header.index(name) for name in columns]
    values = [[row[i] for i in pick] for row in data]
    return {'times': times, 'columns': columns, 'values': values,
            'labels': [row[-1] for row in data], 'offset': offset, 'sources': sources}


def source_context(source_root):
    """Pin the companion originals; retain literal cells without inferring test joins."""
    members = fc.SOURCES['pronto']['members']
    names = ['Operation logs/Operation log.xlsx', 'README.txt',
             'Pre-processed data/Aligned and labelled alarm and process data/readme.txt']
    sources = []
    for name in names:
        path, pin = source_root / 'pronto/zip' / name, members[name]
        if path.stat().st_size != pin['size'] or fingerprint(path) != pin['sha256']:
            raise ValueError(f'companion original differs: {name}')
        sources.append({'member': name, 'bytes': pin['size'], 'sha256': pin['sha256']})
    helper = ROOT / 'examples/context-register/pronto/verify_sources.py'
    spec = importlib.util.spec_from_file_location('pronto_original_cells', helper)
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    book = source_root / 'pronto/zip' / names[0]
    selected = {'Operation Log 0907': ['A18', 'B18', 'H18', 'H19', 'G20', 'A98', 'B98', 'H98', 'H99', 'G100'],
                'Operation Log 0912 ': ['B51', 'H51', 'H52', 'B52', 'G54', 'B56', 'H56', 'H57', 'B57', 'G59']}
    cells = {}
    for sheet, addresses in selected.items():
        actual = reader.xlsx_cells(book, sheet)
        cells[sheet] = {address: actual[address] for address in addresses}
    return {'sources': sources, 'literal_log_cells': cells,
            'limits': 'Nominal log settings and health/flow descriptions, not automatic joins to merged blocks or measured medians.'}


def segment(day, bounds, expected_label):
    a, b = bounds
    if not 0 <= a < b <= len(day['labels']) or set(day['labels'][a:b]) != {expected_label}:
        raise ValueError(f'rows {bounds}: expected only {expected_label}')
    return fc.historian_csv_text(day['times'][a:b], day['columns'], day['values'][a:b])


def describe(day, bounds):
    a, b = bounds
    return {'merged_rows_half_open': bounds, 'physical_lines_inclusive': [a + 2, b + 1], 'records': b - a,
            'first_time': day['times'][a].isoformat(sep=' '), 'last_time': day['times'][b - 1].isoformat(sep=' ')}


def execute(normal, score, fault_start, out):
    args = [sys.executable, '-S', str(ROOT / 'scripts/csv_normal_bands.py'),
            '--normal', str(normal), '--score', str(score), '--fault-start', str(fault_start),
            '--method', 'drift', '--fit-fraction', '0.5', '--out', str(out)]
    result = subprocess.run(args, capture_output=True, text=True, encoding='utf-8',
                            env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}, timeout=120)
    if result.returncode:
        raise ValueError(f'band CLI refused: {result.stderr.strip()}')
    return json.loads((out / 'csv_normal_bands.json').read_text(encoding='utf-8'))


def diagnostic(result):
    fault = result['scored']['fault']
    pre = fault['false_alarms_before_fault']
    hit = fault['detection_run3_row']
    return {'pre_fault_flagged': pre['flagged_samples'], 'pre_fault_records': pre['samples'],
            'detected': hit is not None, 'delay_seconds': fault['detection_run3_delay'],
            'criterion_met': hit is not None and hit >= fault['fault_start_row']
                             and pre['flagged_samples'] <= 0.005 * pre['samples'],
            'k': result['k'], 'k_target_met': result['k_selection']['target_met'],
            'warnings': result.get('warnings', []),
            'bad_scored_samples_by_tag': {tag: row['bad_samples'] for tag, row in result['scored']['per_tag'].items()}}


def produce(source_root, scratch):
    plan = json.loads((HERE / 'plan.json').read_text(encoding='utf-8'))
    if plan['method'] != 'drift' or plan['fit_fraction'] != 0.5:
        raise ValueError('this fixed experiment requires drift and fit_fraction 0.5')
    pins = json.loads((ROOT / 'data/corpus_pins.json').read_text(encoding='utf-8'))
    days = {day: source_day(day, source_root, pins) for day in ('2', '3', '4')}
    context = source_context(source_root)
    normal_blocks = []
    for name, day in days.items():
        changes = fc.label_changes(day['labels'])
        for i, (a, label) in enumerate(changes):
            b = changes[i + 1][0] if i + 1 < len(changes) else len(day['labels'])
            if label == 'Normal':
                medians = {tag: statistics.median(float(row[day['columns'].index(tag)])
                                                for row in day['values'][a:b]) for tag in ('AirIn', 'WaterIn')}
                normal_blocks.append({'day': name, **describe(day, [a, b]), 'column_medians': medians})
    cases = []
    for cfg in plan['cases']:
        day = days[cfg['day']]
        a, b = cfg['score']
        fs = cfg['fault']
        if not (cfg['early'][1] <= a and cfg['recent'][1] == a < fs < b):
            raise ValueError('baseline and score overlap or onset is outside score')
        # Independently validate every label before calling the band tool.
        segment(day, [a, fs], 'Normal')
        segment(day, [fs, b], cfg['label'])
        folder = scratch / cfg['id']
        folder.mkdir()
        score_text = fc.historian_csv_text(day['times'][a:b], day['columns'], day['values'][a:b])
        score = folder / 'common-score.csv'
        score.write_text(score_text, encoding='utf-8', newline='')
        choices = {}
        for variant in ('early', 'recent'):
            bounds = cfg[variant]
            text = segment(day, bounds, 'Normal')
            normal = folder / (variant + '-normal.csv')
            normal.write_text(text, encoding='utf-8', newline='')
            result = execute(normal, score, fs - a, folder / variant)
            split = bounds[0] + int((bounds[1] - bounds[0]) * 0.5)
            choices[variant] = {'normal': describe(day, bounds), 'fit_rows_half_open': [bounds[0], split],
                                'k_selection_rows_half_open': [split, bounds[1]],
                                'normal_csv_sha256': fingerprint(normal), 'diagnostic': diagnostic(result), 'result': result}
        # A distinct full-score reproduction; its population is not the paired comparison.
        r0, r1 = cfg['reference_score']
        segment(day, [r0, fs], 'Normal')
        segment(day, [fs, r1], cfg['label'])
        reference = folder / 'reference-full-score.csv'
        reference.write_text(fc.historian_csv_text(day['times'][r0:r1], day['columns'], day['values'][r0:r1]),
                             encoding='utf-8', newline='')
        ref = execute(folder / 'early-normal.csv', reference, fs - r0, folder / 'reference')
        cases.append({'id': cfg['id'], 'source_day': cfg['day'], 'fault_label': cfg['label'],
                      'score': describe(day, cfg['score']), 'common_score_sha256': fingerprint(score),
                      'fault_merged_row': fs, 'choices': choices,
                      'original_full_score_control': {'score': describe(day, cfg['reference_score']),
                                                      'diagnostic': diagnostic(ref), 'result': ref}})
    bound = ['scripts/csv_normal_bands.py', 'scripts/fetch_corpus.py', 'scripts/corpus_adapters.py',
             'examples/context-register/pronto/verify_sources.py']
    return {'schema': 'pronto-baseline-context-1', 'plan': plan, 'sources': [s for day in days.values() for s in day['sources']],
            'tool_hashes_lf': {n: hashlib.sha256((ROOT / n).read_bytes().replace(b'\r\n', b'\n')).hexdigest() for n in bound},
            'alignment_offsets': {n: day['offset'] for n, day in days.items()}, 'normal_blocks': normal_blocks,
            'companion_context': context, 'cases': cases}


def markdown(report):
    lines = ['# A normal label does not choose a baseline', '',
             'Fixed development diagnostic on existing PRONTO records. Recent candidates are shorter; context, length and',
             'noise history change together. No causal effect, prospective selection rule or operating approval is established.', '',
             '| Case | Choice | Normal records | Common pre-fault flags | Detection delay (s) | Criterion met | K target met |',
             '|---|---|---:|---|---:|---|---|']
    for case in report['cases']:
        for name, choice in case['choices'].items():
            d = choice['diagnostic']; delay = d['delay_seconds']
            delay_text = 'not detected' if delay is None else f'{delay:g}'
            lines.append(f"| {case['id']} | {name} | {choice['normal']['records']} | "
                         f"{d['pre_fault_flagged']}/{d['pre_fault_records']} | {delay_text} | "
                         f"{d['criterion_met']} | {d['k_target_met']} |")
    lines += ['', 'Criterion: three consecutive any-tag flags at/after the labelled onset and at most 0.5% of common',
              'pre-fault records flagged. K selection has its separate existing target. Both filters start at the common',
              'score interval with no carried history. No extra burn-in is removed within that interval. Moving the start',
              'changes warm-up and population relative to the original full-score controls; these paired counts cannot',
              'replace matrix counts. No failure is discarded.',
              'The JSON retains every band-tool result, warning, bad-sample count, source fingerprint and exact range.', '',
              '## Separate original full-score controls', '',
              'These use the earlier scoring starts and different denominators; they are not the paired comparison.', '',
              '| Case | Pre-fault flags | Detection delay (s) |', '|---|---|---:|']
    for case in report['cases']:
        d = case['original_full_score_control']['diagnostic']; delay = d['delay_seconds']
        lines.append(f"| {case['id']} | {d['pre_fault_flagged']}/{d['pre_fault_records']} | {delay if delay is not None else 'not detected'} |")
    lines += ['', '## Normal-labelled source blocks', '',
              'Medians describe the supplied columns, not verified setpoints or a resolved equipment identity.', '',
              '| Day | Merged rows [start,end) | Records | AirIn median | WaterIn median |', '|---|---|---:|---:|---:|']
    for block in report['normal_blocks']:
        med = block['column_medians']
        lines.append(f"| {block['day']} | {block['merged_rows_half_open']} | {block['records']} | {med['AirIn']:.6g} | {med['WaterIn']:.6g} |")
    lines += ['', 'No blocks are pooled. The row-based drift filter would treat samples across gaps as adjacent.',
              'No qualified contiguous multi-day normal baseline was established here; N056 remains open.', '',
              'Source: A. Stief et al., PRONTO, Zenodo 1341583, CC BY 4.0.',
              'https://zenodo.org/records/1341583 ; doi:10.1016/j.jprocont.2019.04.009.',
              'This derived comparison preserves source labels and values; it adds fixed window selection and statistical summaries.', '']
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source-root', type=Path, default=ROOT / 'data/external')
    choice = ap.add_mutually_exclusive_group(required=True)
    choice.add_argument('--check', action='store_true')
    choice.add_argument('--out', type=Path)
    args = ap.parse_args()
    if args.out is not None and (args.out.exists() or args.out.is_symlink()):
        ap.error('--out must be a fresh destination; preserve the existing report')
    try:
        with tempfile.TemporaryDirectory(prefix='pronto-baseline-') as tmp:
            report = produce(args.source_root, Path(tmp))
        rendered = {'results.json': json.dumps(report, indent=2, allow_nan=False) + '\n', 'results.md': markdown(report)}
        if args.check:
            for name, text in rendered.items():
                if (HERE / 'expected' / name).read_text(encoding='utf-8') != text:
                    raise ValueError(f'{name} differs from committed record; do not overwrite it to hide a changed result')
            print('Both records reproduce from twelve actual band CLIs. Source meaning and baseline applicability still need review.')
        else:
            args.out.mkdir(parents=True, exist_ok=False)
            for name, text in rendered.items():
                (args.out / name).write_text(text, encoding='utf-8', newline='\n')
            print('Wrote fixed baseline diagnostic; no detector, default or operating record was changed.')
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f'Refused: {exc}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
