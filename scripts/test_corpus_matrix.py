"""Fast checks for the generalization matrix (stdlib only; runs no tool and reads no external data).

  - data/corpus.json is well formed: unique ids, required fields, every local path either present or fetchable
    (or committed), candidates and exclusions carry a license or a reason
  - the matrix's row-to-input table names only registered inputs, each of which says it exercises that row
  - docs/GENERALIZATION.md matches out/generalization/matrix.json (corpus_matrix.py --check)
  - a fabricated failing cell shows up in the rendered gaps section, and so does a tool with a single source family
"""
import contextlib
import copy
import io
import json
import tempfile
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import corpus_matrix as cm  # noqa: E402

REQUIRED = ("id", "name", "family", "kind", "source_url", "license", "local_path", "committed", "fetch", "exercises")


class Registry(unittest.TestCase):
    def setUp(self):
        self.corpus = cm.load_corpus()

    def test_inputs_well_formed(self):
        ids = [i["id"] for i in self.corpus["inputs"]]
        self.assertEqual(len(ids), len(set(ids)), "duplicate input ids")
        for i in self.corpus["inputs"]:
            for f in REQUIRED:
                self.assertIn(f, i, f"{i.get('id')}: missing {f}")
            self.assertTrue(i["license"].strip(), i["id"])
            self.assertTrue(i["source_url"].startswith("https://"), i["id"])
            self.assertFalse(Path(i["local_path"]).is_absolute() or ":" in i["local_path"],
                             f"{i['id']}: local_path must be repo-relative")
            self.assertTrue(set(i["exercises"]) <= set(cm.ROWS), i["id"])

    def test_every_path_exists_or_can_be_fetched(self):
        for i in self.corpus["inputs"]:
            present = (ROOT / i["local_path"]).exists()
            if i["committed"]:
                self.assertTrue(present, f"{i['id']} is marked committed but {i['local_path']} is absent")
            else:
                self.assertTrue(present or (i["fetch"] or "").strip(),
                                f"{i['id']}: {i['local_path']} absent and no fetch command")
                self.assertTrue((i["fetch"] or "").startswith("python scripts/"),
                                f"{i['id']}: an uncommitted input needs a repo fetch command")

    def test_candidates_and_exclusions(self):
        for c in self.corpus["candidates"]:
            for f in ("name", "url", "license", "what", "would_exercise"):
                self.assertTrue(str(c.get(f, "")).strip(), f"candidate {c.get('name')}: {f}")
        for x in self.corpus["excluded"]:
            self.assertTrue(x["reason"].strip(), x["name"])

    def test_row_inputs_registered(self):
        inputs = cm.inputs_by_id(self.corpus)
        for row, ids in cm.ROW_INPUTS.items():
            for i in ids:
                self.assertIn(i, inputs, f"row {row} names unregistered input {i}")
                self.assertIn(row, inputs[i]["exercises"], f"{i} does not list row {row} in exercises")

    def test_no_local_absolute_paths_in_outputs(self):
        for p in (cm.CORPUS, cm.OUT_JSON, cm.DOC):
            if p.is_file():
                text = p.read_text(encoding="utf-8")
                for marker in ("C:\\", "C:/", "/Users/", "/home/", "AppData", "\\Temp\\", "/tmp/"):
                    self.assertNotIn(marker, text, f"{p.name} contains a local path ({marker})")


