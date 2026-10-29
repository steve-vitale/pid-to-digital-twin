"""Controls for the data-lineage spine (pipeline/stages.json, scripts/pipeline.py, scripts/provenance.py).

1. The manifest is consistent with the repository: every script it names exists, stages are in dependency order,
   and every stage input is a source, produced upstream, or listed code/config.
2. The committed lock matches the committed outputs: every auto stage that needs no download is FRESH.
3. Propagation, on a temp copy of the repository (committed data is never touched):
   - a Tennessee Eastman review correction (a test fixture: FT-105 moved from K-101 to V-101, applied with
     scripts/apply_review.py; the real FT-110 purge move already came from the topology check)
     makes the downstream stages stale; one `pipeline.py rebuild --from te.source` brings the change into the
     Ignition tags, the PI AF sheet, the review sheet, the mimic layout and the 3D scene data, with no file edited
     by hand, and everything rebuildable is fresh again;
   - a confirmation recorded by a non-operations reviewer keeps that label in every output and is not counted as an
     operations review;
   - an OPEN100 identifier-text correction reaches the twin's Ignition tags, PI sheet and review queue the same way;
   - a second rebuild produces byte-identical outputs (deterministic).
Stdlib only.
"""
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from fnmatch import fnmatch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import pipeline  # noqa: E402
from provenance import reviewer_track  # noqa: E402

results = []
OPEN100 = "data/external/pid2graph/PID2Graph/Complete/PID2Graph OPEN100"
TWIN = "out/twin/r2-tiles-trace/codex"


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}{'' if ok else ': ' + str(detail)}")


# The temp-copy rebuilds never start a renderer (Blender, a headless browser): those stages block instead.
RENDER_ENV = ("BLENDER_EXE", "BROWSER_EXE")


def run(args, cwd=ROOT):
    env = {k: v for k, v in os.environ.items() if k not in RENDER_ENV}
    return subprocess.run([sys.executable] + [str(a) for a in args], cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env={**env, "PYTHONIOENCODING": "utf-8"})


def tree_hash(folder):
    h = hashlib.sha256()
    for p in sorted(Path(folder).rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            h.update(p.relative_to(folder).as_posix().encode() + p.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()


# ---------------------------------------------------------------- 1. manifest consistency

def manifest_checks():
    manifest, lock = pipeline.load(ROOT)
    stages = manifest["stages"]
    ids = [s["id"] for s in stages]
    check("stage ids are unique", len(ids) == len(set(ids)), ids)
    seen, order_ok, unknown = set(), True, []
    for s in stages:
        for u in s.get("upstream", []):
            if u not in ids:
                unknown.append((s["id"], u))
            elif u not in seen:
                order_ok = False
        seen.add(s["id"])
    check("every upstream exists", not unknown, unknown)
    check("stages are listed in dependency order", order_ok)
    check("every stage names a known kind, rebuild mode and dataset",
          all(s["kind"] in manifest["kinds"] and s["rebuild"] in manifest["rebuild_modes"]
              and s["dataset"] in (*manifest["datasets"], "shared") for s in stages))
    missing = [(s["id"], p) for s in stages for p in s.get("code", []) + s.get("config", []) if not (ROOT / p).is_file()]
    check("every script and config file the manifest lists exists", not missing, missing)
    cmd_scripts = [(s["id"], c[1]) for s in stages for c in s.get("command", []) + s.get("recorded_commands", [])
                   if len(c) > 1 and c[1].endswith(".py")]
    check("every command's script exists and is hashed as the stage's code",
          all((ROOT / p).is_file() and p in s_code(stages, sid) for sid, p in cmd_scripts),
          [x for x in cmd_scripts if not (ROOT / x[1]).is_file() or x[1] not in s_code(stages, x[0])])
    by_id = {s["id"]: s for s in stages}

    def ancestors(sid):
        out, todo = set(), list(by_id[sid].get("upstream", []))
        while todo:
            u = todo.pop()
            if u not in out:
                out.add(u)
                todo += by_id[u].get("upstream", [])
        return out

    orphans = []
    for s in stages:
        produced = [p for a in ancestors(s["id"]) for p in by_id[a].get("outputs", [])]
        for pattern in s.get("inputs", []):
            if not any(pattern == p or fnmatch(pattern, p) or fnmatch(p, pattern) for p in produced):
                orphans.append((s["id"], pattern))
    check("every stage input is produced upstream or by a source stage", not orphans, orphans)
    sources_missing = [(s["id"], p) for s in stages if s["kind"] == "source" for p in s["outputs"]
                       if not pipeline.expand(ROOT, [p])[0]]
    check("every source stage's data is in the repository", not sources_missing, sources_missing)
    for sid in ("te.mimic", "te.scene", "te.replay"):
        check(f"{sid} is labelled proof of concept", by_id[sid].get("poc") is True)
    check("platform exports are not labelled proof of concept",
          not by_id["te.exports"]["poc"] and not by_id["open100.exports"]["poc"])
    check("every lock entry names a manifest stage", set(lock["stages"]) <= set(ids), set(lock["stages"]) - set(ids))
    check("every dataset model is a source or recorded stage output (a dataset without an asset model says so)",
          all(any(d["model"] in s.get("outputs", []) for s in stages if s["kind"] in ("source", "recorded"))
              if d.get("model") else bool(d.get("no_model")) for d in manifest["datasets"].values()))
    # 2. the committed lock agrees with the committed files
    fresh = pipeline.freshness(ROOT, manifest, lock)
    offline_auto = [s["id"] for s in stages if s["rebuild"] == "auto" and not s.get("requires")]
    check("committed lock: every offline auto stage is FRESH", all(fresh[i][0] == "FRESH" for i in offline_auto),
          {i: fresh[i] for i in offline_auto if fresh[i][0] != "FRESH"})


def s_code(stages, sid):
    return next(s for s in stages if s["id"] == sid).get("code", [])


# ---------------------------------------------------------------- 3. propagation on a temp copy

def copy_repo(tmp):
    shutil.copytree(ROOT / "scripts", tmp / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / "pipeline", tmp / "pipeline")
    shutil.copytree(ROOT / "extraction", tmp / "extraction")
    shutil.copytree(ROOT / OPEN100, tmp / OPEN100)
    manifest, _ = pipeline.load(ROOT)
    for s in manifest["stages"]:
        for p in pipeline.expand(ROOT, s.get("outputs", []) + s.get("inputs", []) + s.get("config", []))[0]:
            (tmp / p).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / p, tmp / p)


def write_sheet(path, cols, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})


