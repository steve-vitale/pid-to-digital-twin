"""Rename TE tags from one recorded mapping, in the files that hold tags (valves 2026-10-28, transmitters 2026-10-29).

Why (2026-10-28, data/te_retag_2026-10-28.json): the seed model numbered the valves 201-212 in XMV order, so every valve carried a different number from the
measurement that drives it (FV-201 was moved by FI-102's loop) and two carried the wrong letter (HV-205 and TV-211
sit on flow loops). scripts/te_control_loops.py found this; the pairings come from the closed-loop code, checked
against the recorded data.

Why (2026-10-29, data/te_retag_2026-10-29.json): every measurement is a field transmitter feeding the DCS, but the
sheets drew FI-101 next to FIC-101, which a controls reader takes for a local gauge. The transmitters become FT, PT,
LT, TT, AT and JT (journal entry 61).

What it edits: the SOURCE files that name these tags (the model, the drawing and display layouts, tour cards, hazard
citations, HMI unit lists, tests and current-state docs). Generated outputs are rebuilt by scripts/pipeline.py from
the corrected model, never edited here. The journal and dated results stay as written; they describe revision A.
Each renamed instrument or final element keeps its old tag as `former_tag`, so older evidence can still be joined
to it. An item renamed twice keeps the tag it had just before this rename.

Refuses when a new tag already exists in the model, when the mapping is not one-to-one, or when a file listed in
the mapping no longer mentions any old tag (a sign the mapping is out of date). Exact whole-tag matches only, in
both printed forms ("FV-201" and "FV 201").

Usage: python scripts/retag_te_valves.py [--mapping data/te_retag_2026-10-29.json] [--write]
       (without --write: report what would change)
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAPPING = ROOT / "data" / "te_retag_2026-10-28.json"
MODEL = ROOT / "data" / "te_process_model.json"


def load_mapping(path=MAPPING):
    m = json.loads(path.read_text(encoding="utf-8"))
    old_to_new = m["map"]
    if len(set(old_to_new.values())) != len(old_to_new):
        raise SystemExit("mapping is not one-to-one")
    if set(old_to_new) & set(old_to_new.values()):
        raise SystemExit("an old tag is also a new tag; the rename would chain")
    return m, old_to_new


def pattern(old_to_new):
    alts = "|".join(re.escape(t).replace(r"\-", "[- ]") for t in sorted(old_to_new, key=len, reverse=True))
    return re.compile(rf"(?<![A-Z0-9])({alts})(?![0-9])")


def rename_text(text, old_to_new, rx):
    def sub(mo):
        found = mo.group(1)
        sep = found[len(found.rstrip("0123456789")) - 1]
        new = old_to_new[found.replace(" ", "-")]
        return new.replace("-", sep)
    return rx.subn(sub, text)


def rename_model(model, old_to_new):
    """Rename tag fields in the model and keep the old tag as former_tag on each renamed item."""
    items = model["instruments"] + model["final_elements"]
    existing = {i["tag"] for i in items}
    clash = sorted(set(old_to_new.values()) & existing)
    if clash:
        raise SystemExit(f"new tags already in the model: {clash}")
    for it in items:
        if it["tag"] in old_to_new:
            it["former_tag"] = it["tag"]
            it["tag"] = old_to_new[it["tag"]]
    return model


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--mapping", default=str(MAPPING.relative_to(ROOT)))
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    mapping, old_to_new = load_mapping(ROOT / args.mapping)
    rx = pattern(old_to_new)
    total = 0
    for rel in mapping["files"]:
        path = ROOT / rel
        text = path.read_text(encoding="utf-8")
        if rel == "data/te_process_model.json":
            before = json.loads(text)
            renamed = {it["tag"] for it in before["instruments"] + before["final_elements"] if it["tag"] in old_to_new}
            model = rename_model(before, old_to_new)
            new_text, n = rename_text(json.dumps(model, indent=2, ensure_ascii=True) + "\n", old_to_new, rx)
            # former_tag must keep the tag this rename replaced: restore it after the textual pass, on the renamed
            # items only (an item renamed on an earlier date keeps that earlier former_tag).
            model = json.loads(new_text)
            new_to_old = {nw: o for o, nw in old_to_new.items() if o in renamed}
            for it in model["instruments"] + model["final_elements"]:
                if it["tag"] in new_to_old:
                    it["former_tag"] = new_to_old[it["tag"]]
            meta = model["meta"]
            meta["tag_convention"] = mapping["model_tag_convention"]
            new_text = json.dumps(model, indent=2, ensure_ascii=True) + "\n"
        else:
            new_text, n = rename_text(text, old_to_new, rx)
        if n == 0 and rx.search(text) is None:
            raise SystemExit(f"{rel}: mentions none of the old tags; is the mapping out of date?")
        total += n
        print(f"{rel}: {n} replacement(s)")
        if args.write:
            path.write_text(new_text, encoding="utf-8", newline="\n")
    print(f"{total} replacement(s) in {len(mapping['files'])} file(s){'' if args.write else ' (dry run)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
