"""Follow the data: stage freshness, rebuilds that propagate a correction, and a confidence summary per dataset.

The stages, their inputs, outputs and commands are listed in pipeline/stages.json (explained in
docs/DATA_LINEAGE.md). When a stage is built, the hashes of its inputs, code, config and outputs go into
pipeline/pipeline.lock.json. A stage is STALE when any of those changed since; a correction made at the start
(a review applied to a model) therefore shows up as every downstream stage going stale, and one rebuild brings them
all back.

  python scripts/pipeline.py status [--dataset te|open100|dexpi]
  python scripts/pipeline.py rebuild --from <stage> [--dry-run] [--accept-recorded]
  python scripts/pipeline.py confidence [--dataset te|open100|dexpi] [--json]
  (all take --root <dir> to work on a copy of the repository)

rebuild runs the named stage and everything downstream of it, in manifest order:
  source     accepted as it is (its hash is recorded): a correction is made with the stage's edited_by tool first;
  auto       its command is run when its requires (files), requires_modules (Python packages) and requires_env
             (a variable naming a local program, used in the command as $NAME) are present, otherwise it is
             reported BLOCKED and left stale;
  recorded   never re-run here (model calls, or inputs that are not committed); accepted as it is only when the
             rebuild starts from it or --accept-recorded is given;
  manual     never run here; the command is printed.
Exit status: 0 every auto stage downstream rebuilt, 1 a command failed, 2 an auto stage was BLOCKED by a missing
prerequisite. Manual and recorded steps downstream are listed either way; they never count as rebuilt.

  python scripts/pipeline.py record --stage <id>
marks a check, runtime or recorded stage as done after you ran its command by hand (hashes it as it is now).

Hashes normalise CRLF to LF, and ZIP archives are hashed by their members, so a Windows checkout and a Linux
checkout agree. Stdlib only. No downloads, model
calls or gateway operations happen here: the commands that need them are only ever printed.
"""
import argparse
import glob
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from provenance import rollup  # noqa: E402

MANIFEST = "pipeline/stages.json"
LOCK = "pipeline/pipeline.lock.json"


# ---------------------------------------------------------------- manifest and hashing

def load(root):
    manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    lock_path = root / LOCK
    lock = json.loads(lock_path.read_text(encoding="utf-8")) if lock_path.exists() else {"stages": {}}
    return manifest, lock


def expand(root, patterns):
    """Glob patterns -> sorted existing relative paths; a pattern that matches nothing is returned as missing."""
    found, missing = [], []
    for pattern in patterns:
        hits = sorted(Path(p).relative_to(root).as_posix() for p in glob.glob(str(root / pattern)) if Path(p).is_file())
        if hits:
            found += hits
        else:
            missing.append(pattern)
    return sorted(set(found)), missing


def file_hash(path):
    data = path.read_bytes()
    if path.suffix.lower() == ".zip":
        # A ZIP is hashed by its members (name, timestamp, uncompressed bytes): the compressed bytes and the "made by"
        # field depend on the platform's zlib and OS, so the same project archive differs byte for byte between a
        # Windows and a Linux build while every member is identical.
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                h = hashlib.sha256(b"zip-members-1")
                for info in sorted(z.infolist(), key=lambda i: i.filename):
                    member = z.read(info)
                    h.update(info.filename.encode() + repr(info.date_time).encode()
                             + len(member).to_bytes(8, "big") + member)
                return h.hexdigest()
        except zipfile.BadZipFile:
            pass
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def hashes(root, patterns):
    found, missing = expand(root, patterns)
    return {p: file_hash(root / p) for p in found}, missing


def stage_inputs(stage):
    return stage.get("inputs", []) + stage.get("code", []) + stage.get("config", [])


def missing_requires(root, stage):
    """Local prerequisites that are absent: files (cached downloads), Python modules (requires_modules) and
    environment variables naming a local program (requires_env, e.g. BLENDER_EXE; commands use them as $NAME)."""
    files = [p for p in stage.get("requires", []) if not (root / p).exists()]
    modules = [m for m in stage.get("requires_modules", []) if importlib.util.find_spec(m) is None]
    env = [v for v in stage.get("requires_env", []) if not os.environ.get(v)]
    return files + [f"python module {m}" for m in modules] + [f"environment variable {v}" for v in env]


def short_requires(missing, n=4):
    return ", ".join(missing[:n]) + (f" (+{len(missing) - n} more)" if len(missing) > n else "")


