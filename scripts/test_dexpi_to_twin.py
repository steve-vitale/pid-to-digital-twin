"""Controls for scripts/dexpi_to_twin.py (DEXPI key -> intake prediction -> review bundle, no model). Stdlib only.

A synthetic key always runs: tee collapse, exact tags, null confidence, clamping, the drop report and the intake.
If the real DEXPI sheets have been built locally (adapt_dexpi.py fetch + build), every built geometry-keyed sheet is
also converted and imported: each key symbol in the six classes must arrive with its class and exact drawn tag, each
key edge between two such symbols must survive, every dropped node must be reported, and the intake must succeed.
Without the cache those checks are skipped with a message, never failed. Nothing here measures extraction accuracy.
"""
import json
import copy
import hashlib
import shutil
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock

import adapt_dexpi as A
import dexpi_to_twin as D
import import_site_drawing as I
import score_pid2graph as sc


def png(width, height):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    raw = b"".join(b"\x00" + b"\xff" * width for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


# Pixel boxes on a 200 x 100 page. Tee-1 joins Pump-1, Valve-1 and Valve-2; Tank-1's box runs off the right edge.
NODES = {"Pump-1": ("pump", (10, 10, 30, 30)), "Valve-1": ("valve", (50, 10, 60, 20)),
         "Valve-2": ("valve", (50, 40, 60, 50)), "Tee-1": ("connector", (0, 0, 0, 0)),
         "Tank-1": ("tank", (150, 20, 205, 80)), "PIF-1": ("instrumentation", (100, 60, 110, 70))}
EDGES = [("Pump-1", "Tee-1"), ("Tee-1", "Valve-1"), ("Tee-1", "Valve-2"), ("Valve-1", "Tank-1"), ("PIF-1", "Tank-1")]
TAGS = {"Pump-1": "P 101", "Valve-1": "73KH12-50", "Valve-2": None, "Tank-1": "T4750", "PIF-1": "PICSA 4712.02"}


def write_key(folder, sid="dexpi-t01"):
    folder = Path(folder)
    lines = ['<?xml version="1.0" encoding="utf-8"?>', '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">']
    lines += [f'<key id="d{i}" for="node" attr.name="{n}" attr.type="string" />'
              for i, n in enumerate(("label", "xmin", "xmax", "ymin", "ymax"))]
    lines.append('<graph edgedefault="undirected">')
    for nid, (cls, (x0, y0, x1, y1)) in NODES.items():
        lines.append(f'<node id="{nid}"><data key="d0">{cls}</data><data key="d1">{x0}</data><data key="d2">{x1}</data>'
                     f'<data key="d3">{y0}</data><data key="d4">{y1}</data></node>')
    lines += [f'<edge id="e{i}" source="{a}" target="{b}" />' for i, (a, b) in enumerate(EDGES)]
    lines += ["</graph>", "</graphml>"]
    (folder / f"{sid}.graphml").write_text("\n".join(lines), encoding="utf-8")
    (folder / f"{sid}.tags.json").write_text(json.dumps({"tags": TAGS, "dexpi_class": {
        "Pump-1": "CentrifugalPump", "Valve-1": "BallValve", "Valve-2": "GlobeValve", "Tee-1": "PipeTee",
        "Tank-1": "Tank", "PIF-1": "ProcessInstrumentationFunction"}}), encoding="utf-8")
    (folder / f"{sid}.png").write_bytes(png(200, 100))
    return sid


def bundle_tags(bundle):
    model = json.loads((Path(bundle) / "plant_model.json").read_text(encoding="utf-8"))
    out = {}
    for coll in ("units", "instruments", "line_items", "offpage_connectors"):
        for item in model[coll]:
            for appearance in item["provenance"]:
                out[appearance["symbol"]] = item["tag"]
    return model, out


class Synthetic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        d = Path(cls.tmp.name)
        cls.sid = write_key(d)
        cls.pred, cls.report = D.convert(cls.sid, d)
        cfg = {"license": "CC-BY-4.0"}
        spec = {"xml": "x/T01.xml", "title": "synthetic"}
        _, cls.manifest = D.write_outputs(cls.sid, cls.pred, d / "work", cfg, spec, d / f"{cls.sid}.png")
        cls.result = I.import_drawing(cls.manifest, d / "bundle")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_symbols_tags_and_null_confidence(self):
        s = {x["id"]: x for x in self.pred["symbols"]}
        self.assertEqual(sorted(s), sorted(k for k, v in NODES.items() if v[0] != "connector"))
        for sid, sym in s.items():
            self.assertEqual(sym["class"], NODES[sid][0])
            self.assertEqual(sym["tag"], TAGS[sid])          # exact, spaces and dots kept
            self.assertIsNone(sym["confidence"])
        self.assertEqual(s["Pump-1"]["box"], [50.0, 100.0, 150.0, 300.0])

    def test_box_off_the_page_is_clamped_and_reported(self):
        self.assertEqual({x["id"]: x for x in self.pred["symbols"]}["Tank-1"]["box"][2], 1000.0)
        self.assertEqual(self.report["dropped"]["boxes_clamped_to_page"], ["Tank-1"])

    def test_tee_collapses_to_pairwise_links_and_direct_edges_survive(self):
        links = {frozenset((c["from"], c["to"])) for c in self.pred["connections"]}
        self.assertEqual(links, {frozenset(p) for p in [("Pump-1", "Valve-1"), ("Pump-1", "Valve-2"), ("Valve-1", "Valve-2"),
                                                         ("Valve-1", "Tank-1"), ("PIF-1", "Tank-1")]})
        o = self.report["out"]
        self.assertEqual((o["connections_kept_as_drawn"], o["connections_added_by_collapsing_tees"]), (2, 3))
        self.assertEqual(self.report["dropped"]["edges_between_symbols_lost"], [])

    def test_drops_are_reported(self):
        self.assertEqual(sum(self.report["dropped"]["key_nodes"].values()), 1)
        self.assertIn("PipeTee", next(iter(self.report["dropped"]["key_nodes"])))
        self.assertTrue(self.report["lossy_steps"])

    def test_producer_says_no_model(self):
        m = json.loads(self.manifest.read_text(encoding="utf-8"))
        self.assertEqual(m["producer"], {"method": "converted from DEXPI XML, no model", "tool": "dexpi_to_twin.py", "model": None})
        self.assertEqual(m["extraction_format"], "prediction")

    def test_intake_succeeds_and_keeps_tags(self):
        self.assertTrue(self.result["exports_written"])
        self.assertFalse(self.result["operational_export_allowed"])
        model, tags = bundle_tags(self.result["output"])
        for sid, tag in TAGS.items():
            self.assertEqual(tags[sid], tag)
        self.assertEqual(self.result["summary"]["streams_extracted"], len(self.pred["connections"]))
        self.assertEqual(model["meta"]["intake"]["supplied_producer"]["model"], None)

    def test_tag_list_sheet_is_refused(self):
        with self.assertRaises(SystemExit):
            D.sheet_spec("dexpi-c08a")


class BuiltSheets(unittest.TestCase):
    def test_every_built_sheet(self):
        built = [s for s in A.config()["geometry_keyed"]
                 if all((A.SHEETS / f"{s['id']}.{e}").is_file() for e in ("graphml", "tags.json", "png"))]
        if not built:
            self.skipTest("DEXPI sheets not built; run python scripts/adapt_dexpi.py fetch && python scripts/adapt_dexpi.py build")
        with tempfile.TemporaryDirectory() as tmp:
            cfg = A.config()
            for spec in built:
                sid = spec["id"]
                with self.subTest(sheet=sid):
                    pred, report = D.convert(sid, None, A.local_path(spec["xml"]))
                    w, h = sc.png_size(A.SHEETS / f"{sid}.png")
                    nodes, adj = sc.load_key(A.SHEETS / f"{sid}.graphml", w, h)
                    key_tags = json.loads((A.SHEETS / f"{sid}.tags.json").read_text(encoding="utf-8"))["tags"]
                    kept = {k: n for k, n in nodes.items() if n["class"] in sc.SCORED}
                    syms = {s["id"]: s for s in pred["symbols"]}
                    self.assertEqual(set(syms), set(kept))
                    for k, n in kept.items():
                        self.assertEqual(syms[k]["class"], n["class"])
                        self.assertEqual(syms[k]["tag"], key_tags.get(k))
                    links = {frozenset((c["from"], c["to"])) for c in pred["connections"]}
                    direct = {frozenset((a, b)) for a in adj for b in adj[a] if a in kept and b in kept}
                    self.assertLessEqual(direct, links)
                    self.assertEqual(links, {frozenset(l) for l in sc.asset_links(nodes, adj)})
                    self.assertEqual(sum(report["dropped"]["key_nodes"].values()), len(nodes) - len(kept))
                    self.assertIsInstance(report["xml"], dict, "pinned XML should be cached alongside a built key")
                    _, manifest = D.write_outputs(sid, pred, Path(tmp) / "work", cfg, spec, A.SHEETS / f"{sid}.png")
                    result = I.import_drawing(manifest, Path(tmp) / f"bundle-{sid}")
                    self.assertTrue(result["exports_written"])
                    _, tags = bundle_tags(result["output"])
                    self.assertEqual({k: tags[k] for k in kept}, {k: key_tags.get(k) for k in kept})
                    self.assertEqual(result["summary"]["streams_extracted"], len(links))


class PortableStaging(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "originals"
        self.source.mkdir()
        self.sid = write_key(self.source)
        self.image = self.source / f"{self.sid}.png"
        self.pred, _ = D.convert(self.sid, self.source)
        self.out = self.root / "staging"

    def write(self, out=None, pred=None):
        return D.write_outputs(self.sid, pred or self.pred, out or self.out,
                               {"license": "CC-BY-4.0"}, {"xml": "T01.xml", "title": "synthetic"}, self.image)

    def snapshot(self, folder):
        return {str(p.relative_to(folder)): p.read_bytes() for p in folder.rglob("*") if p.is_file()}

    def test_packet_moves_without_original_image_and_imports(self):
        self.write()
        original = self.image.read_bytes()
        first = self.snapshot(self.out)
        self.write()  # identical reuse
        self.assertEqual(first, self.snapshot(self.out))
        moved = self.root / "recipient" / "packet"
        shutil.copytree(self.out, moved)
        self.image.rename(self.image.with_suffix(".hidden"))
        manifest = moved / f"{self.sid}.intake-manifest.json"
        content = json.loads(manifest.read_text())
        self.assertEqual(content["image"], f"{self.sid}.source.png")
        self.assertEqual((moved / content["image"]).read_bytes(), original)
        result = I.import_drawing(manifest, self.root / "received-bundle")
        self.assertEqual(result["summary"]["streams_extracted"], len(self.pred["connections"]))
        self.assertEqual((Path(result["output"]) / "source/0.png").read_bytes(), original)

    def test_conflicting_retained_image_refuses_before_report_replacement(self):
        self.write()
        (self.out / f"{self.sid}.source.png").write_bytes(b"another drawing")
        before = self.snapshot(self.out)
        with self.assertRaisesRegex(ValueError, "retained image conflicts"):
            self.write()
        self.assertEqual(before, self.snapshot(self.out))
        self.assertEqual(hashlib.sha256(self.image.read_bytes()).hexdigest(), self.pred["source"]["image_sha256"])

    def test_source_hash_change_and_unsafe_id_refuse_before_output(self):
        changed = copy.deepcopy(self.pred)
        changed["source"]["image_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "changed since prediction"):
            self.write(pred=changed)
        self.assertFalse(self.out.exists())
        for sid in ("../escape", "/absolute", "two/names", "..", " space", "x" * 129):
            with self.subTest(sid=sid), self.assertRaisesRegex(ValueError, "sheet ID"):
                D.retain_intake_image(self.image, self.out, sid, self.pred["source"]["image_sha256"])
        self.assertFalse(self.out.exists())

    def test_nonregular_retained_path_refuses(self):
        self.out.mkdir()
        destination = self.out / f"{self.sid}.source.png"
        destination.mkdir()
        with self.assertRaisesRegex(ValueError, "retained image conflicts"):
            self.write()
    def test_retained_image_link_refuses(self):
        self.out.mkdir()
        destination = self.out / f"{self.sid}.source.png"
        try:
            destination.symlink_to(self.image)
        except OSError as exc:
            self.skipTest(f"OS symlink permission unavailable: {exc}")
        with self.assertRaisesRegex(ValueError, "symbolic link"):
            self.write()
        self.assertEqual(self.image.read_bytes(), png(200, 100))

    def test_generated_output_cannot_replace_original_source(self):
        image = self.source / f"{self.sid}.prediction.json"
        image.write_bytes(self.image.read_bytes())
        before = self.snapshot(self.source)
        with self.assertRaisesRegex(ValueError, "overlaps the source image"):
            D.write_outputs(self.sid, self.pred, self.source, {"license": "test"},
                            {"xml": "T01.xml", "title": "synthetic"}, image)
        self.assertEqual(before, self.snapshot(self.source))
        import dexpi_reader as R
        xml = self.source / f"{self.sid}.model.json"
        xml.write_text('<PlantModel><Equipment ID="P1" ComponentClass="CentrifugalPump"/></PlantModel>')
        before = self.snapshot(self.source)
        with mock.patch.object(R, "prediction", return_value=(self.pred, {})):
            with self.assertRaisesRegex(R.DexpiError, "overlaps a source"):
                R.run(xml, self.source, self.sid, png=self.image, quiet=True)
        self.assertEqual(before, self.snapshot(self.source))

    def test_direct_xml_writer_retains_image_and_refuses_conflict_before_any_report(self):
        import dexpi_reader as R
        xml = self.source / "unit.xml"
        xml.write_text('<PlantModel><Equipment ID="P1" ComponentClass="CentrifugalPump"/></PlantModel>')
        # Isolate writer behavior from geometry; cached-sheet/independent CLIs exercise real prediction conversion.
        with mock.patch.object(R, "prediction", return_value=(self.pred, {})):
            R.run(xml, self.out, self.sid, png=self.image, quiet=True)
            baseline = self.snapshot(self.out)
            self.assertEqual(json.loads((self.out / f"{self.sid}.intake-manifest.json").read_text())["image"],
                             f"{self.sid}.source.png")
            R.run(xml, self.out, self.sid, png=self.image, quiet=True)
            self.assertEqual(baseline, self.snapshot(self.out))
            (self.out / f"{self.sid}.source.png").write_bytes(b"retain conflict")
            before = self.snapshot(self.out)
            with self.assertRaisesRegex(R.DexpiError, "retained image conflicts"):
                R.run(xml, self.out, self.sid, png=self.image, quiet=True)
            self.assertEqual(before, self.snapshot(self.out))
            with self.assertRaisesRegex(R.DexpiError, "sheet ID"):
                R.run(xml, self.root / "new", "../escape", png=self.image, quiet=True)
            self.assertFalse((self.root / "new").exists())


if __name__ == "__main__":
    unittest.main(verbosity=1)
