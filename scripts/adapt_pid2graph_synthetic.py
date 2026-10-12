"""Bounded external-dataset example using the existing scorer and twin-1 pipeline.

No model comparison, no ground-truth text invented, no truth passed to extraction.
Third-party source/derived files remain under ignored data/external and runs/out/twin.
"""
import argparse
import os
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import sys
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

import score_pid2graph as scorer
from fetch_pid2graph import HttpRangeFile, BLOCK

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'data/dataset_adapters/pid2graph_synthetic.json'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def settings():
    cfg = json.loads(CONFIG.read_text())
    return cfg, ROOT / 'data/external/pid2graph' / cfg['archive_prefix']


class CheckedRangeFile(HttpRangeFile):
    """Fail closed rather than reading an ignored Range response as archive bytes."""
    def _block(self, n):
        if n not in self.cache:
            start, end = n * BLOCK, min((n + 1) * BLOCK, self.size) - 1
            req = urllib.request.Request(self.url, headers={'Range': f'bytes={start}-{end}'})
            with urllib.request.urlopen(req, timeout=120) as response:
                if response.status != 206 or response.headers.get('Content-Range') != f'bytes {start}-{end}/{self.size}':
                    raise ValueError('Server did not honor the exact HTTP Range; refusing full archive download')
                content = response.read(end - start + 2)
            if len(content) != end - start + 1:
                raise ValueError('Truncated or oversized HTTP Range response')
            self.cache[n] = content
            self.fetched += len(content)
        return self.cache[n]