def descendants(manifest, start):
    ids = [s["id"] for s in manifest["stages"]]
    if start not in ids:
        raise SystemExit(f"unknown stage {start!r}; stages: {', '.join(ids)}")
    chosen = {start}
    for s in manifest["stages"]:  # manifest order is dependency order (checked by scripts/test_pipeline.py)
        if any(u in chosen for u in s.get("upstream", [])):
            chosen.add(s["id"])
    return [s for s in manifest["stages"] if s["id"] in chosen]


# ---------------------------------------------------------------- freshness

def freshness(root, manifest, lock):
    """stage id -> (state, detail). States: FRESH, STALE, NEVER BUILT HERE, MISSING."""
    result = {}
    for s in manifest["stages"]:
        entry = lock["stages"].get(s["id"])
        ins, missing_in = hashes(root, stage_inputs(s))
        outs, missing_out = hashes(root, s.get("outputs", []))
        if missing_in:
            result[s["id"]] = ("MISSING", "input not in this checkout: " + ", ".join(missing_in))
            continue
        if entry is None:
            missing_req = missing_requires(root, s)
            detail = ("committed outputs predate the lock, not built by pipeline.py here; " if outs else "") + how_to(s)
            if missing_req and s["rebuild"] == "auto":
                detail += f" (needs {short_requires(missing_req)}: {s.get('requires_note', '')})"
            result[s["id"]] = ("NEVER BUILT HERE", detail)
            continue
        changed_in = sorted(p for p in set(ins) | set(entry.get("inputs", {})) if ins.get(p) != entry["inputs"].get(p))
        changed_out = sorted(p for p in set(outs) | set(entry.get("outputs", {})) if outs.get(p) != entry["outputs"].get(p))
        stale_up = [u for u in s.get("upstream", []) if result.get(u, ("FRESH",))[0] != "FRESH"]
        if missing_out:
            result[s["id"]] = ("STALE", "output missing: " + ", ".join(missing_out))
        elif changed_in:
            result[s["id"]] = ("STALE", "input changed: " + short(changed_in) + ("" if s["rebuild"] == "auto" else "; " + how_to(s)))
        elif changed_out:
            word = "changed since accepted" if s["kind"] in ("source", "recorded") else "outputs differ from the last build"
            result[s["id"]] = ("STALE", f"{word}: {short(changed_out)}")
        elif stale_up:
            result[s["id"]] = ("STALE", "upstream not fresh: " + ", ".join(stale_up))
        else:
            result[s["id"]] = ("FRESH", "")
    return result


def short(paths, n=3):
    return ", ".join(paths[:n]) + (f" (+{len(paths) - n} more)" if len(paths) > n else "")


def how_to(s):
    if s["rebuild"] == "auto":
        return f"rebuild: python scripts/pipeline.py rebuild --from {s['id']}"
    if s["rebuild"] == "source":
        return f"accept: python scripts/pipeline.py rebuild --from {s['id']}"
    note = s.get("requires_note", "")
    return ("re-run outside this orchestrator" if s["rebuild"] == "recorded" else "run by hand") + (f" ({note})" if note else "")


# ---------------------------------------------------------------- confidence

def dataset_rollup(root, manifest, dataset):
    model = manifest["datasets"][dataset].get("model")
    if not model:
        return None
    path = root / model
    if not path.exists():
        return None
    return rollup(json.loads(path.read_text(encoding="utf-8")))


def ops_counts(counts):
    """(operations-reviewed, other reviewed, unreviewed) over one class."""
    ops = counts.get("ops_review", {})
    # Plain confirmed/corrected/rejected only appear for an operations reviewer; any other reviewer's decision
    # carries a suffix (scripts/provenance.py), so it can never be counted here by accident.
    by_ops = sum(ops.get(k, 0) for k in ("confirmed", "corrected", "rejected"))
    unreviewed = ops.get("unverified", 0)
    return by_ops, counts["total"] - unreviewed - by_ops, unreviewed


