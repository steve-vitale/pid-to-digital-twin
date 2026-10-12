"""Adapter plumbing controls, not a dataset/generalization evaluation."""
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import adapt_pid2graph_synthetic as adapter


class AdapterControls(unittest.TestCase):
    def fixture(self, folder, label='valve', xmax=30):
        png = folder / 'sample.png'
        png.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\0' * 8 + struct.pack('>II', 100, 100))
        ns = 'http://graphml.graphdrawing.org/xmlns'
        root = ET.Element(f'{{{ns}}}graphml')
        for key in ['label', 'xmin', 'ymin', 'xmax', 'ymax']:
            ET.SubElement(root, f'{{{ns}}}key', {'id': key, 'attr.name': key, 'for': 'node'})
        graph = ET.SubElement(root, f'{{{ns}}}graph', {'edgedefault': 'undirected'})
        for sid, cls, box in [('a', label, [10, 10, xmax, 30]), ('c', 'connector', [40, 20, 40, 20]), ('b', 'instrumentation', [60, 10, 80, 30])]:
            node = ET.SubElement(graph, f'{{{ns}}}node', {'id': sid})
            for key, value in zip(['label', 'xmin', 'ymin', 'xmax', 'ymax'], [cls] + box):
                ET.SubElement(node, f'{{{ns}}}data', {'key': key}).text = str(value)
        for source, target in [('a', 'c'), ('c', 'b')]:
            ET.SubElement(graph, f'{{{ns}}}edge', {'source': source, 'target': target})
        path = folder / 'sample.graphml'
        ET.ElementTree(root).write(path)
        return path, png

    def test_split_is_disjoint_and_excludes_old_holdout_b(self):
        cfg, _ = adapter.settings()
        dev, reserved = set(cfg['development']), set(cfg['reserved_unopened'])
        self.assertFalse(dev & reserved)
        old = set('23,44,62,78,109,111,122,143,149,158,209,224,290,345,363,366,382,400,494,496'.split(','))
        self.assertFalse((dev | reserved) & old)
        self.assertEqual(cfg['dataset'], 'PID2Graph Synthetic')

    def test_oracle_preserves_absence_and_collapses_connectors(self):
        with tempfile.TemporaryDirectory() as tmp:
            key, png = self.fixture(Path(tmp))
            pred, coverage = adapter.oracle_prediction(key, png)
            self.assertEqual(pred['connections'], [{'from': 'a', 'to': 'b'}])
            self.assertTrue(all(s['tag'] is None and s['confidence'] is None for s in pred['symbols']))
            self.assertEqual(pred['symbols'][0]['box'], [100, 100, 300, 300])
            score = adapter.scorer.score(key, pred, png)
            self.assertEqual(score['review_load']['per_100'], 0)

    def test_unknown_taxonomy_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            key, png = self.fixture(Path(tmp), label='new-unmapped-class')
            with self.assertRaisesRegex(ValueError, 'Unmapped'):
                adapter.oracle_prediction(key, png)

    def test_out_of_bounds_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            key, png = self.fixture(Path(tmp), xmax=101)
            with self.assertRaisesRegex(ValueError, 'outside'):
                adapter.oracle_prediction(key, png)

    def test_range_response_must_be_partial_and_exact(self):
        class BadResponse:
            status = 200
            headers = {}
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, length): raise AssertionError('Must reject before body download')
        remote = object.__new__(adapter.CheckedRangeFile)
        remote.cache, remote.size, remote.url, remote.fetched = {}, 100, 'https://example.invalid/data.zip', 0
        with patch.object(adapter.urllib.request, 'urlopen', return_value=BadResponse()):
            with self.assertRaisesRegex(ValueError, 'Range'):
                remote._block(0)

    def test_range_response_truncation_is_rejected(self):
        class BadResponse:
            status = 206
            headers = {'Content-Range': 'bytes 0-99/100'}
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, length): return b'x'
        remote = object.__new__(adapter.CheckedRangeFile)
        remote.cache, remote.size, remote.url, remote.fetched = {}, 100, 'https://example.invalid/data.zip', 0
        with patch.object(adapter.urllib.request, 'urlopen', return_value=BadResponse()):
            with self.assertRaisesRegex(ValueError, 'Truncated'):
                remote._block(0)

    def test_structural_validity_never_implies_operational_approval(self):
        status = adapter.review_readiness({'units': [{'id': 'u1'}], 'streams': []})
        self.assertTrue(status['draft_review_exports_allowed'])
        self.assertFalse(status['operational_export_allowed'])
        self.assertEqual(status['unreviewed_items'], 1)

    def test_ops_review_does_not_resolve_unmeasured_domain_semantics(self):
        status = adapter.review_readiness({'units': [{'id': 'u1', 'ops_review': {'status': 'confirmed'}}]})
        self.assertEqual(status['unreviewed_items'], 0)
        self.assertFalse(status['operational_export_allowed'])

    def test_changed_source_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / '0.graphml'
            path.write_text('original')
            cfg = {'expected_source_sha256': {'0.graphml': adapter.digest(path)}}
            adapter.verify_sources(cfg, Path(tmp))
            path.write_text('edited')
            with self.assertRaisesRegex(ValueError, 'checksum changed'):
                adapter.verify_sources(cfg, Path(tmp))


if __name__ == '__main__':
    unittest.main()
