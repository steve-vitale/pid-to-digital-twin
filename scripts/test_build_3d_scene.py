"""Offline contract -> 3D scene checks; no Blender, no replay download, no plant-geometry claim.

The generated Blender script is executed end to end against a stub `bpy` module (a dry run): it proves the
script is complete and consistent with the scene, not that Blender renders it. Real renders are a separate,
optional step (docs/3D_TOUR_PLAN.md).
"""
import ast
import contextlib
import copy
import io
import json
import re
import math
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_3d_scene as b3  # noqa: E402
import hazard_citations as hz  # noqa: E402
import orientation_tour as ot  # noqa: E402
import verify_3d_render as v3  # noqa: E402


class Stub:
    """Accepts any attribute, call, index or iteration, and records operator calls."""
    calls = []

    def __init__(self, name='bpy'):
        object.__setattr__(self, '_name', name)
        object.__setattr__(self, '_attrs', {})

    def __getattr__(self, key):
        attrs = object.__getattribute__(self, '_attrs')
        if key not in attrs:
            attrs[key] = Stub(self._name + '.' + key)
        return attrs[key]

    def __setattr__(self, key, value):
        object.__getattribute__(self, '_attrs')[key] = value

    def __call__(self, *args, **kwargs):
        Stub.calls.append((self._name, args, kwargs))
        return Stub(self._name + '()')

    def __getitem__(self, key):
        return Stub('%s[%r]' % (self._name, key))

    def __setitem__(self, key, value):
        pass

    def __iter__(self):
        return iter(())

    def __contains__(self, item):
        return False

    def __bool__(self):
        return True

    def get(self, *args):
        return Stub(self._name + '.get()')


class FakeVector(tuple):
    """Just enough of mathutils.Vector for the generated script's geometry helpers to run offline."""
    def __new__(cls, v=(0.0, 0.0, 0.0)):
        return tuple.__new__(cls, (float(c) for c in v))

    def __add__(self, o):
        return FakeVector(a + b for a, b in zip(self, o))

    def __sub__(self, o):
        return FakeVector(a - b for a, b in zip(self, o))

    def __mul__(self, k):
        return FakeVector(a * k for a in self)

    __rmul__ = __mul__

    def __truediv__(self, k):
        return FakeVector(a / k for a in self)

    def __neg__(self):
        return FakeVector(-a for a in self)

    @property
    def length(self):
        return math.sqrt(sum(a * a for a in self))

    def normalized(self):
        n = self.length or 1.0
        return self / n

    def to_track_quat(self, *_):
        return (1.0, 0.0, 0.0, 0.0)

    def copy(self):
        return FakeVector(self)


# Files the 3D tour adds to the public repository. The hygiene check below runs over them on every test run.
TOUR_FILES = ("scripts/build_3d_scene.py", "scripts/blender_tour_template.py", "scripts/orientation_tour.py",
              "scripts/label_layout.py", "scripts/hazard_citations.py", "scripts/verify_3d_render.py",
              "scripts/test_build_3d_scene.py", "scripts/test_verify_3d_render.py",
              "data/hazard_citations_prototype.json", "data/te_tour_cards.json",
              "docs/3D_TOUR_PLAN.md", "docs/HAZARD_CITATIONS_DESIGN.md")
# Generic patterns only. The sensitive strings themselves are never written here: specific terms come from the
# HAZARD_DENY_TERMS environment variable (hazard_citations.deny_terms), outside the repository.
HYGIENE_RULES = (
    ("absolute user or drive path", re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/]|(?:^|[\s\"'(])/(?:Users|home)/")),
    ("hard-coded deny-list", re.compile(r"^\s*(?:FORBIDDEN|DENY\w*)\s*=\s*[(\[]\s*[\"']", re.M)),
    ("e-mail address", re.compile(r"[\w.+-]+@[\w-]+\.[A-Za-z]{2,}")),
)
PATH_LITERAL = re.compile(r"[\"']((?:[\w.-]+/)+[\w.-]+\.(?:json|ts|tsx|js|py|csv)|[\w-]+/(?:[\w.-]+/)+)[\"']")
DOC_LINK = re.compile(r"\]\(([^)#:\s]+\.md)(?:#[^)]*)?\)")


