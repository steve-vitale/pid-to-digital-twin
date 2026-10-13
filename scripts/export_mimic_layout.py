"""The Tennessee Eastman overview mimic as plain layout data. PROOF OF CONCEPT display, built to iterate on.

The overview screen (scripts/ignition/build_mimic.py) is rendered by the same function the Ignition build uses, then
reduced to what a reviewer or a test needs: each unit's drawn position, and for each reading shown on the overview,
which unit it is drawn beside, where, the tag path it reads, and the provenance of the model item behind it
(scripts/provenance.py). No gateway, replay data or third-party package is needed.

Positions and the choice of readings are first-pass display choices (docs/OPERATOR_SCREENS.md), not reviewed by
operations. What this file can show is that the layout follows the model: a corrected owner in
data/te_process_model.json moves the reading here on the next build.

Deterministic, stdlib only.
Usage:  python scripts/export_mimic_layout.py [model.json] [out.json]
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "ignition"))
import build_mimic  # noqa: E402
from build_scene_data import sha256_text  # noqa: E402
from provenance import element  # noqa: E402

MODEL = ROOT / "data" / "te_process_model.json"
OUT = ROOT / "out" / "mimic" / "te_overview_layout.json"
PROVIDER = "Twin"  # the tag provider name scripts/ignition/build_gateway.py uses


def layout(model, source_hash):
    view = build_mimic.mimic(PROVIDER, model)
    parts = {c["meta"]["name"]: c for c in view["root"]["children"]}
    items = {i["tag"]: i for i in model["instruments"] + model["final_elements"]}
    units, readings = [], []
    for uid in build_mimic.UNIT_ORDER:
        eq = parts["Equipment_" + uid]["position"]
        units.append({"id": uid, "equipment_box": [eq["x"], eq["y"], eq["width"], eq["height"]]})
        for tag in build_mimic.placed_tags(model, uid):
            label, value = parts["Tag_" + tag], parts["Value_" + tag]
            path = value["propConfig"]["props.text"]["binding"]["config"]["tagPath"]
            readings.append({"tag": tag, "drawn_beside": uid, "label_xy": [label["position"]["x"], label["position"]["y"]],
                             "reads": path, "owner_in_model": items[tag]["unit"], "provenance": element(items[tag])})
    return {
        "meta": {
            "kind": "proof_of_concept",
            "status": "first-pass display layout, built to iterate on; not reviewed by operations",
            "generated_by": "scripts/export_mimic_layout.py (renders scripts/ignition/build_mimic.py offline)",
            "source": "data/te_process_model.json",
            "source_sha256": source_hash,
            "inherits": "each reading carries the provenance of its model item; positions are illustrative",
        },
        "units": units,
        "readings": readings,
    }


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    model_path = Path(argv[0]) if argv else MODEL
    out = Path(argv[1]) if len(argv) > 1 else OUT
    model = json.loads(model_path.read_text(encoding="utf-8"))
    doc = layout(model, sha256_text(model_path))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {out.relative_to(ROOT).as_posix() if out.is_relative_to(ROOT) else out}: "
          f"{len(doc['readings'])} overview readings beside {len(doc['units'])} units (proof of concept)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
