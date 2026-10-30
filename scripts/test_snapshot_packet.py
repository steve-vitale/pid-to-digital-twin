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


if __name__ == '__main__':
    unittest.main()
