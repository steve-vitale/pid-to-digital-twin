"""Offline cross-process contract tests; no gateway, real source or plant coverage claim."""
import copy
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'scripts' / 'ignition'))
from display_contract import require_display_layout, stream_is_directed, validate_display_layout


def main():
    model = json.loads((ROOT / 'data/fixtures/water_utility_twin.json').read_text())
    layout = json.loads((ROOT / 'data/fixtures/water_utility_display.json').read_text())
    uid = next(iter(layout['units']))
    checks = []
    def check(name, ok):
        checks.append(bool(ok))
        print(('PASS' if ok else 'FAIL') + '  ' + name)
    check('second process accepts existing twin-1 model with unfamiliar IDs', not validate_display_layout(model, layout))
    check('mixed engineering units preserved', {i['uom'] for i in model['instruments']} == {'bar', '%', 'state'})
    check('unmapped measurements are permitted without invented addresses', all('data_point' not in i for i in model['instruments']))
    check('unknown or absent direction does not authorize arrows', not stream_is_directed({'direction':'unknown'}) and not stream_is_directed({}))
    check('only explicit forward directions authorize forward arrows', stream_is_directed({'direction':'forward'}) and not stream_is_directed({'direction':'reverse'}))
    for name, mutate in [
        ('wrong model', lambda c: c.update(model_id='other')),
        ('dangling association', lambda c: c['units'][uid]['cards']['PT-301']['association'].update(id='missing')),
        ('wrong measurement stream', lambda c: c['units'][uid]['cards']['PT-301']['association'].update(id='L0-001')),
        ('unknown measurement', lambda c: c['units'][uid]['cards'].update({'missing':copy.deepcopy(c['units'][uid]['cards']['PT-301'])})),
        ('nonfinite anchor', lambda c: c['units'][uid]['cards']['PT-301'].update(anchor=[math.nan,0])),
        ('missing evidence', lambda c: c['units'][uid]['cards']['PT-301']['association'].update(evidence='')),
        ('unresolved physical tap', lambda c: c['units'][uid]['cards']['PT-301']['association'].update(status='unresolved')),
        ('negative equipment size', lambda c: c['units'][uid].update(equipment=[0,0,-1,100])),
        ('pressure cannot drive level fill', lambda c: c['units'][uid].update(level='PT-301')),
    ]:
        candidate = copy.deepcopy(layout); mutate(candidate)
        check('reject ' + name, bool(validate_display_layout(model,candidate)))
    candidate = copy.deepcopy(layout)
    card = candidate['units'][uid]['cards']['PT-301']; card.pop('anchor')
    card['association']={'status':'unresolved','evidence':'No supported physical tap association.'}
    check('explicit unresolved measurement may remain unanchored', not validate_display_layout(model,candidate))
    try:
        require_display_layout(model, {'schema_version':0})
    except ValueError:
        check('invalid contract fails before rendering', True)
    else:
        check('invalid contract fails before rendering', False)
    # Exercise the same spatial renderer used by TE, with no TE channel adapter.
    import build_mimic
    before = copy.deepcopy(model)
    kids = build_mimic.unit_context('Fixture', model, uid, layout=layout)
    text = json.dumps(kids)
    check('same renderer accepts second-process config', bool(kids) and 'PT-301' in text)
    check('renderer preserves model facts', model == before)
    check('each configured equipment view renders with mixed-unit channels', all(build_mimic.unit_context('Fixture',model,u,layout=layout) for u in layout['units']))
    check('second-process rendering contains no TE namespace', 'TE_Plant' not in text)
    # Decode all SVGs: unknown direction may never produce a visible stream arrow.
    import base64
    svgs=[]
    def visit(obj):
        if isinstance(obj,dict):
            source=obj.get('source','')
            if isinstance(source,str) and source.startswith('data:image/svg+xml;base64,'):
                svgs.append(base64.b64decode(source.split(',',1)[1]).decode())
            for value in obj.values(): visit(value)
        elif isinstance(obj,list):
            for value in obj: visit(value)
    visit(kids)
    check('unknown stream direction renders without arrow marker', bool(svgs) and not any('marker-end=' in s for s in svgs))
    check('unmapped reading has explicit UNKNOWN fallback', 'UNKNOWN' in text)
    check('unmapped process cannot acquire fabricated live bindings', 'tagPath' not in text)
    unresolved = build_mimic.unit_context('Fixture', model, uid, layout=candidate)
    check('unresolved association renders an explicit unplaced notice', 'Location unresolved' in json.dumps(unresolved))
    unusual = copy.deepcopy(layout); unusual['units'][uid]['kind'] = 'site_specific_filter'
    fallback = build_mimic.unit_context('Fixture', model, uid, layout=unusual)
    check('unfamiliar symbol kind renders safely', bool(fallback))
    check('second-process generation is deterministic', kids == build_mimic.unit_context('Fixture',model,uid,layout=layout))
    print('%d checks; %d failed' % (len(checks),sum(not c for c in checks)))
    return 0 if all(checks) else 1


if __name__ == '__main__':
    sys.exit(main())