def summary(root, manifest, dataset):
    """One line: what the dataset's per-element fields say, carried by every stage built from it."""
    if not manifest["datasets"][dataset].get("model"):
        return manifest["datasets"][dataset].get("no_model", "no asset model; scored extraction only")
    r = dataset_rollup(root, manifest, dataset)
    if r is None:
        return "model not in this checkout"
    reviewed = sum(ops_counts(c)[0] for c in r.values())
    if dataset == "te":
        tags = [r.get("instruments", {}), r.get("final_elements", {})]
        n = sum(c.get("total", 0) for c in tags)
        sc = sum(c.get("source_check", {}).get(k, 0) for c in tags for k in ("confirmed", "corrected"))
        corr = sum(c.get("source_check", {}).get("corrected", 0) for c in tags)
        topo = [r.get("units", {}), r.get("streams", {})]
        tn = sum(c.get("total", 0) for c in topo)
        tc = sum(c.get("source_check", {}).get(k, 0) for c in topo for k in ("confirmed", "corrected"))
        return (f"tags {sc}/{n} source-checked ({corr} corrected); units+streams {tc}/{tn} checked; "
                f"{reviewed} operations-reviewed")
    total = sum(c["total"] for c in r.values())
    tiers = {}
    for c in r.values():
        for k, v in c.get("risk_tier", {}).items():
            tiers[k] = tiers.get(k, 0) + v
    unver = sum(c.get("source_check", {}).get("unverified", 0) for c in r.values())
    unrated = total - sum(tiers.get(k, 0) for k in ("green", "amber", "red"))
    unrated_note = f"; {unrated:,} unrated (review queue puts these in amber)" if unrated else ""
    return (f"{unver:,}/{total:,} items unverified; risk green {tiers.get('green', 0):,} / amber {tiers.get('amber', 0):,} "
            f"/ red {tiers.get('red', 0):,}{unrated_note}; {reviewed} operations-reviewed")


def carried(root, manifest, stage, cache):
    ds = stage["dataset"]
    names = [n for n in manifest["datasets"] if manifest["datasets"][n].get("model")] if ds == "shared" else [ds]
    for name in names:
        if name not in cache:
            cache[name] = summary(root, manifest, name)
    text = " | ".join((f"{name}: " if ds == "shared" else "") + cache[name] for name in names)
    return ("PROOF OF CONCEPT; inherits " if stage.get("poc") else "") + text


def cmd_confidence(root, manifest, args):
    out = {}
    for name, meta in manifest["datasets"].items():
        if args.dataset and name != args.dataset:
            continue
        out[name] = {"title": meta["title"], "model": meta["model"], "per_element": dataset_rollup(root, manifest, name),
                     "measured": meta["measured"], "summary": summary(root, manifest, name)}
    if args.json:
        print(json.dumps(out, indent=1, sort_keys=True))
        return 0
    for name, d in out.items():
        print(f"\n== {d['title']}  ({d['model'] or 'no asset model'})")
        print(f"   carried by every stage built from it: {d['summary']}")
        if d["per_element"] is None:
            print("   " + ("model not in this checkout" if d["model"] else "no per-element confidence: no asset model"))
            continue
        print(f"   {'class':<19}{'total':>6}  {'source check':<28}{'ops review':<34}{'risk tier':<30}{'tag status / open'}")
        for cls, c in d["per_element"].items():
            fmt = lambda key: ", ".join(f"{k} {v:,}" for k, v in c.get(key, {}).items()) or "-"  # noqa: E731
            extra = fmt("tag_status") if "tag_status" in c else ""
            if c.get("open_question"):
                extra = (extra + "; " if extra else "") + f"open questions {c['open_question']}"
            if c.get("field_corrections"):
                extra = (extra + "; " if extra else "") + f"scoped field corrections {c['field_corrections']}"
            print(f"   {cls:<19}{c['total']:>6,}  {fmt('source_check'):<28}{fmt('ops_review'):<34}{fmt('risk_tier'):<30}{extra}")
        print("   measured or recorded (set level, from the docs):")
        for m in d["measured"]:
            print(f"     - {m['what']}: {m['value']}  [{m['source']}]")
    print("\nA review counts as an operations review only when the reviewer string names an operations role; "
          "anything else keeps its label (scripts/provenance.py).")
    return 0


# ---------------------------------------------------------------- status and rebuild

def cmd_status(root, manifest, lock, args):
    fresh = freshness(root, manifest, lock)
    cache = {}
    width = max(len(s["id"]) for s in manifest["stages"])
    for ds in (*manifest["datasets"], "shared"):
        rows = [s for s in manifest["stages"] if s["dataset"] == ds and (not args.dataset or ds in (args.dataset, "shared"))]
        if not rows:
            continue
        print(f"\n== {manifest['datasets'][ds]['title'] if ds in manifest['datasets'] else 'Shared by both datasets'}")
        for s in rows:
            state, detail = fresh[s["id"]]
            print(f"  {s['stage']}  {s['id']:<{width}}  {s['kind']:<9} {state:<16} {detail}")
            print(f"     {'':<{width}}  carries: {carried(root, manifest, s, cache)}")
    stale = [k for k, (state, _) in fresh.items() if state != "FRESH"]
    print(f"\n{len(fresh) - len(stale)}/{len(fresh)} stages fresh." + (" Not fresh: " + ", ".join(stale) if stale else ""))
    return 0


