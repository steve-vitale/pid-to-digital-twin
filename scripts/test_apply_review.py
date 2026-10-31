"""Controls for the review loop (scripts/apply_review.py and the generators), on temp copies of the committed models.

The loop is only trustworthy if bad sheets are refused, alarm requests that need a change review are not applied,
re-applying changes nothing, the regenerated sheet round-trips, and the decisions reach the platform outputs.
"""
import csv
import copy
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import generate  # noqa: E402
import apply_review  # noqa: E402

TWIN_ID = generate.TWIN_REVIEW_COLS.index("item_id")
TWIN_WHY = generate.TWIN_REVIEW_COLS.index("why_check_this")

results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}{'' if ok else ': ' + str(detail)}")


def run(model, rows, cols, tmp, extra=()):
    sheet = tmp / "sheet.csv"
    with sheet.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})
    p = subprocess.run([sys.executable, str(ROOT / "scripts" / "apply_review.py"), str(model), str(sheet),
                        "--reviewer", "Test reviewer", "--date", "2026-10-08", "--record-dir", str(tmp / "rec"),
                        *extra], capture_output=True, text=True, encoding="utf-8",
                       # This test reads the child's output as UTF-8, so it asks for UTF-8: a piped Windows child
                       # otherwise writes the ANSI code page and the read fails on the first non-ASCII character.
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    chosen = re.search(r"^Record: (.+)$", p.stdout, re.M)
    rec = tmp / "rec" / (chosen.group(1) if chosen else "no-record.json")
    return p, (json.loads(rec.read_text(encoding="utf-8")) if rec.exists() else None)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="review-test-"))
    try:
        # ---- Tennessee Eastman
        te = tmp / "te_process_model.json"
        shutil.copy(ROOT / "data" / "te_process_model.json", te)
        before = te.read_text(encoding="utf-8")
        cols = generate.REVIEW_COLS
        rows = [
            {"item_id": "FT-101", "OPS_confirm_or_correct": "confirm", "OPS_show_on_operator_screen_Y_N": "Y"},
            {"item_id": "TT-122", "OPS_confirm_or_correct": "correct",
             "OPS_correct_value": "description=Separator cooling water outlet temperature", "OPS_notes": "per teprob.f"},
            {"item_id": "PT-107", "OPS_alarm_priority_H_M_L_none": "none"},     # remove a published alarm: MOC
            {"item_id": "FT-102", "OPS_alarm_priority_H_M_L_none": "H"},        # new alarm, no setpoint: MOC
            {"item_id": "TT-109", "OPS_alarm_priority_H_M_L_none": "M"},        # priority of a published alarm: applied
            {"item_id": "XX-999", "OPS_confirm_or_correct": "confirm"},         # no such item
            {"item_id": "LT-108", "OPS_confirm_or_correct": "correct"},         # correct without a value
            {"item_id": "LT-112", "OPS_confirm_or_correct": "correct", "OPS_correct_value": "colour=red"},  # bad field
            {"item_id": "LT-115", "OPS_confirm_or_correct": "maybe"},           # bad decision
            {"item_id": "FT-104", "OPS_confirm_or_correct": "correct", "OPS_correct_value": "tag="},  # empty value
        ]
        p, rec = run(te, rows, cols, tmp)
        check("bad rows make the run exit non-zero", p.returncode == 1, p.returncode)
        check("5 refusals (unknown item, missing value, bad field, bad decision, empty value)",
              rec and len(rec["refused"]) == 5, rec and rec["refused"])
        check("an empty correction value is refused, never applied as a blank",
              rec and any(r["item"] == "FT-104" and "has no value" in r["reason"] for r in rec["refused"]),
              rec and rec["refused"])
        check("5 decisions applied", rec and len(rec["applied"]) == 5, rec and [a["item"] for a in rec["applied"]])
        moc = {m["item"]: m["request"] for m in (rec or {}).get("needs_moc", [])}
        check("removing PT-107's published alarm is flagged for a change review", moc.get("PT-107") == "remove alarm", moc)
        check("FT-102's unknown alarm basis is flagged without inferring installed absence",
              moc.get("FT-102", "").startswith("verify"), moc)
        check("TT-109 priority change (published alarm) is not flagged", "TT-109" not in moc, moc)
        m = json.loads(te.read_text(encoding="utf-8"))
        ti = next(i for i in m["instruments"] if i["tag"] == "TT-122")
        check("correction applied, old value kept in history",
              ti["description"] == "Separator cooling water outlet temperature"
              and ti["ops_review"]["history"][-1]["changes"]["description"][0] != ti["description"], ti.get("ops_review"))
        check("source verification untouched", ti["verification"]["status"] in ("confirmed", "corrected"))
        import difflib
        diff = [d for d in difflib.unified_diff(before.splitlines(), te.read_text(encoding="utf-8").splitlines(), n=0)
                if d.startswith("-") and not d.startswith("---")]
        after = set(te.read_text(encoding="utf-8").splitlines())
        # Removed lines: the corrected one, plus lines that only gained a trailing comma before an inserted block.
        real = [d for d in diff if d[1:] + "," not in after]
        check("file format preserved (only the corrected line really changes; the rest is additions)",
              len(real) == 1 and "description" in real[0], real[:5])

        # Re-apply the good rows: nothing changes.
        good = [r for r in rows if r["item_id"] in ("FT-101", "TT-122", "PT-107", "FT-102", "TT-109")]
        p, rec = run(te, good, cols, tmp)
        check("re-applying the same decisions changes nothing", rec and not rec["applied"] and rec["unchanged"] == 5,
              rec and rec["applied"])

        # Round trip: the regenerated sheet prints the decisions back; applying it changes nothing.
        regen = [dict(zip(cols, r)) for r in generate.review_rows(m)]
        r101 = next(r for r in regen if r["item_id"] == "FT-101")
        check("regenerated sheet is pre-filled", r101["OPS_confirm_or_correct"] == "confirm"
              and r101["OPS_show_on_operator_screen_Y_N"] == "Y", r101)
        p, rec = run(te, regen, cols, tmp)
        check("applying the regenerated sheet changes nothing", rec and not rec["applied"] and not rec["refused"],
              rec and (rec["applied"][:2], rec["refused"][:2]))

        # ---- Extracted twin
        tw_dir = tmp / "twin"
        tw_dir.mkdir()
        tw = tw_dir / "plant_model.json"
        shutil.copy(ROOT / "out" / "twin" / "r2-tiles-trace" / "codex" / "plant_model.json", tw)
        tm = json.loads(tw.read_text(encoding="utf-8"))
        # A clarification is a scoped notes-only review, never whole-record confirmation.
        original = copy.deepcopy(tm)
        pair = {"S0-IN002", "S0-IN003"}
        for x in tm["instruments"]:
            if x["id"] in pair:
                x.pop("ops_review", None)
        unreviewed = copy.deepcopy(tm)
        note_rows = [{"item_id": i, "OPS_notes": "NEEDS CLARIFICATION: retain both; signal unresolved"}
                     for i in sorted(pair)]
        log = apply_review.apply(tm, note_rows, "Test reviewer", "2026-10-10", apply_review.index(tm))
        check("clarification applies no corrections or MOC", len(log["applied"]) == 2
              and not log["refused"] and not log["needs_moc"]
              and all(not x["changes"] for x in log["applied"]))
        stripped = copy.deepcopy(tm)
        for x in stripped["instruments"]:
            if x["id"] in pair:
                check("clarification retains unverified unmapped symbol " + x["id"],
                      x["verification"]["status"] == x["ops_review"]["status"] == "unverified"
                      and "data_point" not in x)
                x.pop("ops_review")
        check("clarification changes only review metadata", stripped == unreviewed)
        regen = [dict(zip(generate.TWIN_REVIEW_COLS, r)) for r in generate.twin_review_rows(tm)]
        flagged = [r for r in regen if r["item_id"] in pair]
        check("clarification visible in queue without new status", len(flagged) == 2
              and all(r["why_check_this"].startswith("NEEDS CLARIFICATION:")
                      and r["model_status"] == "unverified" and not r["OPS_confirm_or_correct"] for r in flagged))
        log = apply_review.apply(tm, flagged, "Test reviewer", "2026-10-10", apply_review.index(tm))
        check("clarification round trip idempotent", log["unchanged"] == 2 and not log["applied"])
        # Identifier-only review never confirms inferred semantics or assigns a signal.
        scoped = copy.deepcopy(original)
        target = next(x for x in scoped["instruments"] if x["id"] == "S0-IN019")
        target.update(tag="MS 4010", description="MS 4010", loop="4010")
        target.pop("ops_review", None)
        apply_review.sync_hierarchy_tag(scoped.get("hierarchy"), "S0-IN019", "MS 4010")
        before_identifier = copy.deepcopy(scoped)
        row = {"item_id": "S0-IN019", "OPS_confirm_or_correct": "correct",
               "OPS_correct_value": "tag=MS 14010", "OPS_scope": "identifier_text", "OPS_notes": "Text only"}
        log = apply_review.apply(scoped, [row], "Test reviewer", "2026-10-10", apply_review.index(scoped))
        check("identifier correction synchronizes tag, mirrored description and loop", not log["refused"]
              and (target["tag"], target["description"], target["loop"]) == ("MS 14010", "MS 14010", "14010"))
        check("identifier review remains record-unverified with field-scoped history",
              target["ops_review"]["status"] == target["verification"]["status"] == "unverified"
              and target["ops_review"]["history"][-1]["scope"] == "identifier_text"
              and set(target["ops_review"]["field_decisions"]) == {"tag", "description", "loop"})
        stripped = copy.deepcopy(scoped)
        x = next(x for x in stripped["instruments"] if x["id"] == "S0-IN019")
        x.update(tag="MS 4010", description="MS 4010", loop="4010")
        x.pop("ops_review")
        apply_review.sync_hierarchy_tag(stripped.get("hierarchy"), "S0-IN019", "MS 4010")
        check("identifier review preserves every other field and record", stripped == before_identifier)
        log = apply_review.apply(scoped, [row], "Test reviewer", "2026-10-10", apply_review.index(scoped))
        check("identifier correction repeat is idempotent", log["unchanged"] == 1 and not log["applied"])
        regen = [dict(zip(generate.TWIN_REVIEW_COLS, r)) for r in generate.twin_review_rows(scoped)]
        r = next(r for r in regen if r["item_id"] == "S0-IN019")
        check("identifier queue does not turn narrow correction into confirmation", not r["OPS_confirm_or_correct"]
              and r["model_status"] == "unverified")
        log = apply_review.apply(scoped, [r], "Test reviewer", "2026-10-10", apply_review.index(scoped))
        check("identifier regenerated queue round trip preserves field decisions", log["unchanged"] == 1
              and not log["applied"] and set(target["ops_review"]["field_decisions"]) == {"tag", "description", "loop"})
        for correction in ("tag=TT 14010", "tag=MS 14010;variable=temperature", "tag=MS 14010;description=Switch", "tag=unknown"):
            test_model = copy.deepcopy(before_identifier)
            log = apply_review.apply(test_model, [{**row, "OPS_correct_value": correction}], "Test reviewer",
                                     "2026-10-10", apply_review.index(test_model))
            check("identifier scope refuses semantic expansion: " + correction,
                  len(log["refused"]) == 1 and test_model == before_identifier)
        mismatch = copy.deepcopy(before_identifier)
        next(x for x in mismatch["instruments"] if x["id"] == "S0-IN019")["loop"] = "999"
        log = apply_review.apply(mismatch, [row], "Test reviewer", "2026-10-10", apply_review.index(mismatch))
        check("identifier scope refuses mismatched derived loop", len(log["refused"]) == 1 and not log["applied"])
        # Valve interpretation is a reviewed association, not a second physical valve.
        valve_model = copy.deepcopy(original)
        vt = next(x for x in valve_model["instruments"] if x["id"] == "S0-IN019")
        vt.update(variable="moisture", variable_method="ISA-5.1 first letter", instrument_kind="measurement / control")
        vt.pop("reviewed_valve_association", None)
        valve_before = copy.deepcopy(valve_model)
        vr = {"item_id": "S0-IN019", "OPS_confirm_or_correct": "correct", "OPS_scope": "valve_association",
              "OPS_correct_value": "parent=S0-VL013;variable=unknown", "OPS_notes": "Valve; legend pending"}
        log = apply_review.apply(valve_model, [vr], "Test reviewer", "2026-10-10", apply_review.index(valve_model))
        check("valve association scoped without whole-record approval", not log["refused"]
              and vt["variable"] == "unknown" and vt["instrument_kind"] == "valve callout"
              and vt["reviewed_valve_association"] == "S0-VL013"
              and vt["verification"]["status"] == vt["ops_review"]["status"] == "unverified")
        restored = copy.deepcopy(valve_model)
        rt = next(x for x in restored["instruments"] if x["id"] == "S0-IN019")
        bt = next(x for x in valve_before["instruments"] if x["id"] == "S0-IN019")
        for k in ("variable", "variable_method", "instrument_kind", "ops_review"):
            rt[k] = copy.deepcopy(bt[k])
        rt.pop("reviewed_valve_association")
        check("valve review preserves all other fields, records and source geometry", restored == valve_before)
        log = apply_review.apply(valve_model, [vr], "Test reviewer", "2026-10-10", apply_review.index(valve_model))
        check("valve review idempotent", log["unchanged"] == 1 and not log["applied"])
        regen = [dict(zip(generate.TWIN_REVIEW_COLS, r)) for r in generate.twin_review_rows(valve_model)]
        rr = next(r for r in regen if r["item_id"] == "S0-IN019")
        log = apply_review.apply(valve_model, [rr], "Test reviewer", "2026-10-10", apply_review.index(valve_model))
        check("valve queue is metadata-only and round-trips unverified", not rr["OPS_confirm_or_correct"]
              and "valve callout" in str(rr) and log["unchanged"] == 1)
        tags = generate.twin_ignition(valve_model)
        flat = []
        def walk(n):
            flat.append(n)
            for c in n.get("tags", []): walk(c)
        walk(tags)
        vi = next(n for n in flat if n.get("parameters", {}).get("AssetId", {}).get("value") == "S0-IN019")
        typ = next(n for n in flat if n.get("tagType") == "UdtType" and n["name"] == vi["typeId"])
        check("valve Ignition export has no PV or point parameters", vi["typeId"] == "Callout_Valve"
              and not any(t["name"] == "PV" for t in typ["tags"])
              and not {"PointName", "BasePath", "OPCServer"}.intersection(vi["parameters"]))
        pi = next(r for r in generate.twin_pi_rows(valve_model) if "S0-IN019 |" in r[4])
        check("valve PI export has no PI point reference", pi[6] == "String" and not pi[8] and not pi[9])
        for correction in ("parent=S0-VL012;variable=unknown", "parent=S0-IN002;variable=unknown",
                           "parent=S0-VL013;variable=temperature", "parent=S0-VL013;variable=unknown;class=valve"):
            bad = copy.deepcopy(valve_before)
            log = apply_review.apply(bad, [{**vr, "OPS_correct_value": correction}], "Test", "2026-10-10", apply_review.index(bad))
            check("valve scope refuses wider interpretation: " + correction, bool(log["refused"]) and bad == valve_before)
        mapped = copy.deepcopy(valve_before)
        next(x for x in mapped["instruments"] if x["id"] == "S0-IN019")["data_point"] = {"point": "existing"}
        log = apply_review.apply(mapped, [vr], "Test", "2026-10-10", apply_review.index(mapped))
        check("valve scope refuses mapped record", bool(log["refused"]) and not log["applied"])
        # Matching by either tag or explicit asset ID cannot invent a callout signal.
        import map_points
        from unittest.mock import patch
        import contextlib
        import io
        mapping_model = tmp / "valve-model.json"
        mapping_model.write_text(json.dumps(valve_model))
        io_file = tmp / "valve-io.csv"
        for pin in ("", "S0-IN019"):
            io_file.write_text("tag,server,base_path,point,asset_id\nMS 14010,test,test,test," + pin + "\n")
            output = io.StringIO()
            with patch.object(map_points, "ROOT", tmp), patch.object(sys, "argv", ["map_points", str(mapping_model), str(io_file), "--dry-run"]), contextlib.redirect_stdout(output):
                map_points.main()
            check("callout mapping blocked " + ("by ID" if pin else "by tag"), "Mapped: 0" in output.getvalue()
                  and "signal requires separate review" in output.getvalue()
                  and json.loads(mapping_model.read_text()) == valve_model)
        tm = original
        inst = tm["instruments"][0]["id"]
        unit = next(u for u in tm["units"] if any(x["unit"] == u["id"] for x in tm["instruments"]))
        child = next(x for x in tm["instruments"] if x["unit"] == unit["id"] and x["id"] != inst)
        conf = tm["instruments"][-1]["id"]
        rows = [{"item_id": inst, "OPS_confirm_or_correct": "reject", "OPS_notes": "not a real instrument"},
                {"item_id": unit["id"], "OPS_confirm_or_correct": "reject"},
                {"item_id": conf, "OPS_confirm_or_correct": "correct", "OPS_correct_value": "TT-9999"}]
        p, rec = run(tw, rows, generate.TWIN_REVIEW_COLS, tmp)
        check("twin: 3 decisions applied", rec and len(rec["applied"]) == 3, p.stdout[-500:])
        tm = json.loads(tw.read_text(encoding="utf-8"))
        tags = json.dumps(generate.twin_ignition(tm))
        check("rejected instrument left out of the Ignition tags", f'"value": "{inst}"' not in tags)
        check("rejected equipment left out; its instruments move to _Unassigned",
              f'"value": "{unit["id"]}"' not in tags and f'"value": "{child["id"]}"' in tags)
        corrected = next(x for x in tm["instruments"] if x["id"] == conf)
        check("bare value corrects the tag", corrected["tag"] == "TT-9999", corrected["tag"])
        check("ReviewStatus override carries the decision", '"value": "corrected"' in tags)
        pi = json.dumps(generate.twin_pi_rows(tm))
        check("rejected instrument left out of the PI AF sheet", inst not in pi or f'{inst} |' not in pi)

        # A corrected placeholder tag is no longer a placeholder: the queue must not call the new tag one.
        ph = next(x for g in ("units", "instruments", "line_items") for x in tm[g] if x["tag_status"] == "placeholder")
        p, rec = run(tw, [{"item_id": ph["id"], "OPS_confirm_or_correct": "correct", "OPS_correct_value": "XV-4242"}],
                     generate.TWIN_REVIEW_COLS, tmp)
        tm = json.loads(tw.read_text(encoding="utf-8"))
        fixed = next(x for g in ("units", "instruments", "line_items") for x in tm[g] if x["id"] == ph["id"])
        row = next(r for r in generate.twin_review_rows(tm) if r[TWIN_ID] == ph["id"])
        check("a corrected placeholder tag is marked reviewed, with the old status in the history",
              fixed["tag"] == "XV-4242" and fixed["tag_status"] == "reviewed"
              and fixed["ops_review"]["history"][-1]["changes"].get("tag_status") == ["placeholder", "reviewed"],
              (fixed.get("tag_status"), fixed.get("ops_review")))
        check("the regenerated queue no longer calls the corrected tag a placeholder",
              "placeholder" not in row[TWIN_WHY], row[TWIN_WHY])
        md = next((tmp / "rec").glob("2026-10-08-twin.md")).read_bytes()
        check("the change record is written with LF line endings on every OS", b"\r\n" not in md)

        # Files that can't be read are refused in plain words, not with a traceback.
        def cli(*args):
            return subprocess.run([sys.executable, str(ROOT / "scripts" / "apply_review.py"), *map(str, args),
                                   "--reviewer", "T", "--record-dir", str(tmp / "rec2")], capture_output=True,
                                  text=True, encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        header_only = tmp / "header.csv"
        header_only.write_text(",".join(generate.TWIN_REVIEW_COLS) + "\n", encoding="utf-8")
        p = cli(tw, header_only)
        check("a header-only sheet is said to have no rows, not no item_id column",
              p.returncode != 0 and "has no rows" in p.stderr and "no item_id column" not in p.stderr, p.stderr)
        for args, missing in (((tmp / "nope.json", header_only), "nope.json"), ((tw, tmp / "nope.csv"), "nope.csv")):
            p = cli(*args)
            check(f"a missing {missing} is refused without a traceback",
                  p.returncode == 2 and missing in p.stderr and "Traceback" not in p.stderr, p.stderr[-300:])
        for role in ('model', 'sheet'):
            for extension in ('md', 'json'):
                guard = tmp / f'publication-{role}-{extension}'
                guard.mkdir()
                model, sheet, recs = guard / 'model.json', guard / 'review.csv', guard / 'receipts'
                model.write_bytes((ROOT / 'data/te_process_model.json').read_bytes())
                sheet.write_text('item_id,OPS_confirm_or_correct\nFT-101,confirm\n', encoding='utf-8')
                recs.mkdir()
                target = recs / f'2026-10-30-model.{extension}'
                target.hardlink_to(model if role == 'model' else sheet)
                before = {p: p.read_bytes() for p in guard.rglob('*') if p.is_file()}
                p = subprocess.run([sys.executable, str(ROOT / 'scripts/apply_review.py'), str(model), str(sheet),
                    '--reviewer', 'test', '--date', '2026-10-30', '--record-dir', str(recs)],
                    capture_output=True, encoding='utf-8', env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
                check(f'{extension} receipt preserves {role} before review model update',
                      p.returncode == 2 and 'aliases an input' in p.stderr and
                      before == {q: q.read_bytes() for q in guard.rglob('*') if q.is_file()}, p.stderr)
        fresh = tmp / 'dry-receipts'
        p = subprocess.run([sys.executable, str(ROOT / 'scripts/apply_review.py'), str(model), str(sheet),
            '--reviewer', 'test', '--record-dir', str(fresh), '--dry-run'], capture_output=True, encoding='utf-8',
            env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
        check('dry review does not create a receipt directory', p.returncode == 0 and not fresh.exists(), p.stderr)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("all passed" if all(results) else "FAILURES")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
