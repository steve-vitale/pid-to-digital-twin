"""Check source selection, complete appearances and reproducible offline graph/review outputs; no network."""
import contextlib
import copy
import csv
import hashlib
import io
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "scripts"))
import graph_export as gx
import statements
from serve_snapshot import Snapshot


def read(path):
    return json.loads(Path(path).read_bytes())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check():
    source, model = read(HERE / "source.json"), read(HERE / "model.json")
    original_path = ROOT / source["source_model"]
    require(hashlib.sha256(original_path.read_bytes().replace(b"\r\n", b"\n")).hexdigest() ==
            source["source_model_sha256_lf"], "source model revision changed; explicitly review the selection")
    original = next(u for u in read(original_path)[source["section"]] if u["id"] == source["item_id"])
    require(model["units"] == [original], "selected item is not an exact source-model copy")
    require([p.get("sheet") for p in original["provenance"]] == source["sheets"] == ["2", "3", "4"],
            "source appearance set changed")
    full = gx.build(HERE / "model.json")
    for profile in ("full", "core"):
        result = gx.apply_profile(full, profile)
        require(result == read(HERE / f"{profile}.graph.json"), f"{profile} graph differs from current export")
        require(not gx.problems(result), f"{profile} graph does not validate")
        node = next(n for n in result["nodes"] if n["id"] == original["id"])
        require(node["provenance"] == original["provenance"], f"{profile} appearance records lost or reordered")
    packet = Snapshot(HERE / "full.graph.json")
    returned = packet.asset(original["id"])["result"]
    require(returned["provenance"] == original["provenance"], "snapshot dropped evidence")
    returned["provenance"].clear()
    require(packet.asset(original["id"])["result"]["provenance"] == original["provenance"],
            "returned evidence mutates the loaded snapshot")
    population = read(HERE / "review/statements.json")["statements"]
    focused = [s for s in population if s["subject"] == original["id"]]
    require(len({s["id"] for s in population}) == len(population), "duplicate statement identities")
    for statement in focused:
        require(statement["item_evidence"]["provenance"] == original["provenance"], "statement lost raw records")
        evidence = statement["evidence"]["item_appearances"]
        require([e["record"] for e in evidence] == original["provenance"], "review evidence lost records")
        require(all(e["image"] is None and "no sheet image" in e["note"] for e in evidence),
                "source-only packet obscures missing images")
    with (HERE / "review/review_sheet.csv").open(encoding="utf-8", newline="") as stream:
        rows = {r["statement_id"]: r for r in csv.DictReader(stream)}
    for statement in focused:
        require(all("drawing sheet " + sheet in rows[statement["id"]]["source"] for sheet in source["sheets"]),
                "CSV pointer hides an appearance")
    with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
        statements.main(["render", str(HERE / "full.graph.json"), "--out", tmp])
        for name in ("statements.json", "review.html", "review_sheet.csv"):
            require((Path(tmp) / name).read_bytes() == (HERE / "review" / name).read_bytes(),
                    name + " differs from current render")
    # An unchanged primary locator must not hide a later source change from a review fingerprint.
    changed = copy.deepcopy(focused[0])
    changed["item_evidence"]["provenance"][1]["box_0_1000"][0] += 1
    require(statements.review_fingerprint(changed, {}) != statements.review_fingerprint(focused[0], {}),
            "second locator change is invisible to the statement binding")
    return len(focused)


if __name__ == "__main__":
    try:
        count = check()
        print(f"PASS: exact source item; 3 ordered appearances; full/core, snapshot and {count} review statements")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