class Rendering(unittest.TestCase):
    def test_changed_dynamic_dependency_invalidates_intake_results(self):
        original_hash = cm.file_hash
        for row, input_id in ((3, "te-rev-a"), (4, "dexpi"), (7, "dexpi")):
            with self.subTest(row=row, input=input_id):
                recorded = {f: original_hash(f) for f in cm.tool_files(row, input_id)}
                matrix = {"cells": [{"row": row, "input": input_id, "tool_files": recorded}]}
                self.assertEqual(cm.stale_cells(matrix), [])
                with patch.object(cm, "file_hash", side_effect=lambda f:
                                  "changed-confidence-code" if f == "scripts/confidence.py" else original_hash(f)):
                    stale = cm.stale_cells(matrix)
                self.assertEqual(len(stale), 1)
                self.assertIn("scripts/confidence.py", stale[0])

    def test_omitted_required_dependency_is_not_a_current_result(self):
        recorded = {f: cm.file_hash(f) for f in cm.tool_files(3, "open100-dev")}
        self.assertIn("scripts/build_twin.py", recorded)
        del recorded["scripts/build_twin.py"]
        stale = cm.stale_cells({"cells": [{"row": 3, "input": "open100-dev", "tool_files": recorded}]})
        self.assertEqual(len(stale), 1)
        self.assertIn("required tool hash missing: scripts/build_twin.py", stale[0])

    def test_check_passes(self):
        self.assertTrue(cm.OUT_JSON.is_file(), "run python scripts/corpus_matrix.py first")
        self.assertEqual(cm.main(["--check"]), 0)

    def test_fabricated_failure_reaches_gaps(self):
        corpus = cm.load_corpus()
        inputs = cm.inputs_by_id(corpus)
        matrix = {"ran_at": "test", "seconds": 0, "cells": [
            cm.cell(1, inputs["open100-dev"], "pass", "F1 0.930"),
            cm.cell(1, inputs["dexpi"], "fail", "F1 0.100", "FABRICATED: the tracer lost every link"),
            cm.cell(6, inputs["te-braatz-runs"], "pass", "21/21 agree"),
            cm.cell(2, inputs["pid2graph-synthetic"], "needs data", reason="needs data: python scripts/fetch_pid2graph.py"),
        ]}
        text = cm.render(matrix, corpus)
        gaps = text.split("## Gaps", 1)[1].split("## Inputs", 1)[0]
        self.assertIn("FABRICATED: the tracer lost every link", gaps)
        self.assertIn("needs data: python scripts/fetch_pid2graph.py", gaps)
        self.assertIn("csv_normal_bands.py", gaps.split("only one source family", 1)[1])
        self.assertIn("FAIL F1 0.100", text.split("## The matrix", 1)[1].split("## By row", 1)[0])

    def test_intro_states_every_criterion_and_the_pronto_one_was_set_after_the_run(self):
        corpus = cm.load_corpus()
        text = cm.render({"ran_at": "test", "seconds": 0, "cells": []}, corpus)
        intro = text.split("## The matrix", 1)[0]
        self.assertNotIn("fixed before the run;", intro)
        self.assertIn("unless the row says otherwise", intro)
        row6 = text.split("### 6.", 1)[1].split("### 7.", 1)[0]
        self.assertIn("pronto-day3", row6)
        self.assertIn("set after the first run had been seen", row6)
        self.assertIn("0.5%", row6)

    def test_self_generated_inputs_flagged_and_counted_as_circular(self):
        corpus = cm.load_corpus()
        inputs = cm.inputs_by_id(corpus)
        matrix = {"ran_at": "test", "seconds": 0, "cells": [
            cm.cell(4, inputs["te-rev-a"], "pass", "matches the published result (0/19 drawn)"),
            cm.cell(4, inputs["bayer-rt1"], "pass", "4/4 loop legs drawn",
                    detail={"legs": [{"controller": "TIC-104", "output": "TV-104A", "status": "drawn"}],
                            "headlines": ["3 of 3 loops drawn, 0 partly drawn, 0 not drawn",
                                          "1 of 1 loops drawn, 0 partly drawn, 0 not drawn"]}),
            cm.cell(4, inputs["dexpi"], "pass", "2/2 loops"),
        ]}
        text = cm.render(matrix, corpus)
        grid = text.split("## The matrix", 1)[1].split("## By row", 1)[0]
        te_line = next(l for l in grid.splitlines() if l.startswith("| `te-rev-a`"))
        self.assertIn(cm.SELF_GENERATED_MARK, te_line)
        dexpi_line = next(l for l in grid.splitlines() if l.startswith("| `dexpi`"))
        self.assertNotIn(cm.SELF_GENERATED_MARK, dexpi_line)
        single = text.split("only one source family", 1)[1].split("###", 1)[0]
        self.assertIn("loop_audit.py", single)  # te-generated + bayer-generated are circular; only dexpi is independent
        self.assertIn("self-generated", single)
        row4 = text.split("### 4.", 1)[1].split("### 5.", 1)[0]
        bayer_line = next(l for l in row4.splitlines() if l.startswith("| `bayer-rt1`"))
        self.assertIn("1 leg", bayer_line)  # bayer-rt1 gets a detail, not an empty cell

    def test_te_loop_cells_read_as_matching_the_published_result(self):
        inputs = cm.inputs_by_id(cm.load_corpus())
        for rev, shown in (("te-rev-a", "0/19 drawn"), ("te-rev-c", "0/19 drawn, 19 partly"),
                           ("te-rev-d", "19/19 drawn")):
            with self.subTest(rev):
                c = cm.row4(inputs[rev])
                self.assertEqual(c["status"], "pass")
                self.assertEqual(c["value"], f"matches the published result ({shown})")

    def test_dexpi_loop_cell_says_combined_and_counts_distinct_tags(self):
        inputs = cm.inputs_by_id(cm.load_corpus())
        if cm.missing_files(inputs["dexpi"]):
            self.skipTest("DEXPI data not cached")
        c = cm.row4(inputs["dexpi"])
        self.assertNotIn("all tags", c["value"])
        self.assertNotIn("refuses", c["reason"])
        self.assertIn("combined", c["value"])
        d = c["detail"]
        self.assertEqual(d["combined_instruments"], 2)
        self.assertEqual(d["distinct_tags_checked"], len(d["tags_checked"]))
        self.assertLess(d["distinct_tags_checked"], 3 * len(d["loops"]))
        self.assertIn(f"{d['distinct_tags_checked']} distinct tags", cm.detail_line(c) + c["value"])

    def test_cells_carry_run_time_and_tool_hash_and_check_flags_stale_cells(self):
        inputs = cm.inputs_by_id(cm.load_corpus())
        c = cm.run_cell(4, inputs["te-rev-d"])
        self.assertRegex(c["ran_at"], r"^\d{4}-\d\d-\d\d \d\d:\d\d UTC$")
        self.assertIn("scripts/loop_audit.py", c["tool_files"])
        self.assertEqual(cm.stale_cells({"cells": [c]}), [])
        old = copy.deepcopy(c)
        old["tool_files"]["scripts/loop_audit.py"] = "sha256:0000000000000000"
        stale = cm.stale_cells({"cells": [old]})
        self.assertEqual(len(stale), 1)
        self.assertIn("scripts/loop_audit.py changed", stale[0])
        legacy = {k: v for k, v in c.items() if k not in ("ran_at", "tool_files")}
        self.assertIn("no tool hash recorded", cm.stale_cells({"cells": [legacy]})[0])
        text = cm.render({"ran_at": "2026-10-29 18:13 UTC", "seconds": 1, "cells": [c, legacy]}, cm.load_corpus())
        header = text.split("## The matrix", 1)[0]
        self.assertIn(f"row 4: {c['ran_at']}", header)
        self.assertNotIn("in total", header)

    def test_check_fails_clearly_on_a_stale_or_unhashed_matrix(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            inputs = cm.inputs_by_id(cm.load_corpus())
            c = cm.run_cell(4, inputs["te-rev-d"])
            c["tool_files"]["scripts/loop_audit.py"] = "sha256:0000000000000000"
            legacy = {k: v for k, v in cm.cell(5, inputs["te-model"], "pass", "13 files").items()}
            matrix = {"ran_at": "t", "seconds": 0, "rows_run_this_time": [4], "cells": [c, legacy]}
            (d / "matrix.json").write_text(json.dumps(matrix), encoding="utf-8")
            (d / "GENERALIZATION.md").write_text(cm.render(matrix, cm.load_corpus()), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = cm.main(["--check", "--out-dir", str(d)])
            self.assertEqual(code, 1)
            self.assertIn("stale", out.getvalue())
            self.assertIn("te-rev-d", out.getvalue())
            self.assertIn("te-model", out.getvalue())
            self.assertIn("python scripts/corpus_matrix.py", out.getvalue())

    def test_not_scored_inputs_are_na_with_their_reason(self):
        inputs = cm.inputs_by_id(cm.load_corpus())
        for i in inputs.values():
            if i["kind"] in cm.NOT_SCORED_KINDS:
                self.assertTrue(i.get("not_scored", "").strip(), i["id"])
                c = cm.run_cell(i["exercises"][0], i)
                self.assertEqual(c["status"], "n/a", i["id"])
                self.assertIn(i["not_scored"][:40], c["reason"])

    def test_every_new_input_has_attribution_and_realness(self):
        for i in cm.load_corpus()["inputs"]:
            if i["id"] in cm.DEXPI_READER_INPUTS or i["kind"] in cm.NOT_SCORED_KINDS + (cm.AGENT_KIND,) or i["id"] in (
                    "skab", "hai-21.03", "pronto-day2", "pronto-day4", "idaes-hda", "dwsim-fossee",
                    *cm.HELDOUT_HISTORIAN):
                self.assertTrue(i.get("attribution"), i["id"])
                self.assertIn("real", i, i["id"])
        skab = cm.inputs_by_id(cm.load_corpus())["skab"]
        self.assertIn("GPL-3.0", skab["license"])
        self.assertIn("never vendored", skab["license"])

    def test_inputs_option_keeps_every_other_cell_untouched(self):
        inputs = cm.inputs_by_id(cm.load_corpus())
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            keep = cm.cell(4, inputs["te-rev-d"], "pass", "KEEP ME")
            keep.update(ran_at="2000-01-01 00:00 UTC", tool_files={"scripts/loop_audit.py": "sha256:x"})
            other = cm.cell(1, inputs["open100-dev"], "pass", "F1 0.9")
            matrix = {"ran_at": "t", "seconds": 0, "rows_run_this_time": [4], "cells": [keep, other]}
            (d / "matrix.json").write_text(json.dumps(matrix), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cm.main(["--rows", "4", "--inputs", "omre-1958-pid", "--out-dir", str(d)]), 0)
            out = json.loads((d / "matrix.json").read_text(encoding="utf-8"))
            got = {(c["row"], c["input"]): c for c in out["cells"]}
            self.assertEqual(got[(4, "te-rev-d")], keep)
            self.assertEqual(got[(1, "open100-dev")], other)
            self.assertEqual(got[(4, "omre-1958-pid")]["status"], "n/a")
            self.assertEqual(out["inputs_run_this_time"], ["omre-1958-pid"])


    def test_readme_fault6_check_reads_the_statement_for_the_method_run(self):
        text = (ROOT / cm.HISTORIAN_README).read_text(encoding="utf-8")
        for method in ("drift", "level"):
            with self.subTest(method):
                says = cm.readme_fault6_check(method, {"delay_min": -1, "false_alarm_samples_before_fault": -1})
                self.assertIsNotNone(says["line"], says)
                self.assertFalse(says["agrees"])  # an impossible run never agrees
                self.assertIn(f"({method})", says["says"])
                delay = float(says["says"].split("detection at ", 1)[1].split(" minutes")[0])
                pre = int(says["says"].split("minutes, ", 1)[1].split(" of")[0])
                ok = cm.readme_fault6_check(method, {"delay_min": delay, "false_alarm_samples_before_fault": pre})
                self.assertTrue(ok["agrees"])
                self.assertIn("3-consecutive", "\n".join(text.splitlines()[says["line"] - 1:says["line"] + 2]))
        drift = cm.readme_fault6_check("drift", {"delay_min": 0, "false_alarm_samples_before_fault": 0})
        self.assertNotIn("at 0 minutes", drift["says"])  # the README states a later delay for drift than for level
        self.assertFalse(cm.readme_fault6_check("nosuch", {"delay_min": 0, "false_alarm_samples_before_fault": 0})
                         ["agrees"])

    def test_agent_keyed_cells_labelled_and_kept_apart(self):
        corpus = cm.load_corpus()
        inputs = cm.inputs_by_id(corpus)
        for i in cm.AGENT_KEYED:
            self.assertEqual(inputs[i]["kind"], cm.AGENT_KIND)
            self.assertTrue((ROOT / inputs[i]["local_path"] / "key_meta.json").is_file(), i)
            self.assertEqual(set(inputs[i]["stage"]), set(inputs[i]["sheets"]), i)
            for r in (1, 2, 3, 8):
                self.assertIn(i, cm.ROW_INPUTS[r])
        ag = cm.cell(1, inputs["pronto-fig1"], "pass", "F1 0.950")
        ag["key"] = "agent-made"
        ag["detail"]["key"] = {"not_independent": {"X1": "a second scan"}}
        matrix = {"ran_at": "test", "seconds": 0, "cells": [cm.cell(1, inputs["open100-dev"], "pass", "F1 0.930"), ag]}
        text = cm.render(matrix, corpus)
        grid = text.split("## The matrix", 1)[1].split("## By row", 1)[0]
        line = next(l for l in grid.splitlines() if l.startswith("| `pronto-fig1`"))
        self.assertIn(cm.AGENT_KEY_MARK, line)
        human = next(l for l in grid.splitlines() if l.startswith("| `open100-dev`"))
        self.assertNotIn(cm.AGENT_KEY_MARK, human)
        row1 = text.split("### 1.", 1)[1].split("### 2.", 1)[0]
        by_row = next(l for l in row1.splitlines() if l.startswith("| `pronto-fig1` |"))
        self.assertIn(cm.AGENT_KEY_LABEL, by_row)
        self.assertIn("X1: a second scan", by_row)
        single = text.split("only one source family", 1)[1].split("###", 1)[0]
        self.assertIn("agent-keyed: pronto", single)  # not counted as a second independent family

    def test_agent_keyed_row4_is_na_without_any_data(self):
        inputs = cm.inputs_by_id(cm.load_corpus())
        for i in ("omre-1958-pid", "pronto-fig1"):
            c = cm.run_cell(4, inputs[i])
            self.assertEqual(c["status"], "n/a", i)
            self.assertIn(inputs[i]["row4_na"][:40], c["reason"])
            self.assertNotIn("key", c)

    def test_agent_key_staging_matches_the_key_frame(self):
        inputs = cm.inputs_by_id(cm.load_corpus())
        try:
            import PIL  # noqa: F401
            import fitz  # noqa: F401
        except ImportError:
            self.skipTest("Pillow / PyMuPDF not installed")
        import score_pid2graph as sc
        for i in cm.AGENT_KEYED:
            inp = inputs[i]
            if cm.missing_files(inp):
                continue
            meta = json.loads((ROOT / inp["local_path"] / "key_meta.json").read_text(encoding="utf-8"))["sheets"]
            with tempfile.TemporaryDirectory() as d:
                notes = cm.stage_agent_sheets(inp, d)
                for s in inp["sheets"]:
                    self.assertEqual(list(sc.png_size(Path(d) / f"{s}.png")), list(meta[s]["size_px"]), s)
                    self.assertTrue((Path(d) / f"{s}.graphml").is_file())
            self.assertEqual(set(notes), set(inp["sheets"]))

    def test_heldout_historian_sources_registered_with_fetch(self):
        import fetch_corpus as fc
        inputs = cm.inputs_by_id(cm.load_corpus())
        for i in cm.HELDOUT_HISTORIAN:
            inp = inputs[i]
            self.assertEqual(inp["exercises"], [6])
            self.assertIn("CC BY 4.0", inp["license"])
            self.assertTrue(inp.get("cyclic"), i)
            self.assertIn(i, fc.FILE_SOURCES)
            self.assertEqual(inp["fetch"], f"python scripts/fetch_corpus.py {i}")
            self.assertIn("scripts/historian_adapters.py", cm.tool_files(6, i))
        row6 = cm.render({"ran_at": "t", "seconds": 0, "cells": []}, cm.load_corpus()).split("### 6.", 1)[1]
        self.assertIn("held out", row6.split("### 7.", 1)[0])
        self.assertIn("--method drift", row6.split("### 7.", 1)[0])

    def test_vendor_renders_wired_held_out_to_rows_1_and_8(self):
        inp = cm.inputs_by_id(cm.load_corpus())[cm.VENDOR]
        self.assertEqual(inp["kind"], "keyed-sheets")
        self.assertNotIn("not_scored", inp)
        self.assertEqual(cm.PIPE_SETS[cm.VENDOR], "dexpi-1.2-vendor")
        for r in (1, 8):
            files = cm.tool_files(r, cm.VENDOR)
            for f in ("scripts/corpus_adapters.py", "scripts/adapt_dexpi.py", "scripts/line_layers.py",
                      "scripts/trace_connections.py", "scripts/score_pid2graph.py"):
                self.assertIn(f, files)
        text = cm.render({"ran_at": "t", "seconds": 0, "cells": []}, cm.load_corpus())
        row8 = text.split("### 8.", 1)[1].split("## Gaps", 1)[0]
        self.assertNotIn("n/a until each render has a key", row8)
        self.assertIn("A174", row8)
        self.assertIn("partly blind", row8)

    def test_row7_second_reading_is_reported_beside_the_primary(self):
        inputs = cm.inputs_by_id(cm.load_corpus())
        inp = inputs["dexpi-1.2-autocad"]
        files = [f for f in cm.dexpi_selection(inp) if f["file"] == "I05V01_AUD.EX01.xml"] if not cm.missing_files(
            inp) else []
        if not files:
            self.skipTest("DEXPI TrainingTestCases not cached")
        with tempfile.TemporaryDirectory() as d:
            rec = cm.reader_file_check(files[0], d)[0]
        self.assertEqual(rec["status"], "fail")  # primary result unchanged by the second reading
        self.assertIn("second_reading", rec)
        self.assertIn("I05V01_AUD.EX01.xml", cm.TRUTH_LIMITS_7)
        row7 = cm.render({"ran_at": "t", "seconds": 0, "cells": []}, cm.load_corpus()).split("### 7.", 1)[1]
        self.assertIn("Second reading, set after the results were seen", row7.split("### 8.", 1)[0])
        self.assertIn("IEC-?", row7.split("### 8.", 1)[0])

    def test_honest_labelling_notes_leave_verdicts_alone(self):
        inp = {"id": "fake-historian", "family": "fake"}
        run = {"method": "drift", "k": 20, "pre_fault_flagged": 0, "pre_fault_rows": 100, "detected": True,
               "pre_fault_tags": [], "overlap_detection_only": False, "pass": True}
        c = cm.band_cell(inp, {"a": dict(run, k_target_met=False), "b": dict(run, k_target_met=True)}, "fit")
        self.assertEqual(c["status"], "pass")  # the K note never changes the verdict
        self.assertIn("K target not met 1/2", c["value"])
        self.assertIn("`k_target_met` is false on 1 of 2 runs (a)", c["note"])
        self.assertNotIn("note", cm.band_cell(inp, {"b": dict(run, k_target_met=True)}, "fit"))
        scan = cm.cell(2, {"id": "open100-scan-L1", "family": "open100"}, "pass", "wrong max 0.033")
        scan["key_only_duplicate_of"] = "open100-holdout"
        cm.add_note(scan, cm.KEY_ONLY_SCAN_NOTE)
        page = cm.render({"ran_at": "t", "seconds": 0, "cells": [scan]}, cm.load_corpus())
        self.assertIn("**note:** key-only input", page)
        self.assertIn("1 of the passes (rows 2 on the `open100-scan-L*` inputs) repeat `open100-holdout`", page)
        if cm.OUT_JSON.is_file():  # the committed scan cells say so and really repeat the holdout cell
            by = {(c["row"], c["input"]): c for c in json.loads(cm.OUT_JSON.read_text(encoding="utf-8"))["cells"]}
            for (r, i), twin in cm.KEY_ONLY_SCAN_CELLS.items():
                if (r, i) in by and by[(r, i)]["status"] == "pass":
                    self.assertEqual(by[(r, i)].get("key_only_duplicate_of"), twin)
                    self.assertEqual(by[(r, i)]["value"], by[(r, twin)]["value"])

    def test_check_detects_drift(self):
        if not cm.OUT_JSON.is_file():
            self.skipTest("no matrix.json")
        matrix = json.loads(cm.OUT_JSON.read_text(encoding="utf-8"))
        changed = copy.deepcopy(matrix)
        changed["cells"][0]["value"] = "tampered"
        self.assertNotEqual(cm.render(matrix, cm.load_corpus()), cm.render(changed, cm.load_corpus()))


class Adapters(unittest.TestCase):
    """corpus_adapters.py on tiny synthetic inputs (no downloaded data)."""

    def test_dexpi_truth_and_loop_list(self):
        import xml.etree.ElementTree as ET
        import corpus_adapters as ca
        ga = lambda n, v: f'<GenericAttribute Name="ProcessInstrumentationFunction{n}AssignmentClass" Value="{v}"/>'
        xml = ('<PlantModel><PlantInformation OriginatingSystem="X"/>'
               '<Equipment ID="E1"><Equipment ID="E1a"/></Equipment>'
               '<ActuatingSystem ID="AS1"><GenericAttributes><GenericAttribute '
               'Name="ActuatingSystemNumberAssignmentClass" Value="FV 7"/></GenericAttributes></ActuatingSystem>'
               '<InstrumentationLoopFunction ID="L1"><Association Type="is a collection including" ItemID="P1"/>'
               '<Association Type="is a collection including" ItemID="P2"/></InstrumentationLoopFunction>'
               f'<ProcessInstrumentationFunction ID="P1"><GenericAttributes>{ga("Category", "F")}{ga("s", "IC")}'
               f'{ga("Number", "7")}</GenericAttributes><ActuatingFunction ID="AF1">'
               '<Association Type="is fulfilled by" ItemID="AS1"/></ActuatingFunction></ProcessInstrumentationFunction>'
               f'<ProcessInstrumentationFunction ID="P2"><GenericAttributes>{ga("Category", "F")}{ga("s", "T")}'
               f'{ga("Number", "7")}</GenericAttributes></ProcessInstrumentationFunction></PlantModel>')
        root = ET.fromstring(xml)
        t = ca.dexpi_truth(root)
        self.assertEqual((t["equipment"], t["instrument_functions"], t["control_functions"], t["loops"]), (1, 2, 1, 1))
        loops, incomplete = ca.dexpi_loop_list(root)
        self.assertEqual(loops, [["FIC 7", "FT 7", "FV 7", "loop function L1"]])
        self.assertEqual(incomplete, [])
        self.assertTrue(ca.refusal_confirmed("element IDs used more than once (X)", dict(t, duplicate_ids=["X"])))
        self.assertFalse(ca.refusal_confirmed("element IDs used more than once (X)", t))

    def test_skab_conversion_drops_labels_and_finds_the_fault(self):
        import corpus_adapters as ca
        with tempfile.TemporaryDirectory() as d:
            src, dest = Path(d) / "r.csv", Path(d) / "o.csv"
            src.write_text("datetime;A;B;anomaly;changepoint\n2020-01-01 00:00:00;1;2;0.0;0.0\n"
                           "2020-01-01 00:00:01;1;2;0.0;1.0\n2020-01-01 00:00:02;5;2;1.0;0.0\n", encoding="utf-8")
            info = ca.skab_to_csv(src, dest)
            self.assertEqual(info, {"rows": 3, "fault_start_row": 2, "first_changepoint_row": 1})
            self.assertEqual(dest.read_text(encoding="utf-8").splitlines()[0], "datetime,A,B")

    def test_idaes_model_boundary_and_balance(self):
        import corpus_adapters as ca
        fs = {"model": {"id": "T", "unit_models": {"F1": {"type": "feed"}, "M1": {"type": "mixer"},
                                                   "P1": {"type": "product"}},
                        "arcs": {"s1": {"source": "F1", "dest": "M1"}, "s2": {"source": "M1", "dest": "P1"}},
                        "stream_table": {"columns": ["Variable", "Units", "s1", "s2"],
                                         "data": [["flow_mol x", {"raw": "mol/s"}, [1.0, "fixed"], [1.0, "unfixed"]]]}}}
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "f.json"
            p.write_text(json.dumps(fs), encoding="utf-8")
            model, summary = ca.idaes_model(p)
        self.assertEqual([u["id"] for u in model["units"]], ["M1"])
        self.assertEqual([(s["from"], s["to"]) for s in model["streams"]], [("BL", "M1"), ("M1", "BL")])
        self.assertEqual(summary["mixer_balance"], {"M1": 0.0})


if __name__ == "__main__":
    unittest.main()
