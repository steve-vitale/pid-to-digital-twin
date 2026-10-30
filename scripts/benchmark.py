"""Re-score versioned corpus cases and compare saved model/method runs by task, family and identical coverage.

Offline; no model calls, downloads or executable commands from manifests. See CONTRIBUTING.md.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parent.parent
TASKS = {'drawing-extraction': 'pid2graph-v1', 'description-facts': 'native-facts-v1'}
TEXT = {'.json', '.graphml', '.xml', '.md', '.txt', '.csv', '.py'}
FIELDS = {'units': ('id', ('type',)), 'streams': ('id', ('from', 'to')),
          'instruments': ('tag', ('unit', 'stream', 'variable', 'uom')),
          'final_elements': ('tag', ('unit', 'stream', 'uom')),
          'manual_valves': ('tag', ('unit', 'stream')),
          'relief_devices': ('tag', ('unit', 'stream')),
          'controllers': ('tag', ('unit', 'measurement'))}


class ProvenanceError(ValueError):
    pass


def bound(condition, message):
    if not condition:
        raise ProvenanceError(message)


def check_saved_metadata(record, run, case):
    """A schema label is not permission to discard conflicting recorded provenance."""
    if record.get('schema') == 'pid-prediction/1':
        bound('prediction' in record or bool(record.get('error') or record.get('parse_error')),
              'Saved pid-prediction envelope needs prediction or an explicit failure')
    known = (record.get('schema') == 'pid-prediction/1' and record.get('prediction') is not None
             and not record.get('error') and not record.get('parse_error'))
    for field, expected in [('model', run['model']['id']),
                            ('image_sha256', case['files']['input']['sha256'])]:
        if known or field in record:
            bound(record.get(field) == expected, 'Saved ' + field + ' disagrees with run/case')
    if known or 'prompt_sha256' in record:
        prompts = [r['sha256'] for r in run['recipe'] if r.get('role') == 'main_prompt']
        bound(len(prompts) == 1 and record.get('prompt_sha256') == prompts[0], 'Saved main prompt disagrees with its recipe role')
    if 'tool' in record:
        bound(record['tool'] == run.get('recorded_tool'), 'Saved tool disagrees with recorded_tool')
    tiling, tracer = record.get('tiling'), record.get('tracer')
    if isinstance(tiling, dict):
        if 'preface_sha256' in tiling:
            prefaces = [r['sha256'] for r in run['recipe'] if r.get('role') == 'tile_preface']
            bound(len(prefaces) == 1 and tiling['preface_sha256'] == prefaces[0], 'Saved tile preface disagrees with its recipe role')
        for field, setting in [('grid', 'tiles'), ('overlap', 'overlap')]:
            if field in tiling:
                bound(tiling[field] == run['configuration'].get(setting), 'Saved tiling disagrees with configuration.' + setting)
    if isinstance(tracer, dict) and 'mode' in tracer:
        bound(tracer['mode'] == run['configuration'].get('trace'), 'Saved tracer disagrees with configuration.trace')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def strict_pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, 'Duplicate JSON key')
        result[key] = value
    return result


def read_json(path):
    with path.open('rb') as stream:
        raw = stream.read(16 * 1024 * 1024 + 1)
    require(len(raw) <= 16 * 1024 * 1024, 'JSON input exceeds 16 MiB')
    def invalid(value):
        raise ValueError('Non-finite JSON number: ' + value)
    value = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=strict_pairs, parse_constant=invalid)
    encoded(value)  # Also refuse overflow and invalid Unicode before reporting.
    return value


def file_hash(path):
    raw = path.read_bytes()
    return digest(raw.replace(b'\r\n', b'\n') if path.suffix.lower() in TEXT else raw)


def local(root, value):
    require(isinstance(value, str) and value and not Path(value).is_absolute(), 'Use a root-relative file path')
    path = (root / value).resolve()
    require(path.is_relative_to(root.resolve()), 'File reference escapes the selected root')
    return path


def reference(root, ref, missing=False):
    require(isinstance(ref, dict) and {'path', 'sha256'} <= set(ref) <= {'path', 'sha256', 'role'},
            'File reference needs path and sha256, with optional recipe role')
    if 'role' in ref:
        require(isinstance(ref['role'], str) and ref['role'], 'Recipe role must be nonempty text')
    require(isinstance(ref['sha256'], str) and len(ref['sha256']) == 64 and
            all(c in '0123456789abcdef' for c in ref['sha256']), 'Invalid file fingerprint')
    path = local(root, ref['path'])
    if missing and not path.exists():
        return None
    require(path.is_file(), 'Referenced file is unavailable: ' + ref['path'])
    require(file_hash(path) == ref['sha256'], 'Stale file fingerprint: ' + ref['path'])
    return path


def text_fields(row, fields, label):
    require(isinstance(row, dict), label + ' must be an object')
    for field in fields:
        require(isinstance(row.get(field), str) and row[field].strip(), label + '.' + field + ' must be nonempty text')


def native_facts(value):
    """Literal identity/type/placement/connection/control fields only; no name or source interpretation score."""
    require(isinstance(value, dict), 'Native answer must be an object')
    model = value.get('model', value)
    require(isinstance(model, dict), 'Native model must be an object')
    require(any(k in model for k in FIELDS), 'Answer has no supported native-model sections')
    facts = []
    for section, (identity, fields) in FIELDS.items():
        rows = model.get(section, [])
        require(isinstance(rows, list), section + ' must be a list')
        seen = set()
        for row in rows:
            text_fields(row, (identity,), section)
            ident = row[identity]
            require(ident not in seen, 'Duplicate native record identity: ' + ident)
            seen.add(ident)
            facts.append([section, ident, 'exists', True])
            for field in fields:
                if field in row:
                    require(isinstance(row[field], str) or row[field] is None, 'Native fact fields must be text or null')
                    facts.append([section, ident, field, row[field]])
            if section == 'controllers':
                output = row.get('output', {})
                require(isinstance(output, dict), 'Controller output must be an object')
                for field, target in output.items():
                    if field == 'split_range':
                        require(isinstance(target, list), 'split_range must be a list')
                        for item in target:
                            facts.append([section, ident, 'output.final_element', item])
                    else:
                        facts.append([section, ident, 'output.' + field, target])
    return {json.dumps(f, sort_keys=True, ensure_ascii=False, allow_nan=False) for f in facts}


def counts(tp, predicted, truth):
    return {'tp': tp, 'predicted': predicted, 'truth': truth}


def metrics(total):
    result = {}
    for name, row in total.items():
        tp, pred, truth = row['tp'], row['predicted'], row['truth']
        result[name] = {'precision': tp / pred if pred else 0.0,
                        'recall': tp / truth if truth else None,
                        'f1': 2 * tp / (pred + truth) if pred + truth else None}
    return result


def score_case(task, files, prediction):
    if task == 'drawing-extraction':
        import score_pid2graph as scorer
        value = prediction if prediction is not None else {'symbols': [], 'connections': []}
        require(isinstance(value, dict) and isinstance(value.get('symbols'), list) and
                isinstance(value.get('connections'), list), 'Expected symbols/connections lists')
        scored = scorer.score(files['key'], value, files['input'])
        result = {}
        for name, row in (('symbols_rough', scored['rough']['classified']),
                          ('symbols_strict', scored['strict']['classified']), ('networks', scored['connections'])):
            result[name] = counts(row['tp'], row['predicted'], row['in_key'])
        return result, {'ignored_or_malformed_symbols': scored['malformed_symbols']}
    expected = read_json(files['key'])
    require(isinstance(expected, dict) and set(expected) == {'facts'}, 'Fact key needs exactly facts')
    require(isinstance(expected['facts'], list) and expected['facts'], 'Fact key must not be empty')
    require(all(isinstance(f, list) and len(f) == 4 and f[0] in FIELDS and
                isinstance(f[1], str) and f[1] and isinstance(f[2], str) for f in expected['facts']),
            'Fact key needs [section, identity, field, value] atoms')
    truth = {json.dumps(f, sort_keys=True, ensure_ascii=False, allow_nan=False) for f in expected['facts']}
    require(len(truth) == len(expected['facts']), 'Fact key contains duplicates')
    actual = native_facts(prediction) if prediction is not None else set()
    result = {'facts': counts(len(actual & truth), len(actual), len(truth))}
    for section in FIELDS:
        want = {f for f in truth if json.loads(f)[0] == section}
        got = {f for f in actual if json.loads(f)[0] == section}
        result[section] = counts(len(want & got), len(got), len(want))
    return result, {'missing_facts': [json.loads(f) for f in sorted(truth - actual)],
                    'unexpected_facts': [json.loads(f) for f in sorted(actual - truth)]}


def evaluate(suite_path, root=ROOT):
    suite = read_json(suite_path)
    text_fields(suite, ('id', 'version', 'task', 'protocol', 'registration'), 'suite')
    task = suite['task']
    require(task in TASKS, 'Unsupported task; add a tested scorer adapter before registering this task')
    sources = ['benchmark.py'] + (['score_pid2graph.py', 'evaluate_vendor.py', 'replicate_stats.py',
                                 'score_tags.py', 'test_scorer_controls.py'] if task == 'drawing-extraction' else [])
    code_hashes = {p: file_hash(Path(__file__).parent / p) for p in sources}
    require(isinstance(suite.get('cases'), list) and suite['cases'], 'Suite needs cases')
    require(isinstance(suite.get('runs'), list) and suite['runs'], 'Suite needs run manifest paths')
    cases, loaded, controls = {}, {}, {}
    for case in suite['cases']:
        text_fields(case, ('id', 'family', 'split', 'evidence', 'source_url', 'license', 'key_author'), 'case')
        require(case['split'] in ('development', 'validation', 'held-out', 'synthetic-control'), 'Unknown case split')
        require(case['id'] not in cases, 'Duplicate case ID')
        required = {'input', 'key'} | ({'expected'} if task == 'description-facts' else set())
        require(set(case.get('files', {})) == required, 'Case needs ' + ', '.join(sorted(required)) + ' references')
        files = {k: reference(root, v) for k, v in case['files'].items()}
        # Validate keys independently: a bad key must stop evaluation, never become a model failure.
        score_case(task, files, None)
        if task == 'drawing-extraction':
            import evaluate_vendor as vendor
            import score_pid2graph as scorer
            table = {}
            for name, pred in vendor.controls_for(files['key'], files['input']).items():
                detail = scorer.score(files['key'], pred, files['input'])
                row = vendor.sheet_metrics(detail)
                if name == 'shifted':
                    row['_strict_located_tp'] = detail['strict']['located']['tp']
                    row['_strict_located_key'] = detail['strict']['located']['in_key']
                table[name] = row
            table['_key_links'] = detail['connections']['in_key']
            failures = vendor.check_controls({case['id']: table}, {k: table[k] for k in vendor.CONTROL_ORDER})
            require(not failures, 'Known-answer control failed: ' + '; '.join(failures))
            require(table['perfect']['key_items'] > 0, 'Drawing key has no scored items')
            controls[case['id']] = table
        else:
            golden, _ = score_case(task, files, read_json(files['expected']))
            row = golden['facts']
            require(row['truth'] > 0 and row['tp'] == row['truth'] == row['predicted'], 'Expected model does not exactly match the fact key')
            controls[case['id']] = {'expected': golden, 'empty': score_case(task, files, None)[0]}
        cases[case['id']], loaded[case['id']] = case, files
    results, submissions = [], []
    run_ids = set()
    used_artifacts = set()
    for path in suite['runs']:
        run_path = local(root, path)
        run = read_json(run_path)
        text_fields(run, ('id', 'ran_at', 'interface', 'method', 'provenance'), 'run')
        text_fields(run.get('model'), ('provider', 'id', 'version'), 'model')
        require(run['id'] not in run_ids, 'Duplicate run ID')
        run_ids.add(run['id'])
        attempted = run.get('cases')
        require(isinstance(attempted, list) and attempted and all(isinstance(c, str) and c in cases for c in attempted),
                'Run needs declared attempted case IDs')
        require(len(set(attempted)) == len(attempted), 'Duplicate attempted case')
        predictions = run.get('predictions')
        require(isinstance(predictions, dict) and not set(predictions) - set(attempted), 'Prediction is outside the attempted set')
        require(isinstance(run.get('configuration'), dict), 'Run needs a configuration object (unknown values stay explicit)')
        require(isinstance(run.get('recipe'), list) and run['recipe'], 'Run needs pinned prompt/recipe files')
        for ref in run['recipe']:
            reference(root, ref)
        submissions.append({'id': run['id'], 'path': path, 'sha256': file_hash(run_path)})
        buckets = defaultdict(list)
        for cid in sorted(attempted):
            case = cases[cid]
            buckets[(case['family'], case['split'], case['evidence'])].append(cid)
        for (family, split, evidence), ids in sorted(buckets.items()):
            cohort = {'task': task, 'scoring_contract': TASKS[task], 'protocol': suite['protocol'],
                      'scorer_code_sha256': code_hashes, 'cases': [cases[cid] for cid in ids]}
            rows, total = [], {}
            for cid in ids:
                case = cases[cid]
                ref = predictions.get(cid)
                prediction, status = None, 'missing'
                note = None
                recorded_run_at = None
                reported = {'seconds': None, 'cost_usd': None, 'cost_usd_notional': None}
                if ref is not None:
                    # Changed bytes are a provenance error; missing attempted output is a scored failure.
                    artifact = reference(root, ref, missing=True)
                    if artifact:
                        stat = artifact.stat()
                        file_identity = (stat.st_dev, stat.st_ino) if stat.st_ino else str(artifact)
                        identity = (json.dumps(run['model'], sort_keys=True), run['interface'], run['method'],
                                    digest(encoded(run['configuration'])), cid, file_identity)
                        require(identity not in used_artifacts, 'Same answer file reused as a model/method replicate')
                        used_artifacts.add(identity)
                        try:
                            record = read_json(artifact)
                            require(isinstance(record, dict), 'Answer must be a JSON object')
                            metadata = {'schema', 'model', 'tool', 'image_sha256', 'prompt_sha256', 'tiling', 'tracer'}
                            if 'prediction' in record or (task == 'drawing-extraction' and metadata.intersection(record)):
                                check_saved_metadata(record, run, case)
                            reported = {k: record.get(k) for k in reported}
                            recorded_run_at = record.get('ran_at')
                            prediction = record.get('prediction', record)
                            status = 'failed' if prediction is None or record.get('error') or record.get('parse_error') else 'ok'
                            if status != 'ok':
                                prediction = None
                        except ProvenanceError:
                            raise
                        except (ValueError, UnicodeError, RecursionError) as exc:
                            status, note = 'invalid-answer', str(exc)
                try:
                    scored, diagnostics = score_case(task, loaded[cid], prediction)
                except (ValueError, TypeError, KeyError, AttributeError, IndexError, OverflowError) as exc:
                    # Key and inputs were checked above. A malformed attempted answer earns an empty answer's score.
                    scored, diagnostics = score_case(task, loaded[cid], None)
                    status, note = 'invalid-answer', str(exc)
                for metric, row in scored.items():
                    summed = total.setdefault(metric, counts(0, 0, 0))
                    for field in summed:
                        summed[field] += row[field]
                rows.append({'case': cid, 'status': status, 'note': note, 'counts': scored, 'diagnostics': diagnostics,
                             'reported_resources': reported, 'recorded_run_at': recorded_run_at,
                             'prediction_ref': ref})
            results.append({'run': run['id'], 'model': run['model'], 'interface': run['interface'],
                            'method': run['method'], 'configuration': run['configuration'], 'recipe': run['recipe'],
                            'ran_at': run['ran_at'], 'provenance': run['provenance'], 'cohort': digest(encoded(cohort)),
                            'family': family, 'split': split, 'evidence': evidence, 'case_count': len(ids),
                            'not_attempted': sorted(set(cases) - set(attempted)), 'rows': rows,
                            'counts': total, 'metrics': metrics(total)})
    groups = defaultdict(list)
    for result in results:
        identity = {k: result[k] for k in ('cohort', 'model', 'interface', 'method', 'configuration', 'recipe')}
        groups[digest(encoded(identity))].append(result)
    summary = []
    for group_id, repeats in sorted(groups.items()):
        first = repeats[0]
        row = {k: first[k] for k in ('model', 'interface', 'method', 'configuration', 'cohort', 'family', 'split', 'evidence', 'case_count')}
        row.update(group=group_id, runs=[r['run'] for r in repeats], replicates=len(repeats), metrics={})
        for metric in first['metrics']:
            values = [r['metrics'][metric]['f1'] for r in repeats]
            values = [v for v in values if v is not None]
            row['metrics'][metric] = {'mean_f1': statistics.mean(values) if values else None,
                                      'min_f1': min(values) if values else None, 'max_f1': max(values) if values else None,
                                      'stdev_f1': statistics.stdev(values) if len(values) > 1 else None}
        summary.append(row)
    return {'schema': 'task-benchmark-1', 'suite': suite['id'], 'suite_version': suite['version'], 'task': task,
            'registration': suite['registration'], 'scoring_contract': TASKS[task],
            'suite_sha256': file_hash(suite_path), 'code_sha256': code_hashes,
            'hash_method': 'SHA256; CRLF normalized to LF for declared text extensions, raw binary otherwise',
            'case_total': len(cases), 'controls': controls, 'submissions': submissions, 'results': results, 'summary': summary,
            'limits': ['Compare only the same cohort and scoring contract; model identity is contributor-declared, not provider-attested.',
                       'Each replicate pools counts over its cases; summary reports mean/range/stdev over replicates, not a significance test or winner.',
                       'Missing/failed attempted answers score empty; unattempted cases remain visible and create different comparison cohorts.',
                       'Public keys and retrospective registration do not establish blindness. Synthetic controls and corrected/development results are separate.',
                       'Description facts grade literal selected fields only: no prose names, source validity, dimensions, limits, layout quality or plant truth.']}


def markdown(report):
    def safe(value):
        return str(value).replace('|', '\\|').replace('\n', ' ').replace('\r', ' ')
    lines = ['# Task results: ' + safe(report['suite']), '',
             'Task: `' + report['task'] + '`. ' + safe(report['registration']), '',
             'Only rows with the same cohort are directly comparable. See JSON for exact cases, failures, fingerprints and configurations.', '',
             '| Model / version | Method / interface | Family / split / evidence | Cohort | Cases | Replicates | Metric | Mean F1 | Min–max | SD |',
             '|---|---|---|---|---|---|---|---|---|---|']
    def fmt(value):
        return 'unavailable' if value is None else f'{value:.4f}'
    for row in report['summary']:
        for metric, values in row['metrics'].items():
            if values['mean_f1'] is None or (report['task'] == 'description-facts' and metric == 'facts'):
                continue
            model = row['model']['id'] + ' / ' + row['model']['version']
            lines.append('| ' + ' | '.join(safe(v) for v in [model, row['method'] + ' / ' + row['interface'],
                row['family'] + ' / ' + row['split'] + ' / ' + row['evidence'], row['cohort'][:12], row['case_count'],
                row['replicates'], metric, fmt(values['mean_f1']), fmt(values['min_f1']) + '–' + fmt(values['max_f1']), fmt(values['stdev_f1'])]) + ' |')
    lines += ['', '## Coverage and failures', '']
    for row in report['results']:
        bad = [r['case'] + ':' + r['status'] for r in row['rows'] if r['status'] != 'ok']
        lines.append('- ' + safe(row['run']) + ' (' + safe(row['family']) + ' / ' + safe(row['split']) + '): ' +
                     str(row['case_count']) + ' cases in this family/cohort; suite total ' + str(report['case_total']) +
                     '; suite-wide unattempted: ' + safe(', '.join(row['not_attempted']) or 'none') +
                     '; failed attempted answers: ' + safe(', '.join(bad) or 'none') + '.')
        for case in row['rows']:
            for label in ('missing_facts', 'unexpected_facts'):
                facts = case['diagnostics'].get(label, [])
                if facts:
                    lines.append('  ' + safe(case['case']) + ' ' + label + ': ' +
                                 safe(json.dumps(facts, ensure_ascii=False)) + '.')
    lines += ['', '## Limits', ''] + ['- ' + limit for limit in report['limits']] + ['']
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument('--suite', type=Path)
    selection.add_argument('--registry', type=Path, help='check every registered suite/report offline')
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--out', type=Path, help='new output prefix, or committed prefix with --check')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.registry:
            registry = read_json(args.registry)
            require(isinstance(registry.get('reports'), list) and registry['reports'], 'Registry needs reports')
            for entry in registry['reports']:
                result = main(['--suite', str(local(args.root, entry['suite'])), '--root', str(args.root),
                               '--out', str(local(args.root, entry['report'])), '--check'])
                require(result == 0, 'Registered benchmark report failed: ' + entry['suite'])
            return 0
        require(args.out is not None, '--out is required with --suite')
        report = evaluate(args.suite, args.root)
        payloads = {args.out.with_suffix('.json'): encoded(report), args.out.with_suffix('.md'): markdown(report).encode('utf-8')}
        if args.check:
            changed = [str(p) for p, raw in payloads.items() if not p.is_file() or p.read_bytes().replace(b'\r\n', b'\n') != raw]
            require(not changed, 'Report stale or missing: ' + ', '.join(changed))
        else:
            require(all(not p.exists() and not p.is_symlink() for p in payloads), 'Choose a new report prefix; existing reports are retained')
            require(all(p.parent.is_dir() for p in payloads), 'Output parent must exist')
            protected = {args.suite.resolve()}
            require(not any(p.resolve() in protected for p in payloads), 'Report aliases the suite input')
            for path, raw in payloads.items():
                with path.open('xb') as stream:
                    stream.write(raw)
        print(f'{report["suite"]}: {len(report["results"])} run/cohort results, {len(report["summary"])} model/method groups')
        return 0
    except (ValueError, OSError, UnicodeError, RecursionError, TypeError, KeyError, AttributeError, OverflowError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
