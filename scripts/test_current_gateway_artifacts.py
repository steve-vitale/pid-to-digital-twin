"""Offline current-source import/semantic contract. Never constructs a gateway client.

These are file-level checks, not runtime Ignition schema, quality, or browser acceptance.
The reviewed OPEN100 fixture deliberately keeps FT 1401 ambiguous and MS 14010 metadata-only.
"""
import contextlib
import copy
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
# Offline tests do not need or read a private gateway environment file.
os.environ.pop('IGNITION_ENV_FILE', None)
sys.path.insert(0, str(ROOT / 'scripts/ignition'))
import build_gateway as bg
import build_views as bv
import verify_gateway as vg
from te_channels import expanded_items, channel_columns

TWIN = ROOT / 'out/twin/r2-tiles-trace/codex'


def snapshot():
    held = object.__new__(vg.Held)  # no network constructor
    held.provider = json.loads((bg.OUT / 'twin_provider.json').read_text())
    held.types = {t['name']: t for t in held.folder('_types_')['tags']}
    with zipfile.ZipFile(bg.OUT / 'PIDTwin.zip') as z:
        held.views = {n.split('/views/')[1][:-len('/view.json')]: json.loads(z.read(n))
                      for n in z.namelist() if n.endswith('/view.json')}
        pages = json.loads(z.read('com.inductiveautomation.perspective/page-config/config.json'))['pages']
        assert z.testzip() is None
        for n in z.namelist():
            if n.endswith('/resource.json'):
                resource = json.loads(z.read(n))
                assert resource['scope'] == 'G'
                assert all(n.rsplit('/', 1)[0] + '/' + f in z.namelist() for f in resource['files'])
    return held, pages


def walk(node):
    yield node
    for child in node.get('children', []):
        yield from walk(child)


