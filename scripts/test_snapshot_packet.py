"""Offline snapshot controls: preserve evidence, refuse malformed packets and keep paged results complete."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import serve_snapshot as server
import graph_export
import context_register
import test_context_register

ROOT = Path(__file__).resolve().parents[1]


class SnapshotControls(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / 'graph.json'
        self.graph = json.loads((ROOT / 'examples/graph-export/bayer_graph.json').read_text(encoding='utf-8'))

    def load(self, graph=None):
        self.path.write_text(json.dumps(self.graph if graph is None else graph), encoding='utf-8')
        return server.Snapshot(self.path)

    def test_full_evidence_is_immutable_after_load(self):
        packet = self.load()
        expected = next(n for n in self.graph['nodes'] if n['id'] == 'P-1')
        first = packet.asset('P-1')
        self.assertEqual(first['result'], expected)
        self.assertIsNone(first['source_acquisition_time'])
        self.assertFalse(first['live'])
        self.path.write_text('{}', encoding='utf-8')
        first['result']['attributes'].clear()
        with patch.object(Path, 'open', side_effect=AssertionError('Unexpected Path.open')):
            self.assertEqual(packet.asset('P-1')['result'], expected)
            packet.summary()
            packet.relations('P-1', 50)
            packet.question_list('P-1')

    def test_input_size_refuses_without_parsing_the_rest(self):
        self.path.write_bytes(b'{' + b' ' * 200)
        with patch.object(server, 'MAX_INPUT_BYTES', 128), self.assertRaisesRegex(server.InputError, 'exceeds'):
            server.Snapshot(self.path)

    def test_response_limit_never_silently_drops_claims(self):
        packet = self.load()
        with patch.object(server, 'MAX_RESPONSE_BYTES', 128), self.assertRaisesRegex(server.InputError, 'exceeds'):
            packet.asset('P-1')

    def test_ambiguous_or_untransportable_json_refuses(self):
        for text in ('{"schema":"x","schema":"y"}', '{"value":NaN}', '{"title":"\\ud800"}'):
            with self.subTest(text=text):
                self.path.write_text(text, encoding='utf-8')
                with self.assertRaises((server.InputError, UnicodeError)):
                    server.Snapshot(self.path)

    def test_malformed_records_refuse(self):
        cases = [[], dict(self.graph, events=None), dict(self.graph, questions=[{'id':'Q','assets':['P-1']}]),
                 dict(self.graph, questions=[{'id':'Q'},{'id':'Q'}])]
        duplicate = copy.deepcopy(self.graph)
        duplicate['nodes'].append(copy.deepcopy(duplicate['nodes'][0]))
        cases.append(duplicate)
        bad_edge = copy.deepcopy(self.graph)
        bad_edge['edges'][0]['to'] = 'UNKNOWN'
        cases.append(bad_edge)
        for graph in cases:
            with self.subTest(graph_type=type(graph).__name__), self.assertRaises(server.InputError):
                self.load(graph)

    def test_paging_preserves_every_record_and_refuses_invalid_boundaries(self):
        packet = self.load()
        expected = [e for e in self.graph['edges'] if 'P-1' in (e['from'],e['to'])]
        seen = []
        offset = 0
        while True:
            page = packet.relations('P-1', 1, offset)['result']
            seen.extend(page['relations'])
            offset = page['next_offset']
            if offset is None:
                break
        self.assertEqual(seen, expected)
        for offset in (-1, True, 1.5, len(expected), len(expected)+1):
            with self.subTest(offset=offset), self.assertRaises(server.InputError):
                packet.relations('P-1', 1, offset)
        self.assertEqual(packet.search('no-such-asset',50)['result']['matches'], [])
        with self.assertRaises(server.InputError):
            packet.relations('P-1',True)

    def test_unknown_identity_cannot_select_a_source_path(self):
        packet = self.load()
        with self.assertRaisesRegex(server.InputError, 'Unknown asset'):
            packet.asset('../../outside.json')
        with self.assertRaisesRegex(server.InputError, 'Unknown question'):
            packet.question('https://example.invalid/source')

    def test_recorded_example_matches_the_supplied_graph_with_questions(self):
        graph = graph_export.build(ROOT/'data/bayer_rt/process_model.json',
                                   questions=ROOT/'examples/opportunity-screen/bayer/questions.json')
        raw = (json.dumps(graph,ensure_ascii=False,indent=1)+'\n').encode('utf-8')
        sample = json.loads((ROOT/'examples/internal-mcp/sample_asset.json').read_text(encoding='utf-8'))
        self.assertEqual(sample['snapshot_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(sample['result'], next(n for n in graph['nodes'] if n['id']=='P-1'))
        self.assertFalse(sample['live'])
        self.assertIsNone(sample['source_acquisition_time'])

    def context_fixture(self, remove=False):
        fixture = test_context_register.ContextRegister()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.graph['nodes'][1]['attributes'][0]['source'] = {'kind': 'illustrative fixture'}
        fixture.save_inputs()
        fixture.two_accepted()
        if remove:
            fixture.questions['questions'] = [q for q in fixture.questions['questions'] if q['id'] != 'Q2@P-2']
            fixture.manifest['documents'][1]['locators'][0]['questions'] = []
            fixture.save_inputs()
            fixture.refresh()
        return fixture

    def test_explicit_context_preserves_full_answers_history_sources_and_snapshot(self):
        fixture = self.context_fixture(remove=True)
        graph_path, context_path = fixture.root/'bundle/enriched_graph.json', fixture.root/'bundle/context.json'
        register = fixture.read()
        packet = server.Snapshot(graph_path, context_path)
        self.assertTrue(packet.summary()['result']['context_available'])
        self.assertEqual(packet.summary()['result']['decisions'], len(register['decisions']))
        self.assertEqual(packet.context_questions()['result']['questions'], [
            dict(id=qid, present=q['present'], state=q['state'], owner=q['owner'])
            for qid, q in register['current'].items()])
        self.assertFalse(packet.context_question('Q2@P-2')['result']['current']['present'])
        seen, offset = [], 0
        while True:
            response = packet.decisions(limit=1, offset=offset)
            page = response['result']
            self.assertEqual(response['context_sha256'], hashlib.sha256(context_path.read_bytes()).hexdigest())
            seen.extend(page['decisions'])
            offset = page['next_offset']
            if offset is None:
                break
        self.assertEqual(seen, register['decisions'])
        self.assertEqual(packet.decisions('Q2@P-2')['result']['decisions'], [register['decisions'][1]])
        self.assertEqual(packet.context_question('Q1@P-1')['result']['ownership_history'], [register['ownership_history'][0]])
        self.assertEqual(packet.context_question('Q1@P-1')['result']['sources'], [register['sources'][0]])
        before = packet.decisions()
        context_path.write_text('{}', encoding='utf-8')
        with patch.object(Path, 'open', side_effect=AssertionError('No automatic refresh or fetch')):
            self.assertEqual(packet.decisions(), before)
            packet.context_question('Q2@P-2')
        with self.assertRaises(server.InputError):
            server.Snapshot(graph_path, context_path)

    def test_graph_only_context_never_follows_a_sidecar_reference(self):
        self.graph['context_register'] = {'schema': 'context-register-1', 'sidecar': '../../private.json'}
        packet = self.load()
        self.assertFalse(packet.summary()['result']['context_available'])
        with patch.object(Path, 'open', side_effect=AssertionError('Must not follow sidecar')):
            for fn in (packet.context_questions, packet.context_question, packet.decisions):
                with self.assertRaisesRegex(server.InputError, 'unavailable'):
                    fn('Q1') if fn == packet.context_question else fn()

    def test_mismatched_legacy_malformed_and_oversized_context_refuse(self):
        fixture = self.context_fixture()
        graph_path, context_path = fixture.root/'bundle/enriched_graph.json', fixture.root/'bundle/context.json'
        register, graph = fixture.read(), fixture.read('bundle/enriched_graph.json')
        wrong = copy.deepcopy(register)
        wrong['current']['Q1@P-1']['owner'] = 'different-owner'
        context_path.write_text(json.dumps(wrong), encoding='utf-8')
        with self.assertRaisesRegex(server.InputError, 'hash'):
            server.Snapshot(graph_path, context_path)
        graph['context_register']['content_sha256'] = context_register.digest(wrong)
        graph_path.write_text(json.dumps(graph), encoding='utf-8')
        with self.assertRaisesRegex(server.InputError, 'current state'):
            server.Snapshot(graph_path, context_path)
        graph['context_register'].pop('content_sha256')
        graph_path.write_text(json.dumps(graph), encoding='utf-8')
        with self.assertRaisesRegex(server.InputError, 'no bound context'):
            server.Snapshot(graph_path, context_path)
        for text in ('{"schema":"one","schema":"two"}', '{"value":NaN}', '{"title":"\\ud800"}'):
            context_path.write_text(text, encoding='utf-8')
            with self.assertRaises((server.InputError, UnicodeError)):
                server.Snapshot(graph_path, context_path)
        # Patch only the context reader's limit after a normal graph load boundary is accounted for.
        context_path.write_bytes(b' ' * (len(graph_path.read_bytes()) + 100))
        with patch.object(server, 'MAX_INPUT_BYTES', len(graph_path.read_bytes()) + 1):
            with self.assertRaisesRegex(server.InputError, 'Context snapshot exceeds'):
                server.Snapshot(graph_path, context_path)

    def test_context_paging_errors_and_single_record_size_limit(self):
        fixture = self.context_fixture()
        packet = server.Snapshot(fixture.root/'bundle/enriched_graph.json', fixture.root/'bundle/context.json')
        for bad in (-1, True, 1.5, 2, 3):
            with self.subTest(offset=bad), self.assertRaises(server.InputError):
                packet.decisions(offset=bad)
        with self.assertRaisesRegex(server.InputError, 'Unknown context'):
            packet.context_question('../../arbitrary.json')
        with self.assertRaisesRegex(server.InputError, 'Unknown context'):
            packet.decisions('https://example.invalid/source')
        with patch.object(server, 'MAX_RESPONSE_BYTES', 500), self.assertRaisesRegex(server.InputError, 'exceeds'):
            packet.decisions(limit=1)

    def test_stream_identity_is_exact_and_retains_original_edge_without_inferred_adjacency(self):
        graph = graph_export.build(ROOT/'data/bayer_rt/process_model.json',
                                   questions=ROOT/'examples/opportunity-screen/bayer/questions.json')
        packet = self.load(graph)
        expected = next(e for e in graph['edges'] if e['id'] == 'S1' and e['type'] == 'connects')
        self.assertEqual(packet.asset('stream:S1')['result'], expected)
        self.assertEqual(packet.relations('stream:S1', 100)['result']['relations'], [
            e for e in graph['edges'] if e is expected or 'stream:S1' in (e['from'], e['to'])])
        found = packet.question_list('stream:S1')['result']['questions']
        self.assertTrue(any(q['id'] == 'E11@stream:S1' for q in found))
        self.assertEqual(packet.search('stream:S1', 50)['result']['matches'][0]['id'], 'stream:S1')
        for alias in ('S1', 'stream:S1 ', 'stream:missing'):
            with self.subTest(alias=alias), self.assertRaises(server.InputError):
                packet.asset(alias)
        collision = copy.deepcopy(graph)
        collision['nodes'].append(dict(copy.deepcopy(graph['nodes'][0]), id='stream:S1'))
        with self.assertRaisesRegex(server.InputError, 'collide'):
            self.load(collision)


if __name__ == '__main__':
    unittest.main()
