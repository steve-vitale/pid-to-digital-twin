"""Seen-data diagnostic: the already examined 220 cached DEXPI exports; no fetch or model calls."""
import collections
import hashlib
import json
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "scripts"))
import corpus_adapters as ca
import dexpi_reader as dr
import graph_export as gx

KNOWN_REFUSALS = {
    "dexpi 1.2/example pids/I02 Control/I02V01_AUD.EX01.xml": ["XMP_002"],
    "dexpi 1.2/example pids/I03 Measurement and Control/I03V01_AUD.EX01.xml": ["XMP_003"],
    "dexpi 1.2/example pids/I04 Measurement and Control/I04V01_AUD.EX01.xml": ["XMP_004"],
    "dexpi 1.2/example pids/I08 Local pressure indication, CCR pressure indication, alarms and switches/I08V01_AUD.EX01.xml": ["XMP_21063", "XMP_21075"],
    "dexpi 1.2/example pids/I11 Measurement/I11V01_AUD.EX01I.xml": ["XMP_1111"],
    "dexpi 1.2/example pids/I12 Control/I12V01_AUD.EX01.xml": ["XMP_012"],
}


def run():
    files = ca.dexpi_files("1.2") + ca.dexpi_files("1.3")
    if len(files) != 220:
        raise ValueError(f"expected all 220 pinned XML files, found {len(files)}; run python scripts/fetch_corpus.py dexpi-ttc-all")
    pins = json.loads((ROOT / "data/corpus_pins.json").read_text(encoding="utf-8"))["dexpi-ttc-all"]
    result = {"scope": "seen-data diagnostic; retention of reader interpretation, not independent engineering truth",
              "files": 220, "models": 0, "known_refusals": [], "unplaced_items": 0, "files_with_unplaced": 0,
              "historical_role_downgrades": 0, "historical_missing_controls": 0,
              "current_role_mismatches": [], "current_missing_controls": [], "graph_errors": []}
    work = HERE / ".work"
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="audit-", dir=work) as tmp:
        model_path = Path(tmp) / "model.json"
        for item in files:
            path = ca.DEXPI_ROOT / item["rel"]
            pin = pins[item["rel"]]
            if path.stat().st_size != pin["bytes"] or hashlib.sha256(path.read_bytes()).hexdigest() != pin["sha256"]:
                raise ValueError("pinned bytes changed: " + item["rel"])
            try:
                model = dr.Reader(path).read()
            except ValueError as exc:
                counts = collections.Counter(e.get("ID") for e in ET.parse(path).iter() if e.get("ID"))
                duplicates = sorted(k for k, n in counts.items() if n > 1)
                if KNOWN_REFUSALS.get(item["rel"]) != duplicates or "element IDs used more than once" not in str(exc):
                    raise ValueError("new or unconfirmed reader refusal: " + item["rel"]) from exc
                result["known_refusals"].append({"file": item["rel"], "duplicate_ids": duplicates})
                continue
            result["models"] += 1
            unplaced = model.get("unplaced", [])
            result["unplaced_items"] += len(unplaced)
            result["files_with_unplaced"] += bool(unplaced)
            # Exact pre-repair kind rule: a transparent historical counterfactual, not a second reader.
            for u in unplaced:
                old_kind = "final_element" if "Operated" in str(u.get("dexpi_class", "")) or u.get("actuated") else "line_item"
                result["historical_role_downgrades"] += old_kind != u["kind"]
            _, old_edges, _ = gx.from_hand_built(model)
            old_pairs = {(t, a, b) for t, a, b, _ in old_edges}
            refs = []
            for controller in model.get("controllers", []):
                for field in ("measurement_unplaced", "output_unplaced"):
                    targets = controller.get(field)
                    targets = targets if isinstance(targets, list) else [targets] if targets else []
                    for target in targets:
                        a, b = (target, controller["tag"]) if field == "measurement_unplaced" else (controller["tag"], target)
                        refs.append(("controls", a, b))
                        result["historical_missing_controls"] += ("controls", a, b) not in old_pairs
            model_path.write_text(json.dumps(model), encoding="utf-8")
            try:
                graph = gx.build(model_path)
            except (ValueError, KeyError, TypeError) as exc:
                result["graph_errors"].append({"file": item["rel"], "error": str(exc)})
                continue
            for problem in gx.problems(graph):
                result["graph_errors"].append({"file": item["rel"], "error": problem})
            nodes = {n["id"]: n for n in graph["nodes"]}
            pairs = {(e["type"], e["from"], e["to"]) for e in graph["edges"]}
            for u in unplaced:
                if nodes[u["tag"]]["kind"] != u["kind"]:
                    result["current_role_mismatches"].append({"file": item["rel"], "tag": u["tag"]})
            for t, a, b in refs:
                if (t, a, b) not in pairs:
                    result["current_missing_controls"].append({"file": item["rel"], "from": a, "to": b})
    print(json.dumps(result, indent=2))
    observed = (result["models"], len(result["known_refusals"]), result["unplaced_items"], result["files_with_unplaced"],
                result["historical_role_downgrades"], result["historical_missing_controls"])
    expected = (214, 6, 88, 56, 87, 44)
    if observed != expected or any(result[k] for k in ("current_role_mismatches", "current_missing_controls", "graph_errors")):
        raise ValueError("bounded diagnostic differs from expected counts; inspect the report")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(run())
    except (OSError, ValueError, KeyError, ET.ParseError) as exc:
        print("FAIL:", exc, file=sys.stderr)
        sys.exit(1)
