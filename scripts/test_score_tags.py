"""Controls for the tag scorer (scripts/score_tags.py) on synthetic keys. Stdlib only.

Positive and negative controls in the spirit of test_scorer_controls.py: a perfect answer scores 1.0, an empty
answer scores 0, wrong text is wrong (not missed), missing text is no_tag, and moving every box off its symbol
turns every tag into a miss even when the text is right.
"""
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

import score_tags as st

KEY = {"V1": ("valve", (100, 100, 140, 120), "FV-101"), "I1": ("instrumentation", (300, 100, 340, 140), "FIC 101"),
       "P1": ("pump", (500, 100, 560, 160), "P4711"), "G1": ("general", (700, 100, 720, 120), None)}


def png(path, w=1000, h=1000):
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    raw = b"".join(b"\x00" + b"\xff" * w for _ in range(1))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def write_key(d):
    rows = ['<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
            '<key id="l" for="node" attr.name="label"/><key id="a" for="node" attr.name="xmin"/>',
            '<key id="b" for="node" attr.name="xmax"/><key id="c" for="node" attr.name="ymin"/>',
            '<key id="e" for="node" attr.name="ymax"/><graph>']
    for k, (cls, (x0, y0, x1, y1), _) in KEY.items():
        rows.append(f'<node id="{k}"><data key="l">{cls}</data><data key="a">{x0}</data><data key="b">{x1}</data>'
                    f'<data key="c">{y0}</data><data key="e">{y1}</data></node>')
    rows.append("</graph></graphml>")
    (d / "s.graphml").write_text("".join(rows), encoding="utf-8")
    (d / "s.tags.json").write_text(json.dumps({"tags": {k: v[2] for k, v in KEY.items()}}), encoding="utf-8")
    png(d / "s.png")


def answer(tags, shift=0):
    return {"symbols": [{"id": f"s{i}", "class": cls, "tag": tags.get(k),
                         "box": [x0 + shift, y0 + shift, x1 + shift, y1 + shift]}
                        for i, (k, (cls, (x0, y0, x1, y1), _)) in enumerate(KEY.items())], "connections": []}


class Controls(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        write_key(self.d)

    def tearDown(self):
        self.tmp.cleanup()

    def score(self, pred):
        return st.score_geometry(self.d / "s.graphml", self.d / "s.tags.json", pred, self.d / "s.png")

    def test_perfect(self):
        r = self.score(answer({k: v[2] for k, v in KEY.items()}))
        self.assertEqual(r["with_truth"], 3)        # the unlabeled symbol has no truth
        self.assertEqual(r["strict"]["accuracy_on_found"], 1.0)
        self.assertEqual(r["strict"]["end_to_end_recall"], 1.0)

    def test_empty_and_failed(self):
        for pred in ({"symbols": [], "connections": []}, None):
            r = self.score(pred)
            self.assertEqual(r["strict"]["missed"], 3)
            self.assertEqual(r["strict"]["end_to_end_recall"], 0.0)
            self.assertIsNone(r["strict"]["accuracy_on_found"])

    def test_wrong_and_missing_text(self):
        r = self.score(answer({"V1": "FV-102", "I1": None, "P1": "P4711"}))
        self.assertEqual((r["strict"]["correct"], r["strict"]["wrong"], r["strict"]["no_tag"]), (1, 1, 1))

    def test_separators_strict_vs_lenient(self):
        r = self.score(answer({"V1": "FV 101", "I1": "fic101", "P1": "P-4711"}))
        self.assertEqual(r["strict"]["correct"], 1)    # only "fic101" == "FIC101" after whitespace removal
        self.assertEqual(r["lenient"]["correct"], 3)

    def test_boxes_moved_away_are_misses(self):
        r = self.score(answer({k: v[2] for k, v in KEY.items()}, shift=400))
        self.assertEqual(r["strict"]["correct"], 0)

    def test_normalisers(self):
        self.assertEqual(st.norm_strict(" pi(z) 27 5003a "), "PI(Z)275003A")
        self.assertEqual(st.norm_lenient("PIS⁺Z⁺A 275003"), "PISZA275003")


class TagList(unittest.TestCase):
    def test_recall_and_class(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "k.taglist.json"
            p.write_text(json.dumps({"items": [
                {"identifier": "P0020", "class": "instrumentation", "list": "instrument"},
                {"identifier": "AB020", "class": "valve", "list": "valve"},
                {"identifier": "BA100", "class": "tank", "list": "equipment"}]}), encoding="utf-8")
            pred = {"symbols": [{"id": "a", "class": "instrumentation", "tag": "PI P0020"},
                                {"id": "b", "class": "general", "tag": "AB-020"},
                                {"id": "c", "class": "tank", "tag": None},
                                {"id": "d", "class": "tank", "tag": "BA10"}]}
            r = st.score_taglist(p, pred)
            self.assertEqual(r["all"]["found"], 2)
            self.assertEqual(r["all"]["found_with_list_class"], 1)
            self.assertEqual(r["by_list"]["equipment"]["found"], 0)   # "BA10" is not "BA100"
            self.assertEqual(st.score_taglist(p, None)["all"]["found"], 0)


if __name__ == "__main__":
    unittest.main()
