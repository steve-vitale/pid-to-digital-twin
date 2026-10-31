"""Description packet regression controls: source preservation, directed topology and generated bundles.

Uses authored illustrative fixtures, Pillow and native generators; no model calls or network.
"""
import copy
import csv
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import description_workflow as workflow
import serve_snapshot

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / 'examples/from-description/assisted'
SCRIPT = ROOT / 'scripts/description_workflow.py'


class DescriptionWorkflowTests(unittest.TestCase):
    def test_mgpi_source_adaptation_preserves_aliases_evidence_and_scoring_limit(self):
        import benchmark
        case = ROOT / 'examples/from-description/mgpi'
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            workflow.prepare(case / 'source.txt', folder / 'packet')
            result = folder / 'result'
            report = workflow.build(folder / 'packet', case / 'answer.json', result)
            self.assertTrue(report['ok'], report)
            self.assertEqual(report['sheets'], 2)
            graph = json.loads((result / 'graph.json').read_bytes())
            indicator = next(n for n in graph['nodes'] if n['id'] == 'LI_HYPO')
            self.assertEqual(indicator['status'], 'unverified')
            claims = {a['name']: a['value'] for a in indicator['attributes']}
            self.assertIn('no automatic unloading shutdown', claims['alarm_action_basis'])
            text = (result / 'exports/svg/HYPO_BULK.svg').read_text(encoding='utf-8')
            self.assertIn('LI_HYPO', text)
            self.assertEqual(json.loads((result / 'questions/questions.json').read_bytes())['counts']['findings'], 0)
        model = json.loads((case / 'model-expanded-source.json').read_bytes())
        false = json.loads((case / 'controls/false-shutdown.json').read_bytes())
        # Pin the exposed limit: alarm semantics are retained in output but not graded by native-facts-v1.
        self.assertEqual(benchmark.native_facts(model), benchmark.native_facts(false))
        # Every action claim is now visible beside its quote even though legacy selected-field scoring misses it.
        reviews=[]
        for candidate in (model,false):
            packet=workflow.interpretation_review(candidate,(case/'source.txt').read_bytes())
            rows=list(csv.DictReader(io.StringIO(packet['interpretation_review.csv'].decode('utf-8'))))
            row=next(r for r in rows if r['model_pointer']=='/instruments/0/alarm_action_basis')
            self.assertEqual(row['verdict'],'unreviewed')
            self.assertIn('alarm',json.loads(row['source_quote_json']).lower())
            reviews.append(row)
        self.assertNotEqual(reviews[0]['value_json'],reviews[1]['value_json'])
        self.assertEqual(reviews[0]['source_quote_json'],reviews[1]['source_quote_json'])
        initial = json.loads((case / 'v1/facts.json').read_bytes())['facts']
        expanded = json.loads((case / 'v2/facts.json').read_bytes())['facts']
        self.assertEqual({json.dumps(x) for x in expanded} - {json.dumps(x) for x in initial},
                         {json.dumps(['instruments', 'LI_HYPO', 'unit', 'HYPO_BULK'])})

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='description-test-')
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.source = self.folder / 'description.txt'
        self.source.write_bytes(workflow.REFERENCE_SOURCE.encode('utf-8'))
        self.packet = self.folder / 'packet'
        workflow.prepare(self.source, self.packet)

    def answer(self, value):
        path = self.folder / 'answer.json'
        path.write_bytes(workflow.json_bytes(value))
        return path

    def check_value(self, value):
        return workflow.check(self.packet, self.answer(value))

    def test_review_packet_preserves_nested_values_and_exposes_uncited_source(self):
        answer=workflow.reference_answer()
        record=answer['model']['units'][0]
        record['extra']={'a/b~c':[None,False,0,{},[]],'source':'source.txt:L8-L8'}
        record['name']='=SUM(1,2)'
        files=workflow.interpretation_review(answer['model'],workflow.REFERENCE_SOURCE.encode('utf-8'))
        rows=list(csv.DictReader(io.StringIO(files['interpretation_review.csv'].decode('utf-8'))))
        values={r['model_pointer']:json.loads(r['value_json']) for r in rows}
        self.assertEqual([values['/units/0/extra/a~1b~0c/'+str(i)] for i in range(5)],
                         [None,False,0,{},[]])
        self.assertEqual(values['/units/0/name'],'=SUM(1,2)')
        self.assertTrue(all(r['verdict']=='unreviewed' for r in rows))
        self.assertTrue(all(not cell.startswith(('=','+','-','@')) for r in rows for cell in r.values()))
        nested=next(r for r in rows if r['model_pointer']=='/units/0/extra/a~1b~0c/0')
        self.assertEqual(nested['source_locator'],'source.txt:L8-L8')
        self.assertEqual(json.loads(nested['source_quote_json']),workflow.REFERENCE_SOURCE.splitlines()[7])
        coverage=list(csv.DictReader(io.StringIO(files['source_coverage.csv'].decode('utf-8'))))
        self.assertEqual(len(coverage),8)
        self.assertEqual(json.loads(coverage[0]['citing_record_pointers_json']),[])
        self.assertIn('/units/0',json.loads(coverage[7]['citing_record_pointers_json']))
        self.assertTrue(all(r['review_state']=='unreviewed' for r in coverage))

    def test_prepare_runs_without_site_packages_and_preserves_raw_source(self):
        raw = b'\xef\xbb\xbf' + workflow.REFERENCE_SOURCE.replace('\n', '\r\n').encode('utf-8')
        self.source.write_bytes(raw)
        out = self.folder / 'stdlib-packet'
        proc = subprocess.run([sys.executable, '-S', str(SCRIPT), 'prepare', '--source', str(self.source),
                               '--out', str(out)], capture_output=True, timeout=10)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual((out / 'source.txt').read_bytes(), raw)
        answer = workflow.reference_answer()
        answer['model']['meta']['source_sha256'] = workflow.digest(raw)
        answer_path = self.answer(answer)
        answer_raw = answer_path.read_bytes().replace(b'\n', b'\r\n')
        answer_path.write_bytes(answer_raw)
        self.assertTrue(workflow.check(out, answer_path)['ok'])
        bundle = self.folder / 'raw-input-result'
        self.assertTrue(workflow.build(out, answer_path, bundle)['ok'])
        self.assertEqual((bundle / 'source.txt').read_bytes(), raw)
        self.assertEqual((bundle / 'answer.json').read_bytes(), answer_raw)
        for p in bundle.rglob('*'):
            if p.is_file() and p.suffix != '.png' and p.name not in ('source.txt', 'answer.json'):
                self.assertNotIn(b'\r\n', p.read_bytes(), str(p))

    def test_linear_branch_recycle_and_offpage_bundles(self):
        fixtures = [('linear', 'source.txt', 'result/answer.json'),
                    ('branch', 'branch-source.txt', 'branch-answer.json'),
                    ('offpage', 'source.txt', 'offpage-answer.json')]
        for name, source, answer in fixtures:
            with self.subTest(name=name):
                packet = self.folder / (name + '-packet')
                workflow.prepare(EXAMPLE / source, packet)
                out = self.folder / (name + '-result')
                report = workflow.build(packet, EXAMPLE / answer, out)
                self.assertTrue(report['ok'], report)
                self.assertEqual((out / 'source.txt').read_bytes(), (EXAMPLE / source).read_bytes())
                manifest = json.loads((out / 'build.json').read_bytes())
                self.assertIn('interpretation_review.csv',manifest['files_sha256'])
                self.assertIn('source_coverage.csv',manifest['files_sha256'])
                self.assertIn('REVIEW.md', manifest['files_sha256'])
                self.assertEqual(set(manifest['files_sha256']),
                                 {p.relative_to(out).as_posix() for p in out.rglob('*') if p.is_file()} - {'build.json'})
                for path, sha in manifest['files_sha256'].items():
                    self.assertEqual(workflow.digest((out / path).read_bytes()), sha, path)
                model = json.loads((out / 'model.json').read_bytes())
                graph = json.loads((out / 'graph.json').read_bytes())
                self.assertEqual(len(list((out / 'pid').glob('*.png'))), report['sheets'])
                self.assertEqual({n['id'] for n in graph['nodes'] if n['kind'] == 'equipment'},
                                 {u['id'] for u in model['units']})
                edges = {(e['type'], e['from'], e['to']) for e in graph['edges']}
                self.assertEqual({e for e in edges if e[0] == 'connects'},
                                 {('connects', s['from'], s['to']) for s in model['streams']})
                for controller in model.get('controllers', []):
                    self.assertIn(('controls', controller['measurement'], controller['tag']), edges)
                    self.assertIn(('controls', controller['tag'], controller['output']['final_element']), edges)
                self.assertTrue((out / 'questions/screen.md').is_file())
                self.assertTrue((out / 'exports/ignition/tags.json').is_file())
                snapshot = serve_snapshot.Snapshot(out / 'graph.json')
                self.assertEqual(snapshot.asset('P-1')['result']['id'], 'P-1')
                self.assertTrue(snapshot.question_list('P-1')['result']['questions'])
                before = {p: (out / p).read_bytes() for p in manifest['files_sha256']}
                with self.assertRaisesRegex(workflow.InputError, 'new output directory'):
                    workflow.build(packet, EXAMPLE / answer, out)
                self.assertTrue(all((out / p).read_bytes() == raw for p, raw in before.items()))

    def test_model_and_drawing_cannot_disagree_or_invent_a_stream(self):
        for mutate, expected in (
            (lambda a: a['layout']['sheets'][0]['routes'][1].update(to={'unit': 'TK-1'}), 'model stream S2.to'),
            (lambda a: a['layout']['sheets'][0]['routes'][1].update(stream='NO-SUCH-STREAM'), 'must name a model stream'),
            (lambda a: a['layout']['sheets'][0]['routes'][1].update(pts=[[950, 900], [1655, 900]]), 'touch the named equipment'),
            (lambda a: a['layout']['sheets'][0]['routes'][1].update(to={'net': 'guess'}), 'ambiguous net'),
        ):
            answer = workflow.reference_answer()
            mutate(answer)
            report = self.check_value(answer)
            self.assertFalse(report['ok'])
            self.assertIn(expected, '\n'.join(report['errors']))

    def test_controller_output_contract_has_typed_targets(self):
        for output in ({'unsupported_key': 'FV-101'}, {'final_element': 'FT-101'},
                       {'final_element': 'FV-101', 'setpoint_of': 'FIC-101'},
                       {'split_range': ['FV-101', 'FV-101']}, {'setpoint_of': 'FIC-101'}):
            with self.subTest(output=output):
                answer = workflow.reference_answer()
                answer['model']['controllers'][0]['output'] = output
                report = self.check_value(answer)
                self.assertFalse(report['ok'])
                self.assertIn('model.controllers.FIC-101.output', '\n'.join(report['errors']))

    def test_extreme_geometry_refused_before_rendering(self):
        answer = workflow.reference_answer()
        answer['layout']['sheets'][0]['units']['TK-1'].update(shape='column', top=-100000000,
                                                           bottom=100000000, trays=True)
        proc = subprocess.run([sys.executable, str(SCRIPT), 'check', '--packet', str(self.packet),
                               '--answer', str(self.answer(answer))], capture_output=True, timeout=10)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        report = json.loads(proc.stdout)
        self.assertIn('units.TK-1.top', '\n'.join(report['errors']))
        self.assertFalse((self.folder / 'pid').exists())

    def test_equipment_type_and_symbol_agree(self):
        answer = workflow.reference_answer()
        answer['layout']['sheets'][0]['units']['TK-1'] = {'shape': 'pump', 'at': [800, 900], 'r': 45}
        report = self.check_value(answer)
        self.assertFalse(report['ok'])
        self.assertIn('does not match the model equipment type', '\n'.join(report['errors']))

    def test_drawing_cannot_discard_its_draft_disclaimers(self):
        answer = workflow.reference_answer()
        answer['layout']['title_block'].update(revision='APPROVED', notes=['APPROVED FOR OPERATION'])
        report = self.check_value(answer)
        self.assertFalse(report['ok'])
        self.assertIn('layout.title_block.revision', '\n'.join(report['errors']))
        self.assertIn('layout.title_block.notes', '\n'.join(report['errors']))

    def test_source_locator_is_exact_but_does_not_establish_interpretation(self):
        answer = workflow.reference_answer()
        answer['evidence']['source.txt:L2-L2'] = 'Different source text'
        self.assertFalse(self.check_value(answer)['ok'])
        answer = workflow.reference_answer()
        answer['model']['units'][0]['name'] = 'A deliberately incorrect interpretation'
        # This is the essential limit: matching a real quotation cannot prove its interpretation.
        self.assertTrue(self.check_value(answer)['ok'])
        answer['model']['units'][0]['verification'] = {'status': 'confirmed'}
        self.assertFalse(self.check_value(answer)['ok'])

    def test_changed_source_duplicate_json_and_unsafe_ids_refused(self):
        path = self.answer(workflow.reference_answer())
        path.write_bytes(b'{"model":{},"model":{},"layout":{},"evidence":{}}')
        with self.assertRaisesRegex(workflow.InputError, 'Duplicate JSON'):
            workflow.check(self.packet, path)
        answer = workflow.reference_answer()
        answer['layout']['sheets'][0]['id'] = '../escape'
        self.assertFalse(self.check_value(answer)['ok'])
        (self.packet / 'source.txt').write_bytes(b'Changed evidence')
        with self.assertRaisesRegex(workflow.InputError, 'prepared source changed'):
            self.check_value(workflow.reference_answer())

    def test_tee_and_continuation_conflicts_refused(self):
        branch = json.loads((EXAMPLE / 'branch-answer.json').read_bytes())
        self.packet = self.folder / 'branch-packet'
        workflow.prepare(EXAMPLE / 'branch-source.txt', self.packet)
        branch['layout']['sheets'][0]['routes'][4]['from']['at'] = [1900, 910]
        self.assertFalse(self.check_value(branch)['ok'])
        offpage = json.loads((EXAMPLE / 'offpage-answer.json').read_bytes())
        self.packet = self.folder / 'packet'
        offpage['layout']['sheets'][1]['routes'][0].update(to={'flag': 'IN'}, **{'from': {'unit': 'P-1'}})
        self.assertFalse(self.check_value(offpage)['ok'])


if __name__ == '__main__':
    unittest.main()
