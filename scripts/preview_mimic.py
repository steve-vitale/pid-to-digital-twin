"""Build offline Perspective export plus a self-contained, read-only HTML preview.

Preview evaluates the same transforms in CPython; it is NOT a Perspective runtime.
Recorded fixtures require checksum-verified data from scripts/fetch_te_data.py.
"""
import base64
import copy
import html
import json
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'ignition'))
import build_mimic
import build_views
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'out' / 'process_mimic'


class Quality:
    def __init__(self, good): self.good = good
    def isGood(self): return self.good


def transform(code, value, good=True):
    """Run a STORED transform body the way Perspective compiles it: signature + newline + body, unmodified.
    Re-indenting here hid a parse error that every native transform hit (journal entry 38)."""
    scope = {}
    exec(build_mimic.TRANSFORM_SIGNATURE + '\n' + code, scope)
    return scope['transform'](None, value, Quality(good), None)


def resolve(component, values, states, good):
    c = copy.deepcopy(component)
    for path, cfg in c.get('propConfig', {}).items():
        binding = cfg['binding']
        if binding['type'] == 'tag-history':
            c['props']['text'] = 'Gateway history (not rendered offline)'
            continue
        p = binding['config']['tagPath']
        tag, member = p.split('/')[-2:]
        value = (values if member == 'PV' else states).get(tag)
        if tag == '_Summary':
            value = sum(v == 2 for v in states.values()) if member == 'AlarmsActive' else values.get('_OutOfNormalCount')
        if member == 'ReviewStatus':
            value = 'Gateway metadata'
        ok = good and value is not None
        for t in binding.get('transforms', []):
            if t['type'] == 'script': value = transform(t['code'], value, ok)
            elif t['type'] == 'map': value = next((m['output'] for m in t['mappings'] if m['input'] == value), t['fallback'])
        if not ok and not binding.get('transforms'):
            value = None
        target = c
        pieces = path.split('.')
        for k in pieces[:-1]: target = target.setdefault(k, {})
        target[pieces[-1]] = value if value is not None else 'UNKNOWN'
    return c


def render(v, values, states, good):
    out = []
    for raw in v['root']['children']:
        c = resolve(raw, values, states, good)
        p, props = c['position'], c['props']
        style = {'position': 'absolute', 'boxSizing': 'border-box', 'overflow': 'hidden',
                 'left': p['x'], 'top': p['y'], 'width': p['width'], 'height': p['height'], **props.get('style', {})}
        css = ';'.join(re.sub(r'[A-Z]', lambda m: '-' + m[0].lower(), k) + ':' + (str(val) + 'px' if isinstance(val, (int, float)) and k != 'lineHeight' else str(val)) for k, val in style.items())
        attr = ' style="' + html.escape(css, quote=True) + '"'
        page = c.get('events', {}).get('dom', {}).get('onClick', {}).get('config', {}).get('page')
        if page:
            attr += ' onclick="navigate(' + html.escape(json.dumps(page), quote=True) + ')"'
        if c['type'] == 'ia.display.image':
            out.append('<img alt="' + c['meta']['name'] + '"' + attr + ' src="' + props['source'] + '">')
        elif c['type'] == 'ia.display.moving-analog-indicator':
            value = props.get('processValue')
            out.append('<div' + attr + '>Band position: ' + html.escape(str(value)) + '</div>')
        else:
            out.append('<div' + attr + '>' + html.escape(str(props.get('text', ''))) + '</div>')
    return ''.join(out)


