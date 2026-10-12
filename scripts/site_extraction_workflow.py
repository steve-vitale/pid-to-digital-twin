"""One PNG -> frozen extraction handoff -> unverified local review bundle.

prepare/collect are offline. execute ALONE sends the drawing and prompt to OpenAI
through the already authenticated Codex CLI subscription. Obtain data-sharing and
organizational authorization first; a CLI flag is not permission. No API keys,
automatic retries, fallback, model comparisons, gateway or deployment actions.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import tempfile

import import_site_drawing as intake

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'site-extraction-job-1'
RECIPE = {'id': 'synthetic-adaptation-whole-sheet-v1', 'tool': 'codex',
          'model': 'gpt-6.1-sol', 'prompt': 'extraction/prompt.md',
          'prompt_sha256': 'c16899efee9c3769e51b17063183bccb869544dba36b439eaa1fa42ffe7e132b',
          'tiles': None, 'tracing': False, 'parent_rule': 'linked'}
WARNING = ('UNVERIFIED DRAFT ONLY. No operational approval, point mapping or plant import. '
           'Readiness metadata is descriptive, not an interlock in independent exporters.')
IMPLEMENTATIONS = ('scripts/site_extraction_workflow.py', 'scripts/adapt_pid2graph_synthetic.py',
                   'scripts/run_extraction.py', 'scripts/import_site_drawing.py',
                   'scripts/build_twin.py', 'scripts/generate.py', 'scripts/pi_mapping.py')


def read_json(path):
    return intake.strict_json(intake.read_bounded(Path(path), intake.MAX_JSON_BYTES))


def write_json(path, value):
    intake.write_json(path, value)


def now():
    return datetime.now(timezone.utc).isoformat()


def new_output(path):
    path = Path(path).absolute()
    intake.require(not path.exists() and not path.is_symlink(), f'Output already exists: {path}')
    intake.require(path.parent.is_dir(), 'Output parent must exist')
    return path


def code_hashes():
    return {name: intake.digest((ROOT / name).read_bytes()) for name in IMPLEMENTATIONS}


def git_revision():
    # Read metadata only: prepare/check/collect never launch subprocesses.
    try:
        git = ROOT / '.git'
        head = (git / 'HEAD').read_text().strip()
        if head.startswith('ref: '):
            ref = head[5:]
            target = git / ref
            if target.is_file():
                head = target.read_text().strip()
            else:
                head = next(line.split()[0] for line in (git / 'packed-refs').read_text().splitlines()
                            if line.endswith(' ' + ref))
        return head if len(head) == 40 else None
    except (OSError, StopIteration):
        return None


def prepare(image, drawing_id, revision, page, out, check_only=False):
    out = new_output(out)
    source = Path(image).resolve()
    raw = intake.read_bounded(source, intake.MAX_IMAGE_BYTES)
    dims = intake.png_dimensions(raw)
    identity = {'drawing_id': drawing_id, 'revision': revision, 'page': page}
    for key in ('drawing_id', 'revision'):
        intake.text_field(identity, key)
    intake.require(type(page) is int and page > 0, 'page must be a positive integer')
    prompt = (ROOT / RECIPE['prompt']).read_bytes()
    intake.require(intake.digest(prompt) == RECIPE['prompt_sha256'], 'Pinned prompt changed; stop and review recipe')
    manifest = {'schema_version': SCHEMA, 'recipe': RECIPE, 'drawing': identity,
                'image_sha256': intake.digest(raw), 'image_bytes': len(raw), 'image_size_px': dims,
                'original_filename': source.name, 'prepared_at': now(),
                'repository_head': git_revision(), 'repository_dirty': 'not inspected; implementation hashes are authoritative',
                'implementation_sha256': code_hashes(), 'warning': WARNING,
                'source_validation': 'PNG container/CRC only; pixel decoding, readability and revision authority unverified'}
    if check_only:
        return {'valid': True, 'written': False, 'model_called': False, 'job': manifest}
    stage = Path(tempfile.mkdtemp(prefix='.site-job-', dir=out.parent))
    try:
        (stage / 'source').mkdir()
        (stage / 'source/0.png').write_bytes(raw)
        (stage / 'source/prompt.md').write_bytes(prompt)
        write_json(stage / 'job.json', manifest)
        (stage / 'attempts').mkdir()
        (stage / 'READ_ME.txt').write_text(__doc__ + '\n' + WARNING + '\n\n'
            'Next: explicitly authorize execute, or collect a matching preserved run record.\n'
            'Keep this entire job private; preparation is not an extraction run.\n', encoding='utf-8')
        new_output(out)
        os.rename(stage, out)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return {'valid': True, 'written': True, 'model_called': False, 'job': str(out),
            'next_external_action_argv': ['python', 'scripts/site_extraction_workflow.py', 'execute', '--job', str(out)],
            'authorization_warning': 'Execution sends this drawing to OpenAI using your configured subscription. Verify permission and account/billing first; preparation grants none.'}


def load_job(directory):
    directory = Path(directory).resolve()
    job = read_json(directory / 'job.json')
    intake.require(isinstance(job, dict) and job.get('schema_version') == SCHEMA, 'Unsupported job')
    intake.require(job.get('recipe') == RECIPE, 'Recipe mismatch')
    intake.require(intake.digest(intake.read_bounded(directory / 'source/0.png', intake.MAX_IMAGE_BYTES))
                   == job.get('image_sha256'), 'Prepared image changed')
    intake.require(intake.digest((directory / 'source/prompt.md').read_bytes()) == RECIPE['prompt_sha256'],
                   'Prepared prompt changed')
    for key in ('drawing_id', 'revision'):
        intake.text_field(job['drawing'], key)
    intake.require(type(job['drawing'].get('page')) is int and job['drawing']['page'] > 0, 'Invalid page')
    return directory, job


def validate_record(record, job, evidence):
    intake.require(isinstance(record, dict), 'Record must be an object')
    intake.require(not record.get('error') and not record.get('parse_error'), 'Failed extraction record')
    exit_code = record.get('exit_code')
    intake.require(exit_code is None or type(exit_code) is int and exit_code == 0, 'Invalid or nonzero process exit')
    intake.require(evidence == 'contract-fixture' or not record.get('synthetic_contract_fixture'),
                   'Synthetic contract evidence cannot be relabeled as actual extraction')
    intake.require(record.get('image_sha256') == job['image_sha256'], 'Result image hash mismatch')
    intake.require(record.get('prompt_sha256') == RECIPE['prompt_sha256'], 'Result prompt hash mismatch')
    intake.require(record.get('model') == RECIPE['model'], 'Reported model missing or differs from frozen recipe')
    intake.require(not record.get('tiling') and not record.get('tracing'), 'Result is not the frozen whole-sheet recipe')
    if evidence == 'native-replay':
        intake.require(record.get('tool') == 'codex-native' and record.get('recipe_deviation')
                       and record.get('access_path') and record.get('reasoning_effort'),
                       'Native replay must preserve explicit transport/reasoning deviation')
    elif evidence == 'cli-replay':
        intake.require(record.get('tool') == 'codex' and type(record.get('exit_code')) is int and record.get('exit_code') == 0
                       and record.get('access_path'), 'CLI replay needs successful exit and access-path evidence')
    elif evidence == 'contract-fixture':
        intake.require(record.get('tool') == 'synthetic-contract-fixture'
                       and record.get('synthetic_contract_fixture') is True, 'Not an explicitly synthetic fixture')
    else:
        raise ValueError('Unsupported evidence type')
    return intake.validate_prediction(record.get('prediction'))


def execute(directory, retry_of=None):
    """External action, never called from preparation or collection. No retry loops."""
    directory, job = load_job(directory)
    intake.require(job['implementation_sha256'] == code_hashes(),
                   'Implementation changed since preparation; prepare a new job before execution')
    attempts = directory / 'attempts'
    old = sorted(p for p in attempts.iterdir() if p.is_dir())
    if old:
        intake.require(retry_of is not None, 'Existing attempt; an explicit --retry-of is required')
        intake.require(retry_of in [p.name for p in old], 'retry-of must name an existing attempt')
    else:
        intake.require(retry_of is None, 'No attempt exists to retry')
    attempt = attempts / f'attempt-{len(old) + 1:04d}'
    attempt.mkdir()  # Exclusive creation; never overwrite receipts.
    status = {'schema_version': 'site-extraction-attempt-1', 'state': 'incomplete',
              'started_at': now(), 'retry_of': retry_of, 'job_sha256': intake.digest((directory / 'job.json').read_bytes()),
              'model_call_requested': True, 'api_billing_verified': False}
    write_json(attempt / 'status.json', status)
    failure = None
    try:
        # Reuse the stricter historical tool interface unchanged. Snapshot is byte-identical.
        import adapt_pid2graph_synthetic as adapter
        config = {'development': ['0'], 'recipe': dict(RECIPE, prompt=str(directory / 'source/prompt.md'))}
        adapter.extract(config, directory / 'source', attempt)
        load_job(directory)
        record = read_json(attempt / '0.json')
        validate_record(record, job, 'cli-replay')
        status['state'] = 'succeeded'
    except Exception as error:
        failure = f'{type(error).__name__}: {error}'
        status.update(state='failed', error=failure)
    status['finished_at'] = now()
    write_json(attempt / 'status.json', status)
    if failure:
        raise ValueError(f'Extraction failed; preserved {attempt}: {failure}')
    return {'attempt': str(attempt), 'state': 'succeeded', 'model_called': True,
            'next': 'Collect the recorded attempt explicitly; no review or approval was performed.'}


def collect(directory, record_path, evidence, out, check_only=False):
    directory, job = load_job(directory)
    out = new_output(out)
    record_path = Path(record_path).resolve()
    raw = intake.read_bounded(record_path, intake.MAX_JSON_BYTES)
    record = intake.strict_json(raw)
    validate_record(record, job, evidence)
    # If a record is from this workflow, require completed success; a stray partial reply is insufficient.
    if record_path.is_relative_to(directory / 'attempts'):
        status = read_json(record_path.parent / 'status.json')
        intake.require(status.get('state') == 'succeeded' and status.get('job_sha256')
                       == intake.digest((directory / 'job.json').read_bytes()), 'Attempt incomplete, failed or belongs to changed job')
    receipt = {'schema_version': 'site-extraction-collection-1', 'evidence': evidence,
               'synthetic_contract_fixture': evidence == 'contract-fixture', 'new_model_run': False,
               'record_sha256': intake.digest(raw), 'job': job,
               'producer_claims_independently_verified': False,
               'billing_note': 'Any original api_spend_usd=0 is an inherited producer claim, not verified billing or a cost guarantee.',
               'execution': {k: record.get(k) for k in ('tool', 'model', 'requested_model', 'provider', 'access_path',
                            'reasoning_effort', 'recipe_deviation', 'isolation', 'exit_code', 'seconds')},
               'collection_implementation_sha256': code_hashes(), 'warning': WARNING}
    if check_only:
        return {'valid': True, 'written': False, 'model_called': False, 'receipt': receipt}
    stage = Path(tempfile.mkdtemp(prefix='.site-collect-', dir=out.parent))
    try:
        source = stage / 'input'
        source.mkdir()
        # Snapshot validated bytes once more; no paths from a result are executed or followed.
        image = (directory / 'source/0.png').read_bytes()
        intake.require(intake.digest(image) == job['image_sha256'], 'Image changed during collection')
        (source / '0.png').write_bytes(image)
        (source / 'record.json').write_bytes(raw)
        manifest = dict(job['drawing'], schema_version=intake.SCHEMA, image='0.png', extraction='record.json',
                        extraction_format='run-record', producer={'method': RECIPE['id'] + '; ' + evidence,
                        'tool': record['tool'], 'model': record['model']})
        write_json(source / 'manifest.json', manifest)
        bundle = stage / 'bundle'
        result = intake.import_drawing(source / 'manifest.json', bundle)
        write_json(bundle / 'extraction_handoff.json', receipt)
        prompt = (directory / 'source/prompt.md').read_bytes()
        intake.require(intake.digest(prompt) == RECIPE['prompt_sha256'], 'Prompt changed during collection')
        (bundle / 'source/prepared-prompt.md').write_bytes(prompt)
        if record_path.is_relative_to(directory / 'attempts'):
            for filename in ('status.json', '0.log'):
                path = record_path.parent / filename
                if path.is_file():
                    (bundle / 'source' / ('attempt-' + filename)).write_bytes(
                        intake.read_bounded(path, intake.MAX_JSON_BYTES))
        (bundle / 'READ_ME.txt').write_text((bundle / 'READ_ME.txt').read_text() + '\n'
            + f'Evidence: {evidence}. Collection replayed supplied output; it did not call a model.\n'
            + ('SYNTHETIC CONTRACT FIXTURE: no actual extraction or quality evidence.\n' if evidence == 'contract-fixture' else '')
            + 'See extraction_handoff.json for frozen method and preserved transport differences.\n', encoding='utf-8')
        new_output(out)
        os.rename(bundle, out)
        result.update(output=str(out), evidence=evidence, model_called=False)
        return result
    finally:
        shutil.rmtree(stage)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest='mode', required=True)
    prep = modes.add_parser('prepare', help='Offline: validate and snapshot ONE PNG; no extraction')
    prep.add_argument('--image', required=True)
    prep.add_argument('--drawing-id', required=True)
    prep.add_argument('--revision', required=True)
    prep.add_argument('--page', required=True, type=int)
    prep.add_argument('--out', required=True)
    prep.add_argument('--check-only', action='store_true', help='Validate only; write nothing')
    run = modes.add_parser('execute', description=__doc__, help='EXTERNAL: sends PNG/prompt to authenticated Codex/OpenAI')
    run.add_argument('--job', required=True)
    run.add_argument('--retry-of', help='Explicitly name prior attempt; this is not organizational permission')
    gather = modes.add_parser('collect', help='Offline: validate existing evidence and write draft review bundle')
    gather.add_argument('--job', required=True)
    gather.add_argument('--record', required=True)
    gather.add_argument('--evidence', required=True, choices=['cli-replay', 'native-replay', 'contract-fixture'])
    gather.add_argument('--out', required=True)
    gather.add_argument('--check-only', action='store_true', help='Validate evidence only; does not test conversion')
    args = parser.parse_args(argv)
    try:
        if args.mode == 'prepare':
            result = prepare(args.image, args.drawing_id, args.revision, args.page, args.out, args.check_only)
        elif args.mode == 'execute':
            result = execute(args.job, args.retry_of)
        else:
            result = collect(args.job, args.record, args.evidence, args.out, args.check_only)
    except (ValueError, OSError, TypeError, KeyError, OverflowError, RecursionError) as error:
        parser.exit(2, f'Site extraction workflow failed: {error}\n')
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