def hygiene_problems(name, text, root=ROOT, terms=()):
    problems = [f"{name}: {label}" for label, rule in HYGIENE_RULES if rule.search(text)]
    if name.endswith(".py"):
        # A file path literal must point into this repository (or at a generated out/ path), never at another
        # repository's layout.
        problems += [f"{name}: path literal outside this repository: {m}" for m in PATH_LITERAL.findall(text)
                     if not m.startswith("out/") and not (root / m).exists()]
    if name.endswith(".md"):
        base = (root / name).parent
        problems += [f"{name}: link to a missing document: {m}" for m in DOC_LINK.findall(text)
                     if not (base / m).exists()]
    low = text.lower()
    problems += [f"{name}: deny term #{i}" for i, t in enumerate(terms) if t in low]
    return problems


def public_hygiene_problems(root=ROOT):
    terms = hz.deny_terms()
    out = []
    for name in TOUR_FILES:
        out += hygiene_problems(name, (root / name).read_text(encoding="utf-8"), root, terms)
    return out


def hygiene_controls_ok():
    """Each rule must fire on a planted example built at run time (so no real sensitive string is stored)."""
    planted = {
        "x.py": "p = '" + "C:" + "/" + "Users/someone/tools'",
        "y.py": "DENY" + "_LIST = ('" + "x" * 5 + "',)",
        "z.py": "who = '" + "someone" + "@" + "example.org'",
        "w.py": "CORPUS = '" + "lib/" + "another-repo/" + "cards.ts'",
        "v.py": "FIXTURES = '" + "fixtures/somebody-" + "checks/'",
        "docs/v.md": "see [notes](" + "MISSING_NOTE" + ".md)",
        "u.py": "text = 'a " + "secretterm" + " b'",
    }
    return all(hygiene_problems(name, text, ROOT, terms=("secretterm",) if name == "u.py" else ())
               for name, text in planted.items()) and \
        not hygiene_problems("ok.py", "path = 'data/te_unit_purposes.json'", ROOT)


