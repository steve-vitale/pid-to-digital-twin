"""Offline contract controls; not an Ignition schema/runtime certification."""
import base64
import copy
import json
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'ignition'))
import build_mimic as m
from preview_mimic import transform
ROOT = Path(__file__).resolve().parents[1]
MODEL = json.loads((ROOT / 'data/te_process_model.json').read_text())
DOC = json.loads((ROOT / 'out/ignition/gateway/twin_provider.json').read_text())


def paths():
    types = {t['name']: t for t in next(t for t in DOC['tags'] if t['name'] == '_types_')['tags']}
    found = set()
    def walk(node, path):
        for t in node.get('tags', []):
            p = path + '/' + t['name'] if path else t['name']
            found.add('[Twin]' + p)
            walk(t, p)
            if t.get('tagType') == 'UdtInstance': walk(types[t['typeId']], p)
    walk(DOC, '')
    return found


class MimicTests(unittest.TestCase):
    def setUp(self): self.v = m.mimic('Twin', MODEL)
    def test_tag_contract(self):
        existing = paths()
        for c in self.v['root']['children']:
            for cfg in c.get('propConfig', {}).values():
                b = cfg['binding']
                self.assertEqual(b['type'], 'tag')
                self.assertIn(b['config']['tagPath'], existing)
    def test_no_process_mutation_or_new_streams(self):
        model = copy.deepcopy(MODEL)
        m.mimic('Twin', model)
        self.assertEqual(model, MODEL)
        self.assertTrue(set(m.STREAMS) <= {s['id'] for s in MODEL['streams']})
        for c in self.v['root']['children']:
            for event in c.get('events', {}).get('dom', {}).values():
                self.assertEqual(event['type'], 'nav')
        text = json.dumps(self.v)
        self.assertIn('UNVERIFIED', text)
        self.assertIn('ownership unresolved', text)
        self.assertIn('not measured valve position', text)
    def test_no_unmapped_agitator_binding(self):
        for c in self.v['root']['children']:
            self.assertNotIn('/SC-212/', json.dumps(c.get('propConfig', {})))
    def test_unique_names_and_supported_structure(self):
        names = [c['meta']['name'] for c in self.v['root']['children']]
        self.assertEqual(len(names), len(set(names)))
        for c in self.v['root']['children']:
            self.assertIn(c['type'], ['ia.display.image', 'ia.display.label'])
            self.assertGreater(c['position']['width'], 0)
            self.assertGreater(c['position']['height'], 0)
    def test_quality_and_numeric_controls(self):
        for value in [123, 0, None, float('nan'), float('inf'), 'bad']:
            self.assertIn('UNKNOWN', transform(m.VALUE_SCRIPT, value, False))
        for value in [None, float('nan'), float('inf'), 'bad']:
            self.assertIn('UNKNOWN', transform(m.VALUE_SCRIPT, value))
        self.assertEqual(transform(m.VALUE_SCRIPT, 0), '0.0')
        self.assertEqual(transform(m.STATE_SCRIPT, 2), 'ALARM ACTIVE')
        self.assertEqual(transform(m.STATE_SCRIPT, 2, False), 'State unknown')
        self.assertEqual(transform(m.STATE_SCRIPT, 99), 'State unknown')
    def test_svg_controls(self):
        for kind in ['reactor', 'separator', 'output']:
            for value in [0, 50, 100, -4, 130, None, float('nan'), float('inf')]:
                for good in [True, False]:
                    svg = base64.b64decode(transform(m.graphic_script(kind), value, good).split(',')[1]).decode()
                    ET.fromstring(svg)
                    self.assertNotIn('__', svg)
                    if not good or value is None or str(value) in ['nan', 'inf']:
                        self.assertIn('UNKNOWN', svg)
                    if good and value in [-4, 130]: self.assertIn('off scale', svg)
    def test_hidden_tags(self):
        v = m.mimic('Twin', MODEL, {'LI-108', 'TV-211', 'SC-212'})
        bindings = json.dumps([c.get('propConfig', {}) for c in v['root']['children']])
        for tag in ['LI-108', 'TV-211', 'SC-212']: self.assertNotIn('/' + tag + '/', bindings)
    def test_summary_quality_and_independent_bindings(self):
        for name in ['AlarmSummary', 'BandSummary']:
            c = next(c for c in self.v['root']['children'] if c['meta']['name'] == name)
            code = c['propConfig']['props.text']['binding']['transforms'][0]['code']
            color = c['propConfig']['props.style.color']['binding']['transforms'][0]['code']
            self.assertTrue(transform(code, 0).endswith(': 0'))
            self.assertTrue(transform(code, 2).endswith(': 2'))
            self.assertTrue(transform(code, 2, False).endswith(': unknown'))
            self.assertEqual(transform(color, 2, False), '#6b7280')
        # PV and State are independent bindings. Neither transform invents good data
        # when its own input quality is bad, even if the other remains temporarily good.
        self.assertIn('UNKNOWN', transform(m.VALUE_SCRIPT, 2700, False))
        self.assertEqual(transform(m.STATE_SCRIPT, 0, True), 'Within normal band')
        self.assertEqual(transform(m.VALUE_SCRIPT, 2700, True), '2700.0')
        self.assertEqual(transform(m.STATE_SCRIPT, 0, False), 'State unknown')

    def test_measurement_row_alignment_and_spacing(self):
        components = {c['meta']['name']: c for c in self.v['root']['children']}
        self.assertLessEqual(m.VIEW_HEIGHT, 1000)
        for tags in m.TAGS.values():
            for tag in tags:
                cells = [components[prefix + tag] for prefix in ['Tag_', 'Value_']]
                self.assertEqual(len({c['position']['y'] for c in cells}), 1)
                self.assertLessEqual(cells[0]['position']['x'] + cells[0]['position']['width'], cells[1]['position']['x'])
                for c in cells:
                    self.assertEqual(c['props']['style']['whiteSpace'], 'nowrap')
                    self.assertGreaterEqual(c['props']['style']['fontSize'], 14)
        for c in components.values():
            p = c['position']
            self.assertLessEqual(p['x'] + p['width'], 1600)
            self.assertLessEqual(p['y'] + p['height'], m.VIEW_HEIGHT)

    def test_value_unit_pair_and_unknown_readability(self):
        components = {c['meta']['name']: c for c in self.v['root']['children']}
        for item in MODEL['instruments'] + MODEL['final_elements']:
            tag = item['tag']
            if 'Value_' + tag not in components or tag == 'SC-212':
                continue
            c = components['Value_' + tag]
            code = c['propConfig']['props.text']['binding']['transforms'][0]['code']
            self.assertEqual(transform(code, 0), '0.0 ' + item['uom'])
            if item['uom'] == '%':
                self.assertIn('(off scale)', transform(code, 130))
            self.assertEqual(transform(code, 1, False), 'UNKNOWN')
            self.assertEqual(transform(code, float('nan')), 'UNKNOWN')
            self.assertGreaterEqual(c['position']['width'], 200)
            self.assertNotIn('Units_' + tag, components)

    def test_project_export_route_and_determinism(self):
        import io
        import zipfile
        import build_views
        meta = json.loads((ROOT / 'out/ignition/gateway/build_meta.json').read_text())
        args = (DOC, ROOT / meta['twin_source'], 'Twin', set(meta['alarms']))
        first, views = build_views.project_zip(*args, meta=meta)
        second, _ = build_views.project_zip(*args, meta=meta)
        self.assertEqual(first, second)
        with zipfile.ZipFile(io.BytesIO(first)) as z:
            config = json.loads(z.read('com.inductiveautomation.perspective/page-config/config.json'))
            self.assertEqual(config['pages']['/mimic']['viewPath'], 'TE/ProcessMimic')
            self.assertIn('/schematic', config['pages'])
        self.assertEqual(views['TE/ProcessMimic'], self.v)

    def test_all_units_streams_and_overview_ownership(self):
        components = {c['meta']['name']: c for c in self.v['root']['children']}
        self.assertEqual(set(m.UNIT_ORDER), {u['id'] for u in MODEL['units']})
        for uid in m.UNIT_ORDER:
            self.assertIn('Equipment_' + uid, components)
            self.assertEqual(components['Equipment_' + uid]['events']['dom']['onClick']['config']['page'], '/unit/' + uid)
        self.assertEqual(set(m.STREAMS), {s['id'] for s in MODEL['streams']})
        for stream in MODEL['streams']:
            self.assertIn('Stream_' + stream['id'], components)
        items = {i['tag']:i for i in MODEL['instruments'] + MODEL['final_elements']}
        for uid,tags in m.TAGS.items():
            for tag in tags:
                self.assertEqual(items[tag]['unit'],uid)

    def test_unit_detail_routes_coverage_and_boundaries(self):
        import build_hmi
        meta = json.loads((ROOT / 'out/ignition/gateway/build_meta.json').read_text())
        views,pages = build_hmi.te_views('Twin',meta['te_ranges'],meta['alarms'],set())
        self.assertEqual(views['TE/Overview'],views['TE/ProcessMimic'])
        expected = ['Overview','Feed','Reactor','Condenser','Separator','Compressor','Stripper','Alarms','Drawings']
        for uid in m.UNIT_ORDER:
            screen = views['TE/Unit_' + uid]
            cs = {c['meta']['name']:c for c in screen['root']['children']}
            nav = [c for c in screen['root']['children'] if c['meta']['name'].startswith('Nav_')]
            self.assertEqual([c['props']['text'] for c in nav],expected)
            self.assertEqual([c['events']['dom']['onClick']['config']['page'] for c in nav if c['props']['style']['fontWeight']=='bold'],['/unit/'+uid])
            self.assertEqual(cs['BackOverview']['events']['dom']['onClick']['config']['page'],'/')
            from te_channels import expanded_items
            for item in expanded_items(MODEL):
                if item['unit']==uid:
                    self.assertIn('Tag_'+item['tag'],cs)
                    if item['tag']!='SC-212':
                        self.assertIn('Trend_'+item['tag'],cs)
                        self.assertIn('State_'+item['tag'],cs)
            for st in MODEL['streams']:
                if uid in (st['from'],st['to']):
                    text = cs['UnitStream_'+st['id']]['props']['text']
                    self.assertIn(st['from']+' → '+st['to'],text)
                    linked=[i for i in MODEL['instruments']+MODEL['final_elements'] if i.get('stream')==st['id']]
                    for item in linked:
                        self.assertIn('Boundary_'+st['id']+'_'+item['tag'],cs)
                    if not linked:
                        self.assertIn('BoundaryUnknown_'+st['id'],cs)
            for c in cs.values():
                pos=c['position']
                self.assertLessEqual(pos['x']+pos['width'],1600)
                self.assertLessEqual(pos['y']+pos['height'],screen['props']['defaultSize']['height'])
                for cfg in c.get('propConfig',{}).values():
                    binding=cfg['binding']
                    if binding['type']=='tag':
                        self.assertIn(binding['config']['tagPath'], paths())
                    else:
                        self.assertEqual(binding['type'],'tag-history')
                        for tag in binding['config']['tags']:
                            self.assertIn(tag['path'],paths())

    def test_rejected_and_parent_hidden_do_not_bind_removed_tags(self):
        import build_hmi
        meta = json.loads((ROOT / 'out/ignition/gateway/build_meta.json').read_text())
        rejected = {'PI-107', 'AI-123', 'AI-123-B', 'AI-123-C', 'AI-123-D', 'AI-123-E', 'AI-123-F'}
        ranges = {k:v for k,v in meta['te_ranges'].items() if k not in rejected}
        views,_ = build_hmi.te_views('Twin',ranges,meta['alarms'],{'AI-129'})
        bindings = json.dumps([c.get('propConfig',{}) for v in views.values() for c in v['root']['children']])
        for tag in rejected | {'AI-129','AI-129-B','AI-129-C','AI-129-D','AI-129-E','AI-129-F','AI-129-G','AI-129-H'}:
            self.assertNotIn('/'+tag+'/',bindings)

    def test_all_unit_spatial_measurements_and_associations(self):
        from te_channels import expanded_items
        layout = m.DISPLAY
        self.assertEqual(set(layout['units']), set(m.UNIT_ORDER))
        for uid in m.UNIT_ORDER:
            cs = {c['meta']['name']:c for c in m.unit_context('Twin', MODEL, uid)}
            self.assertIn('UnitSpatialConnections',cs)
            for item in expanded_items(MODEL):
                if item['unit'] == uid and item['tag'] != 'SC-212':
                    self.assertIn('SpatialName_' + item['tag'],cs)
                    self.assertIn('SpatialTag_' + item['tag'],cs)
            for tag,p in layout['units'][uid]['cards'].items():
                self.assertEqual(p['association']['status'],'approximate')
                self.assertTrue(p['association']['evidence'])
        self.assertIn('Unavailable_SC-212',{c['meta']['name'] for c in m.unit_context('Twin', MODEL, 'R-101')})

    def test_unmapped_stream_note_clears_stripper_measurements(self):
        cs={c['meta']['name']:c for c in m.unit_context('Twin',MODEL,'C-101')}
        note=cs['BoundaryUnknown_S5']['position']
        for c in cs.values():
            if c['meta']['name'].startswith(('SpatialName_','SpatialValue_','SpatialTag_','Boundary_S10_')):
                p=c['position']
                overlap=(note['x'] < p['x']+p['width'] and note['x']+note['width'] > p['x'] and note['y'] < p['y']+p['height'] and note['y']+note['height'] > p['y'])
                self.assertFalse(overlap,c['meta']['name'])

    def test_spatial_quality_and_no_unavailable_bindings(self):
        for uid in m.UNIT_ORDER:
            cs=m.unit_context('Twin', MODEL,uid)
            self.assertEqual(len(cs), len({c['meta']['name'] for c in cs}))
            for c in cs:
                self.assertNotIn('/SC-212/',json.dumps(c.get('propConfig',{})))
                b=c.get('propConfig',{}).get('props.text',{}).get('binding',{})
                if c['meta']['name'].startswith(('Boundary_','SpatialValue_')) and b:
                    code=b['transforms'][0]['code']
                    self.assertIn('UNKNOWN',transform(code,123,False))
                    self.assertIn('UNKNOWN',transform(code,float('nan')))
                    self.assertTrue(transform(code,0).startswith('0.0'))

    def test_spatial_does_not_change_source_model_or_overview(self):
        original=copy.deepcopy(MODEL)
        for uid in m.UNIT_ORDER: m.unit_context('Twin', MODEL,uid)
        self.assertEqual(original,MODEL)
        self.assertEqual(self.v,m.mimic('Twin',MODEL))

    def test_deterministic_generation(self):
        self.assertEqual(self.v, m.mimic('Twin', MODEL))


if __name__ == '__main__': unittest.main()