def apply(tmp, model, rows, reviewer, twin=False):
    import generate
    cols = generate.TWIN_REVIEW_COLS + ["OPS_scope"] if twin else generate.REVIEW_COLS
    sheet = tmp / "reviewed.csv"
    write_sheet(sheet, cols, rows)
    return run([tmp / "scripts/apply_review.py", tmp / model, sheet, "--reviewer", reviewer, "--date", "2026-10-13",
                "--record-dir", tmp / "rec"], cwd=tmp)


def status(tmp):
    manifest, lock = pipeline.load(tmp)
    return pipeline.freshness(tmp, manifest, lock)


def outputs_hash(tmp):
    manifest, _ = pipeline.load(tmp)
    return {p: pipeline.file_hash(tmp / p) for s in manifest["stages"] if s["rebuild"] == "auto"
            for p in pipeline.expand(tmp, s.get("outputs", []))[0]}


def te_propagation(tmp):
    scripts_before = tree_hash(tmp / "scripts")
    committed_model = pipeline.file_hash(ROOT / "data/te_process_model.json")
    te_auto = ["te.exports", "te.mimic", "te.scene"]
    st = status(tmp)
    check("temp copy starts fresh", all(st[i][0] == "FRESH" for i in ["te.source"] + te_auto), st)
    layout = json.loads((tmp / "out/mimic/te_overview_layout.json").read_text(encoding="utf-8"))
    before = next(r for r in layout["readings"] if r["tag"] == "FT-105")
    check("control: before the correction FT-105 is drawn beside K-101", before["drawn_beside"] == "K-101", before)

    p = apply(tmp, "data/te_process_model.json",
              [{"item_id": "FT-105", "OPS_confirm_or_correct": "correct", "OPS_correct_value": "unit=V-101",
                "OPS_notes": "test fixture: a tag moved to show propagation, not a real finding"}],
              "B-1, process engineer (test fixture, not a real review)")
    check("review correction applied through scripts/apply_review.py", p.returncode == 0, p.stdout + p.stderr)
    p = apply(tmp, "data/te_process_model.json", [{"item_id": "FT-101", "OPS_confirm_or_correct": "confirm"}],
              "A-1, non-operations reviewer: text and legibility only (test fixture)")
    check("a non-operations confirmation applied (Track A should never confirm; the label must survive if one does)",
          p.returncode == 0, p.stdout + p.stderr)
    st = status(tmp)
    check("status: the source shows as changed", st["te.source"][0] == "STALE" and "changed since accepted" in st["te.source"][1], st["te.source"])
    check("status: every downstream TE stage is stale", all(st[i][0] == "STALE" for i in te_auto), {i: st[i] for i in te_auto})

    r = run([tmp / "scripts/pipeline.py", "--root", tmp, "rebuild", "--from", "te.source"], cwd=tmp)
    blocked = sorted(line.split()[1].rstrip(":") for line in r.stdout.splitlines() if line.startswith("BLOCKED"))
    # The temp copy has no TE replay download, so the stages that need it (and everything below them) must block;
    # a stage may also block on a missing optional package (e.g. Pillow for the generated P&ID). Nothing else may.
    manifest, _ = pipeline.load(tmp)
    by_id = {s["id"]: s for s in manifest["stages"]}
    may_block = set()
    for s in manifest["stages"]:
        if (pipeline.missing_requires(tmp, s) or set(s.get("requires_env", [])) & set(RENDER_ENV)
                or any(u in may_block for u in s.get("upstream", []))):
            may_block.add(s["id"])
    must_block = {"te.bands", "ignition.gateway", "te.fault_detection"}
    check("rebuild ran; only stages needing the TE replay download or a missing package were blocked (exit 2)",
          r.returncode == 2 and must_block <= set(blocked) and set(blocked) <= may_block
          and all(i in by_id for i in blocked), (r.returncode, blocked, r.stdout[-1500:]))

    tags = json.loads((tmp / "out/ignition/te_tags.json").read_text(encoding="utf-8"))
    folders = {t["name"]: t for t in tags["tags"]}
    type_of = {i["name"]: i["typeId"] for i in folders["TE_Plant"]["tags"]}
    members = {t["name"]: [m["documentation"] for m in t["tags"]] for t in folders["_types_"]["tags"]}
    check("Ignition tags: FT-105 is now a member of the separator's UDT, not the compressor's",
          any(d.startswith("FT-105 ") for d in members[type_of["V-101"]])
          and not any(d.startswith("FT-105 ") for d in members[type_of["K-101"]]))
    check("Ignition tags: the documentation carries the review",
          any(d.startswith("FT-105 ") and d.endswith("ops review: corrected") for d in members[type_of["V-101"]]))
    check("Ignition tags: a non-operations confirmation keeps its label",
          any(d.startswith("FT-101 ") and d.endswith("ops review: confirmed (non-operations reviewer)") for d in members[type_of["U-100"]]))
    rows = list(csv.reader((tmp / "out/pi/pi_builder_af.csv").read_text(encoding="utf-8-sig").splitlines()))
    fi105 = [r for r in rows if r and r[-1].endswith(".FT-105.PV")]  # sheet v2: descriptions are in attribute_descriptions.csv
    check("PI AF sheet: FT-105 sits under TE Plant\\V-101", [r[1] for r in fi105] == ["TE Plant\\V-101"], fi105)
    review = list(csv.DictReader((tmp / "out/ops_review_sheet.csv").read_text(encoding="utf-8-sig").splitlines()))
    row = next(r for r in review if r["item_id"] == "FT-105")
    check("review sheet: FT-105 belongs to the separator and prints the decision back",
          row["belongs_to"] == "Vapor/Liquid Separator" and row["OPS_confirm_or_correct"] == "confirm", row)
    layout = json.loads((tmp / "out/mimic/te_overview_layout.json").read_text(encoding="utf-8"))
    after = next(r for r in layout["readings"] if r["tag"] == "FT-105")
    v101 = next(u for u in layout["units"] if u["id"] == "V-101")["equipment_box"]
    check("mimic layout: FT-105 is drawn beside V-101, in the V-101 column, reading the V-101 tag path",
          after["drawn_beside"] == "V-101" and after["label_xy"][0] == v101[0] - 45
          and after["reads"].endswith("/V-101/FT-105/PV") and after["owner_in_model"] == "V-101", after)
    scene = json.loads((tmp / "out/scene/te_scene.json").read_text(encoding="utf-8"))
    units = {u["id"]: u for u in scene["units"]}
    tag = next((t for t in units["V-101"]["tags"] if t["tag"] == "FT-105"), None)
    check("3D scene data: FT-105 is on V-101 and gone from K-101, carrying the review",
          tag and tag["provenance"]["ops_review"] == "corrected"
          and not any(t["tag"] == "FT-105" for t in units["K-101"]["tags"]), tag)
    fi101 = next(t for t in units["U-100"]["tags"] if t["tag"] == "FT-101")
    check("3D scene data: the non-operations confirmation keeps its label",
          fi101["provenance"]["ops_review"] == "confirmed (non-operations reviewer)"
          and fi101["provenance"]["reviewer_track"] == "non-operations", fi101)
    check("3D scene data stays labelled proof of concept", scene["meta"]["kind"] == "proof_of_concept")

    st = status(tmp)
    check("status after rebuild: source and every offline TE stage fresh",
          all(st[i][0] == "FRESH" for i in ["te.source"] + te_auto), {i: st[i] for i in ["te.source"] + te_auto})
    c = run([tmp / "scripts/pipeline.py", "--root", tmp, "confidence", "--dataset", "te", "--json"], cwd=tmp)
    te = json.loads(c.stdout)["te"]
    check("confidence: one operations decision counted; the non-operations confirmation is not",
          "1 operations-reviewed" in te["summary"]
          and te["per_element"]["instruments"]["ops_review"].get("confirmed (non-operations reviewer)") == 1, te["summary"])
    check("nothing edited by hand: scripts identical, committed model untouched",
          tree_hash(tmp / "scripts") == scripts_before
          and pipeline.file_hash(ROOT / "data/te_process_model.json") == committed_model)