def fetch(cfg, directory):
    remote = CheckedRangeFile(cfg['archive_url'])
    if remote.size != cfg['archive_bytes']:
        raise ValueError('Archive size changed; review source/version before downloading')
    z = zipfile.ZipFile(io.BufferedReader(remote, buffer_size=BLOCK))
    wanted = [cfg['archive_prefix'] + s + ext for s in cfg['development'] for ext in (cfg['source_image_extension'], '.graphml')]
    entries = [z.getinfo(name) for name in wanted]
    if sum(e.file_size for e in entries) > cfg['max_sample_bytes']:
        raise ValueError('Selected uncompressed sample exceeds configured bound')
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {'source': cfg['source'], 'license': cfg['license'], 'files': [], 'reserved_unopened': cfg['reserved_unopened']}
    for entry in entries:
        destination = directory / Path(entry.filename).name
        content = z.read(entry)  # zipfile validates CRC; names selected exactly, never extract arbitrary paths
        expected = cfg.get('expected_source_sha256', {}).get(destination.name)
        if expected and hashlib.sha256(content).hexdigest() != expected:
            raise ValueError(f'Source checksum changed: {destination.name}')
        destination.write_bytes(content)
        manifest['files'].append({'archive_path': entry.filename, 'bytes': len(content), 'sha256': digest(destination)})
    from PIL import Image
    for sheet in cfg['development']:
        source = directory / (sheet + cfg['source_image_extension'])
        target = directory / (sheet + '.png')
        with Image.open(source) as image:
            image.convert('RGB').save(target)
        manifest.setdefault('normalized_images', []).append({'source': source.name, 'png': target.name, 'sha256': digest(target)})
    manifest['network_bytes'] = remote.fetched
    (directory / 'sample_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest, indent=2))


def verify_sources(cfg, directory):
    for name, expected in cfg['expected_source_sha256'].items():
        if digest(directory / name) != expected:
            raise ValueError(f'Source checksum changed: {name}')


def source_context(graphml, png, prediction):
    root = ET.parse(graphml).getroot()
    names = {k.get('id'): k.get('attr.name') for k in root.findall('g:key', scorer.NS)}
    edges = []
    for edge in root.findall('g:graph/g:edge', scorer.NS):
        attrs = {names[d.get('key')]: d.text for d in edge.findall('g:data', scorer.NS)}
        edges.append({'source': edge.get('source'), 'target': edge.get('target'),
                      'source_line_style': attrs.get('edge_label'), 'semantic_line_type': None})
    nodes, _ = scorer.load_key(graphml, *scorer.png_size(png))
    keys = {k: v for k, v in nodes.items() if v['class'] in scorer.SCORED}
    predictions = scorer.valid_symbols(prediction)
    matched = scorer.match(predictions, keys, False, scorer.THRESHOLDS['rough'])
    comparisons = [{'prediction_id': item['id'], 'source_node_id': matched[item['id']],
                    'source_class': keys[matched[item['id']]]['class'], 'model_class': item['class'],
                    'engineering_interpretation_verified': False}
                   for item in predictions if item['id'] in matched]
    return {'source_edges': edges, 'class_comparisons': comparisons,
            'warning': 'Source/model classes remain separate; line style is not inferred to be process/signal semantics.'}


def oracle_prediction(graphml, png):
    width, height = scorer.png_size(png)
    nodes, adj = scorer.load_key(graphml, width, height)
    unknown = set(n['class'] for n in nodes.values()) - set(scorer.SCORED) - scorer.PASS_THROUGH - {'background'}
    if unknown:
        raise ValueError(f'Unmapped annotation classes: {sorted(unknown)}')
    for node in nodes.values():
        x0, y0, x1, y1 = node['box']
        if not (0 <= x0 <= x1 <= 1000 and 0 <= y0 <= y1 <= 1000):
            raise ValueError('Annotation box outside drawing or reversed')
    symbols = [{'id': sid, 'class': n['class'], 'box': n['box'], 'tag': None, 'confidence': None}
               for sid, n in nodes.items() if n['class'] in scorer.SCORED]
    links = [sorted(link) for link in scorer.asset_links(nodes, adj)]
    prediction = {'symbols': symbols, 'connections': [{'from': a, 'to': b} for a, b in sorted(links)]}
    root = ET.parse(graphml).getroot()
    key_names = {k.get('id'): k.get('attr.name') for k in root.findall('g:key', scorer.NS)}
    edge_labels = Counter(d.text for e in root.findall('g:graph/g:edge', scorer.NS)
                          for d in e.findall('g:data', scorer.NS) if key_names.get(d.get('key')) == 'edge_label')
    coverage = {'image_size_px': [width, height], 'nodes_by_class': dict(Counter(n['class'] for n in nodes.values())),
                'annotation_keys': [k.get('attr.name') for k in root.findall('g:key', scorer.NS)],
                'graph_edgedefault': root.find('g:graph', scorer.NS).get('edgedefault'),
                'edge_labels': dict(edge_labels), 'edge_style_preserved_by_existing_scorer': False,
                'asset_symbols': len(symbols), 'collapsed_undirected_links': len(links)}
    return prediction, coverage


def review_readiness(model):
    """Operational guard using the existing ops_review decisions; never auto-approve."""
    items = [x for collection in ('units', 'instruments', 'line_items', 'offpage_connectors', 'streams')
             for x in model.get(collection, [])]
    unreviewed = sum(x.get('ops_review', {}).get('status') not in ('confirmed', 'corrected', 'rejected') for x in items)
    blockers = ['Dataset class semantics have not been approved for operational asset roles',
                'Solid/non-solid line semantics are discarded by the current prediction contract',
                'No plant-specific point mapping, ranges, quality policy or deployment verification']
    if unreviewed:
        blockers.append(f'{unreviewed} assets/connections lack an operations review decision')
    return {'draft_review_exports_allowed': True, 'operational_export_allowed': False,
            'unreviewed_items': unreviewed, 'blockers': blockers,
            'review_workflow': 'docs/REVIEW_LOOP.md; apply_review.py --dry-run before applying reviewed CSV'}


def evaluate(cfg, directory, mode, run_dir, require_reviewed=False):
    import build_twin
    import generate
    run_dir.mkdir(parents=True, exist_ok=True)
    verify_sources(cfg, directory)
    reports = []
    contexts = {}
    for sheet in cfg['development']:
        png, key = directory / f'{sheet}.png', directory / f'{sheet}.graphml'
        truth, coverage = oracle_prediction(key, png)
        path = run_dir / f'{sheet}.json'
        if mode == 'oracle':
            record = {'tool': 'oracle-label-adapter', 'model': 'ground-truth, not AI extraction',
                      'evaluation_mode': 'oracle-label adaptation; not extraction accuracy', 'prediction': truth,
                      'image_sha256': digest(png), 'answer_key_sha256': digest(key)}
            path.write_text(json.dumps(record, indent=2) + '\n')
        else:
            record = json.loads(path.read_text())
            if record.get('prompt_sha256') != digest(ROOT / cfg['recipe']['prompt']) or record.get('image_sha256') != digest(png):
                raise ValueError('Extraction prompt/image hash differs from pinned recipe or sample')
            if record.get('model') != cfg['recipe']['model']:
                raise ValueError(f'Unexpected actual model metadata: {record.get("model")}')
            if not record.get('prediction'):
                raise ValueError(f'Extraction did not produce a prediction: {record.get("error")}')
        contexts[sheet] = source_context(key, png, record['prediction'])
        reports.append({'sheet': sheet, 'coverage': coverage, 'execution': {k: record.get(k) for k in ('tool', 'model', 'provider', 'access_path', 'reasoning_effort', 'recipe_deviation', 'image_sha256', 'prompt_sha256', 'seconds')}, 'score': scorer.score(key, record['prediction'], png)})
    label = 'pid2graph-synthetic-' + mode
    # Reuse existing converter directly so no OPEN100-calibrated confidence model is applied out of domain.
    execution_tool = 'oracle-label-adapter' if mode == 'oracle' else reports[0]['execution']['tool']
    model = build_twin.build(execution_tool, run_dir,
                             cfg['development'], directory, {}, label, parent_rule='linked')
    model['meta']['evaluation_mode'] = 'oracle-label adaptation; not extraction accuracy' if mode == 'oracle' else 'single pinned model extraction'
    model['meta']['dataset_source'] = cfg['source']
    model['meta']['dataset_license'] = cfg['license']
    model['meta']['source_edge_style_counts'] = {r['sheet']: r['coverage']['edge_labels'] for r in reports}
    model['meta']['extraction_transport'] = {r['sheet']: r['execution'] for r in reports}
    model['meta']['edge_style_warning'] = 'Existing collapsed adjacency discards solid/non-solid styles; streams are not verified process flow.'
    problems = generate.validate_twin(model)
    if problems:
        raise ValueError(f'Twin validation failed before export: {problems}')
    readiness = review_readiness(model)
    model['meta']['review_requirements'] = readiness
    if require_reviewed and not readiness['operational_export_allowed']:
        raise ValueError('Operational export blocked before writing outputs: ' + '; '.join(readiness['blockers']))
    out = ROOT / 'out/twin' / label / ('oracle' if mode == 'oracle' else 'codex')
    out.mkdir(parents=True, exist_ok=True)
    (out / 'source_annotation_context.json').write_text(json.dumps(contexts, indent=2) + '\n')
    (out / 'plant_model.json').write_text(json.dumps(model, indent=2) + '\n')
    written = generate.export_twin(model, out)
    symbol_tp = sum(r['score']['rough']['classified']['tp'] for r in reports)
    symbol_pred = sum(r['score']['rough']['classified']['predicted'] for r in reports)
    symbol_key = sum(r['score']['rough']['classified']['in_key'] for r in reports)
    link_tp = sum(r['score']['connections']['tp'] for r in reports)
    link_pred = sum(r['score']['connections']['predicted'] for r in reports)
    link_key = sum(r['score']['connections']['in_key'] for r in reports)
    corrections = sum(r['score']['review_load']['corrections'] for r in reports)
    key_items = sum(r['score']['review_load']['key_items'] for r in reports)
    confusions = Counter((item['source_class'], item['model_class']) for context in contexts.values() for item in context['class_comparisons'])
    aggregate = {'source_model_class_agreement': [{'source_class': source, 'model_class': target, 'count': count} for (source, target), count in sorted(confusions.items())],
                 'symbol_classification_micro': scorer.prf(symbol_tp, symbol_pred, symbol_key),
                 'connections_micro': scorer.prf(link_tp, link_pred, link_key),
                 'review_load': {'corrections': corrections, 'key_items': key_items, 'per_100': round(100 * corrections / key_items, 2) if key_items else 0}}
    report = {'dataset': cfg['dataset'], 'mode': model['meta']['evaluation_mode'], 'source': cfg['source'],
              'license': cfg['license'], 'development_only': cfg['development'], 'reserved_unopened': cfg['reserved_unopened'],
              'recipe': cfg['recipe'], 'prompt_sha256': digest(ROOT / cfg['recipe']['prompt']), 'sheets': reports,
              'review_readiness': readiness, 'aggregate': aggregate, 'twin_summary': model['summary'], 'twin_validation': problems, 'exports': written,
              'gaps': {'missing_tags': sum(x.get('tag') is None for k in ('units', 'instruments', 'line_items', 'offpage_connectors') for x in model[k]),
                       'instruments_without_unit': sum(not x.get('unit') for x in model['instruments']),
                       'streams_unknown_direction': sum(x.get('direction') == 'unknown' for x in model['streams'])}}
    destination = ROOT / 'out' / f'pid2graph_synthetic_{mode}_adaptation.json'
    destination.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


def extract(cfg, directory, run_dir):
    """Single first-round recipe via existing ChatGPT subscription; never load keys."""
    import re
    import shutil
    import subprocess
    import tempfile
    import time
    from datetime import datetime, timezone
    from run_extraction import parse_json
    run_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = ROOT / cfg['recipe']['prompt']
    prompt = prompt_path.read_text()
    for sheet in cfg['development']:
        record_path = run_dir / f'{sheet}.json'
        if record_path.exists():
            raise ValueError(f'Refusing overwrite/retry of first attempt: {record_path}')
        source = directory / f'{sheet}.png'
        with tempfile.TemporaryDirectory(prefix='pid-synthetic-extraction-') as tmp:
            work = Path(tmp)
            image, reply = work / 'drawing.png', work / 'reply.json'
            shutil.copyfile(source, image)
            command = ['codex', 'exec', '--ephemeral', '--ignore-user-config', '--skip-git-repo-check',
                       '-s', 'read-only', '--disable', 'shell_tool', '--disable', 'unified_exec',
                       '-c', 'web_search="disabled"', '-c', f'sqlite_home="{work / "state"}"',
                       '-c', f'log_dir="{work / "logs"}"', '-C', str(work), '-i', str(image), '-o', str(reply),
                       '-m', cfg['recipe']['model'], '-']
            started = time.time()
            try:
                environment = dict(os.environ, XDG_RUNTIME_DIR=str(work / 'runtime'))
                (work / 'runtime').mkdir()
                result = subprocess.run(command, input=prompt, text=True, capture_output=True, timeout=600, env=environment)
                log = result.stderr + result.stdout
                raw = reply.read_text() if reply.exists() else None
                reported_model = re.search(r'^model:\s*(\S+)', log, re.M)
                reported_provider = re.search(r'^provider:\s*(\S+)', log, re.M)
                parsed, parse_error = parse_json(raw)
                record = {'tool': 'codex', 'model': reported_model.group(1) if reported_model else None,
                          'provider': reported_provider.group(1) if reported_provider else None,
                          'requested_model': cfg['recipe']['model'], 'access_path': 'existing ChatGPT subscription, codex exec',
                          'prediction': parsed, 'raw_text': raw, 'parse_error': parse_error,
                          'error': None if result.returncode == 0 and raw else log[-4000:], 'exit_code': result.returncode}
            except subprocess.TimeoutExpired:
                record = {'tool': 'codex', 'model': None, 'prediction': None, 'error': '600-second timeout'}
                log = 'timeout'
            record.update({'sheet': sheet, 'prompt_file': cfg['recipe']['prompt'], 'prompt_sha256': digest(prompt_path),
                           'image_sha256': digest(source), 'seconds': round(time.time() - started, 2),
                           'ran_at': datetime.now(timezone.utc).isoformat(), 'api_spend_usd': 0,
                           'isolation': 'temporary image-only working folder; read-only; shell/unified_exec/web search disabled; user config ignored'})
            record_path.write_text(json.dumps(record, indent=2) + '\n')
            (run_dir / f'{sheet}.log').write_text(log)
            print(json.dumps({k: record.get(k) for k in ('sheet', 'model', 'provider', 'seconds', 'error')}), flush=True)
            if record.get('error') or record.get('model') != cfg['recipe']['model']:
                raise RuntimeError('Pinned extraction unavailable or model unverified; recorded first attempt, stopped')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['fetch', 'oracle', 'extract', 'evaluate'])
    parser.add_argument('--run-dir', type=Path)
    parser.add_argument('--require-reviewed', action='store_true', help='Fail before twin export while operational review requirements remain unresolved')
    args = parser.parse_args()
    cfg, directory = settings()
    if args.mode == 'fetch':
        fetch(cfg, directory)
    else:
        run_dir = args.run_dir or ROOT / 'runs/pid2graph-synthetic-adaptation' / ('oracle' if args.mode == 'oracle' else 'codex')
        if args.mode == 'extract':
            extract(cfg, directory, run_dir)
        else:
            evaluate(cfg, directory, args.mode, run_dir, args.require_reviewed)


if __name__ == '__main__':
    main()
