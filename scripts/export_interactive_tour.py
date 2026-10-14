"""Proof of concept: export the data the interactive browser tour (drafts/interactive-tour/) is built from.

Nothing here is a new source of truth. Every field is read from the files the Blender tour and the Ignition / PI AF
builds already use, through the same functions:
  data/te_process_model.json        units, streams, tags (the twin contract), via build_3d_scene.build_scene
  data/te_display_layout.json       symbol kind per unit, tag associations (display_contract checks it first)
  data/te_unit_purposes.json        the purpose sentence per unit and its teprob.f citations
  data/te_tour_cards.json           the tour's short function line per equipment kind
  data/hazard_citations_prototype.json   the public-incident citation each Blender stop shows
  out/ignition/normal_bands.json, out/ignition/gateway/build_meta.json   normal bands and published alarm setpoints
  out/ignition/gateway/twin_provider.json, out/pi/pi_builder_af.csv     the Ignition tag path and PI AF path per tag
  data/external/te-braatz/d00_te.dat, d06_te.dat   the recorded Braatz replays (downloaded, not redistributed)
  scripts/blender_tour_template.py  the flow legend's service colours (read as text, never executed)

Output: out/interactive_tour/tour_data.json (regenerable, ignored by git because it carries replay values).
The Node build (drafts/interactive-tour/build.mjs) turns it into the page; drafts/interactive-tour/verify.mjs then
checks the page against the raw files independently of this script.

Model use: none at run time. Written with AI assistance; not reviewed by an operator.

  python scripts/fetch_te_data.py              # the two replay files, checksum-verified
  python scripts/export_interactive_tour.py
"""
import argparse
import ast
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "ignition"))
import build_3d_scene as B  # noqa: E402
import orientation_tour as O  # noqa: E402
import verify_3d_render as V  # noqa: E402
from te_channels import channel_columns  # noqa: E402

FAULT_START = 160          # IDV(6) switches on at sample 160 of 960 in the Braatz test files
MINUTES_PER_SAMPLE = 3
RUNS = {"normal": ("d00_te.dat", "Normal operation (Braatz d00_te.dat)"),
        "fault6": ("d06_te.dat", "Fault 6, loss of A feed, from sample 160 (Braatz d06_te.dat)")}
ENERGY = {"bl": "process fluid at feed or battery-limit pressure", "motor": "electrical (motor)",
          "agitator": "electrical (agitator motor)", "utility": "utility fluid (cooling water or steam)"}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def sig(v, digits=6):
    """A replay value kept to six significant figures: enough that every band and alarm comparison the repo makes
    on the raw value gives the same answer (checked below), small enough for a page."""
    if not isinstance(v, (int, float)) or not math.isfinite(v):
        return None
    return float(f"{v:.{digits}g}")


