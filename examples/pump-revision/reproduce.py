"""Connect two fictional source revisions using existing local tools. No plant or company acceptance."""
import argparse
import asyncio
import copy
import csv
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

EXAMPLE = Path(__file__).resolve().parent
ROOT = EXAMPLE.parents[1]
INPUTS = EXAMPLE / 'inputs'
PUMP = 'PUMP-NOTE@P-1'
TANK = 'TANK-SERVICE@TK-1'
E1 = 'E1@P-1'
ENV = dict(os.environ, PYTHONIOENCODING='utf-8')
read = lambda p: json.loads(p.read_text(encoding='utf-8'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')


def rel(path):
    try:
        value = os.path.relpath(path, ROOT)
    except ValueError:  # Windows cannot express a relative path across drive letters.
        value = str(Path(path).resolve())
    return value.replace('\\', '/')


def files(folder):
    return {p.relative_to(folder).as_posix(): sha(p) for p in folder.rglob('*') if p.is_file()} if folder.exists() else None


class Demonstration:
    def __init__(self, out):
        self.out = out
        self.commands = []
        self.checks = []
        self.input_hashes = files(INPUTS)

    def check(self, label, value):
        self.checks.append({'label': label, 'pass': bool(value)})
        write_json(self.out / 'checks.json', self.checks)
        assert value, label

    def cli(self, label, script, args, expected=0):
        command = [sys.executable, '-S', 'scripts/' + script, *map(str, args)]
        p = subprocess.run(command, cwd=ROOT, env=ENV, capture_output=True)
        (self.out / (label + '.stdout')).write_bytes(p.stdout)
        (self.out / (label + '.stderr')).write_bytes(p.stderr)
        self.commands.append({'label': label, 'command': command, 'cwd': str(ROOT), 'exit': p.returncode})
        write_json(self.out / 'commands.json', self.commands)
        self.check(label + ' exit ' + str(expected), p.returncode == expected)
        self.check(label + ' frozen sources unchanged', files(INPUTS) == self.input_hashes)
        return p

    def context_args(self, revision, dest, register=None, answers=None, bad_pin=False):
        base = self.out / revision
        args = ['--model', rel(base / 'graph.json'), '--questions', rel(base / 'questions.json'),
                '--sources', rel(INPUTS / revision / ('sources-with-A-pump-hash.json' if bad_pin else 'sources.json')),
                '--out', rel(dest)]
        if register: args += ['--register', rel(register)]
        if answers: args += ['--answers', rel(answers)]
        return args

    def prepare_inputs(self, revision):
        base = self.out / revision
        base.mkdir()
        model = INPUTS / revision / 'model.json'
        self.cli(revision + '-screen', 'question_engine.py', ['--model', rel(model), '--catalog', 'data/questions.json',
                 '--question', 'E1', '--out', rel(base / 'screen')])
        generated = read(base / 'screen/questions.json')
        self.check(revision + ' actual sole generated E1', [q['id'] for q in generated['questions']] == [E1])
        combined = copy.deepcopy(generated)
        manual = read(INPUTS / revision / 'manual-questions.json')['questions']
        combined['questions'].extend(copy.deepcopy(manual))
        combined['composition'] = {'generated_finding_ids': [E1], 'authored_source_question_ids': [PUMP, TANK],
                                   'note': 'Manual source questions are authored training fixtures, not catalog findings.'}
        self.check(revision + ' complete generated finding unchanged', combined['questions'][0] == generated['questions'][0])
        self.check(revision + ' exact authored question records', combined['questions'][1:] == manual)
        write_json(base / 'questions.json', combined)
        self.cli(revision + '-graph', 'graph_export.py', [rel(model), '--questions', rel(base / 'questions.json'),
                 '--out', rel(base / 'graph.json')])
        self.cli(revision + '-graph-check', 'graph_export.py', ['--check', rel(base / 'graph.json')])
        graph = read(base / 'graph.json')
        pump = next(n for n in graph['nodes'] if n['id'] == 'P-1')
        claims = {a['name']: a for a in pump['attributes']}
        facts = next(n for n in read(model)['units'] if n['id'] == 'P-1')['facts']
        for name, fact in facts.items():
            for key, value in fact.items():
                if key == 'source': continue
                claim = claims[name + '.' + key]
                self.check(revision + '/' + name + '.' + key + ' exact typed value',
                           type(claim['value']) is type(value) and claim['value'] == value)
                self.check(revision + '/' + name + '.' + key + ' source and unverified',
                           claim['source'] == {'kind': 'document', 'document': fact['source']} and claim['status'] == 'unverified')
        self.check(revision + ' bearing note not natively mapped',
                   not any('BX-' in json.dumps(a) for a in pump['attributes']))

    def answers(self, revision, prepared):
        intents = read(INPUTS / 'ANSWER-INTENTS.json')
        with (prepared / 'answers.csv').open(encoding='utf-8', newline='') as f:
            columns = csv.DictReader(f).fieldnames
        with (prepared / 'evidence_choices.csv').open(encoding='utf-8', newline='') as f:
            choices = list(csv.DictReader(f))
        rows = []
        for intent in intents[revision]:
            matches = [r for r in choices if r['question_id'] == intent['question_id']]
            self.check(revision + '/' + intent['question_id'] + ' one actual prepared choice', len(matches) == 1)
            choice = matches[0]
            row = {key: '' for key in columns}
            row.update(intent)
            actor = intents['fictional_actors']
            row.update(owner=actor['owner'], assigned_by=actor['assigned_by'], assigned_on=actor['date'],
                       reviewer=actor['reviewer'], reviewed_on=actor['date'], source_id=choice['source_id'],
                       locator_id=choice['locator_id'], evidence_fingerprint=choice['evidence_fingerprint'],
                       note='Synthetic local source decision; no company authorization or observed plant truth.')
            rows.append(row)
        target = self.out / revision / 'filled_answers.csv'
        with target.open('w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=columns, lineterminator='\n')
            writer.writeheader(); writer.writerows(rows)
        return target

    def refusal(self, label, bad_pin=False, old_csv=False, populated=False):
        dest = self.out / 'refusals' / label
        if populated:
            dest.mkdir(parents=True)
            (dest / 'keep.txt').write_bytes(b'Pre-existing destination must remain exact.\n')
        before = files(dest)
        args = self.context_args('B', dest, register=self.out / 'B/refreshed/context.json' if old_csv else None,
                                 answers=self.out / 'A/filled_answers.csv' if old_csv else None, bad_pin=bad_pin)
        p = self.cli(label, 'context_register.py', ['apply' if old_csv else 'prepare', *args], expected=2)
        self.check(label + ' absent or populated destination unchanged', files(dest) == before)
        self.check(label + ' documented input refusal', b'context register:' in p.stderr)

    def run(self):
        self.out.mkdir(parents=True)
        shutil.copytree(INPUTS, self.out / 'source-records')
        shutil.copyfile(ROOT / 'data/questions.json', self.out / 'source-records/questions-catalog.json')
        packet_sources = files(self.out / 'source-records')
        self.check('packet contains every exact original fixture', all(packet_sources.get(k) == v for k, v in self.input_hashes.items()))
        self.check('packet contains exact selected catalog', packet_sources['questions-catalog.json'] == sha(ROOT / 'data/questions.json'))
        self.prepare_inputs('A')
        self.cli('A-prepare', 'context_register.py', ['prepare', *self.context_args('A', self.out / 'A/prepared')])
        answers = self.answers('A', self.out / 'A/prepared')
        self.cli('A-apply', 'context_register.py', ['apply', *self.context_args('A', self.out / 'A/current',
                 register=self.out / 'A/prepared/context.json', answers=answers)])
        a = read(self.out / 'A/current/context.json')
        self.check('A pump partial and tank answered', a['current'][PUMP]['state'] == 'partial' and a['current'][TANK]['state'] == 'answered')
        self.check('A E1 unanswered', a['current'][E1]['state'] == 'unanswered')
        self.prepare_inputs('B')
        self.refusal('B-bad-pin-absent', bad_pin=True)
        self.refusal('B-bad-pin-populated', bad_pin=True, populated=True)
        self.cli('B-refresh', 'context_register.py', ['apply', *self.context_args('B', self.out / 'B/refreshed',
                 register=self.out / 'A/current/context.json')])
        refreshed = read(self.out / 'B/refreshed/context.json')
        self.check('B refresh exact old decisions', refreshed['decisions'] == a['decisions'])
        self.check('B refresh exact old ownership', refreshed['ownership_history'] == a['ownership_history'])
        pump_answer, = refreshed['current'][PUMP]['answers']
        self.check('B pump old answer stale by source revision', pump_answer['freshness'] == 'stale' and 'source revision/bytes/locator' in pump_answer['changed'])
        tank_answer, = refreshed['current'][TANK]['answers']
        self.check('B independent tank answer remains current', tank_answer['freshness'] == 'current' and refreshed['current'][TANK]['state'] == 'answered')
        self.refusal('B-old-csv-absent', old_csv=True)
        self.refusal('B-old-csv-populated', old_csv=True, populated=True)
        self.cli('B-prepare', 'context_register.py', ['prepare', *self.context_args('B', self.out / 'B/prepared',
                 register=self.out / 'B/refreshed/context.json')])
        answers = self.answers('B', self.out / 'B/prepared')
        self.cli('B-apply', 'context_register.py', ['apply', *self.context_args('B', self.out / 'B/current',
                 register=self.out / 'B/refreshed/context.json', answers=answers)])
        b = read(self.out / 'B/current/context.json')
        self.check('B new partial answer and E1 still unanswered', b['current'][PUMP]['state'] == 'partial' and b['current'][E1]['state'] == 'unanswered')
        self.check('B old complete history remains exact prefix', b['decisions'][:len(a['decisions'])] == a['decisions'])
        self.check('B old complete ownership remains exact prefix', b['ownership_history'][:len(a['ownership_history'])] == a['ownership_history'])
        self.check('B new decision source value and unresolved plant truth', b['decisions'][-1]['value'] == '12 kPa' and all(d['plant_truth'] == 'unknown' for d in b['decisions']))
        for revision in ('A', 'B'):
            self.cli(revision + '-enriched-check', 'graph_export.py', ['--check', rel(self.out / revision / 'current/enriched_graph.json')])
            graph = read(self.out / revision / 'current/enriched_graph.json')
            original = read(self.out / revision / 'screen/questions.json')['questions'][0]
            actual = next(q for q in graph['questions'] if q['id'] == E1)
            self.check(revision + ' E1 complete finding retained through context', {k: v for k, v in actual.items() if k != 'context'} == original)
        self.report(a, refreshed, b)
        self.check('all frozen input bytes preserved at completion', files(INPUTS) == self.input_hashes)
        self.check('packet original records unchanged at completion', files(self.out / 'source-records') == packet_sources)
        write_json(self.out / 'CLI-RESULT.json', {'pass': True, 'actual_CLIs': len(self.commands), 'assertions': len(self.checks),
                   'source_inputs_sha256': self.input_hashes, 'scope': 'Author connected synthetic example; actual SDK and independent acceptance remain separate.'})

    def report(self, a, refreshed, b):
        rows = []
        for revision, register in [('A', a), ('B', b)]:
            model = read(INPUTS / revision / 'model.json')
            pump = next(u for u in model['units'] if u['id'] == 'P-1')
            omitted = read(INPUTS / revision / 'unmapped.json')
            rows.append({'revision': revision, 'source_sha256': sha(INPUTS / revision / 'pump-note.txt'),
                         'facts': pump['facts'], 'unmapped': omitted,
                         'pump_answer_state': register['current'][PUMP]['state'],
                         'E1_state': register['current'][E1]['state'],
                         'graph_sha256': sha(self.out / revision / 'current/enriched_graph.json'),
                         'context_sha256': sha(self.out / revision / 'current/context.json')})
        write_json(self.out / 'CHANGE-REVIEW.json', {'revisions': rows, 'source_decision_scope': 'Synthetic partial source answer only',
                   'refresh_B_pump': refreshed['current'][PUMP], 'independent_tank': refreshed['current'][TANK],
                   'physical_checks': 'not run', 'safety_checks': 'not run', 'company_acceptance': 'not performed', 'recipient_acceptance': 'not performed'})
        lines = ['# One pump note changes; the investigation stays reviewable', '',
                 'ILLUSTRATIVE: invented records and fictional local source decisions. No plant observations or company approval.', '',
                 '| Supplied evidence / review | Revision A | Revision B |', '|---|---|---|',
                 '| Pump-note revision | A | B |', '| Raw supplied head | 12 m | 12 kPa |',
                 '| Rated flow | 0 m3/h | 0 m3/h |', '| Reset enabled | false | false |',
                 '| Inspection date | null | null |', '| Uncertainty | unknown | unknown |',
                 '| Bearing note, retained original text and explicitly unmapped | BX-UNKNOWN | BX-REVISED |',
                 '| Pump source answer | Partial, source match only | Old answer stale after refresh; fresh partial source answer |',
                 '| Separate tank source answer | Current | Current |', '| Generated E1 investigation | Unanswered | Unanswered |', '',
                 'The units are incompatible raw supplied units. No conversion, design correction, savings or operating instruction follows.',
                 'Original notes, native input models and the selected catalog travel in source-records/. The bearing note has no native mapping; snapshot MCP does not fetch source files.',
                 'The exact old 12 m decision, source evidence and ownership survive beside the new 12 kPa record.', '',
                 'Structural graph checks ran. Physical and safety checks did not run. Actual engineer, recipient and company acceptance were not performed.', '',
                 'Read [A source note](source-records/A/pump-note.txt), [B source note](source-records/B/pump-note.txt),',
                 '[A context](A/current/context.md), [B context](B/current/context.md), and [exact values and hashes](CHANGE-REVIEW.json).', '']
        (self.out / 'CHANGE-REVIEW.md').write_text('\n'.join(lines), encoding='utf-8')
        brief = ['# Fictional first-question handoff', '', 'Status: Draft; receiving owner needed.', '',
                 '- Question: PUMP-NOTE@P-1; related generated investigation E1@P-1 remains unanswered.',
                 '- Supplied source answer: revision B says 12 kPa; this is not a conversion from revision A\'s 12 m.',
                 '- Evidence: [PUMP-NOTE revision B](source-records/B/pump-note.txt), lines2-8; SHA-256 `' + rows[1]['source_sha256'] + '`.',
                 '- Native model: [supplied revision B](source-records/B/model.json); SHA-256 `' + sha(INPUTS / 'B/model.json') + '`.',
                 '- Selected graph: [B enriched graph](B/current/enriched_graph.json); SHA-256 `' + rows[1]['graph_sha256'] + '`.',
                 '- Selected context and complete history: [B context register](B/current/context.json); SHA-256 `' + rows[1]['context_sha256'] + '`.',
                 '- Complete question packet: [B questions](B/current/enriched_questions.json); SHA-256 `' + sha(self.out / 'B/current/enriched_questions.json') + '`.',
                 '- Generated E1 catalog: [retained selected catalog](source-records/questions-catalog.json); SHA-256 `' + sha(ROOT / 'data/questions.json') + '`.',
                 '- Unresolved: operating suitability, actual flow/head, applicable units and the unmapped bearing note.',
                 '- Next action: an authorized engineer must reconcile the source and determine suitable operating evidence.',
                 '- Receiving owner: Unassigned; company authority and recipient acceptance not performed.',
                 '- Trial not run; benefit not measured. Physical/safety checks not run.', '']
        (self.out / 'HANDOFF.md').write_text('\n'.join(brief), encoding='utf-8')


async def snapshot_checks(out):
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters
    assert importlib.metadata.version('mcp') == '2.3.0'
    responses, checks = [], []
    input_hashes = files(INPUTS)
    packet_hashes = {revision: files(out / revision) for revision in ('A', 'B')}
    packet_sources = files(out / 'source-records')
    sdk = out / 'sdk'
    sdk.mkdir()
    runtime = sdk / 'selected'
    runtime.mkdir()
    selected_graph, selected_context = runtime / 'graph.json', runtime / 'context.json'
    def check(label, value):
        checks.append({'label': label, 'pass': bool(value)})
        write_json(sdk / 'checks.json', checks)
        assert value, label
    def select(revision):
        shutil.copyfile(out / revision / 'current/enriched_graph.json', selected_graph)
        shutil.copyfile(out / revision / 'current/context.json', selected_context)
    async def packet(client, revision, label):
        graph = read(out / revision / 'current/enriched_graph.json')
        context = read(out / revision / 'current/context.json')
        result = []
        async def call(name, arguments=None):
            value = await client.call_tool(name, arguments or {})
            raw = value.model_dump(mode='json', by_alias=True, exclude_none=True)
            responses.append({'stage': label, 'tool': name, 'arguments': arguments or {}, 'response': raw})
            write_json(sdk / 'responses.json', responses)
            check(label + '/' + name + ' success and exact serialized copies',
                  not value.is_error and json.loads(value.content[0].text) == value.structured_content)
            body = value.structured_content
            check(label + '/' + name + ' exact graph/context selected hashes',
                  body['snapshot_sha256'] == sha(out / revision / 'current/enriched_graph.json') and
                  body['context_sha256'] == sha(out / revision / 'current/context.json') and
                  body['context_content_sha256'] == graph['context_register']['content_sha256'])
            check(label + '/' + name + ' explicit supplied nonlive scope',
                  body['data_mode'] == 'supplied_snapshot' and body['live'] is False and body['source_acquisition_time'] is None)
            result.append(body)
            return body['result']
        summary = await call('snapshot_summary')
        expected = {'schema': graph['schema'], 'title': graph.get('title'), 'source_model': graph.get('source_model'),
                    'nodes': len(graph['nodes']), 'edges': len(graph['edges']), 'questions': len(graph['questions']),
                    'virtual_streams': sum(e.get('type') == 'connects' for e in graph['edges']),
                    'context_available': True, 'context_questions': len(context['current']), 'decisions': len(context['decisions']),
                    'available_sections': ['nodes', 'edges', 'questions', 'context', 'decision_history', 'ownership_history'],
                    'unserved_review_events': len(graph.get('events', [])), 'not_exported': graph.get('not_exported', [])}
        check(label + ' complete summary equals selected files', summary == expected)
        for aid in ('P-1', 'TK-1'):
            asset = await call('get_asset', {'asset_id': aid})
            check(label + '/' + aid + ' complete node', asset == next(n for n in graph['nodes'] if n['id'] == aid))
            relations = await call('get_relations', {'asset_id': aid, 'limit': 100})
            expected_edges = [e for e in graph['edges'] if aid in (e['from'], e['to'])]
            check(label + '/' + aid + ' complete incident relations', relations == {'total': len(expected_edges), 'offset': 0,
                  'limit': 100, 'next_offset': None, 'truncated': False, 'relations': expected_edges})
        question = await call('get_question', {'question_id': E1})
        check(label + ' complete E1 question', question == next(q for q in graph['questions'] if q['id'] == E1))
        for qid in (PUMP, TANK):
            current = await call('get_context', {'question_id': qid})
            expected = {'question_id': qid, 'current': context['current'][qid],
                        'ownership_history': [r for r in context['ownership_history'] if r['question_id'] == qid],
                        'sources': [dict(s, locators=[l for l in s['locators'] if qid in l['questions']]) for s in context['sources']
                                    if any(qid in l['questions'] for l in s['locators'])]}
            check(label + '/' + qid + ' complete context/source/ownership', current == expected)
        decisions, offset = [], 0
        while True:
            page = await call('list_decisions', {'limit': 1, 'offset': offset})
            expected_rows = context['decisions'][offset:offset + 1]
            check(label + ' exact decision page ' + str(offset), page['decisions'] == expected_rows and page['total'] == len(context['decisions']))
            decisions.extend(page['decisions'])
            if page['next_offset'] is None: break
            offset = page['next_offset']
        check(label + ' entire ordered history and unknown plant truth', decisions == context['decisions'] and all(d['plant_truth'] == 'unknown' for d in decisions))
        return result
    select('A')
    params = lambda: StdioServerParameters(command=sys.executable, args=['-u', str(ROOT / 'scripts/serve_snapshot.py'),
                                '--graph', str(selected_graph), '--context', str(selected_context)], env=ENV)
    async with Client(params(), read_timeout_seconds=20) as client:
        first = await packet(client, 'A', 'A-loaded')
        select('B')
        second = await packet(client, 'A', 'A-after-B-files')
        check('old process returns identical complete envelopes after selected files replaced', first == second)
    async with Client(params(), read_timeout_seconds=20) as client:
        await packet(client, 'B', 'B-restarted')
    negative = []
    for graph_revision, context_revision in (('A', 'B'), ('B', 'A')):
        command = [sys.executable, str(ROOT / 'scripts/serve_snapshot.py'), '--graph',
                   str(out / graph_revision / 'current/enriched_graph.json'), '--context', str(out / context_revision / 'current/context.json')]
        p = subprocess.run(command, input=b'', capture_output=True, env=ENV, timeout=20)
        label = graph_revision + '-graph-' + context_revision + '-context'
        (sdk / (label + '.stdout')).write_bytes(p.stdout); (sdk / (label + '.stderr')).write_bytes(p.stderr)
        negative.append({'command': command, 'exit': p.returncode})
        check(label + ' explicit startup refusal', p.returncode != 0 and b'Invalid selected context' in p.stderr)
    check('SDK source fixtures unchanged', files(INPUTS) == input_hashes)
    check('SDK portable original source records unchanged', files(out / 'source-records') == packet_sources)
    check('SDK original generated packets unchanged', {revision: files(out / revision) for revision in ('A', 'B')} == packet_hashes)
    write_json(sdk / 'RESULT.json', {'pass': True, 'actual_stdio_sessions': 2, 'actual_responses': len(responses),
               'assertions': len(checks), 'negative_startup_CLIs': negative, 'mcp': importlib.metadata.version('mcp'),
               'scope': 'Author exact selected snapshot/restart example; no Copilot tenant/company/plant acceptance.'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--sdk-only', action='store_true')
    args = parser.parse_args()
    out = args.out.resolve()
    if args.sdk_only:
        assert read(out / 'CLI-RESULT.json')['pass'] and not (out / 'sdk').exists()
        asyncio.run(snapshot_checks(out))
    else:
        assert not out.exists(), 'Use a fresh output folder; earlier runs are retained.'
        Demonstration(out).run()
    print('PASS connected fictional revision example; inspect exact receipts and limits.')


if __name__ == '__main__':
    main()
