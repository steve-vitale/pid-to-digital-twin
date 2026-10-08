"""Controls for the review loop (scripts/apply_review.py and the generators), on temp copies of the committed models.

The loop is only trustworthy if bad sheets are refused, alarm requests that need a change review are not applied,
re-applying changes nothing, the regenerated sheet round-trips, and the decisions reach the platform outputs.
"""
import csv
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import generate  # noqa: E402

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
                        *extra], capture_output=True, text=True, encoding="utf-8")
    rec = tmp / "rec" / f"2026-10-08-{model.stem if model.name != 'plant_model.json' else model.parent.name}.json"
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
            {"item_id": "FI-101", "OPS_confirm_or_correct": "confirm", "OPS_show_on_operator_screen_Y_N": "Y"},
            {"item_id": "TI-122", "OPS_confirm_or_correct": "correct",
             "OPS_correct_value": "description=Separator cooling water outlet temperature", "OPS_notes": "per teprob.f"},
            {"item_id": "PI-107", "OPS_alarm_priority_H_M_L_none": "none"},     # remove a published alarm: MOC
            {"item_id": "FI-102", "OPS_alarm_priority_H_M_L_none": "H"},        # new alarm, no setpoint: MOC
            {"item_id": "TI-109", "OPS_alarm_priority_H_M_L_none": "M"},        # priority of a published alarm: applied
            {"item_id": "XX-999", "OPS_confirm_or_correct": "confirm"},         # no such item
            {"item_id": "LI-108", "OPS_confirm_or_correct": "correct"},         # correct without a value
            {"item_id": "LI-112", "OPS_confirm_or_correct": "correct", "OPS_correct_value": "colour=red"},  # bad field
            {"item_id": "LI-115", "OPS_confirm_or_correct": "maybe"},           # bad decision
        ]
        p, rec = run(te, rows, cols, tmp)
        check("bad rows make the run exit non-zero", p.returncode == 1, p.returncode)
        check("4 refusals (unknown item, missing value, bad field, bad decision)",
              rec and len(rec["refused"]) == 4, rec and rec["refused"])
        check("5 decisions applied", rec and len(rec["applied"]) == 5, rec and [a["item"] for a in rec["applied"]])
        moc = {m["item"]: m["request"] for m in (rec or {}).get("needs_moc", [])}
        check("removing PI-107's published alarm is flagged for a change review", moc.get("PI-107") == "remove alarm", moc)
        check("a new alarm on FI-102 (no setpoint) is flagged, not created", moc.get("FI-102", "").startswith("new"), moc)
        check("TI-109 priority change (published alarm) is not flagged", "TI-109" not in moc, moc)
        m = json.loads(te.read_text(encoding="utf-8"))
        ti = next(i for i in m["instruments"] if i["tag"] == "TI-122")
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
        good = [r for r in rows if r["item_id"] in ("FI-101", "TI-122", "PI-107", "FI-102", "TI-109")]
        p, rec = run(te, good, cols, tmp)
        check("re-applying the same decisions changes nothing", rec and not rec["applied"] and rec["unchanged"] == 5,
              rec and rec["applied"])

        # Round trip: the regenerated sheet prints the decisions back; applying it changes nothing.
        regen = [dict(zip(cols, r)) for r in generate.review_rows(m)]
        r101 = next(r for r in regen if r["item_id"] == "FI-101")
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
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("all passed" if all(results) else "FAILURES")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