def service_colors(template_path):
    """SERVICE_COLORS from the Blender tour template, parsed as a literal (the template imports bpy; it is not run)."""
    tree = ast.parse(Path(template_path).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "SERVICE_COLORS" for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError("SERVICE_COLORS not found in %s" % template_path)


def read_rows(path):
    return [list(map(float, line.split())) for line in Path(path).read_text().splitlines() if line.strip()]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(ROOT / "out/interactive_tour/tour_data.json"))
    ap.add_argument("--replays", default=str(ROOT / "data/external/te-braatz"))
    args = ap.parse_args(argv)

    files = {
        "model": "data/te_process_model.json", "layout": "data/te_display_layout.json",
        "purposes": "data/te_unit_purposes.json", "cards": "data/te_tour_cards.json",
        "hazards": "data/hazard_citations_prototype.json", "bands": "out/ignition/normal_bands.json",
        "meta": "out/ignition/gateway/build_meta.json", "provider": "out/ignition/gateway/twin_provider.json",
        "pi": "out/pi/pi_builder_af.csv", "pi_descriptions": "out/pi/attribute_descriptions.csv",
        "colors": "scripts/blender_tour_template.py",
    }
    replay_files = {run: Path(args.replays) / name for run, (name, _) in RUNS.items()}
    missing = [str(p) for p in replay_files.values() if not p.is_file()]
    if missing:
        print("missing replay files (python scripts/fetch_te_data.py): " + ", ".join(missing))
        return 2

    model, layout, bands, alarms, replay6 = B.load_inputs(ROOT / files["model"], ROOT / files["layout"],
                                                          ROOT / files["bands"], ROOT / files["meta"],
                                                          replay_files["fault6"])
    hazards = json.loads((ROOT / files["hazards"]).read_text(encoding="utf-8"))
    purposes = O.load_purposes(ROOT / files["cards"], ROOT / files["purposes"])
    scene = B.build_scene(model, layout, bands, alarms, replay6, [150, 200, 258], FAULT_START)
    full = B.tour_scene(scene, model, layout, bands, alarms, replay6, hazards, FAULT_START, purposes=purposes)

    provider, _ = V.ignition_provider_index(json.loads((ROOT / files["provider"]).read_text(encoding="utf-8")))
    pi, _ = V.pi_index((ROOT / files["pi"]).read_text(encoding="utf-8-sig"),
                       (ROOT / files["pi_descriptions"]).read_text(encoding="utf-8-sig"))
    colors = service_colors(ROOT / files["colors"])
    columns = channel_columns(model)
    stops = {s["unit"]: s for s in full["tour_script"]["stops"]}
    labels = layout.get("labels", {})

    units = []
    for e in full["equipment"]:
        u = next(x for x in model["units"] if x["id"] == e["id"])
        stop = stops.get(e["id"], {})
        p = stop.get("purpose") or {}
        c = stop.get("citation")
        units.append({
            "id": e["id"], "name": e["name"], "kind": e["kind"], "plan": [u["layout"]["x"], u["layout"]["y"]],
            "plan_basis": "2D seed-layout position (relative arrangement of the 2D screen, not a plot plan)",
            "purpose": p.get("purpose"), "citations": p.get("citations", []), "function": p.get("function"),
            "inferred": p.get("inferred", []), "key_tags": e["key_tags"], "flow_text": stop.get("caption_flow"),
            "hazard": None if not c else {k: c.get(k) for k in ("title", "agency", "year", "url", "caption", "hazard")},
            "verification": e["verification"],
        })

    flow_tag = {}
    for i in model["instruments"]:
        if i.get("variable") == "flow" and i.get("stream"):
            flow_tag.setdefault(i["stream"], i["tag"])
    streams = []
    for p in full["pipes"]:
        s = next(x for x in model["streams"] if x["id"] == p["id"])
        streams.append({"id": s["id"], "name": s["name"], "from": s["from"], "to": s["to"],
                        "direction": s.get("direction"), "directed": p["directed"], "direction_basis": p["direction_basis"],
                        "service": p["service"], "service_basis": p["service_basis"], "flow_tag": flow_tag.get(s["id"]),
                        "verification": s.get("verification", {}).get("status", "unverified")})

    utilities = [{"id": u["id"], "tag": u["tag"], "unit": u["unit"], "role": u["role"], "service": u["service"],
                  "basis": u["basis"]} for u in full["utilities"]]

    tags = []
    for m in full["markers"]:
        item = next(i for i in model["instruments"] + model["final_elements"] if i["tag"] == m["tag"])
        op, sd = O.split_limits(m["tag"], alarms)
        band = bands.get(m["tag"])
        tags.append({
            "tag": m["tag"], "kind": m["kind"], "unit": m["unit"], "stream": m["model_stream"],
            "variable": item.get("variable"), "uom": O.disp_uom(m["uom"]), "description": m["description"],
            "label": O._short(m, labels), "connected": m["connected"], "disputed": m["disputed"],
            "attach": m["attach"], "placement_basis": m["placement_basis"],
            "column": columns.get(m["tag"]) if m["connected"] else None,
            "band": None if not band else {k: band[k] for k in ("lo", "hi", "mean")},
            "alarms": {"operating_high": max(op) if op else None, "shutdown_high": min(sd) if sd else None,
                       "all": alarms.get(m["tag"], [])},
            "ignition_path": (provider.get(m["tag"]) or {}).get("path"),
            "pi_path": (pi.get(m["tag"]) or {}).get("path"),
        })

    runs, mismatches = {}, []
    for run, path in replay_files.items():
        rows = read_rows(path)
        values = {}
        for t in tags:
            if t["column"] is None:
                continue
            raw = [r[t["column"]] for r in rows]
            values[t["tag"]] = [sig(v) for v in raw]
            # The page classifies the rounded values; prove they classify like the raw ones on every sample.
            lim = [a["setpointA"] for a in t["alarms"]["all"]]
            for k, (a, b) in enumerate(zip(raw, values[t["tag"]])):
                if (any(a > x for x in lim) != any(b > x for x in lim)) or (
                        t["band"] and (t["band"]["lo"] <= a <= t["band"]["hi"]) != (t["band"]["lo"] <= b <= t["band"]["hi"])):
                    mismatches.append((run, t["tag"], k))
        runs[run] = {"file": "data/external/te-braatz/" + path.name, "sha256": sha256(path), "title": RUNS[run][1],
                     "samples": len(rows), "values": values}
    if mismatches:
        raise SystemExit("rounding changed a band or alarm state: %s" % mismatches[:5])

    def first_alarm(run):
        """First sample at which any tag is above an operating high alarm (the published setpoints only)."""
        for k in range(runs[run]["samples"]):
            hits = [t["tag"] for t in tags if t["tag"] in runs[run]["values"] and t["alarms"]["operating_high"] is not None
                    and runs[run]["values"][t["tag"]][k] is not None
                    and runs[run]["values"][t["tag"]][k] > t["alarms"]["operating_high"]]
            if hits:
                return {"sample": k, "tags": hits, "minutes_after_fault": (k - FAULT_START) * MINUTES_PER_SAMPLE}
        return None

    loto = []
    for p in full["loto_mockup"]["points"]:
        kind, ref = p["point"].split(":", 1)
        target = ({"stream": ref} if kind == "bl" else {"unit": ref} if kind in ("motor", "agitator")
                  else {"utility": ref})
        loto.append({"n": p["n"], "id": p["point"], "text": p["text"].rstrip("*"), "kind": kind,
                     "energy": ENERGY[kind], "target": target, "basis": p["basis"]})

    service_labels = dict(O.SERVICE_LABELS)
    service_labels.update({"cooling_water_supply": "cooling water supply (inferred)",
                           "cooling_water_return": "cooling water return (inferred)", "process": "process"})
    used = sorted({s["service"] for s in streams} | {u["service"] for u in utilities})
    data = {
        "schema": "pid-interactive-tour-data/0 (proof of concept)",
        "title": model["meta"]["title"], "model_id": model["meta"]["model_id"],
        "sources": {k: {"path": v, "sha256": sha256(ROOT / v)} for k, v in files.items()},
        "badge": O.BADGE, "disclaimer": full["disclaimer"], "full_disclaimer": O.FULL_DISCLAIMER,
        "purposes_note": json.loads((ROOT / files["purposes"]).read_text(encoding="utf-8"))["note"],
        "cards_note": purposes.get("source"), "inferred_note": purposes.get("inferred_note"),
        "hazard_status": hazards["status"], "hazard_wording_rule": hazards["wording_rule"],
        "tour_order": [t["unit"] for t in full["tour"]], "tour_order_basis": full["tour_order_basis"],
        "units": units, "streams": streams, "utilities": utilities, "tags": tags,
        "services": {s: {"rgb": [round(c, 3) for c in colors.get(s, colors["process"])[:3]], "label": service_labels.get(s, s)}
                     for s in used},
        "states": list(B.STATES),
        "loto": {"status": full["loto_mockup"]["status"], "points": loto},
        "replay": {"fault_start_sample": FAULT_START, "minutes_per_sample": MINUTES_PER_SAMPLE, "runs": runs,
                   "first_alarm": {r: first_alarm(r) for r in runs}},
        "fault_profile": full["tour_script"]["fault_profile"],
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    fa = data["replay"]["first_alarm"]
    print("wrote %s: %d units, %d streams, %d utilities, %d tags (%d with replay), %d LOTO points; first alarm: "
          "normal %s, fault6 %s" % (out.relative_to(ROOT).as_posix(), len(units), len(streams), len(utilities), len(tags),
                                    sum(1 for t in tags if t["column"] is not None), len(loto),
                                    fa["normal"] and fa["normal"]["sample"], fa["fault6"] and fa["fault6"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