def fixtures(model, meta):
    from fetch_te_data import FILES
    import hashlib
    from te_channels import expanded_items
    tags = expanded_items(model)
    result = []
    for name, rowno in [('d00_te.dat', 0), ('d06_te.dat', 258)]:
        p = ROOT / 'data/external/te-braatz' / name
        assert hashlib.sha256(p.read_bytes()).hexdigest() == FILES[name], 'Replay checksum mismatch'
        row = [float(v) for v in p.read_text().splitlines()[rowno].split()]
        vals = {}
        for i in tags:
            if 'xmeas' in i: col = int(str(i['xmeas']).split('-')[0]) - 1
            elif i['xmv'] <= 11: col = 40 + i['xmv']
            else: continue
            vals[i['tag']] = row[col]
        states = {}
        for tag, value in vals.items():
            band = meta['te_ranges'][tag]['normal']
            alarm = any(value > a['setpointA'] for a in meta['alarms'].get(tag, []))
            states[tag] = 2 if alarm else int(bool(band and not band[0] <= value <= band[1]))
        vals['_OutOfNormalCount'] = sum(bool(meta['te_ranges'][tag]['normal'] and not meta['te_ranges'][tag]['normal'][0] <= value <= meta['te_ranges'][tag]['normal'][1]) for tag, value in vals.items())
        result.append((name + ' / sample ' + str(rowno), vals, states, True))
    result.append(('Disconnected / bad-quality fixture', result[0][1], result[0][2], False))
    return result


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    model = json.loads((ROOT / 'data/te_process_model.json').read_text())
    meta = json.loads((ROOT / 'out/ignition/gateway/build_meta.json').read_text())
    doc = json.loads((ROOT / 'out/ignition/gateway/twin_provider.json').read_text())
    export, views = build_views.project_zip(doc, ROOT / meta['twin_source'], meta['provider'], set(meta['alarms']), meta=meta)
    (OUT / 'PIDTwin-process-mimic.zip').write_bytes(export)
    v = views['TE/ProcessMimic']
    (OUT / 'view.json').write_text(json.dumps(v, indent=2))
    fs = fixtures(model, meta)
    selected = {'/': views['TE/Overview']}
    selected.update({'/unit/' + u: views['TE/Unit_' + u] for u in build_mimic.UNIT_ORDER})
    frames = {route: [render(screen, vals, states, good) for _, vals, states, good in fs] for route, screen in selected.items()}
    heights = {route: screen['props']['defaultSize']['height'] for route, screen in selected.items()}
    labels = [x[0] for x in fs]
    page = """<!doctype html><meta charset="utf-8"><title>TE overview and unit details • offline preview</title>
<style>body{margin:0;background:#e5e5e5;font-family:Arial;color:#1f2937}aside{padding:14px 24px;background:#25313d;color:white;width:1552px}button{padding:8px 18px;margin-right:8px}#canvas{position:relative;width:1600px}</style>
<aside>OFFLINE PREVIEW · actual recorded samples · not an Ignition gateway. History widgets require the gateway and are labeled, not simulated.<br><br><button onclick="show(0)">Normal replay</button><button onclick="show(1)">Fault 6 / pressure alarm</button><button onclick="show(2)">Bad quality</button><span id="fixture"></span></aside><main id="canvas"></main><script>
const frames=FRAMES, labels=LABELS, heights=HEIGHTS; let fixture=0;
function navigate(route){if(route==='/mimic')route='/';if(!frames[route]){alert('This offline preview includes Overview and six unit details. This route is included in the Ignition export and requires gateway validation.');return;}location.hash=route;draw();}
function draw(){let route=location.hash.slice(1)||'/';if(!frames[route])route='/';document.getElementById('canvas').innerHTML=frames[route][fixture];document.getElementById('canvas').style.height=heights[route]+'px';document.getElementById('fixture').textContent=labels[fixture];}
function show(n){fixture=n;draw();}window.addEventListener('hashchange',draw);show(Number(new URLSearchParams(location.search).get('frame')||0));</script>""".replace('FRAMES', json.dumps(frames)).replace('LABELS', json.dumps(labels)).replace('HEIGHTS', json.dumps(heights))
    (OUT / 'preview.html').write_text(page, encoding='utf-8')
    print('Wrote ' + str(OUT))


if __name__ == '__main__': main()
