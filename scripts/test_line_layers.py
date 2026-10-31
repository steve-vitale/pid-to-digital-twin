"""Layered line relationships (scripts/line_layers.py): on small drawn images, a tee gives three pairwise network links
but three pipe segments to one junction and no item-to-item pipe; a plain crossing joins the network but is no
junction; a crossing marked with a dot is a 4-arm junction; an in-line valve sits between its neighbours. The pipe
scorer is checked against known topologies, and, where the data is present, the generated-drawing and DEXPI truths
are read the way their own keys say. Needs OpenCV and numpy (as the tracer does); no model calls, no network."""
import json
import contextlib
import io
import shutil
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import line_layers as ll  # noqa: E402


def pairs(links):
    return {tuple(sorted((x["from"], x["to"]))) for x in links}


def segs(out):
    return {tuple(sorted(s[:2])) for s in out["segments"]}


class Drawn(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.image = Path(self.tmp.name) / "drawing.png"

    def draw(self, boxes, lines, dots=(), classes=None, tags=None):
        img = np.full((1000, 1000), 255, np.uint8)
        for a, b in lines:
            cv2.line(img, a, b, 0, 2)
        for c in dots:
            cv2.circle(img, c, 7, 0, -1)
        for b in boxes.values():
            cv2.rectangle(img, tuple(b[:2]), tuple(b[2:]), 0, 2)
        cv2.imwrite(str(self.image), img)
        # a 2 px outline is drawn 1 px outside the given box: the symbol's box holds all of it
        return [{"id": k, "class": (classes or {}).get(k, "valve"), "box": [b[0] - 1, b[1] - 1, b[2] + 1, b[3] + 1],
                 **({"tag": tags[k]} if k in (tags or {}) else {})} for k, b in boxes.items()]

    def test_enrich_preserves_drawings_and_keeps_model_in_place_and_repeat_behavior(self):
        syms = self.draw({"A": [100, 470, 160, 530], "B": [840, 470, 900, 530]},
                         [((160, 500), (840, 500))])
        folder = Path(self.tmp.name)
        model = {"meta": {"model_kind": "extracted_twin"}, "units": [], "instruments": [],
                 "offpage_connectors": [], "line_items": [
                     {"id": s['id'], "provenance": [{"sheet": "0", "symbol": s['id'],
                         "class": s['class'], "box_0_1000": s['box']}]} for s in syms],
                 "streams": [{"id": "L1", "kind": "extracted_link", "sheet": "0",
                              "from": "A", "to": "B", "from_symbol": "A", "to_symbol": "B"}]}
        path = folder / 'model.json'
        path.write_text(json.dumps(model), encoding='utf-8')
        alias = folder / 'alias.json'
        alias.hardlink_to(self.image)
        replaced = folder / 'replaced.png'
        replaced.write_bytes(self.image.read_bytes())
        before = {p: p.read_bytes() for p in (path, self.image, alias, replaced)}
        arguments = ['enrich', str(path), '--image', '0=' + str(self.image)]
        for out, extra in ((self.image, []), (alias, []),
                           (replaced, ['--image', '0=' + str(replaced), '--image', '0=' + str(self.image)])):
            with self.subTest(out=out.name), contextlib.redirect_stderr(io.StringIO()) as errors:
                self.assertEqual(ll.main(arguments + extra + ['--out', str(out)]), 1)
                self.assertIn('output aliases an input', errors.getvalue())
                self.assertEqual(before, {p: p.read_bytes() for p in before})
        separate = folder / 'enriched.json'
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(ll.main(arguments + ['--out', str(separate)]), 0)
            self.assertEqual(ll.main(arguments + ['--out', str(path)]), 0)
            self.assertEqual(path.read_bytes(), separate.read_bytes())
            self.assertEqual(ll.main(arguments + ['--out', str(path)]), 0)
        self.assertEqual(path.read_bytes(), separate.read_bytes())
        self.assertEqual(self.image.read_bytes(), before[self.image])

    def test_a_tee_is_three_network_links_but_three_segments_to_one_junction(self):
        syms = self.draw({"A": [100, 470, 160, 530], "B": [840, 470, 900, 530], "C": [470, 840, 530, 900]},
                         [((160, 500), (840, 500)), ((500, 500), (500, 840))])
        out = ll.traced_layers(self.image, syms)
        self.assertEqual(pairs(out["links"]), {("A", "B"), ("A", "C"), ("B", "C")})  # network co-membership
        self.assertEqual(len(out["networks"]), 1)
        self.assertEqual(len(out["junctions"]), 1)
        (j, v), = out["junctions"].items()
        self.assertEqual((v["arms"], v["basis"]), (3, "tee"))
        self.assertAlmostEqual(v["x"], 500, delta=4)
        self.assertAlmostEqual(v["y"], 500, delta=4)
        self.assertEqual(segs(out), {tuple(sorted((x, j))) for x in "ABC"})  # no item is piped to another item
        self.assertEqual(out["problems"], [])

    def test_a_plain_crossing_joins_the_network_but_is_not_a_junction(self):
        syms = self.draw({"A": [100, 470, 160, 530], "B": [840, 470, 900, 530], "C": [470, 100, 530, 160],
                          "D": [470, 840, 530, 900]}, [((160, 500), (840, 500)), ((500, 160), (500, 840))])
        out = ll.traced_layers(self.image, syms)
        self.assertEqual(len(pairs(out["links"])), 6)  # the tracer joins crossings, as the answer key does
        self.assertEqual(out["crossings"], {"pass_through": 1, "marked_connected": 0})
        self.assertEqual(out["junctions"], {})
        self.assertEqual(segs(out), {("A", "B"), ("C", "D")})  # each run passes straight through

    def test_a_crossing_marked_with_a_dot_is_a_four_arm_junction(self):
        syms = self.draw({"A": [100, 470, 160, 530], "B": [840, 470, 900, 530], "C": [470, 100, 530, 160],
                          "D": [470, 840, 530, 900]}, [((160, 500), (840, 500)), ((500, 160), (500, 840))],
                         dots=[(500, 500)])
        out = ll.traced_layers(self.image, syms)
        self.assertEqual(out["crossings"], {"pass_through": 0, "marked_connected": 1})
        (j, v), = out["junctions"].items()
        self.assertEqual((v["arms"], v["basis"]), (4, "marked_crossing"))
        self.assertEqual(segs(out), {tuple(sorted((x, j))) for x in "ABCD"})

    def test_specks_at_a_crossing_are_not_a_dot(self):
        # a heavy and a thin line crossing leave a stray pixel or two in the corners (anti-aliasing, a thin line's
        # ragged edge); each touches both runs, as a dot does, but fills only some of the corners (seen on DEXPI C01,
        # where thin lines crossing the heavy pipe were read as connected crossings)
        syms = self.draw({"A": [100, 470, 160, 530], "B": [840, 470, 900, 530], "C": [470, 100, 530, 160],
                          "D": [470, 840, 530, 900]}, [((160, 500), (840, 500))])
        img = cv2.imread(str(self.image), cv2.IMREAD_GRAYSCALE)
        img[160:841, 500] = 0                    # a 1 px thin line crossing the heavy one
        img[498, 499] = img[502, 501] = 0        # two specks, in opposite corners
        cv2.imwrite(str(self.image), img)
        out = ll.traced_layers(self.image, syms)
        self.assertEqual(len(pairs(out["links"])), 6)  # the network layer is the tracer's: still joined
        self.assertEqual(out["crossings"], {"pass_through": 1, "marked_connected": 0})
        self.assertEqual(out["junctions"], {})
        self.assertEqual(segs(out), {("A", "B"), ("C", "D")})

    def test_a_slanted_leader_crossing_a_pipe_joins_nothing_in_the_pipe_layer(self):
        # a label's leader drawn slanted from free space, across pipe A-B, ending just below it on the drop to C
        # (OPEN100 sheet 1). The tracer drops the long part above the pipe (a slanted open stroke does not conduct)
        # and joins the short part below it to both runs; in the pipe layer it is a line crossing A-B, not a branch
        syms = self.draw({"A": [100, 470, 160, 530], "B": [840, 470, 900, 530], "C": [570, 840, 630, 900]},
                         [((160, 500), (840, 500)), ((600, 500), (600, 840))])
        img = cv2.imread(str(self.image), cv2.IMREAD_GRAYSCALE)
        cv2.line(img, (480, 300), (598, 535), 0, 1)
        cv2.imwrite(str(self.image), img)
        out = ll.traced_layers(self.image, syms)
        self.assertEqual(pairs(out["links"]), {("A", "B"), ("A", "C"), ("B", "C")})
        (j, v), = out["junctions"].items()
        self.assertEqual((v["arms"], v["basis"]), (3, "tee"))
        self.assertAlmostEqual(v["x"], 600, delta=4)
        self.assertEqual(segs(out), {tuple(sorted((x, j))) for x in "ABC"})

    def test_a_short_slanted_stroke_ending_on_two_runs_joins_them(self):
        # a short slanted stroke that ends on both runs (crossing neither) is a line between them
        syms = self.draw({"A": [100, 470, 160, 530], "B": [482, 100, 542, 160]},
                         [((160, 500), (500, 500)), ((512, 160), (512, 488))])
        img = cv2.imread(str(self.image), cv2.IMREAD_GRAYSCALE)
        cv2.line(img, (501, 499), (511, 489), 0, 2)
        cv2.imwrite(str(self.image), img)
        out = ll.traced_layers(self.image, syms)
        self.assertEqual(segs(out), {("A", "B")})
        self.assertEqual(out["junctions"], {})

    def test_a_tee_with_a_dot_is_still_a_three_arm_tee(self):
        syms = self.draw({"A": [100, 470, 160, 530], "B": [840, 470, 900, 530], "C": [470, 840, 530, 900]},
                         [((160, 500), (840, 500)), ((500, 500), (500, 840))], dots=[(500, 500)])
        out = ll.traced_layers(self.image, syms)
        self.assertEqual([v["arms"] for v in out["junctions"].values()], [3])
        self.assertEqual(out["crossings"], {"pass_through": 0, "marked_connected": 0})

    def test_an_inline_valve_sits_between_its_neighbours_and_bends_pass_through(self):
        syms = self.draw({"A": [100, 470, 160, 530], "V": [470, 470, 530, 530], "B": [840, 140, 900, 200]},
                         [((160, 500), (470, 500)), ((530, 500), (700, 500)), ((700, 500), (700, 170)),
                          ((700, 170), (840, 170))])
        out = ll.traced_layers(self.image, syms)
        self.assertEqual(pairs(out["links"]), {("A", "V"), ("B", "V")})
        self.assertEqual(segs(out), {("A", "V"), ("B", "V")})
        self.assertEqual(out["junctions"], {})

    def test_excluded_items_drop_out_of_the_pipe_layer_only(self):
        syms = self.draw({"A": [100, 470, 160, 530], "B": [840, 470, 900, 530], "C": [470, 840, 530, 900]},
                         [((160, 500), (840, 500)), ((500, 500), (500, 840))])
        out = ll.traced_layers(self.image, syms, exclude={"C"})
        self.assertEqual(len(pairs(out["links"])), 3)  # the network and pairwise layers are untouched
        self.assertEqual(segs(out), {("A", "B")})      # the tee to C is passed through once C is left out

    # Not every drawn line is pipe (independent review of the sheet-0 layered sample, 2026-10-29: 3 of 15 pipe
    # statements wrong, all because an actuator stem or an instrument leader was emitted as a pipe segment).
    def test_an_instrument_tap_is_on_the_pipe_and_does_not_split_it(self):
        syms = self.draw({"A": [100, 470, 160, 530], "B": [840, 470, 900, 530], "T": [470, 300, 530, 360]},
                         [((160, 500), (840, 500)), ((500, 360), (500, 500))], classes={"T": "instrumentation"})
        out = ll.traced_layers(self.image, syms)
        self.assertEqual(pairs(out["links"]), {("A", "B"), ("A", "T"), ("B", "T")})  # the tracer's links unchanged
        (j, v), = out["junctions"].items()
        self.assertEqual(v["kind"], "instrument_tap")
        self.assertEqual(segs(out), {("A", "B")})                       # the pipe passes the tap
        self.assertEqual(v["on_segment"], ("A", "B"))
        self.assertEqual(out["segment_taps"], {("A", "B"): [j]})
        self.assertEqual({tuple(s[:2]) for s in out["instrument_lines"]}, {("T", j)})
        self.assertEqual(out["problems"], [])

    def test_a_valve_actuator_stem_and_its_instrument_leader_are_not_pipe(self):
        # M (an actuator, classed general) stacked on valve V by a short stem; bubble I's leader ends on the stem at
        # the valve's edge, so the stem and the leader touch only at the valve
        syms = self.draw({"A": [100, 470, 160, 530], "V": [470, 480, 530, 520], "B": [840, 470, 900, 530],
                          "M": [485, 430, 515, 474], "I": [560, 440, 600, 470]},
                         [((160, 500), (470, 500)), ((530, 500), (840, 500)), ((500, 474), (500, 480)),
                          ((560, 470), (500, 478))], classes={"M": "general", "I": "instrumentation"})
        out = ll.traced_layers(self.image, syms)
        self.assertEqual(segs(out), {("A", "V"), ("B", "V")})           # only the process line is pipe
        self.assertEqual({tuple(s[:2]) for s in out["actuator_stems"]}, {("V", "M")})
        self.assertEqual({tuple(s[:2]) for s in out["instrument_lines"]}, {("I", "V")})  # to the valve, not to M
        self.assertEqual(out["junctions"], {})
        self.assertEqual(out["problems"], [])

    def test_a_tee_beside_an_item_box_is_kept(self):
        # the drop from C lands on the run 4 px left of valve V's box: a tee next to V, not V's own drawing
        syms = self.draw({"A": [100, 470, 160, 530], "V": [600, 480, 640, 520], "B": [840, 470, 900, 530],
                          "C": [566, 100, 626, 160]},
                         [((160, 500), (600, 500)), ((640, 500), (840, 500)), ((596, 160), (596, 500))])
        out = ll.traced_layers(self.image, syms)
        (j, v), = out["junctions"].items()
        self.assertEqual((v["arms"], v["kind"]), (3, "pipe_tee"))
        self.assertEqual(segs(out), {tuple(sorted((x, j))) for x in "ACV"} | {("B", "V")})

    def test_a_nozzle_on_its_own_vessel_is_part_of_the_vessel(self):
        syms = self.draw({"E": [100, 300, 300, 700], "N": [306, 490, 326, 510], "B": [840, 470, 900, 530]},
                         [((300, 500), (306, 500)), ((326, 500), (840, 500))], classes={"E": "tank", "N": "general"},
                         tags={"N": "N2"})
        out = ll.traced_layers(self.image, syms)
        self.assertEqual(segs(out), {("B", "N")})
        self.assertEqual({tuple(s[:2]) for s in out["nozzle_stubs"]}, {("N", "E")})

    def test_items_drawn_against_each_other_are_piped_directly(self):
        # blind flange F drawn against valve V's end, reducer R against valve W: no line between them, nothing between
        # them either, so each pair is consecutive on the pipe (the segment says it is drawn touching); a bubble I
        # drawn against W is not a pipe end
        syms = self.draw({"A": [100, 470, 160, 530], "V": [400, 480, 440, 520], "F": [441, 485, 451, 515],
                          "B": [840, 470, 900, 530], "W": [600, 480, 640, 520], "R": [560, 485, 599, 515],
                          "I": [605, 440, 635, 479]},
                         [((160, 500), (400, 500)), ((640, 500), (840, 500))],
                         classes={"F": "general", "R": "general", "I": "instrumentation"})
        out = ll.traced_layers(self.image, syms)
        self.assertEqual(segs(out), {("A", "V"), ("F", "V"), ("B", "W"), ("R", "W")})
        touching = {tuple(sorted(s[:2])) for s in out["segments"] if s[2] is None}
        self.assertEqual(touching, {("F", "V"), ("R", "W")})
        self.assertEqual(out["instrument_lines"], [])
        self.assertEqual(out["problems"], [])


class Generic(unittest.TestCase):
    def test_contract_prunes_stubs_walks_bends_and_keeps_junctions(self):
        adj = {"A": {1: 0}, 1: {"A": 0, 2: 0}, 2: {1: 0, 3: 0, 4: 0}, 3: {2: 0, "B": 0}, "B": {3: 0},
               4: {2: 0, "C": 0}, "C": {4: 0}, 5: {2: 0}}  # 5 is a dead-end stub off the junction
        adj[2][5] = 0
        sg, arms = ll.contract(adj, {"A", "B", "C"})
        self.assertEqual(set(sg), {tuple(sorted((2, x), key=str)) for x in "ABC"})
        self.assertEqual(arms, {2: 3})
        sg, arms = ll.contract({"A": {"B": 0}, "B": {"A": 0}, 7: {8: 0}, 8: {7: 0, 9: 0}, 9: {8: 0}}, {"A", "B"})
        self.assertEqual(set(sg), {("A", "B")})
        # line joining fewer than two items (an item's own outline) is not pipe
        loop = {"A": {1: 0}, 1: {"A": 0, 2: 0, 3: 0}, 2: {1: 0, 3: 0, 4: 0}, 3: {1: 0, 2: 0, 4: 0},
                4: {2: 0, 3: 0}}
        self.assertEqual(ll.contract(loop, {"A"}), ({}, {}))

    def test_a_closed_shape_on_a_line_is_not_a_junction(self):
        # A filled arrowhead (or an unkeyed symbol's outline) drawn on the run from A to B: the run splits into two
        # paths around it and joins again, so 1 and 2 have three arms each but meet only A, B and each other
        tri = {"A": {1: 0}, 1: {"A": 0, 2: 0, 3: 0}, 3: {1: 0, 2: 0}, 2: {1: 0, 3: 0, "B": 0}, "B": {2: 0}}
        self.assertEqual(ll.contract(tri, {"A", "B"}), ({("A", "B"): 0}, {}))
        # an actuator's box drawn (unkeyed) on valve V's stem: a loop hanging off the valve by one line
        box = {"A": {"V": 0}, "V": {"A": 0, "B": 0, 5: 0}, "B": {"V": 0}, 5: {"V": 0, 3: 0, 4: 0},
               3: {5: 0, 4: 0}, 4: {5: 0, 3: 0}}
        self.assertEqual(ll.contract(box, {"A", "B", "V"}), ({("A", "V"): 0, ("B", "V"): 0}, {}))
        # a real bypass is kept: two tees joined directly and through valve V
        byp = {"A": {1: 0}, 1: {"A": 0, 2: 0, "V": 0}, "V": {1: 0, 2: 0}, 2: {1: 0, "V": 0, "B": 0}, "B": {2: 0}}
        sg, arms = ll.contract(byp, {"A", "B", "V"})
        self.assertEqual(arms, {1: 3, 2: 3})
        self.assertEqual(set(sg), {tuple(sorted(s, key=str)) for s in [("A", 1), (1, 2), (1, "V"), (2, "V"), (2, "B")]})

    def test_classify_lines_by_what_they_join(self):
        # A - J1 - J2 - B with a tap J1 (bubble I1) and a branch to C at J2; bubbles I2 and I3 share a leader that
        # meets the line at J2; valve B has actuator M; nozzle N sits on vessel E and is piped to C.
        sg = {("A", "J1"): 0, ("J1", "J2"): 0, ("B", "J2"): 0, ("C", "J2"): 0, ("I1", "J1"): 0, ("I2", "J3"): 0,
              ("I3", "J3"): 0, ("J2", "J3"): 0, ("B", "M"): 0, ("C", "N"): 0, ("E", "N"): 0}
        arms = {"J1": 3, "J2": 4, "J3": 3}
        roles = {"I1": "instrument", "I2": "instrument", "I3": "instrument", "M": ("actuator", "B"),
                 "N": ("nozzle", "E")}
        c = ll.classify(sg, arms, roles)
        self.assertEqual(set(c["pipe"]), {("A", "J2"), ("B", "J2"), ("C", "J2"), ("C", "N")})
        self.assertEqual(c["pipe"][("A", "J2")]["taps"], ["J1"])
        self.assertEqual(set(c["instrument"]), {("I1", "J1"), ("I2", "J3"), ("I3", "J3"), ("J3", "J2")})
        self.assertEqual(set(c["actuator"]), {("B", "M")})
        self.assertEqual(set(c["nozzle"]), {("N", "E")})
        self.assertEqual(c["kinds"], {"J1": "instrument_tap", "J2": "pipe_tee", "J3": "instrument_line_junction"})
        self.assertEqual(c["tap_on"], {"J1": ("A", "J2")})
        # a junction joining an actuator and its own valve is the valve assembly: it folds into the valve
        c = ll.classify({("A", "V"): 0, ("J", "V"): 0, ("J", "M"): 0, ("I", "J"): 0}, {"J": 3},
                        {"M": ("actuator", "V"), "I": "instrument"})
        self.assertEqual((set(c["pipe"]), set(c["actuator"]), set(c["instrument"]), c["kinds"]),
                         ({("A", "V")}, {("V", "M")}, {("I", "V")}, {}))

    def test_networks_from_a_pipe_layer(self):
        nets = ll.pipe_networks([("A", "J1"), ("B", "J1"), ("J1", "J2"), ("C", "J2"), ("C", "D")], {"J1", "J2"})
        self.assertEqual(nets, [{"members": ["A", "B", "C"], "junctions": ["J1", "J2"]},
                                {"members": ["C", "D"], "junctions": []}])

    def test_scorer_against_a_known_topology(self):
        truth = {"junctions": {"T1": (500.0, 500.0), "T2": None}, "segments": {("A", "T1"), ("B", "T1"), ("C", "T1"),
                                                                             ("D", "T2"), ("E", "T2"), ("F", "T2"),
                                                                             ("G", "H")}}
        pred = {"junctions": {"J0001": {"x": 503, "y": 498}, "J0002": {"x": 10, "y": 10}},
                "segments": [("A", "J0001", 0), ("B", "J0001", 0), ("C", "J0001", 0), ("D", "J0002", 0),
                             ("E", "J0002", 0), ("F", "G", 0)]}
        r = ll.score_pipe(pred, truth, side=40)
        # J0001 matches T1 by position; J0002 matches T2 (no position) by its item neighbours
        self.assertEqual(r["junctions"]["tp"], 2)
        self.assertEqual((r["segments"]["tp"], r["segments"]["predicted"], r["segments"]["truth"]), (5, 6, 7))
        self.assertEqual((r["item_to_item"]["tp"], r["item_to_item"]["predicted"], r["item_to_item"]["truth"]),
                         (0, 1, 1))
        perfect = {"junctions": {"J": {"x": 500, "y": 500}}, "segments": [("A", "J", 0), ("B", "J", 0), ("C", "J", 0)]}
        t = {"junctions": {"T": (500.0, 500.0)}, "segments": {("A", "T"), ("B", "T"), ("C", "T")}}
        self.assertEqual(ll.score_pipe(perfect, t, 40)["segments"]["f1"], 1.0)
        far = {"junctions": {"J": {"x": 900, "y": 900}}, "segments": perfect["segments"]}
        self.assertEqual(ll.score_pipe(far, t, 40)["segments"]["tp"], 0)  # a junction elsewhere is not the tee

    def test_scorer_matches_a_tee_without_position_through_matched_junctions(self):
        # DEXPI tee T2 (no drawn position) sits between tees T1 and T3 with a branch to valve V: its neighbours are
        # two junctions and one item, so item neighbours alone (1) cannot place it; matched junctions count too
        truth = {"junctions": {"T1": (100.0, 500.0), "T2": None, "T3": (300.0, 500.0)},
                 "segments": {("A", "T1"), ("C", "T1"), ("T1", "T2"), ("T2", "V"), ("T2", "T3"), ("B", "T3"),
                              ("D", "T3")}}
        pred = {"junctions": {"J1": {"x": 101, "y": 500}, "J2": {"x": 200, "y": 500}, "J3": {"x": 299, "y": 500}},
                "segments": [("A", "J1", 0), ("C", "J1", 0), ("J1", "J2", 0), ("J2", "V", 0), ("J2", "J3", 0),
                             ("B", "J3", 0), ("D", "J3", 0)]}
        r = ll.score_pipe(pred, truth, side=40)
        self.assertEqual((r["junctions"]["tp"], r["segments"]["tp"]), (3, 7))
        # but one shared neighbour is not enough to name a tee
        lone = {"junctions": {"T": None}, "segments": {("A", "T"), ("B", "T"), ("C", "T")}}
        guess = {"junctions": {"J": {"x": 5, "y": 5}}, "segments": [("A", "J", 0), ("X", "J", 0), ("Y", "J", 0)]}
        self.assertEqual(ll.score_pipe(guess, lone, side=40)["junctions"]["tp"], 0)


class Truths(unittest.TestCase):
    def test_generated_drawing_truth_matches_its_key_and_scores(self):
        base = ROOT / "data" / "bayer_rt" / "pid"
        if not (base / "RT1.png").is_file():
            self.skipTest("Bayer sheet not present")
        cfg = ll.SETS["bayer"]
        t = ll.drawn_truth(ROOT / cfg["model"], ROOT / cfg["layout"], base / "manifest.json", base / "key.json")
        self.assertEqual(set(t), {"RT1"})  # the key check inside drawn_truth passed: same line networks
        self.assertTrue(t["RT1"]["junctions"])
        r = ll.score_set("bayer")
        pred = ll.traced_layers(base / "RT1.png", ll.key_symbols(base / "RT1.graphml", base / "RT1.png"))
        c = ll.classify_truth(t["RT1"], pred["roles"])
        # the drawer's instrument taps are taps in the truth too: the pipe passes them, the bubble's line is not pipe
        self.assertIn("instrument_tap", c["kinds"].values())
        self.assertEqual(r["total"]["segments"]["truth"], len(c["segments"]))
        self.assertLess(len(c["segments"]), len(t["RT1"]["segments"]))
        self.assertFalse([s for s in c["segments"] if any(pred["roles"].get(x) == "instrument" for x in s)])
        self.assertEqual(r["total"]["instrument_lines"]["truth"], len(c["instrument_lines"]))
        self.assertGreater(r["total"]["segments"]["f1"], 0.0)

    def test_two_pipes_landing_on_a_vessel_shell_are_not_a_tee(self):
        # SPPID's render of DEXPI C01 (a development sheet, A177): the lines from PV 4712.02 and TV 4750.03 land on
        # the heat exchanger's shell 53 px apart, at nozzles N2 and N3; the shell runs along the box edge between them,
        # so the two landing points were read as one tee beside the box. Each pipe goes to the exchanger.
        base = ROOT / "data" / "external" / "dexpi-ttc-all" / "vendor-keys"
        png = base / "C01V01-HEX.EX02.png"
        if not png.is_file():
            self.skipTest("DEXPI 1.2 vendor render not present (scripts/corpus_adapters.py build_vendor_keys)")
        im = cv2.imread(str(png), cv2.IMREAD_GRAYSCALE)
        H, W = im.shape
        x0, y0, x1, y1 = 3750, 1200, 4350, 1900
        with tempfile.TemporaryDirectory() as tmp:
            crop = Path(tmp) / "crop.png"
            cv2.imwrite(str(crop), im[y0:y1, x0:x1])
            syms = []
            for x in ll.key_symbols(base / "C01V01-HEX.EX02.graphml", png):
                b = [x["box"][0] * W / 1000 - x0, x["box"][1] * H / 1000 - y0, x["box"][2] * W / 1000 - x0,
                     x["box"][3] * H / 1000 - y0]
                if b[0] >= 0 and b[1] >= 0 and b[2] <= x1 - x0 and b[3] <= y1 - y0:
                    syms.append({"id": x["id"][:6], "class": x["class"],
                                 "box": [1000 * b[0] / (x1 - x0), 1000 * b[1] / (y1 - y0), 1000 * b[2] / (x1 - x0),
                                         1000 * b[3] / (y1 - y0)]})
            self.assertEqual(sorted(x["id"] for x in syms), ["SP5539", "SPE107", "SPFA27"])
            out = ll.traced_layers(crop, syms)
        self.assertEqual(out["junctions"], {})
        self.assertEqual(segs(out), {("SP5539", "SPE107"), ("SPE107", "SPFA27")})

    def test_a_drawing_from_another_generator_version_is_refused(self):
        cfg = ll.SETS["te"]
        man = ROOT / "data" / "te_pid" / "rev-a" / "manifest.json"
        if not man.is_file():
            self.skipTest("TE revision A not present")
        with self.assertRaises(ValueError):
            ll.drawn_truth(ROOT / cfg["model"], ROOT / cfg["layout"], man)

    def test_pid2graph_key_graph_gives_a_derived_pipe_truth(self):
        """The PID2Graph key is a graph (symbols joined through connector and crossing nodes), not only pairs: walked
        symbol to symbol it gives direct adjacency, and its line networks are exactly the key's all-pairs links."""
        d = ROOT / "data" / "external" / "pid2graph" / "PID2Graph" / "Complete" / "PID2Graph OPEN100"
        if not (d / "0.graphml").is_file():
            self.skipTest("OPEN100 not present")
        t = ll.pid2graph_truth(d / "0.graphml", d / "0.png")
        self.assertTrue(t["networks_match_key_pairs"])
        self.assertEqual(len(t["junctions"]), 38)  # the key's 3-edge crossings
        w, h = 2604, 1744                          # the tee beside MSCV-XXX's box is in the key
        self.assertTrue(any(abs(x - 537 * w / 1000) < 8 and abs(y - 276 * h / 1000) < 8
                            for x, y in t["junctions"].values()))
        r = ll.score_set("open100", ["0"])["sheets"]["0"]
        self.assertGreaterEqual(r["segments"]["f1"], 0.95)
        self.assertEqual(r["junction_kinds"]["same_kind"], 38)

    def test_dexpi_truth_reads_tees_as_junctions(self):
        try:
            xml = ll.dexpi_xml("dexpi-c01")
        except (ValueError, OSError, KeyError):
            self.skipTest("DEXPI config not readable")
        gml = ROOT / "data" / "external" / "dexpi" / "sheets" / "dexpi-c01.graphml"
        png = gml.with_suffix(".png")
        if not (Path(xml).is_file() and gml.is_file() and png.is_file()):
            self.skipTest("DEXPI examples not cached (python scripts/adapt_dexpi.py fetch && build)")
        t = ll.dexpi_truth(xml, gml, png)
        self.assertEqual(len(t["junctions"]), 5)
        self.assertTrue(all(j.startswith("PipeTee") for j in t["junctions"]))
        self.assertFalse([s for s in t["segments"] if any(x.startswith("ProcessInstrumentationFunction") for x in s)])


VENDOR_XML = """<?xml version="1.0" encoding="utf-8"?>
<PlantModel>
  <PlantInformation OriginatingSystem="SPPID" SchemaVersion="3.3.3"/>
  <Drawing Name="T1" Type="PID"><Extent><Min X="0" Y="0"/><Max X="200" Y="100"/></Extent></Drawing>
  <ShapeCatalogue>
    <Equipment ComponentName="BOX" ComponentClass="Tank">
      <PolyLine NumPoints="5"><Coordinate X="-10" Y="-10"/><Coordinate X="10" Y="-10"/><Coordinate X="10" Y="10"/>
        <Coordinate X="-10" Y="10"/><Coordinate X="-10" Y="-10"/></PolyLine>
    </Equipment>
    <PipingComponent ComponentName="VLV" ComponentClass="GateValve">
      <PolyLine NumPoints="5"><Coordinate X="-5" Y="-4"/><Coordinate X="5" Y="4"/><Coordinate X="5" Y="-4"/>
        <Coordinate X="-5" Y="4"/><Coordinate X="-5" Y="-4"/></PolyLine>
    </PipingComponent>
  </ShapeCatalogue>
  <Equipment ID="E1" ComponentClass="Tank" ComponentName="BOX">
    <Position><Location X="40" Y="50"/><Axis X="0" Y="0" Z="1"/><Reference X="1" Y="0"/></Position></Equipment>
  <Equipment ID="E2" ComponentClass="Tank" ComponentName="BOX">
    <Position><Location X="160" Y="30"/><Axis X="0" Y="0" Z="1"/><Reference X="1" Y="0"/></Position></Equipment>
  <PipingNetworkSystem ID="PNS1">
    <PipingNetworkSegment ID="S1">
      <CenterLine NumPoints="4"><Coordinate X="50" Y="50"/><Coordinate X="120" Y="50"/><Coordinate X="120" Y="30"/>
        <Coordinate X="150" Y="30"/></CenterLine>
      <PipingComponent ID="V1" ComponentClass="GateValve" ComponentName="VLV">
        <Position><Location X="90" Y="50"/><Axis X="0" Y="0" Z="1"/><Reference X="1" Y="0"/></Position>
      </PipingComponent>
      <Connection FromID="E1" ToID="E2"/>
    </PipingNetworkSegment>
  </PipingNetworkSystem>
</PlantModel>
"""


class VendorRender(unittest.TestCase):
    """Adapter A2 (scripts/corpus_adapters.py): a DEXPI export's own render keyed from its XML by a fitted map, read
    by the scorers as any keyed sheet."""
    MAP = (4.0, 30.0, -4.0, 450.0)  # u = 4x + 30, v = -4y + 450: drawing y points up, pixel rows down

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.xml = self.dir / "T1.xml"
        self.xml.write_text(VENDOR_XML, encoding="utf-8")

    def render(self, name, dark=False, drawing=True, shift=(0, 0)):
        a, c, e, f = self.MAP
        px = lambda x, y: (int(round(a * x + c + shift[0])), int(round(e * y + f + shift[1])))  # noqa: E731
        img = np.full((500, 900, 3), (31, 31, 31) if dark else (255, 255, 255), np.uint8)
        ink = (255, 128, 0) if dark else (0, 0, 0)  # a blue line on a dark screen has almost the background's grey
        if dark:
            img[::20, :] = img[:, ::20] = (52, 52, 52)  # a dim display grid
        if drawing:
            for cx, cy in ((40, 50), (160, 30)):
                cv2.rectangle(img, px(cx - 10, cy + 10), px(cx + 10, cy - 10), ink, 2)
            cv2.polylines(img, [np.array([px(-5 + 90, -4 + 50), px(5 + 90, 4 + 50), px(5 + 90, -4 + 50),
                                          px(-5 + 90, 4 + 50)], np.int32)], True, ink, 2)
            for p, q in (((50, 50), (85, 50)), ((95, 50), (120, 50)), ((120, 50), (120, 30)), ((120, 30), (150, 30))):
                cv2.line(img, px(*p), px(*q), ink, 2)
        path = self.dir / name
        cv2.imwrite(str(path), img)
        return path

    def entry(self, render):
        return {"id": "T1", "exporter": "sppid", "case_version": "T01V01", "xml": self.xml, "render": render}

    def test_the_fitted_map_finds_the_known_transform_and_the_scorers_read_the_key(self):
        import corpus_adapters as ca
        import score_pid2graph as sc
        out = self.dir / "keys"
        rec = ca.build_vendor_key(self.entry(self.render("T1.png")), out, overlay_dir=self.dir / "overlays")
        self.assertEqual(rec["status"], "mapped", rec["reason"])
        for got, want in zip(rec["fit"]["map"], self.MAP):
            self.assertAlmostEqual(got, want, delta=0.02 * abs(want) + 1.5)
        self.assertTrue((self.dir / "overlays" / "sppid__T1.png").is_file())
        w, h = sc.png_size(out / "T1.png")
        nodes, adj = sc.load_key(out / "T1.graphml", w, h)
        self.assertEqual({k: v["class"] for k, v in nodes.items()}, {"E1": "tank", "E2": "tank", "V1": "valve"})
        b = nodes["E1"]["box"]  # 0-1000 scale: x 150-230 px of 900, y 210-290 px of 500
        self.assertAlmostEqual(b[0] * w / 1000, 150, delta=3)
        self.assertAlmostEqual(b[1] * h / 1000, 210, delta=3)
        self.assertAlmostEqual(b[3] * h / 1000, 290, delta=3)
        self.assertEqual(sc.asset_links(nodes, adj), {frozenset(("E1", "V1")), frozenset(("E2", "V1"))})
        self.assertEqual(ll.set_sheets("dexpi-1.2-vendor", out), ["T1"])
        r = ll.score_set("dexpi-1.2-vendor", base=out)
        self.assertEqual(r["sheets"]["T1"]["segments"]["truth"], 2)       # E1-V1, V1-E2 from the XML's segment
        self.assertEqual(r["total"]["segments"]["f1"], 1.0)

    def test_a_dark_screen_capture_is_read_as_dark_ink_on_white(self):
        import corpus_adapters as ca
        gray, normalised = ca.read_render(self.render("dark.png", dark=True))
        self.assertTrue(normalised)
        self.assertEqual(int(gray[0, 0]), 255)      # the background, and its grid, are paper
        self.assertEqual(int(gray[1, 1]), 255)
        rec = ca.build_vendor_key(self.entry(self.dir / "dark.png"), self.dir / "keys")
        self.assertEqual(rec["status"], "mapped", rec["reason"])

    def test_a_render_without_the_drawing_is_not_mapped(self):
        import corpus_adapters as ca
        path = self.render("grid.png", drawing=False)
        img = cv2.imread(str(path))
        img[::6, ::6] = 0  # a dot grid: ink everywhere, so points land on it by chance
        cv2.imwrite(str(path), img)
        rec = ca.build_vendor_key(self.entry(path), self.dir / "keys")
        self.assertEqual(rec["status"], "n/a")
        self.assertIn("the map fails its check", rec["reason"])
        self.assertFalse((self.dir / "keys" / "T1.graphml").exists())


class ScorePublication(unittest.TestCase):
    def test_cli_scores_preserve_all_sets_images_and_graphml(self):
        public = ROOT / 'data/external/pid2graph/PID2Graph/Complete/PID2Graph OPEN100'
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            sets, sources = {}, []
            for name in ('first', 'second'):
                base = folder / name
                base.mkdir()
                for extension in ('png', 'graphml'):
                    path = base / ('0.' + extension)
                    shutil.copyfile(public / path.name, path)
                    sources.append(path)
                sets[name] = {'dir': str(base), 'sheets': ['0'], 'scope': 'all', 'truth': 'pid2graph'}
            before = {p: p.read_bytes() for p in sources}
            with mock.patch.dict(ll.SETS, sets):
                for i, source in enumerate(sources):
                    out = folder / f'alias-{i}.json'
                    out.hardlink_to(source)
                    with self.subTest(source=str(source)), contextlib.redirect_stdout(io.StringIO()), \
                            contextlib.redirect_stderr(io.StringIO()) as errors:
                        self.assertEqual(ll.main(['score', '--set', 'first', '--set', 'second', '--json', str(out)]), 1)
                        self.assertIn('output aliases an input', errors.getvalue())
                        self.assertEqual(before, {p: p.read_bytes() for p in before})
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(ll.main(['score', '--set', 'first', '--set', 'second',
                                              '--json', str(folder / 'fresh.json')]), 0)
                self.assertEqual(len(json.loads((folder / 'fresh.json').read_bytes())), 2)

    def test_unmapped_selection_sidecars_are_still_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            source = folder / 'not-mapped.json'
            source.write_text('{"status":"unmapped"}', encoding='utf-8')
            before = source.read_bytes()
            cfg = {'dir': str(folder), 'sheets': None, 'scope': 'process', 'truth': 'dexpi_sidecar'}
            with mock.patch.dict(ll.SETS, {'selection': cfg}), contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(io.StringIO()) as errors:
                self.assertEqual(ll.main(['score', '--set', 'selection', '--json', str(source)]), 1)
            self.assertIn('output aliases an input', errors.getvalue())
            self.assertEqual(source.read_bytes(), before)


class Enrich(unittest.TestCase):
    def test_enrich_refuses_links_that_are_not_the_twins(self):
        img = ROOT / "data" / "external" / "pid2graph" / "PID2Graph" / "Complete" / "PID2Graph OPEN100" / "0.png"
        bundle = ROOT / "examples" / "own-drawing"
        if not img.is_file():
            self.skipTest("OPEN100 sheet 0 not present")
        g = json.loads((ROOT / "examples" / "graph-export" / "sheet0_graph.json").read_text(encoding="utf-8"))
        self.assertTrue(any(n["kind"] == "junction" for n in g["nodes"]), bundle)
        model = {"meta": {"model_kind": "extracted_twin"}, "units": [], "instruments": [], "line_items": [
            {"id": "X1", "provenance": [{"sheet": "0", "symbol": "a", "class": "valve", "box_0_1000": [10, 10, 20, 20]}]},
            {"id": "X2", "provenance": [{"sheet": "0", "symbol": "b", "class": "valve", "box_0_1000": [30, 10, 40, 20]}]}],
            "offpage_connectors": [], "streams": [{"id": "L0-001", "kind": "extracted_link", "sheet": "0",
                                                   "from": "X1", "to": "X2", "from_symbol": "a", "to_symbol": "b"}]}
        with self.assertRaises(ValueError) as cm:
            ll.enrich(model, {"0": img})
        self.assertIn("re-traced links differ", str(cm.exception))
        with self.assertRaises(ValueError):
            ll.enrich({"meta": {}, "units": [], "streams": []}, {})

class DrawingManifest(unittest.TestCase):
    """The real writer and truth reader share CRLF-only text identity, not JSON semantics."""

    VERIFY = """import pathlib,pickle,sys
sys.path.insert(0,sys.argv[1])
import line_layers
truth=line_layers.drawn_truth(*map(pathlib.Path,sys.argv[2:6]))
pathlib.Path(sys.argv[6]).write_bytes(pickle.dumps(truth))
"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)

    def case(self, name, generator_crlf=False, model_crlf=False, layout_crlf=False):
        import subprocess
        folder = self.folder / name
        scripts = folder / "scripts"
        scripts.mkdir(parents=True)
        for filename in ("draw_pid_from_model.py", "line_layers.py", "output_paths.py"):
            data = (ROOT / "scripts" / filename).read_bytes()
            if filename == "draw_pid_from_model.py":
                data = data.replace(b"\r\n", b"\n")
                if generator_crlf:
                    data = data.replace(b"\n", b"\r\n")
            (scripts / filename).write_bytes(data)
        sources = folder / "external"
        sources.mkdir()
        for filename, crlf in (("process_model.json", model_crlf), ("pid_layout.json", layout_crlf)):
            data = (ROOT / "data/bayer_rt" / filename).read_bytes().replace(b"\r\n", b"\n")
            if crlf:
                data = data.replace(b"\n", b"\r\n")
            (sources / filename).write_bytes(data)
        model, layout = sources / "process_model.json", sources / "pid_layout.json"
        out = folder / "output"
        before = {p: p.read_bytes() for p in (scripts / "draw_pid_from_model.py", model, layout)}
        run = subprocess.run([sys.executable, str(scripts / "draw_pid_from_model.py"), "--model", str(model),
                              "--layout", str(layout), "--out", str(out)], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        return scripts, model, layout, out, before

    def verify(self, case, manifest=None, key=None):
        import subprocess
        scripts, model, layout, out, _ = case
        truth = out.parent / "truth.pickle"
        run = subprocess.run([sys.executable, "-c", self.VERIFY, str(scripts), str(model), str(layout),
                              str(manifest or out / "manifest.json"), str(key or out / "key.json"), str(truth)],
                             capture_output=True, text=True)
        return run, truth

    def test_writer_and_verifier_agree_for_all_eight_newline_combinations(self):
        import itertools
        import pickle
        expected_truth = expected_outputs = None
        for flags in itertools.product((False, True), repeat=3):
            with self.subTest(generator_crlf=flags[0], model_crlf=flags[1], layout_crlf=flags[2]):
                case = self.case("".join("C" if f else "L" for f in flags), *flags)
                run, truth = self.verify(case)
                self.assertEqual(run.returncode, 0, run.stderr)
                actual_truth = pickle.loads(truth.read_bytes())
                outputs = {p.name: p.read_bytes() for p in case[3].iterdir()}
                self.assertEqual(set(outputs), {"RT1.png", "RT1.svg", "RT1.graphml", "key.json",
                                               "manifest.json", "sheet_register.csv"})
                self.assertEqual(case[4], {p: p.read_bytes() for p in case[4]})
                if expected_truth is None:
                    expected_truth, expected_outputs = actual_truth, outputs
                    self.assertEqual(set(actual_truth), {"RT1"})
                    self.assertTrue(actual_truth["RT1"]["junctions"])
                else:
                    self.assertEqual(actual_truth, expected_truth)
                    self.assertEqual(outputs, expected_outputs)

    def test_other_dependency_byte_changes_still_refuse(self):
        case = self.case("byte-changes")
        scripts, model, layout, _, _ = case
        for path, field in ((scripts / "draw_pid_from_model.py", "generator_sha256"),
                            (model, "model_sha256"), (layout, "layout_sha256")):
            original = path.read_bytes()
            if path == model:
                parsed = json.loads(original)
                parsed["units"][0]["name"] += " changed content"
                content_edit = json.dumps(parsed).encode("utf-8")
            elif path == layout:
                parsed = json.loads(original)
                parsed["sheets"][0]["title"] += " changed content"
                content_edit = json.dumps(parsed).encode("utf-8")
            else:
                content_edit = original + b"\n# changed generator content\n"
            for kind, changed in (("content", content_edit), ("space", original + b" "),
                                  ("bare-CR", original + b"\r"), ("extra-LF", original + b"\n")):
                with self.subTest(dependency=field, change=kind):
                    try:
                        path.write_bytes(changed)
                        run, _ = self.verify(case)
                        self.assertNotEqual(run.returncode, 0)
                        self.assertIn(field + " differs", run.stderr)
                    finally:
                        path.write_bytes(original)
        run, _ = self.verify(case)
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_wrong_missing_historical_hashes_and_changed_key_still_refuse(self):
        case = self.case("guards")
        _, _, _, out, _ = case
        original = json.loads((out / "manifest.json").read_bytes())
        modified = out.parent / "modified-manifest.json"
        for field in ("generator_sha256", "model_sha256", "layout_sha256"):
            for kind in ("missing", "wrong"):
                with self.subTest(field=field, kind=kind):
                    manifest = dict(original)
                    if kind == "missing":
                        del manifest[field]
                    else:
                        manifest[field] = "0" * 64
                    modified.write_text(json.dumps(manifest), encoding="utf-8")
                    run, _ = self.verify(case, manifest=modified)
                    self.assertNotEqual(run.returncode, 0)
                    self.assertIn(field + " differs", run.stderr)
        for revision in ("rev-a", "rev-c"):
            with self.subTest(historical=revision):
                manifest = ROOT / "data/te_pid" / revision / "manifest.json"
                self.assertTrue(manifest.is_file(), str(manifest))
                run, _ = self.verify(case, manifest=manifest)
                self.assertNotEqual(run.returncode, 0)
                self.assertIn("generator_sha256 differs", run.stderr)
        key = json.loads((out / "key.json").read_bytes())
        key["sheets"]["RT1"]["edges"] = []
        changed_key = out.parent / "changed-key.json"
        changed_key.write_text(json.dumps(key), encoding="utf-8")
        run, _ = self.verify(case, key=changed_key)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("pipe truth's line networks are not the key's", run.stderr)

if __name__ == "__main__":
    unittest.main()