class CurrentGatewayContract(unittest.TestCase):
    def setUp(self):
        self.held, self.pages = snapshot()
        self.te = json.loads(bg.MODEL.read_text())
        self.tw = json.loads((TWIN / 'plant_model.json').read_text())
        self.meta = json.loads((bg.OUT / 'build_meta.json').read_text())

    def test_write_only_is_local_and_matches_committed_artifacts(self):
        # Fail closed if this code path ever reaches network or Gateway setup.
        with tempfile.TemporaryDirectory(dir=ROOT / "out") as tmp, patch.object(bg, 'OUT', Path(tmp)), \
             patch.object(bg, 'Gateway', side_effect=AssertionError('Gateway construction forbidden')), \
             patch('socket.socket.connect', side_effect=AssertionError('network forbidden')), \
             patch('urllib.request.urlopen', side_effect=AssertionError('network forbidden')), \
             patch.object(sys, 'argv', ['build_gateway.py', '--write-only', '--twin', str(TWIN.relative_to(ROOT))]), \
             contextlib.redirect_stdout(io.StringIO()):
            bg.main()
            for filename in ('twin_provider.json', 'build_meta.json', 'PIDTwin.zip'):
                self.assertEqual((Path(tmp) / filename).read_bytes(),
                                 (ROOT / 'out/ignition/gateway' / filename).read_bytes(), filename)

    def test_every_exported_script_transform_parses_as_a_perspective_body(self):
        # Perspective compiles TRANSFORM_SIGNATURE + "\n" + code unmodified. The first native import found every
        # script transform failing to parse (unindented bodies; journal entry 37). This is a Python 3 parse of the
        # exported bytes, a proxy for Jython 2.7: runtime execution still needs a gateway.
        codes = []

        def collect(node):
            if isinstance(node, dict):
                if node.get('type') == 'script' and 'code' in node:
                    codes.append(node['code'])
                for value in node.values():
                    collect(value)
            elif isinstance(node, list):
                for value in node:
                    collect(value)
        collect(self.held.views)
        self.assertGreater(len(codes), 500)
        for code in codes:
            compile(bv.build_hmi.TRANSFORM_SIGNATURE + '\n' + code, '<perspective transform>', 'exec')
        with self.assertRaises(SyntaxError):  # control: the shipped (unindented) form is rejected
            compile(bv.build_hmi.TRANSFORM_SIGNATURE + '\nreturn value\n', '<perspective transform>', 'exec')

    def test_drawing_and_schematic_values_never_render_null(self):
        # The numeric format transform these labels used rendered a Bad (no data) value as the text "null": all 334
        # OPEN100 placeholders read "null" on screen (journal entry 37). Bad quality must read as an honest state.
        class Quality:
            def __init__(self, good): self.good = good
            def isGood(self): return self.good

        def run(code, value, good):
            scope = {}
            exec(bv.build_hmi.TRANSFORM_SIGNATURE + '\n' + code, scope)
            return scope['transform'](None, value, Quality(good), None)
        mapped = set(self.meta['twin_review']['mapped'])
        checked = {'not connected': 0, 'UNKNOWN': 0}
        for name, view in self.held.views.items():
            if not (name.startswith('OPEN100/Sheet_') or name == 'TE/Schematic'):
                continue
            for c in walk(view['root']):
                b = c.get('propConfig', {}).get('props.text', {}).get('binding', {})
                if b.get('type') != 'tag' or not b['config']['tagPath'].endswith('/PV'):
                    continue
                self.assertEqual([t['type'] for t in b['transforms']], ['script'], (name, c['meta']['name']))
                code = b['transforms'][0]['code']
                expect = 'not connected' if name.startswith('OPEN100') and c['meta']['name'] not in mapped \
                    else 'UNKNOWN'
                for value in (None, 0.0, float('nan')):
                    self.assertEqual(run(code, value, False), expect, (name, c['meta']['name']))
                self.assertEqual(run(code, 1234.56, True), '1,234.6')
                self.assertEqual(run(code, float('nan'), True), 'UNKNOWN')
                checked[expect] += 1
        self.assertEqual(checked['not connected'], 334)
        self.assertGreaterEqual(checked['UNKNOWN'], 24)

    def test_schema_shape_tag_paths_routes_and_spatial_views(self):
        self.assertEqual(len(self.held.views), 23)
        self.assertEqual(set(self.held.views), {p['viewPath'] for p in self.pages.values()})
        self.assertEqual(self.held.views['TE/Overview'], self.held.views['TE/ProcessMimic'])
        for uid in bv.build_hmi.UNIT_ORDER:
            view = self.held.views['TE/Unit_' + uid]
            names = {c.get('meta', {}).get('name') for c in walk(view['root'])}
            self.assertIn('UnitGraphicNote', names)
            self.assertIn('BackOverview', names)
            self.assertEqual(self.pages['/unit/' + uid]['viewPath'], 'TE/Unit_' + uid)
        paths = self.held.tag_paths()
        for name, view in self.held.views.items():
            self.assertEqual(view['root']['type'], 'ia.container.coord')
            for _, _, path in vg.bindings(view):
                self.assertIn(path, paths, name)
            for c in walk(view['root']):
                children = [x['meta']['name'] for x in c.get('children', [])]
                self.assertEqual(len(children), len(set(children)), name)
                for events in c.get('events', {}).values():
                    for event in events.values():
                        if event.get('type') == 'nav':
                            self.assertIn(event['config']['page'], self.pages, name)
        self.assertTrue(vg.v2(self.held, self.te, self.tw)['passed'])
        self.assertTrue(vg.v3(self.held, TWIN)['passed'])

    def test_review_semantics_and_no_mapping(self):
        instruments = {i['id']: i for i in self.tw['instruments']}
        instances = {i['parameters']['AssetId']['value']: i for _, i in self.held.instances('OPEN100')}
        ms = instruments['S0-IN019']
        self.assertEqual((ms['tag'], ms['loop'], ms['variable'], ms['instrument_kind'], ms['reviewed_valve_association']),
                         ('MS 14010', '14010', 'unknown', 'valve callout', 'S0-VL013'))
        self.assertEqual(ms['ops_review']['field_decisions']['variable']['scope'], 'valve_association')
        self.assertEqual(ms['ops_review']['field_decisions']['tag']['scope'], 'identifier_text')
        for aid in ('S0-IN002', 'S0-IN003', 'S0-IN019'):
            self.assertFalse(instruments[aid].get('data_point'))
            self.assertEqual(instruments[aid]['verification']['status'], 'unverified')
            self.assertEqual(instruments[aid]['ops_review']['status'], 'unverified')
            self.assertNotIn(aid, self.meta['twin_review']['mapped'])
        for aid in ('S0-IN002', 'S0-IN003'):
            self.assertIn('NEEDS CLARIFICATION', instruments[aid]['ops_review']['notes'])
            self.assertEqual(instances[aid]['typeId'], 'Instrument_FT')
            self.assertTrue(instances[aid]['parameters']['PointName']['value'].startswith('PLACEHOLDER_'))
        self.assertEqual(instances['S0-IN019']['typeId'], 'Callout_Valve')
        self.assertIsNone(self.held.member(instances['S0-IN019'], 'PV'))
        self.assertEqual(set(instances['S0-IN019']['parameters']), {'AssetId', 'SourceTag'})

    def test_channel_sets_quality_contract(self):
        te, no_data, tw = vg.live_sets(self.held, self.meta)
        self.assertEqual(len(channel_columns(self.te)), 52)
        self.assertEqual(len(expanded_items(self.te)), 53)
        self.assertEqual(sum(p.startswith('[Twin]TE_Plant/') for p, *_ in te), 52)
        self.assertEqual(sum(p.startswith('[Twin]OPEN100/') for p, *_ in te), 24)
        self.assertEqual([i['parameters']['Tag']['value'] for _, _, i in no_data], ['SC-212'])
        self.assertEqual(len(tw), 334)
        def reading(good):
            return SimpleNamespace(StatusCode=SimpleNamespace(is_good=lambda: good, name='Good' if good else 'Bad'),
                                   Value=SimpleNamespace(Value=1))
        reads = {p: reading(True) for p, *_ in te}
        reads.update({p: reading(False) for p, *_ in no_data + tw})
        self.assertTrue(vg.v4(reads, te, no_data, tw)['passed'])
        reads[no_data[0][0]] = reading(True)
        self.assertFalse(vg.v4(reads, te, no_data, tw)['passed'])
        reads[no_data[0][0]] = reading(False)
        reads[te[0][0]] = reading(False)
        self.assertFalse(vg.v4(reads, te, no_data, tw)['passed'])
        reads[te[0][0]] = reading(True)
        reads[tw[0][0]] = reading(True)
        self.assertFalse(vg.v4(reads, te, no_data, tw)['passed'])

    def test_missing_expanded_channel_fails(self):
        for folder in self.held.folder('TE_Plant')['tags']:
            folder['tags'] = [i for i in folder['tags'] if i['name'] != 'AI-123-B']
        self.assertFalse(vg.v2(self.held, self.te, self.tw)['passed'])

    def test_invented_callout_pv_or_mapping_fails(self):
        for key, value in [('tags', [{'name': 'PV', 'tagType': 'AtomicTag', 'valueSource': 'memory', 'value': 0}]),
                           ('parameters', {'BasePath': {'value': 'invented'}})]:
            h = copy.deepcopy(self.held)
            instance = next(i for _, i in h.instances('OPEN100') if i['parameters']['AssetId']['value'] == 'S0-IN019')
            if key == 'parameters':
                instance[key].update(value)
            else:
                instance[key] = value
            self.assertFalse(vg.v2(h, self.te, self.tw)['passed'])

    def test_missing_or_numeric_unavailable_indicator_fails(self):
        view = self.held.views['TE/Unit_R-101']
        indicator = next(c for c in walk(view['root']) if c.get('meta', {}).get('name') == 'SC-212')
        indicator['props']['text'] = '0.0'
        self.assertFalse(vg.v3(self.held, TWIN)['passed'])
        indicator['props']['text'] = 'NOT CONNECTED'
        indicator['propConfig'] = {'props.text': {'binding': {'type': 'tag', 'config': {'tagPath': '[Twin]TE_Plant/R-101/SC-212/PV'}}}}
        self.assertFalse(vg.v3(self.held, TWIN)['passed'])
        view['root']['children'].remove(indicator)
        self.assertFalse(vg.v3(self.held, TWIN)['passed'])

    def test_missing_required_binding_fails(self):
        view = self.held.views['TE/Unit_R-101']
        item = next(c for c in walk(view['root']) if c.get('meta', {}).get('name') == 'AI-123-B')
        item['propConfig'].pop('props.text')
        self.assertFalse(vg.v3(self.held, TWIN)['passed'])

    def test_ordinary_unmapped_instrument_still_requires_binding(self):
        view = self.held.views['OPEN100/Sheet_0']
        item = next(c for c in walk(view['root']) if c.get('meta', {}).get('name') == 'S0-IN002')
        item['propConfig'].pop('props.text')
        self.assertFalse(vg.v3(self.held, TWIN)['passed'])

    def test_spatial_unknown_marker_required(self):
        view = self.held.views['TE/Unit_R-101']
        item = next(c for c in walk(view['root']) if c.get('meta', {}).get('name') == 'Unavailable_SC-212')
        item['props']['text'] = 'SC-212 0.0'
        self.assertFalse(vg.v3(self.held, TWIN)['passed'])


if __name__ == '__main__':
    unittest.main()