def open100_propagation(tmp):
    model = f"{TWIN}/plant_model.json"
    p = apply(tmp, model, [{"item_id": "S0-IN001", "OPS_confirm_or_correct": "correct", "OPS_correct_value": "tag=TCV-1401",
                            "OPS_scope": "identifier_text", "OPS_notes": "A: tag text as printed (test fixture)"}],
              "A-1, non-operations reviewer: text and legibility only (test fixture)", twin=True)
    check("OPEN100: identifier-text correction applied through scripts/apply_review.py", p.returncode == 0, p.stdout + p.stderr)
    st = status(tmp)
    check("OPEN100: the model shows as changed and the exports stale",
          st["open100.model"][0] == "STALE" and st["open100.exports"][0] == "STALE", (st["open100.model"], st["open100.exports"]))
    r = run([tmp / "scripts/pipeline.py", "--root", tmp, "rebuild", "--from", "open100.model"], cwd=tmp)
    check("OPEN100: rebuild from the model ran", r.returncode in (0, 2) and "RUN       open100.exports" in r.stdout, r.stdout[-1500:])
    tags = (tmp / f"{TWIN}/ignition/tags.json").read_text(encoding="utf-8")
    pi = (tmp / f"{TWIN}/pi/pi_builder_af.csv").read_text(encoding="utf-8-sig")
    queue = list(csv.DictReader((tmp / f"{TWIN}/review_queue.csv").read_text(encoding="utf-8-sig").splitlines()))
    row = next(q for q in queue if q["item_id"] == "S0-IN001")
    check("OPEN100: the corrected tag reaches the Ignition tags and the PI AF sheet",
          "TCV-1401" in tags and "TCV-1401" in pi and "tag: TCV 1401 " not in pi)
    check("OPEN100: a Track A text correction leaves the item unverified in the review queue",
          row["model_status"] == "unverified" and "TCV-1401" in json.dumps(row), row)
    st = status(tmp)
    check("OPEN100: model and exports fresh after the rebuild",
          st["open100.model"][0] == "FRESH" and st["open100.exports"][0] == "FRESH", (st["open100.model"], st["open100.exports"]))


def determinism(tmp):
    first = outputs_hash(tmp)
    for start in ("te.source", "open100.model"):
        run([tmp / "scripts/pipeline.py", "--root", tmp, "rebuild", "--from", start], cwd=tmp)
    second = outputs_hash(tmp)
    check("a second rebuild writes byte-identical outputs", first == second and first,
          sorted(k for k in set(first) | set(second) if first.get(k) != second.get(k)))


def unit_checks():
    check("reviewer track: an operations role counts", reviewer_track("B-2, shift supervisor") == "operations")
    check("reviewer track: non-operations wins over the word 'operations'",
          reviewer_track("A-1, non-operations reviewer") == "non-operations")
    check("reviewer track: no stated role is not an operations review", reviewer_track("A. Person") == "role not stated")


def main():
    unit_checks()
    manifest_checks()
    tmp = Path(tempfile.mkdtemp(prefix="pipeline-test-"))
    try:
        copy_repo(tmp)
        te_propagation(tmp)
        open100_propagation(tmp)
        determinism(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"{sum(results)}/{len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
