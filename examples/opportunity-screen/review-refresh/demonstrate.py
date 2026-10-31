"""Check a fictional review -> question refresh -> reconfirmation through the actual CLIs. Offline, stdlib only.

Default checks committed expected outputs. --write deliberately regenerates them after the declared checks pass.
All model edits and intermediate packets are confined to a temporary directory.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE = HERE.parent / "food_plant_model.json"
QUESTIONS = ("C12", "E29", "E31", "H6")
ADDED = {"E29@K-203", "E31@F-303", "H6@F-303"}
REJECTED = {"JT-201", "SC-203", "HX-303"}


def command(script, *args):
    p = subprocess.run([sys.executable, "-S", str(ROOT / "scripts" / script), *map(str, args)], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8")
    if p.returncode:
        raise RuntimeError(f"{script} exited {p.returncode}: {p.stdout}\n{p.stderr}")
    return p


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def assets(doc, fid):
    return {a["id"] for f in doc["questions"] if f["id"] == fid for a in f["assets"]}


def demonstrate(write=False):
    original = SOURCE.read_bytes()
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        model = base / "plant_model.json"
        model.write_bytes(original)

        def screen(name):
            out = base / name
            args = ["--model", model, "--out", out]
            for q in QUESTIONS:
                args.extend(("--question", q))
            command("question_engine.py", *args)
            return read(out / "questions.json")

        def apply(sheet, records):
            return command("apply_review.py", model, HERE / sheet,
                           "--reviewer", "Illustrative software control, not a real review",
                           "--date", "2026-10-30", "--record-dir", base / records)

        before = screen("before")
        apply("rejections.csv", "first-records")
        rejected_model = read(model)
        rejected_bytes = model.read_bytes()
        after = screen("after")
        apply("rejections.csv", "repeat-records")
        assert model.read_bytes() == rejected_bytes, "Repeated review changed the model"
        apply("reconfirmations.csv", "reconfirmed-records")
        final = screen("reconfirmed")
        restored = read(model)

        before_ids = {f["id"] for f in before["questions"]}
        after_ids = {f["id"] for f in after["questions"]}
        assert after_ids - before_ids == ADDED
        assert not before_ids - after_ids
        assert "K-201" in assets(before, "C12@model")
        assert "JT-201" in assets(before, "C12@model")
        assert "JT-201" not in assets(after, "C12@model")
        assert "K-201" in assets(after, "C12@model")
        assert not REJECTED & {a["id"] for f in after["questions"] for a in f["assets"]}
        assert {r["id"] for r in after["review_exclusions"]} == REJECTED
        assert final["questions"] == before["questions"], "Explicit reinstatement did not restore the questions"
        assert "review_exclusions" not in final
        idx = lambda m: {r.get("id") or r.get("tag"): r for sec in ("units", "instruments", "final_elements")
                         for r in m.get(sec, [])}
        rejected_index, restored_index = idx(rejected_model), idx(restored)
        for tag in REJECTED:
            assert rejected_index[tag]["ops_review"]["status"] == "rejected"
            assert restored_index[tag]["ops_review"]["status"] == "confirmed"
            assert len(restored_index[tag]["ops_review"]["history"]) > len(rejected_index[tag]["ops_review"]["history"])
        assert SOURCE.read_bytes() == original, "Source fixture changed"
        result = {
            "scope": "Software controls on the existing synthetic food model and fictional review; no real plant or human review.",
            "questions_run": list(QUESTIONS), "new_findings": sorted(ADDED),
            "C12_model_assets_before": sorted(assets(before, "C12@model")),
            "C12_model_assets_after": sorted(assets(after, "C12@model")),
            "excluded_items": sorted(REJECTED), "repeated_review_unchanged": True,
            "explicit_reconfirmation_restores_questions": True, "review_history_retained": True,
            "source_fixture_unchanged": True,
            "source_model_semantic_sha256": hashlib.sha256(json.dumps(json.loads(original), sort_keys=True,
                                                                     separators=(",", ":")).encode()).hexdigest(),
        }
        generated = {"expected.json": json.dumps(result, indent=2) + "\n"}
        generated.update({name: (base / "after" / name).read_text(encoding="utf-8")
                          for name in ("questions.json", "screen.md")})
        for name, content in generated.items():
            path = HERE / "expected" / name
            if write:
                path.parent.mkdir(exist_ok=True)
                path.write_text(content, encoding="utf-8", newline="\n")
            else:
                assert path.read_text(encoding="utf-8") == content, f"Stale expected/{name}"
        return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    print(json.dumps(demonstrate(args.write), indent=2))
