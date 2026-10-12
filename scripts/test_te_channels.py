"""Offline controls for full analyzer coverage; never connects to a gateway."""
import ast
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts' / 'ignition'))
sys.path.insert(0, str(ROOT / 'scripts'))
from te_channels import expanded_items, channel_columns, ANALYZERS
from build_gateway import te_tags, te_columns, ALARMS


def main():
    model = json.loads((ROOT / 'data/te_process_model.json').read_text())
    original = copy.deepcopy(model)
    items, columns = expanded_items(model), channel_columns(model)
    assert model == original
    assert len(items) == 53 and len(columns) == 52
    assert len(set(i['tag'] for i in items)) == 53
    assert set(columns.values()) == set(range(52))
    assert len(set(columns.values())) == 52
    assert columns == te_columns(model)
    # Verify the actual replay function offline without importing the optional
    # asyncua server dependency or starting a listener.
    module = ast.parse((ROOT / 'scripts/ignition/te_sim_server.py').read_text())
    function = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == 'column_map')
    namespace = {}
    exec(compile(ast.Module(body=[function], type_ignores=[]), '<replay-column-map>', 'exec'), namespace)
    assert columns == namespace['column_map'](model)
    assert 'SC-212' not in columns
    for source in model['instruments'] + model['final_elements']:
        if 'xmeas' in source:
            expected = int(str(source['xmeas']).split('-')[0]) - 1
        elif source['xmv'] <= 11:
            expected = 40 + source['xmv']
        else:
            continue
        assert columns[source['tag']] == expected
    for parent, (start, components) in ANALYZERS.items():
        channels = [i for i in items if i.get('analyzer_parent') == parent]
        assert [i['component'] for i in channels] == list(components)
        assert [i['xmeas'] for i in channels] == list(range(start, start + len(components)))
        assert all(i['sampling'] and i['verification']['status'] == 'confirmed' for i in channels)
    types, plant, ranges, review = te_tags(model)
    assert len(ranges) == 53
    assert sum(r['has_data'] for r in ranges.values()) == 52
    assert not ranges['SC-212']['has_data'] and ranges['SC-212']['normal'] is None
    instances = {i['name']: i for u in plant['tags'] if u['name'] != '_Summary' for i in u['tags']}
    assert set(instances) == {i['tag'] for i in items}
    for item in items:
        tag = item['tag']
        assert ranges[tag]['source_item'] == item
        assert instances[tag]['parameters']['Tag']['value'] == tag
        if tag in columns:
            assert ranges[tag]['normal'] is not None
        if item.get('analyzer_parent'):
            assert instances[tag]['typeId'] == 'TE_Measurement'
            assert not any('alarms' in member for member in instances[tag]['tags'])
    measurement = next(t for t in types if t['name'] == 'TE_Measurement')
    pv = next(m for m in measurement['tags'] if m['name'] == 'PV')
    assert pv['readOnly'] and pv['historyEnabled']
    assert pv['engLimitMode'] == 'No_Clamp'
    assert pv['opcItemPath']['binding'].endswith(';s=TE/{Tag}')
    state = next(m for m in measurement['tags'] if m['name'] == 'State')
    band = next(m for m in measurement['tags'] if m['name'] == 'OutOfNormal')
    assert 'try(' not in state['expression'] + band['expression']
    assert '{[.]PV}' in band['expression']  # existing bad quality propagation, no fallback value
    summary = next(u for u in plant['tags'] if u['name'] == '_Summary')
    out = next(m for m in summary['tags'] if m['name'] == 'OutOfNormal')['expression']
    assert out.count('/OutOfNormal}') == 52 and 'SC-212' not in out
    alarm = next(m for m in summary['tags'] if m['name'] == 'AlarmsActive')['expression']
    assert alarm.count('/AlarmActive}') == len(ALARMS)
    assert not any(tag in alarm for tag in columns if tag.startswith('AI-'))
    # Operations decisions on a parent must propagate to every derived component.
    modified = copy.deepcopy(model)
    parent = next(i for i in modified['instruments'] if i['tag'] == 'AI-123')
    parent['ops_review'] = {'status': 'rejected'}
    _, _, rejected_ranges, rejected = te_tags(modified)
    assert not any(t.startswith('AI-123') for t in rejected_ranges)
    assert len([t for t in rejected['rejected'] if t.startswith('AI-123')]) == 6
    parent['ops_review'] = {'show_on_screen': False}
    _, _, _, hidden = te_tags(modified)
    assert len([t for t in hidden['hidden'] if t.startswith('AI-123')]) == 6
    print('PASS: 52 unique recorded channels + SC-212 unmapped; original paths, analyzer provenance, history/read-only/quality configuration, unchanged alarms, parent review inheritance')


if __name__ == '__main__':
    main()