def glyphs_distinct(font_path, chars="1Il", px=40, min_diff=0.25):
    """Rasterize each glyph and require every pair to differ in at least min_diff of their union of ink pixels."""
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(str(font_path), px)
    masks = []
    for ch in chars:
        im = Image.new("L", (px * 2, px * 2), 0)
        ImageDraw.Draw(im).text((px // 2, px // 4), ch, fill=255, font=font)
        masks.append({(x, y) for x in range(im.width) for y in range(im.height) if im.getpixel((x, y)) > 127})
    pairs = [(a, b) for i, a in enumerate(masks) for b in masks[i + 1:]]
    return all(a and b and len(a ^ b) / len(a | b) >= min_diff for a, b in pairs)


def dry_run(source, out_dir):
    Stub.calls = []
    bpy = Stub()
    saved = sys.modules.get('bpy'), list(sys.argv)
    saved_mods = {k: sys.modules.get(k) for k in ('mathutils', 'bpy_extras', 'bpy_extras.object_utils')}
    sys.modules['mathutils'] = types.ModuleType('mathutils')
    sys.modules['mathutils'].Vector = FakeVector
    sys.modules['bpy_extras'] = types.ModuleType('bpy_extras')
    sys.modules['bpy_extras.object_utils'] = types.ModuleType('bpy_extras.object_utils')
    sys.modules['bpy_extras.object_utils'].world_to_camera_view = lambda *a: FakeVector((0.5, 0.5, 10.0))
    sys.modules['bpy'] = types.ModuleType('bpy')
    sys.modules['bpy'].__dict__.update({'ops': bpy.ops, 'data': bpy.data, 'context': bpy.context, 'app': bpy.app})
    sys.argv = ['blender', '--background', '--python', 'x.py', '--', '--out', str(out_dir), '--animation', '--gltf']
    try:
        exec(compile(source, 'te_scene_blender.py', 'exec'), {'__name__': '__main__'})
    finally:
        sys.argv = saved[1]
        if saved[0] is None:
            sys.modules.pop('bpy', None)
        else:
            sys.modules['bpy'] = saved[0]
        for k, v in saved_mods.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
    return Stub.calls


def main():
    model = json.loads((ROOT / 'data/te_process_model.json').read_text(encoding='utf-8'))
    layout = json.loads((ROOT / 'data/te_display_layout.json').read_text(encoding='utf-8'))
    bands = json.loads((ROOT / 'out/ignition/normal_bands.json').read_text(encoding='utf-8'))['bands']
    alarms = json.loads((ROOT / 'out/ignition/gateway/build_meta.json').read_text(encoding='utf-8'))['alarms']
    checks = []

    def check(name, ok):
        checks.append(bool(ok))
        print(('PASS' if ok else 'FAIL') + '  ' + name)

    before = copy.deepcopy(model)
    scene = b3.build_scene(model, layout, bands, alarms)
    records = model['instruments'] + model['final_elements']
    check('scene generation does not modify the model', model == before)
    check('one 3D object per model unit', sorted(e['id'] for e in scene['equipment']) == sorted(u['id'] for u in model['units']))
    check('one pipe per model stream, same endpoints',
          [(p['id'], p['from'], p['to']) for p in scene['pipes']] == [(s['id'], s['from'], s['to']) for s in model['streams']])
    check('every instrument and final element appears exactly once (37 records)',
          sorted(m['tag'] for m in scene['markers']) == sorted(i['tag'] for i in records) and len(records) == 37)
    check('every boundary stream gets a battery-limit marker, no others',
          sorted(b['stream'] for b in scene['boundaries']) == sorted(s['id'] for s in model['streams'] if 'BL' in (s['from'], s['to'])))
    check('every equipment size is declared a placeholder', all(e['geometry_status'].startswith('placeholder') for e in scene['equipment']))
    check('every pipe route is declared a placeholder', all(p['route_status'].startswith('placeholder') for p in scene['pipes']))
    check('recycle return has a paired-column overhead corridor, explicitly placeholder',
          scene.get('rack', {}).get('status', '').startswith('placeholder') and
          len(scene.get('rack', {}).get('stations', [])) >= 3)
    rendered_source = b3.blender_script(b3.tour_scene(scene, model, layout, bands, alarms))
    check('header and compressor render real cutaway shells with illustrative internals',
          'cutaway_shell(uid + "_header"' in rendered_source and
          'cutaway_shell(uid + "_casing"' in rendered_source and '"_impeller_vane' in rendered_source)
    for uid in ('V-101', 'K-101'):
        eq = next(e for e in scene['equipment'] if e['id'] == uid)
        label = next(l for l in scene['labels'] if l['id'] == 'unit:' + uid)
        check(uid + ' callout terminates on its machine, below its top extent', label['anchor'][2] < eq['extent'][2])
    check('scene carries the plain-language disclaimer', 'not plant geometry' in scene['disclaimer'])
    check('plan positions come from the 2D seed layout',
          all(abs(e['position'][0] - u['layout']['x'] * b3.SCALE) < 1e-3 for e, u in zip(scene['equipment'], model['units'])))
    numbers = []

    def walk(obj):
        if isinstance(obj, dict):
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)
        elif isinstance(obj, float):
            numbers.append(obj)
    walk(scene)
    check('all scene coordinates are finite', numbers and all(math.isfinite(n) for n in numbers))
    check('tour follows seed flow order', [t['unit'] for t in scene['tour']] == ['U-100', 'R-101', 'E-101', 'V-101', 'K-101', 'C-101'])
    check('tour order states its basis, unverified by operations', 'unverified by operations' in scene['tour_order_basis'])
    marker = {m['tag']: m for m in scene['markers']}
    check('SC-212 (no replay source) is not connected', not marker['SC-212']['connected'])
    check('only SC-212 is not connected', [m['tag'] for m in scene['markers'] if not m['connected']] == ['SC-212'])
    check('an open discrepancy stays visible (PI-116, unresolvable in the source) and a resolved one does not (TI-122)',
          marker['PI-116']['disputed'] and not marker['TI-122']['disputed'] and marker['TI-122']['unit'] == 'E-101')
    check('display-card associations are reused for placement',
          marker['FI-106']['attach'] == ['stream', 'S6'] and marker['PI-107']['attach'] == ['unit', 'R-101'])
    check('tags without a display card say so', marker['TI-121']['placement_basis'].startswith('seed model unit ownership only'))
    check('stream tags sit at their owning unit end of the pipe', marker['FI-101']['attach'] == ['stream', 'S1'] and
          math.dist(marker['FI-101']['position'][:2], next(p for p in scene['pipes'] if p['id'] == 'S1')['points'][-1][:2]) < 0.6)
    check('deterministic: same inputs give an identical scene', b3.build_scene(model, layout, bands, alarms) == scene)

    # Directions: only an explicit stream direction (verified against the simulator source, out/te_topology_check.md)
    # or the layout's old seed adapter authorizes arrows and a flow-ordered tour.
    check('every stream in the verified model carries its own direction, so every pipe is directed',
          all(s.get('direction') == 'forward' for s in model['streams']) and all(p['directed'] for p in scene['pipes']))
    no_adapter = copy.deepcopy(layout)
    no_adapter.pop('direction_adapter', None)
    undirected_model = copy.deepcopy(model)
    for s in undirected_model['streams']:
        s.pop('direction', None)
    undirected = b3.build_scene(undirected_model, no_adapter)
    check('without a direction (no stream direction, no adapter) no pipe is directed',
          not any(p['directed'] for p in undirected['pipes']))
    check('without directions the tour is model order and says so',
          [t['unit'] for t in undirected['tour']] == [u['id'] for u in model['units']] and undirected['tour_order_basis'].startswith('model_order'))

    # Drift between the model and the shared layout fails before anything is drawn.
    for name, mutate in [
        ('layout for another model', lambda m, l: l.update(model_id='other')),
        ('layout card for an unknown tag', lambda m, l: l['units']['R-101']['cards'].update({'XX-999': copy.deepcopy(l['units']['R-101']['cards']['PI-107'])})),
        ('layout unit missing from model', lambda m, l: m['units'].pop(1)),
        ('unit without a finite 2D position', lambda m, l: m['units'][0]['layout'].update(x=float('nan'))),
    ]:
        m2, l2 = copy.deepcopy(model), copy.deepcopy(layout)
        mutate(m2, l2)
        try:
            b3.build_scene(m2, l2)
        except ValueError:
            check('reject ' + name, True)
        else:
            check('reject ' + name, False)
    unknown_kind = copy.deepcopy(layout)
    unknown_kind['units']['V-101']['kind'] = 'mystery'
    odd = {e['id']: e for e in b3.build_scene(model, unknown_kind)['equipment']}['V-101']
    check('unknown symbol kind gets a labelled generic box, not a guessed shape',
          odd['shape'] == 'box' and 'unknown kind' in odd['geometry_status'])

    # Replay states: synthetic rows only; nothing is inferred for missing or nonfinite values.
    columns = {'PI-107': 0, 'FI-101': 1}
    rows = [[2700.0, 0.25], [2900.0, 0.0], [float('nan'), 0.25]]
    states = b3.replay_states(['PI-107', 'FI-101', 'SC-212'], rows, columns, bands, alarms, [0, 1, 2, 9], 0)
    check('in-band values are normal', states[0]['states'] == {'PI-107': 'normal', 'FI-101': 'normal', 'SC-212': 'not_connected'})
    check('published setpoint makes alarm; out-of-band makes outside_band (a display aid, not an alarm)',
          states[1]['states']['PI-107'] == 'alarm' and states[1]['states']['FI-101'] == 'outside_band')
    check('nonfinite reading is unknown, never normal', states[2]['states']['PI-107'] == 'unknown')
    check('missing sample is unknown for every connected tag',
          states[3]['states']['PI-107'] == 'unknown' and states[3]['states']['SC-212'] == 'not_connected')
    check('minutes are measured from the fault start (3 min per sample)', [s['minutes_after_fault'] for s in states] == [0, 3, 6, 27])
    replay = {'rows': [[0.0] * 52 for _ in range(3)], 'columns': {'SC-212': 0}}
    with_states = b3.build_scene(model, layout, bands, alarms, replay, [0, 1, 2], 1)
    check('a not-connected tag stays not connected even if a column appears',
          all(s['states']['SC-212'] == 'not_connected' for s in with_states['replay_states']))

    # The Blender script embeds exactly this scene and runs end to end against a stub bpy.
    hazards = hz.load_citations()
    purposes = ot.load_purposes(ROOT / 'data/te_tour_cards.json', ROOT / 'data/te_unit_purposes.json')
    main_purposes = json.loads((ROOT / 'data/te_unit_purposes.json').read_text(encoding='utf-8'))['units']
    check('every tour card takes its purpose sentence verbatim from data/te_unit_purposes.json (none of its own)',
          all(k['purpose'] == main_purposes[k['unit']]['purpose'] for k in purposes['kinds'].values())
          and not any('purpose' in k for k in json.loads((ROOT / 'data/te_tour_cards.json').read_text(encoding='utf-8'))['kinds'].values()))
    toured = b3.tour_scene(with_states, model, layout, bands, alarms, replay, hazards, 1, purposes=purposes)
    source = b3.blender_script(toured)
    compile(source, 'te_scene_blender.py', 'exec')
    embedded = json.loads(source.split('r"""', 1)[1].split('"""', 1)[0])
    check('generated Blender script embeds the scene unchanged', embedded == json.loads(json.dumps(toured)))
    imports = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imports |= {a.name.split('.')[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module.split('.')[0])
    check('generated script imports only Blender modules (bpy, bpy_extras, mathutils, bundled numpy) and stdlib',
          imports <= {'bpy', 'bpy_extras', 'mathutils', 'numpy', 'json', 'math', 'os', 'sys'})
    check('generated script loads the bundled OFL label font (1, I and l distinct), not a machine path',
          b3.LABEL_FONT.is_file() and (b3.LABEL_FONT.parent / 'OFL.txt').is_file() and
          'SIL Open Font License' in (b3.LABEL_FONT.parent / 'OFL.txt').read_text(encoding='utf-8') and
          b3.LABEL_FONT.as_posix() in source and '__FONT_PATH__' not in source)
    check('label font draws 1, I and l as clearly different shapes', glyphs_distinct(b3.LABEL_FONT))
    check('generated script embeds the shared label-layout code',
          'def place_labels(' in source and '# __LABEL_LAYOUT__' not in source)
    with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
        calls = dry_run(source, Path(tmp) / 'renders')
    renders = [c for c in calls if c[0] == 'bpy.ops.render.render']
    stills = [c for c in renders if c[2].get('write_still')]
    check('dry run renders every default still (overview, 6 stops, 3 fault stills, flow legend)',
          len(stills) == 1 + len(scene['tour']) + 3 + 1 == len(toured['shots']))
    check('optional stills (all-tags per stop, LOTO mockup) are generated but not rendered by default',
          '40_loto_mockup' in toured['all_shot_names'] and '02b_r-101_all_tags' in toured['all_shot_names'] and
          not any(x['name'] in ('40_loto_mockup', '02b_r-101_all_tags') for x in toured['shots']))
    check('dry run renders one animation when asked', sum(1 for c in renders if c[2].get('animation')) == 1)
    check('dry run builds at least one cylinder per battery limit and unit',
          sum(1 for c in calls if c[0] == 'bpy.ops.mesh.primitive_cylinder_add') >= len(scene['boundaries']) + 6)
    check('dry run exports one GLB for an interactive viewer when asked',
          sum(1 for c in calls if c[0] == 'bpy.ops.export_scene.gltf' and c[2].get('export_extras')) == 1)
    check('dry run adds one leader per label',
          sum(1 for c in calls if c[0] == 'bpy.ops.mesh.primitive_cone_add' and c[2].get('depth') == 1.0 and
              c[2].get('radius1') == 1.0) == len(toured['labels']))
    check('dry run draws flow chevrons (flat arrowheads) on directed pipes',
          sum(1 for c in calls if c[0] == 'bpy.ops.mesh.primitive_cone_add' and c[2].get('vertices') == 3) >=
          sum(p['directed'] for p in scene['pipes']))
    check('no emphasis rings or boxes: emphasis is a limit annotation on the pills', toured['emphasis_rings'] == [] and
          not any(l['kind'] == 'emphasis' for l in toured['labels']))

    # Geometry regressions found by the render verifier (scripts/verify_3d_render.py).
    check('no marker sits inside equipment (429d7a7 put FI-106 and AI-123 inside the reactor)',
          not any(v3.inside_any(m['position'], scene) for m in scene['markers']))
    legacy = b3.build_scene(model, layout, bands, alarms, legacy_markers=True)
    check('legacy placement still reproduces the inside-the-reactor defect (keeps the before/after honest)',
          sorted(m['tag'] for m in legacy['markers'] if v3.inside_any(m['position'], legacy)) == ['AI-123', 'FI-106'])
    rep_geo = v3.Report()
    v3.check_geometry(rep_geo, scene, model)
    check('pipe ends derived from geometry reproduce the stream topology (429d7a7 left S4/S11 off the stripper)',
          not rep_geo.failed)
    rep_old = v3.Report()
    v3.check_geometry(rep_old, legacy, model)
    check('the same check fails on the legacy geometry (S4, S11 and the two buried markers)',
          len(rep_old.failed) == 2 and any('S4' in d for c in rep_old.failed for d in c['details']))
    check('every stop has fitted candidate views at mezzanine eye height; the first is the default camera',
          all(t['camera_candidates'][0]['camera'] == t['camera'] and len(t['camera_candidates']) == len(b3.STOP_AZIMUTHS)
              and all(abs(c['camera'][2] - b3.EYE_Z) < 1e-6 for c in t['camera_candidates']) for t in scene['tour']))
    check('pipes are colour-coded by service and run at two rack elevations',
          {p['service'] for p in scene['pipes']} <= set(b3.SERVICE_LEVEL) and
          {round(max(c[2] for c in p['corners']), 3) for p in scene['pipes']} <= set(b3.RACK_LEVELS.values()))
    check('utility stubs come only from final elements that name the utility, labelled inferred',
          sorted({u['tag'] for u in scene['utilities']}) == ['FV-117', 'FV-119', 'TV-121'] and
          all(u['basis'].startswith('inferred') for u in scene['utilities']))
    check('every stop names 2-4 key tags, all connected and banded',
          all(1 <= len(e['key_tags']) <= 4 and all(marker[t]['connected'] and t in bands for t in e['key_tags'])
              for e in scene['equipment']))

    # Orientation tour: numbers from data, prose labelled, citations public and prototype-labelled.
    real = b3.tour_scene(scene, model, layout, bands, alarms, None, hazards, purposes=purposes,
                         only=[n for n in b3.tour_scene(scene, model, layout, bands, alarms, None, hazards,
                                                        purposes=purposes)['all_shot_names']])
    stops = {s['unit']: s for s in real['tour_script']['stops']}
    lo, hi = ot.fmt(bands['PI-107']['lo']), ot.fmt(bands['PI-107']['hi'])
    check('reactor narration quotes the PI-107 normal band and high alarm from the data files',
          f"PI-107, pressure: normally {lo} to {hi} kPa g, with a high alarm at 2,895" in stops['R-101']['narration'])
    check('each stop narration is short (<= 70 words, about 20-30 s)', all(s['words'] <= 70 for s in stops.values()))
    reactor_shot = next(x for x in real['shots'] if x['name'] == '02_r-101_normal')
    fault_shots = [x for x in real['shots'] if x['name'].startswith(('20_', '21_', '22_'))]
    check('normal stop: PI-107 pill shows the operating high alarm only, no shutdown limit',
          'high alarm 2,895' in reactor_shot['bodies']['tag:PI-107'] and 'shutdown' not in json.dumps(reactor_shot['bodies']))
    check('shutdown limits appear only on fault stills, never on normal stills',
          all('shutdown' not in json.dumps(x['bodies']) for x in real['shots'] if x not in fault_shots))
    crit = real['tour_script']['emphasis'].get('R-101', [])
    check('reactor emphasis comes from data: the published Critical setpoints (3000 kPa g, 175 degC)',
          [e['style'] for e in crit] == ['consequence'] and '3,000' in crit[0]['label'] and '175' in crit[0]['label'])
    check('without a replay there is no first-warning emphasis and no fault narration',
          all(e['style'] != 'first_warning' for v in real['tour_script']['emphasis'].values() for e in v) and
          not any(s['id'].startswith('fault') for s in real['timeline']))
    check('every still and segment carries the corner badge; the full disclaimer is in the intro narration',
          all(any(o['id'] == 'overlay:badge' and o['text'] == ot.BADGE for o in s['overlays'])
              for s in real['shots'] + real['timeline']) and ot.FULL_DISCLAIMER in real['timeline'][0]['narration'])
    check('captions are two lines at most, each within the width',
          all(len(s['caption'].split(chr(10))) <= 2 and all(len(x) <= 150 for x in s['caption'].split(chr(10)))
              for s in real['shots'] + real['timeline']))
    check('stops carry a purpose card and a separate why-this-matters card',
          all(any(o['id'] == 'overlay:purpose' for o in x['overlays']) and any(o['id'] == 'overlay:why' for o in x['overlays'])
              for x in real['shots'] if x.get('focus') and x['name'].endswith('_normal')))
    loto = real['loto_mockup']
    check('LOTO mockup: every point inferred, status says not a procedure and cites OSHA 1910.147',
          loto['points'] and all(p['basis'].startswith('inferred') for p in loto['points']) and
          'not a lockout/tagout procedure' in loto['status'] and '1910.147' in loto['status'])
    check('every stop cites a public incident from the prototype file',
          all(s['citation'] and hz.domain_ok(s['citation']['url']) for s in stops.values()))
    check('reactor leads with the Kuraray reactor-pressure case (aptness check), Bayer phrased generally',
          stops['R-101']['citation']['id'] == 'csb-kuraray-pasadena' and
          'runaway exothermic reactions in general' in hz.citations_for_kind(hazards, 'reactor')[1]['hazard'])
    check('public hygiene: no user paths, outside-repo paths, hard-coded deny-lists, e-mail addresses, dead doc links '
          'or deny terms in the tour files', public_hygiene_problems() == [])
    check('public hygiene check catches planted examples of each rule (positive control)', hygiene_controls_ok())
    if not hz.deny_terms():
        print('NOTE  HAZARD_DENY_TERMS is not set: the deny-term part of the hygiene check was skipped')
    check('curated citation file validates (3-5 per kind, agency URLs, prototype label, no private data)',
          hz.validate(hazards, sorted({e['kind'] for e in scene['equipment']})) == [])
    timed = real['timeline']
    check('timeline is contiguous and ordered', all(a['end'] == b['start'] for a, b in zip(timed, timed[1:])) and
          all(t['start'] <= t['hold'] < t['end'] for t in timed))
    cues = [c for c in ot.srt(timed).strip().split(chr(10) * 2) if c]
    check('SRT cues are numbered 1..n with well-formed times',
          [int(c.split(chr(10))[0]) for c in cues] == list(range(1, len(cues) + 1)) and
          all(' --> ' in c.split(chr(10))[1] for c in cues))
    def secs(stamp):
        h, m, rest = stamp.split(':')
        s, ms = rest.split(',')
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
    spans = [tuple(secs(v) for v in c.split(chr(10))[1].split(' --> ')) for c in cues]
    check('SRT cues never overlap, and the first one says the voice is synthetic',
          all(b[0] >= a[1] - 1e-6 for a, b in zip(spans, spans[1:])) and 'synthetic voice' in cues[0])
    check('spoken text spells out units and tag dashes',
          ot.spoken('PI-107 is 2897 kPa g at +294 min, TV-121 37.7%') ==
          'P I 107 is 2897 kilopascals gauge at plus 294 min, T V 121 37.7 percent')
    prof = ot.fault_profile(['PI-107', 'FI-101'], {'rows': [[2700.0, 0.25], [2700.0, 0.0], [2900.0, 0.0]],
                                                   'columns': {'PI-107': 0, 'FI-101': 1}}, bands, alarms, 0, 2)
    check('fault profile: first band exit and minutes come from the replay rows',
          prof['FI-101']['first_off_sample'] == 1 and prof['FI-101']['minutes_after_fault'] == 3 and
          prof['PI-107']['state_at_alarm'] == 'alarm')
    emph = ot.emphasis(scene, alarms, prof)
    check('first-warning emphasis goes to the unit of the earliest band exit',
          any(e['style'] == 'first_warning' and 'FI-101' in e['reason'] for e in emph.get('U-100', [])))
    leg = b3.tour_scene(legacy, model, layout, bands, alarms, None, hazards, label_mode='legacy')
    check('legacy mode shows every label in every still with the old cameras (before/after reproduction)',
          all(len(s['visible']) == len([x for x in leg['labels'] if x['kind'] != 'emphasis']) for s in leg['shots']) and
          leg['shots'][1]['camera'] == leg['tour'][0]['legacy_camera'] and not leg['timeline'])

    tricky = copy.deepcopy(toured)
    tricky['title'] = 'quotes """ and ' + chr(92) + ' backslash, \u00b0C ' + chr(92)
    src = b3.blender_script(tricky)
    compile(src, 'te_scene_blender.py', 'exec')
    check('engineering text with quotes/backslashes survives embedding',
          json.loads(src.split('r"""', 1)[1].split('"""', 1)[0])['title'] == tricky['title'])
    print(f'{sum(checks)}/{len(checks)} 3D scene contract checks passed')
    return 0 if all(checks) else 1


if __name__ == '__main__':
    sys.exit(main())
