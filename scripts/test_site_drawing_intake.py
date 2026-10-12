"""Synthetic local intake controls; no public data, installed extras or model calls."""
import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import zlib

import import_site_drawing as intake


def png():
    def chunk(kind, payload):
        return struct.pack('>I', len(payload)) + kind + payload + struct.pack('>I', zlib.crc32(kind + payload) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 200, 100, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress((b'\0' + b'\xff' * 600) * 100)) + chunk(b'IEND', b''))


class IntakeControls(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.image = self.root / 'Utility skid rev A.png'
        self.image.write_bytes(png())
        self.extraction = self.root / 'Already extracted symbols.json'
        self.pred = {'symbols': [
            {'id': 'tank', 'class': 'tank', 'tag': 'UTL-TK-101', 'box': [100, 100, 200, 200], 'confidence': .9},
            {'id': 'valve', 'class': 'valve', 'tag': 'V-101', 'box': [400, 100, 450, 150], 'confidence': None},
            {'id': 'instrument', 'class': 'instrumentation', 'tag': 'PT-101', 'box': [110, 250, 150, 290], 'confidence': .6},
            {'id': 'unlinked', 'class': 'instrumentation', 'tag': None, 'box': [405, 200, 440, 240], 'confidence': None}],
            'connections': [{'from': 'tank', 'to': 'valve'}, {'from': 'tank', 'to': 'instrument'}]}
        self.manifest = {'schema_version': intake.SCHEMA, 'drawing_id': 'UTIL-PID-A', 'revision': 'A', 'page': 1,
                         'image': self.image.name, 'extraction': self.extraction.name, 'extraction_format': 'prediction',
                         'producer': {'method': 'authored synthetic test', 'tool': 'manual', 'model': None},
                         'drawing_number': 'UTL-PID-100-1', 'system_name': 'Utility <skid> & test'}
        self.path = self.root / 'manifest.json'
        self.out = self.root / 'review-bundle'
        self.write_inputs()

    def write_inputs(self, record=None):
        self.extraction.write_text(json.dumps(self.pred if record is None else record), encoding='utf-8')
        self.path.write_text(json.dumps(self.manifest), encoding='utf-8')

    def reject(self):
        hashes = [hashlib.sha256(p.read_bytes()).hexdigest() for p in (self.path, self.image, self.extraction)]
        with self.assertRaises((ValueError, TypeError)):
            intake.import_drawing(self.path, self.out)
        self.assertFalse(self.out.exists())
        self.assertFalse(list(self.root.glob('.site-intake-*')))
        self.assertEqual(hashes, [hashlib.sha256(p.read_bytes()).hexdigest() for p in (self.path, self.image, self.extraction)])

    def test_complete_bundle_is_unverified_with_persistent_provenance(self):
        result = intake.import_drawing(self.path, self.out)
        self.assertTrue(result['exports_written'])
        self.assertFalse(result['operational_export_allowed'])
        model = json.loads((self.out / 'plant_model.json').read_text())
        evidence = json.loads((self.out / 'intake_manifest.json').read_text())
        self.assertEqual(evidence['drawing']['drawing_id'], 'UTIL-PID-A')
        self.assertEqual(evidence['image_size_px'], [200, 100])
        self.assertEqual((self.out / evidence['original_manifest']).read_bytes(), self.path.read_bytes())
        self.assertEqual(evidence['manifest_sha256'], intake.digest((self.out / evidence['original_manifest']).read_bytes()))
        self.assertEqual((self.out / 'source/0.png').read_bytes(), self.image.read_bytes())
        self.assertEqual((self.out / 'source/extraction-original.json').read_bytes(), self.extraction.read_bytes())
        self.assertEqual(evidence['sources']['image']['sha256'], intake.digest(self.image.read_bytes()))
        self.assertEqual(evidence['pi_mapping_sha256'], intake.digest(Path(intake.pi_mapping.__file__).read_bytes()))
        self.assertEqual(model['dropped'], {'symbols': [], 'connections': []})
        self.assertNotIn('risk_model', model['meta'])
        self.assertEqual(model['meta']['parent_rule'], 'linked')
        self.assertEqual(len(model['streams']), 2)
        self.assertEqual(model['systems'][0]['sheet'], '0')
        for collection in ('units', 'instruments', 'line_items', 'offpage_connectors', 'streams'):
            for item in model[collection]:
                self.assertEqual(item['verification']['status'], 'unverified')
                self.assertNotIn('risk', item)
                self.assertNotIn('point_mapping', item)
                for p in item.get('provenance', []):
                    self.assertTrue((self.out / p['source_run']).is_file())
                    self.assertEqual(p['source_drawing']['revision'], 'A')
        self.assertTrue(all(s['direction'] == 'unknown' for s in model['streams']))
        unlinked = next(i for i in model['instruments'] if i['tag'] is None)
        self.assertEqual(unlinked['parent_method'], 'geometry_nearest')
        self.assertEqual(next(i for i in model['instruments'] if i['tag'] == 'PT-101')['confidence'], .6)
        for name in ('review_queue.csv', 'ignition/tags.json', 'pi/pi_builder_af.csv', 'svg/sheet_0.svg', 'READ_ME.txt'):
            self.assertTrue((self.out / name).is_file(), name)
        svg = ET.parse(self.out / 'svg/sheet_0.svg')
        bg = svg.find('.//{http://www.w3.org/2000/svg}image')
        self.assertEqual(bg.attrib['href'], '../source/0.png')
        all_output = (self.out / 'plant_model.json').read_text() + (self.out / 'svg/sheet_0.svg').read_text()
        self.assertNotIn(str(self.root), all_output)
        self.assertNotIn('.site-intake-', all_output)

    def test_cli_works_without_site_packages_public_data_or_current_repo_directory(self):
        result = subprocess.run([sys.executable, '-S', str(Path(intake.__file__).resolve()), '--manifest', str(self.path),
                                 '--out', str(self.out)], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)['exports_written'])

    def test_check_only_writes_nothing(self):
        before = set(self.root.iterdir())
        result = intake.import_drawing(self.path, self.out, check_only=True)
        self.assertTrue(result['inputs_valid'])
        self.assertFalse(result['exports_written'])
        self.assertEqual(before, set(self.root.iterdir()))

    def test_repeat_into_new_destinations_is_identical_for_fixture(self):
        intake.import_drawing(self.path, self.out)
        other = self.root / 'another-bundle'
        intake.import_drawing(self.path, other)
        for path in self.out.rglob('*'):
            if path.is_file():
                self.assertEqual(path.read_bytes(), (other / path.relative_to(self.out)).read_bytes())

    def test_equal_distance_parent_is_stable_across_hash_seeds(self):
        self.pred = {'symbols': [
            {'id': 'a', 'class': 'tank', 'box': [100, 100, 200, 200]},
            {'id': 'b', 'class': 'tank', 'box': [400, 100, 500, 200]},
            {'id': 'p', 'class': 'instrumentation', 'box': [275, 100, 325, 200]},
            {'id': 'v', 'class': 'valve', 'box': [275, 300, 325, 400]},
            {'id': 'q', 'class': 'instrumentation', 'box': [275, 500, 325, 600]},
            {'id': 'r', 'class': 'instrumentation', 'box': [275, 700, 325, 800]}],
            'connections': [{'from': 'p', 'to': x} for x in ('a', 'b')] +
                           [{'from': 'v', 'to': x} for x in ('a', 'b')] +
                           [{'from': 'q', 'to': 'p'}, {'from': 'r', 'to': 'q'}]}
        self.write_inputs()
        models = []
        for seed in ('0', '1', '7', '42', '123'):
            output = self.root / ('seed-' + seed)
            result = subprocess.run([sys.executable, '-S', str(Path(intake.__file__).resolve()),
                                     '--manifest', str(self.path), '--out', str(output)],
                                    cwd=self.root, env={**os.environ, 'PYTHONHASHSEED': seed},
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            models.append(json.loads((output / 'plant_model.json').read_text()))
        self.assertTrue(all(m == models[0] for m in models))
        self.assertEqual(models[0]['line_items'][0]['unit'], 'S0-TK001')
        self.assertTrue(all(i['parent'] == 'S0-TK001' for i in models[0]['instruments']))

    def test_forked_instrument_chain_is_stable_across_hash_seeds(self):
        self.pred = {'symbols': [
            {'id': sid, 'class': cls, 'tag': sid, 'box': [x, 100, x + 10, 110]}
            for sid, cls, x in [('T1', 'tank', 100), ('T2', 'tank', 900),
                                ('I', 'instrumentation', 500), ('J1', 'instrumentation', 300),
                                ('J2', 'instrumentation', 700)]],
            'connections': [{'from': a, 'to': b} for a, b in
                            [('I', 'J1'), ('I', 'J2'), ('J1', 'T1'), ('J2', 'T2')]]}
        self.write_inputs()
        models = []
        for seed in ('0', '1', '2', '7', '42', '123'):
            output = self.root / ('fork-seed-' + seed)
            result = subprocess.run([sys.executable, '-S', str(Path(intake.__file__).resolve()),
                                     '--manifest', str(self.path), '--out', str(output)],
                                    cwd=self.root, env={**os.environ, 'PYTHONHASHSEED': seed},
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            models.append(json.loads((output / 'plant_model.json').read_text()))
        self.assertTrue(all(m == models[0] for m in models))
        item = next(i for i in models[0]['instruments'] if i['tag'] == 'I')
        self.assertEqual(item['parent'], 'S0-TK001')
        self.assertEqual(item['parent_method'], 'via_instrument_chain')
        self.assertEqual(item['verification']['status'], 'unverified')

    def test_run_record_and_bbox_import(self):
        box = self.pred['symbols'][0].pop('box')
        self.pred['symbols'][0]['bbox'] = dict(zip(('x_min', 'y_min', 'x_max', 'y_max'), box))
        self.manifest['extraction_format'] = 'run-record'
        self.write_inputs({'prediction': self.pred, 'image_sha256': intake.digest(self.image.read_bytes()), 'tool': 'claimed-tool'})
        self.assertTrue(intake.import_drawing(self.path, self.out)['exports_written'])

    def test_failed_and_hash_mismatched_records_rejected(self):
        self.manifest['extraction_format'] = 'run-record'
        for patch_value in ({'error': 'failed'}, {'parse_error': 'invalid'}, {'image_sha256': 'wrong'}):
            with self.subTest(patch_value=patch_value):
                self.write_inputs({'prediction': self.pred, **patch_value})
                self.reject()

    def test_bad_symbol_shapes_are_rejected(self):
        base = copy.deepcopy(self.pred)
        for change in ({'id': ''}, {'id': '../x'}, {'id': 'bad"id'}, {'class': 'unknown'}, {'tag': 123},
                       {'confidence': True}, {'confidence': 1.01}, {'confidence': float('inf')},
                       {'box': [20, 10, 10, 30]}, {'box': [0, 0, 1001, 5]}, {'box': [0, 0, 0, 5]},
                       {'box': [True, 0, 4, 5]}, {'box': [0, 0, .001, 5]}, {'bbox': {}}):
            with self.subTest(change=change):
                self.pred = copy.deepcopy(base)
                self.pred['symbols'][0].update(change)
                self.write_inputs()
                self.reject()

    def test_bad_connections_and_collections_are_rejected(self):
        base = copy.deepcopy(self.pred)
        for links in ([{'from': 'tank', 'to': 'missing'}], [{'from': 'tank', 'to': 'tank'}],
                      [{'from': 'tank', 'to': 'valve'}, {'from': 'valve', 'to': 'tank'}], [None], {}, None):
            with self.subTest(links=links):
                self.pred = copy.deepcopy(base)
                self.pred['connections'] = links
                self.write_inputs()
                self.reject()
        self.pred = copy.deepcopy(base)
        self.pred['symbols'].append(copy.deepcopy(self.pred['symbols'][0]))
        self.write_inputs()
        self.reject()
        for symbols in ([], {}, None, [None]):
            self.pred['symbols'] = symbols
            self.write_inputs()
            self.reject()

    def test_duplicate_keys_and_non_finite_json_rejected(self):
        for content in ('{"symbols": [], "symbols": []}', '{"symbols": NaN}', '{"extra": 1e999}', '[1,2]', '{bad'):
            self.extraction.write_text(content)
            self.reject()

    def test_formula_and_invalid_xml_text_rejected(self):
        for value in ('=1+1', '  +SUM(A1:A2)', '-1+2', '@SUM(A1:A2)', '\ud800', '\ufffe', '\x00'):
            for target in ('tag', 'drawing_id', 'system_name', 'producer'):
                with self.subTest(value=repr(value), target=target):
                    original = copy.deepcopy(self.manifest)
                    old_tag = self.pred['symbols'][0]['tag']
                    if target == 'tag':
                        self.pred['symbols'][0]['tag'] = value
                    elif target == 'producer':
                        self.manifest['producer']['tool'] = value
                    else:
                        self.manifest[target] = value
                    self.write_inputs()
                    self.reject()
                    self.manifest = original
                    self.pred['symbols'][0]['tag'] = old_tag

    def test_png_structure_rejection(self):
        valid = self.image.read_bytes()
        for content in (b'not png', valid[:24], valid[:-1], valid + b'trailing', valid[:40] + b'X' + valid[41:]):
            self.image.write_bytes(content)
            self.reject()

    def test_png_critical_chunks_and_palette_rules(self):
        def chunk(kind, data):
            return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
        valid = png()
        palette = chunk(b'PLTE', bytes(3))
        indexed = (valid[:8] + chunk(b'IHDR', struct.pack('>IIBBBBB', 200, 100, 8, 3, 0, 0, 0)) + valid[33:])
        cases = (valid[:33] + chunk(b'NEWX', b'') + valid[33:],
                 valid[:33] + palette + palette + valid[33:],
                 valid[:-12] + palette + valid[-12:], indexed,
                 valid[:33] + chunk(b'PLTE', b'xx') + valid[33:],
                 valid[:33] + chunk(b'acTL', bytes(8)) + valid[33:])
        for content in cases:
            self.image.write_bytes(content)
            self.reject()

    def test_manifest_validation(self):
        original = copy.deepcopy(self.manifest)
        for key, value in (('schema_version', 'other'), ('page', True), ('page', 0), ('drawing_id', ''),
                           ('revision', None), ('producer', None), ('extraction_format', 'auto'), ('image', 'missing.png')):
            with self.subTest(key=key, value=value):
                self.manifest = copy.deepcopy(original)
                self.manifest[key] = value
                self.write_inputs()
                self.reject()

    def test_existing_output_and_overlap_preserve_inputs(self):
        self.out.mkdir()
        sentinel = self.out / 'keep.txt'
        sentinel.write_text('unchanged')
        with self.assertRaises(ValueError):
            intake.import_drawing(self.path, self.out)
        self.assertEqual(sentinel.read_text(), 'unchanged')
        for path in (self.root, self.image, self.extraction):
            with self.assertRaises(ValueError):
                intake.import_drawing(self.path, path)

    def test_render_failure_removes_staging_and_never_publishes(self):
        with patch.object(intake.generate, 'export_twin', side_effect=ValueError('render failed')):
            self.reject()

    def test_no_dependency_or_model_modules_imported_by_cli(self):
        code = ('import sys; sys.path.insert(0, ' + repr(str(Path(intake.__file__).parent)) + '); '
                'import import_site_drawing; '
                'assert not {"cv2", "numpy", "trace_connections", "run_extraction", "confidence"}.intersection(sys.modules)')
        result = subprocess.run([sys.executable, '-S', '-c', code], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
