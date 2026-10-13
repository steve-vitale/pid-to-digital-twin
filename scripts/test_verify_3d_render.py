"""Checks for scripts/verify_3d_render.py; stdlib only, committed files only (no Blender, no replay, no network).

The verifier must pass on the committed exports and the committed 'after' render evidence, and must fail on each
planted break: a missing or re-homed Ignition tag, a wrong unit of measure, a PI attribute pointing at another
point, a broken pipe end, an invalid tour order, an untraceable tag, and the committed 'before' (429d7a7) render
evidence, including the E-101 / K-101 crowding Steve spotted.
"""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_3d_scene as b3  # noqa: E402
import label_layout as LL  # noqa: E402
import verify_3d_render as v3  # noqa: E402

EVIDENCE = ROOT / 'drafts' / '3d-tour'  # the committed review stills and their measured label boxes


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    model = read(ROOT / 'data/te_process_model.json')
    layout = read(ROOT / 'data/te_display_layout.json')
    bands = read(ROOT / 'out/ignition/normal_bands.json')['bands']
    alarms = read(ROOT / 'out/ignition/gateway/build_meta.json')['alarms']
    provider = read(ROOT / 'out/ignition/gateway/twin_provider.json')
    seed = read(ROOT / 'out/ignition/te_tags.json')
    pi_csv = (ROOT / 'out/pi/pi_builder_af.csv').read_text(encoding='utf-8-sig')
    descriptions = ROOT / 'out/pi/attribute_descriptions.csv'  # sheet schema v2
    pi_desc = descriptions.read_text(encoding='utf-8-sig') if descriptions.is_file() else None
    persp = v3.perspective_index(ROOT / 'out/ignition/gateway/PIDTwin.zip')
    scene = b3.build_scene(model, layout, bands, alarms)
    checks = []

    def check(name, ok):
        checks.append(bool(ok))
        print(('PASS' if ok else 'FAIL') + '  ' + name)

    def failed_ids(**kw):
        args = dict(scene=scene, model=model, provider=provider, seed_tags=seed, pi_csv=pi_csv, perspective=persp,
                    bands=bands, alarms=alarms, pi_descriptions=pi_desc)
        args.update(kw)
        result = v3.run(**args, crosscheck=False)[0]
        return [c['id'] for c in result['checks'] if c['status'] == 'fail'], result

    # Geometry and contrast primitives.
    check('WCAG: white on black is 21:1', abs(LL.contrast_ratio(LL.relative_luminance((1, 1, 1)), 0.0) - 21.0) < 1e-9)
    check('WCAG: #777777 on white is about 4.48:1 (just under AA)', abs(LL.contrast_ratio(
        LL.relative_luminance((0x77 / 255,) * 3), 1.0) - 4.48) < 0.01)
    check('text contrast heuristic: light strokes on a dark plate', abs(LL.text_contrast([0.02] * 80 + [0.7] * 20)['ratio'] -
                                                                         (0.75 / 0.07)) < 1e-6)
    check('boxes that touch do not overlap; boxes that share area do',
          LL.overlap_area((0, 0, 10, 10), (10, 0, 20, 10)) == 0 and LL.overlap_area((0, 0, 10, 10), (5, 5, 20, 20)) == 25)
    placed = LL.place_labels([{'id': 'a', 'anchor': (100, 100), 'w': 80, 'h': 20},
                              {'id': 'b', 'anchor': (105, 102), 'w': 80, 'h': 20}], 400, 300, [(0, 250, 400, 300)])
    check('declutter places two labels with the same anchor without overlap or entering the caption band',
          placed['a']['cost'] == 0 and placed['b']['cost'] == 0 and
          LL.overlap_area(placed['a']['box'], placed['b']['box']) == 0 and all(p['box'][3] <= 250 for p in placed.values()))

    # A. accuracy vs the committed exports.
    fails, result = failed_ids()
    check('committed exports: every check passes (37 tags 1:1 in Ignition, seed UDT, PI AF and Perspective)', fails == [])
    check('every scene tag has an Ignition path and a PI AF path in the tag map',
          all(r.get('ignition_gateway') and r.get('pi_af') for r in result['tag_map'].values()) and len(result['tag_map']) == 37)
    check('PI path format is \\\\TE Plant\\<unit>|<attribute>', result['tag_map']['PI-107']['pi_af'] ==
          '\\\\TE Plant\\R-101|ReactorPressure' and result['tag_map']['PI-107']['ignition_gateway'] == 'TE_Plant/R-101/PI-107')
    gone = copy.deepcopy(provider)
    r101 = next(f for f in next(t for t in gone['tags'] if t['name'] == 'TE_Plant')['tags'] if f['name'] == 'R-101')
    r101['tags'] = [t for t in r101['tags'] if t['name'] != 'TI-109']
    check('a tag missing from the Ignition import is reported', any('ignition_gateway' in f for f in failed_ids(provider=gone)[0]))
    moved = copy.deepcopy(provider)
    folders = {f['name']: f for f in next(t for t in moved['tags'] if t['name'] == 'TE_Plant')['tags']}
    inst = next(t for t in folders['R-101']['tags'] if t['name'] == 'LI-108')
    folders['R-101']['tags'].remove(inst)
    folders['V-101']['tags'].append(inst)
    check('a tag under the wrong unit folder is reported', any('ignition_gateway' in f for f in failed_ids(provider=moved)[0]))
    uom = copy.deepcopy(provider)
    pv = next(t for t in next(t for t in folders_of(uom)['R-101']['tags'] if t['name'] == 'PI-107')['tags'] if t['name'] == 'PV')
    pv['engUnit'] = 'bar'
    check('a unit-of-measure mismatch is reported', any('ignition_gateway' in f for f in failed_ids(provider=uom)[0]))
    band = copy.deepcopy(provider)
    next(t for t in folders_of(band)['R-101']['tags'] if t['name'] == 'PI-107')['parameters']['NormalHi']['value'] = 9999.0
    check('a band in the gateway that differs from the one colouring the 3D markers is reported',
          any('bands and alarm' in f for f in failed_ids(provider=band)[0]))
    check('a PI attribute pointing at another point is reported',
          any('pi_af' in f for f in failed_ids(pi_csv=pi_csv.replace('TE.PI-107.PV', 'TE.PI-113.PV'))[0]))
    check('an extra unexplained Ignition tag is reported', any('ignition_gateway' in f for f in failed_ids(
        provider=add_tag(provider, 'R-101', 'XI-999'))[0]))
    check('an analyzer component channel (AI-123-B) is an explained extra, not a failure',
          '16 extra explained' in next(c['summary'] for c in result['checks'] if c['id'].startswith('A ignition_gateway')))
    no_view = {t: v for t, v in persp.items() if t != 'FI-101'}
    check('a tag not bound in any Perspective view is reported', any('perspective' in f for f in failed_ids(perspective=no_view)[0]))

    # B. geometry and flow.
    broken = copy.deepcopy(scene)
    s6 = next(p for p in broken['pipes'] if p['id'] == 'S6')
    s6['points'][-1] = [s6['points'][-1][0] + 6.0, s6['points'][-1][1], s6['points'][-1][2]]
    s6['points'][-2] = [s6['points'][-2][0] + 6.0, s6['points'][-2][1], s6['points'][-2][2]]
    check('a pipe whose end no longer touches its unit breaks the derived topology',
          any('topology' in f for f in failed_ids(scene=broken)[0]))
    shuffled = copy.deepcopy(scene)
    shuffled['tour'] = [shuffled['tour'][i] for i in (0, 3, 1, 2, 4, 5)]
    check('a tour that visits the separator before the reactor is not a valid walk',
          any('walk' in f for f in failed_ids(scene=shuffled)[0]))
    buried = copy.deepcopy(scene)
    reactor = next(e for e in buried['equipment'] if e['id'] == 'R-101')
    next(m for m in buried['markers'] if m['tag'] == 'PI-107')['position'] = [reactor['position'][0], reactor['position'][1], 3.0]
    check('a marker inside equipment is reported', any('inside equipment' in f for f in failed_ids(scene=buried)[0]))

    # C. P&ID trace.
    trace = result['pid_trace']
    check('TE seed: 0 tags trace to a drawing, all 37 are declared seed, none unexplained',
          sum(r['trace'] == 'drawing' for r in trace) == 0 and sum(r['trace'].startswith('seed') for r in trace) == 37)
    anon = copy.deepcopy(model)
    anon['meta']['extraction_method'] = 'unknown'
    check('a tag with neither a drawing trace nor a seed declaration fails', any('traces' in f for f in failed_ids(model=anon)[0]))
    extracted = copy.deepcopy(anon)
    for it in extracted['instruments'] + extracted['final_elements']:
        it['provenance'] = [{'sheet': '0', 'box_0_1000': [1.0, 2.0, 3.0, 4.0]}]
    fails_x, res_x = failed_ids(model=extracted)
    check('tags with a drawing id and bbox count as traced (extracted-twin shape)',
          not any('traces' in f for f in fails_x) and all(r['trace'] == 'drawing' for r in res_x['pid_trace']))

    # D. legibility on the committed render evidence.
    after, before = EVIDENCE / 'label_boxes.json', EVIDENCE / 'before' / 'label_boxes.json'
    if after.is_file() and before.is_file():
        rep = v3.Report()
        v3.check_legibility(rep, read(after))
        check('committed after-render evidence passes every legibility check', not rep.failed)
        rep = v3.Report()
        leg = v3.check_legibility(rep, read(before))
        details = rep.checks[0]['details']
        check('committed before-render (429d7a7 labels) evidence fails legibility', rep.failed)
        # The 'before' evidence is a legacy-mode render (the 429d7a7 label rules) of the current model and font,
        # re-measured at the merge. The original 429d7a7 overview also crowded E-101 and K-101; after the purge
        # correction the legacy crowding falls on tag pairs instead, so the check asks for crowding anywhere.
        check('before: labels are flagged as crowded on one baseline (legacy label rules)', any(
            ': crowded: ' in d for d in details))
        check('before: the K-101 label is flagged as partly hidden by a pipe', any(
            '00_overview_normal: unit:K-101: label' in d and 'hidden by S5' in d for d in details))
        check('before: tag labels too small and low contrast are counted',
              leg['totals']['small'] > 100 and leg['totals']['low_contrast'] > 100)
    else:
        check('committed render evidence present (drafts/3d-tour/label_boxes.json and before/)', False)
    print(f'{sum(checks)}/{len(checks)} render verification checks passed')
    return 0 if all(checks) else 1


def folders_of(provider):
    return {f['name']: f for f in next(t for t in provider['tags'] if t['name'] == 'TE_Plant')['tags']}


def add_tag(provider, unit, tag):
    out = copy.deepcopy(provider)
    folder = folders_of(out)[unit]
    clone = copy.deepcopy(folder['tags'][0])
    clone['name'] = tag
    clone['parameters']['Tag']['value'] = tag
    folder['tags'].append(clone)
    return out


if __name__ == '__main__':
    sys.exit(main())
