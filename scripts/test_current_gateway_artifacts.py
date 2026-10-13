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
        # script transform failing to parse (unindented bodies; journal entry 38). This is a Python 3 parse of the
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

    def test_every_band_indicator_shows_its_band(self):
        # TI-109's real 0.24 degC band was drawn on a span stretched to its 175 degC alarm: a sub-pixel sliver that
        # read as missing data (journal entry 38). Every indicator must give its band a visible share of its span.
        shares = {}
        for name, view in self.held.views.items():
            for c in walk(view['root']):
                if c.get('type') == 'ia.display.moving-analog-indicator':
                    p = c['props']
                    shares[(name, c['meta']['name'])] = (p['desiredHigh'] - p['desiredLow']) / (p['maxValue'] - p['minValue'])
                    for key in ('highAlarm', 'highHighAlarm'):
                        if key in p:
                            self.assertLessEqual(p[key], p['maxValue'], (name, c['meta']['name'], key))
        self.assertGreater(len(shares), 50)
        self.assertGreaterEqual(min(shares.values()), 0.1, min(shares, key=shares.get))

    def test_drawing_and_schematic_values_never_render_null(self):
        # The numeric format transform these labels used rendered a Bad (no data) value as the text "null": all 334
        # OPEN100 placeholders read "null" on screen (journal entry 38). Bad quality must read as an honest state.
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

    def summary(self):
        plant = next(t for t in self.held.provider['tags'] if t['name'] == 'TE_Plant')
        return {t['name']: t for t in next(u for u in plant['tags'] if u['name'] == '_Summary')['tags']}

    def test_alarm_count_counts_alarms_not_tags(self):
        # Journal 38: the header read "Alarms: 1" while the table listed PI-107's two active alarms.
        s = self.summary()['AlarmsActive']
        want = [(f'[Twin]TE_Plant/{self.meta["te_ranges"][t]["unit"]}/{t}/PV', a['name'])
                for t, alarms in bg.ALARMS.items() for a in alarms]
        self.assertEqual(s['expression'], ' + '.join(f'toInt(isAlarmActive("{p}", "{n}"))' for p, n in want))
        self.assertEqual(len(want), 3)
        self.assertEqual(s['executionMode'], 'FixedRate')

    def test_data_source_diagnostic_alarms(self):
        s = self.summary()
        te_fed = sorted(p for p, _, _ in vg.live_sets(self.held, self.meta)[0] if p.startswith('[Twin]TE_Plant'))
        demo = sorted(p for p, _, _ in vg.live_sets(self.held, self.meta)[0] if p.startswith('[Twin]OPEN100'))
        self.assertEqual((len(te_fed), len(demo)), (52, 24))
        for name, paths in (('ReplayValuesNotGood', te_fed), ('DemoPointsNotGood', demo)):
            tag = s[name]
            terms = tag['expression'].split(' + ')
            self.assertEqual(sorted(t[len('toInt(!isGood({'):-len('}))')] for t in terms), paths, name)
            self.assertEqual(tag['executionMode'], 'FixedRate')
            (alarm,) = tag['alarms']
            # Inclusive AboveValue: a setpoint of 0 stayed active at a count of 0 in the gateway (journal entry 40).
            self.assertEqual((alarm['name'], alarm['mode'], alarm['setpointA']), ('DataSourceLost', 'AboveValue', 0.5))
            self.assertTrue(alarm['label'].startswith('Data source lost'))
            self.assertEqual(alarm['displayPath'], alarm['label'])
            self.assertIn('DIAGNOSTIC alarm, not a process alarm', alarm['notes'])
        self.assertNotIn('SC-212', s['ReplayValuesNotGood']['expression'])  # no source: Bad by design, not a loss
        self.assertEqual(s['DiagnosticAlarmsActive']['expression'].count('isAlarmActive('), 2)
        # Diagnostic alarms are not process alarms: the process count must not include them.
        self.assertNotIn('_Summary', s['AlarmsActive']['expression'])

    def test_header_labels_and_data_source_box(self):
        class Quality:
            def __init__(self, good): self.good = good
            def isGood(self): return self.good

        def run(code, value, good=True):
            scope = {}
            exec(bv.build_hmi.TRANSFORM_SIGNATURE + '\n' + code, scope)
            return scope['transform'](None, value, Quality(good), None)
        for name, view in self.held.views.items():
            kids = {c['meta']['name']: c for c in view['root']['children']}
            if 'AlarmSummary' not in kids:
                continue  # counted below: every view must have one
            text = kids['AlarmSummary']['propConfig']['props.text']['binding']
            self.assertTrue(text['config']['tagPath'].endswith('/_Summary/AlarmsActive'))
            self.assertEqual(run(text['transforms'][0]['code'], 2), 'Process alarms: 2', name)
            box = kids['DataSourceSummary']['propConfig']
            self.assertTrue(box['props.text']['binding']['config']['tagPath'].endswith('/DiagnosticAlarmsActive'))
            self.assertEqual(run(box['props.text']['binding']['transforms'][0]['code'], 1), 'DATA SOURCE LOST')
            self.assertEqual(run(box['props.text']['binding']['transforms'][0]['code'], 0), 'Data source: OK')
            self.assertEqual(run(box['props.text']['binding']['transforms'][0]['code'], 0, False), 'Data source: unknown')
            bgcode = box['props.style.backgroundColor']['binding']['transforms'][0]['code']
            self.assertNotIn(run(bgcode, 1), (bv.build_hmi.RED, bv.build_hmi.AMBER, '#b91c1c'))  # not a process colour
        every = [n for n, v in self.held.views.items()
                 if 'AlarmSummary' in {c['meta']['name'] for c in v['root']['children']}]
        self.assertEqual(len(every), 24)  # every screen, including /m

    def test_no_data_states_share_one_look(self):
        """'not connected' (no source) and UNKNOWN (source, no Good data) each look the same on every screen."""
        style = bv.build_hmi.NO_SOURCE_STYLE
        mapped = set(self.meta['twin_review']['mapped'])
        no_source = 0
        for name, view in self.held.views.items():
            for c in walk(view['root']):
                props, cfg = c.get('props', {}), c.get('propConfig', {})
                b = cfg.get('props.text', {}).get('binding', {})
                code = ''.join(t.get('code', '') for t in b.get('transforms', []))
                # The indicator itself, not legends or notes that explain the word.
                static_nc = props.get('text') == 'not connected' or c['meta']['name'].startswith('Unavailable_')
                if static_nc or 'return "not connected"' in code:
                    no_source += 1
                    for k, v in style.items():
                        self.assertEqual(props['style'].get(k), v, (name, c['meta']['name'], k))
                    continue
                if (b.get('type') == 'tag' and b['config']['tagPath'].endswith('/PV') and 'UNKNOWN' in code
                        and c['type'] == 'ia.display.label'):
                    # Two schematic labels keep their alarm-colour binding instead (PI-107, TI-109): a label has
                    # one background binding, and alarm red wins there. Recorded as a known gap.
                    if name == 'TE/Schematic' and c['meta']['name'] in bg.ALARMS:
                        continue
                    bgb = cfg.get('props.style.backgroundColor', {}).get('binding', {})
                    bcode = ''.join(t.get('code', '') for t in bgb.get('transforms', []))
                    self.assertIn(bv.build_hmi.BAD_QUALITY_BG, bcode, (name, c['meta']['name']))
                    self.assertIn('quality.isGood()', bcode, (name, c['meta']['name']))
        # 334 drawing placeholders, SC-212's table box and its spatial label.
        self.assertEqual(no_source, 336)
        self.assertEqual(len(mapped), 24)

    def test_indicators_hide_their_pointer_without_good_data(self):
        class Quality:
            def __init__(self, good): self.good = good
            def isGood(self): return self.good

        def run(code, value, good=True):
            scope = {}
            exec(bv.build_hmi.TRANSFORM_SIGNATURE + '\n' + code, scope)
            return scope['transform'](None, value, Quality(good), None)
        n = 0
        for name, view in self.held.views.items():
            for c in walk(view['root']):
                if c.get('type') == 'ia.display.moving-analog-indicator':
                    b = c['propConfig']['props.style.visibility']['binding']
                    self.assertEqual(b['config']['tagPath'], c['propConfig']['props.processValue']['binding']['config']['tagPath'])
                    code = b['transforms'][0]['code']
                    self.assertEqual(run(code, 2700.0), 'visible')
                    self.assertEqual(run(code, 2700.0, False), 'hidden')
                    self.assertEqual(run(code, float('nan')), 'hidden')
                    n += 1
        self.assertGreater(n, 50)

    def test_narrow_overview(self):
        v = self.held.views['TE/Narrow']
        self.assertEqual(self.pages['/m']['viewPath'], 'TE/Narrow')
        self.assertEqual(v['props']['defaultSize']['width'], 390)
        kids = v['root']['children']
        for c in kids:  # nothing wider than the phone
            self.assertLessEqual(c['position']['x'] + c['position']['width'], 390, c['meta']['name'])
        order = [c['meta']['name'] for c in kids]
        # Alarms first: the alarm count, data source and alarm list come before the first unit tile.
        first_tile = order.index('Tile_U-100')
        for name in ('AlarmSummary', 'DataSourceSummary', 'BandSummary', 'AlarmTable'):
            self.assertLess(order.index(name), first_tile, name)
        tiles = [n for n in order if n.startswith('Tile_')]
        self.assertEqual(tiles, ['Tile_' + u for u in bv.build_hmi.UNIT_ORDER])
        import build_mimic
        shown = {n[2:] for n in order if n.startswith('N_')}
        self.assertEqual(shown, {t for ts in build_mimic.TAGS.values() for t in ts})  # same key values as overview
        table = next(c for c in kids if c['meta']['name'] == 'AlarmTable')
        self.assertFalse(table['props']['filters']['active']['states']['clearAcked'])
        # The control-room views are untouched: still 1600 px wide.
        for name, view in self.held.views.items():
            if name != 'TE/Narrow':
                self.assertEqual(view['props']['defaultSize']['width'], 1600, name)

    def test_schema_shape_tag_paths_routes_and_spatial_views(self):
        self.assertEqual(len(self.held.views), 24)  # 23 control-room views + TE/Narrow (/m)
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
        indicator['props']['text'] = 'not connected'
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