def record(root, lock, s):
    ins, _ = hashes(root, stage_inputs(s))
    outs, _ = hashes(root, s.get("outputs", []))
    lock["stages"][s["id"]] = {"inputs": ins, "outputs": outs}


def write_lock(root, lock):
    lock["about"] = ("Hashes (sha256, CRLF normalised to LF) of each stage's inputs, code, config and outputs when "
                     "scripts/pipeline.py last built or accepted it. Written by the orchestrator; do not edit by hand.")
    text = json.dumps({"about": lock["about"], "stages": dict(sorted(lock["stages"].items()))}, indent=1, sort_keys=True)
    (root / LOCK).write_text(text + "\n", encoding="utf-8", newline="\n")


def cmd_rebuild(root, manifest, lock, args):
    plan = descendants(manifest, args.start)
    status, blocked = 0, set()
    for s in plan:
        sid, mode = s["id"], s["rebuild"]
        if any(u in blocked for u in s.get("upstream", [])):
            blocked.add(sid)
            print(f"BLOCKED   {sid}: upstream blocked")
            status = 2
            continue
        if mode == "source":
            print(f"ACCEPT    {sid}: source hashed as it is now")
            if not args.dry_run:
                record(root, lock, s)
        elif mode == "recorded":
            if sid == args.start or args.accept_recorded:
                print(f"ACCEPT    {sid}: recorded outputs accepted as they are (not re-run: {s.get('requires_note', '')})")
                if not args.dry_run:
                    record(root, lock, s)
            else:
                print(f"NOT RUN   {sid}: recorded stage; {how_to(s)}")
        elif mode == "manual":
            commands = "; ".join(" ".join(c) for c in s.get("command", []))
            print(f"MANUAL    {sid}: run by hand, then record: {commands}"
                  + (f" ({s['requires_note']})" if s.get("requires_note") else ""))
        else:
            missing = missing_requires(root, s)
            if missing:
                blocked.add(sid)
                print(f"BLOCKED   {sid}: needs {short_requires(missing)}" + (f" ({s['requires_note']})" if s.get("requires_note") else ""))
                status = 2
                continue
            for command in s["command"]:
                argv = [sys.executable if c == "python" else os.path.expandvars(c) for c in command]
                print(f"RUN       {sid}: {' '.join(command)}")
                if args.dry_run:
                    continue
                done = subprocess.run(argv, cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                      env={**os.environ, "PYTHONIOENCODING": "utf-8"})
                if done.returncode:
                    print(done.stdout[-2000:], done.stderr[-2000:])
                    print(f"FAILED    {sid}: exit {done.returncode}; lock not updated for this stage")
                    write_lock(root, lock)
                    return 1
            if not args.dry_run:
                record(root, lock, s)
    if not args.dry_run:
        write_lock(root, lock)
    print("dry run: nothing written" if args.dry_run else
          f"lock updated: {LOCK}" + ("" if status == 0 else " (some stages need a manual step or were blocked; see above)"))
    return status


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(DEFAULT_ROOT), help="repository root (default: this checkout)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    st = sub.add_parser("status")
    st.add_argument("--dataset", choices=["te", "open100", "dexpi", "bayer"])
    rb = sub.add_parser("rebuild")
    rb.add_argument("--from", dest="start", required=True)
    rb.add_argument("--dry-run", action="store_true")
    rb.add_argument("--accept-recorded", action="store_true",
                    help="accept recorded stages downstream as they are (for a first lock, or after re-running them)")
    rc = sub.add_parser("record")
    rc.add_argument("--stage", required=True)
    cf = sub.add_parser("confidence")
    cf.add_argument("--dataset", choices=["te", "open100", "dexpi", "bayer"])
    cf.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    manifest, lock = load(root)
    if args.cmd == "status":
        return cmd_status(root, manifest, lock, args)
    if args.cmd == "rebuild":
        return cmd_rebuild(root, manifest, lock, args)
    if args.cmd == "record":
        stage = next((s for s in manifest["stages"] if s["id"] == args.stage), None)
        if stage is None or stage["rebuild"] == "auto":
            raise SystemExit(f"record is for check, runtime and recorded stages; rebuild auto stages instead: {args.stage}")
        record(root, lock, stage)
        write_lock(root, lock)
        print(f"recorded {args.stage} as it is now (you ran it by hand; the lock does not prove what you ran)")
        return 0
    return cmd_confidence(root, manifest, args)


if __name__ == "__main__":
    sys.exit(main())
