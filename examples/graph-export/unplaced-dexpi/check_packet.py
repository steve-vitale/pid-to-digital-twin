"""Offline regression and optional pinned-original checks. Standard library only; no network."""
import argparse
import contextlib
import copy
import hashlib
import io
import json
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "scripts"))
import graph_export as gx
import statements


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def attrs(node):
    return {a["name"]: a for a in node["attributes"]}


def check_case(case):
    model_path = HERE / case["model"]
    model = read_json(model_path)
    graph = gx.build(model_path)
    require(graph == read_json(HERE / case["graph"]), case["id"] + ": graph differs from committed expectation")
    require(not gx.problems(graph), case["id"] + ": " + "; ".join(gx.problems(graph)))
    rendered, _, _ = statements.build(graph)
    identities = {s["subject"]: s for s in rendered if s["predicate"] == "kind"}
    nodes = {n["id"]: n for n in graph["nodes"]}
    expected = case["expected"]
    for tag, values in expected["unplaced"].items():
        source_item = next(u for u in model["unplaced"] if u["tag"] == tag)
        node = nodes[tag]
        require(all(source_item.get(k) == v for k, v in values.items()), tag + ": reader fields changed")
        require(node["kind"] == values["kind"], tag + ": known role lost")
        require(node["placement"] == values["unit_basis"], tag + ": placement uncertainty lost")
        require(node["status"] == "unverified", tag + ": invented verification")
        a = attrs(node)
        require(a["dexpi_id"]["value"] == values["dexpi_id"], tag + ": original identity lost")
        require(a["unit"]["value"] is None, tag + ": owning unit invented")
        require(a["unplaced_reason"]["value"] == source_item["unplaced_reason"], tag + ": unresolved reason lost")
        require(all(a[k]["source"]["document"] == source_item["source"] for k in ("dexpi_id", "kind", "unit_basis")),
                tag + ": original source lost")
        require(identities[tag]["object"] == values["kind"] and
                expected["identity_phrases"][tag] in identities[tag]["text"], tag + ": statement role lost")
        require(not any(e["type"] in ("contains", "measures", "acts_on", "protects") and
                        tag in (e["from"], e["to"]) for e in graph["edges"]), tag + ": owning relation invented")
    controls = [e for e in graph["edges"] if e["type"] == "controls"]
    require(sorted([[e["from"], e["to"]] for e in controls]) == sorted(expected["controls"]),
            case["id"] + ": controller references lost or invented")
    for e in controls:
        require(e["status"] == "unverified" and e["direction"] is None, "reference made operationally verified")
        require(e["source"]["document"] == model["controllers"][0]["source"], "controller source lost")
    for controller, fields in expected.get("controller_fields", {}).items():
        a = attrs(nodes[controller])
        require(all(a[k]["value"] == value for k, value in fields.items()), "unresolved reference claims lost")
    return model, graph


def mutation_checks(model):
    """Synthetic mutations of the public model; these are guards, not original-source observations."""
    work = HERE / ".work"
    work.mkdir(exist_ok=True)
    refused = 0
    with tempfile.TemporaryDirectory(prefix="controls-", dir=work) as tmp:
        inp, out = Path(tmp) / "model.json", Path(tmp) / "graph.json"

        def put(m):
            inp.write_text(json.dumps(m), encoding="utf-8")

        mutations = []
        for value in ("ABSENT", "FT-04", ["FV-04", None], {"tag": "FV-04"}, 1):
            m = copy.deepcopy(model)
            m["controllers"][0]["output_unplaced"] = value
            mutations.append(m)
        m = copy.deepcopy(model)
        m["unplaced"].append(copy.deepcopy(m["unplaced"][0]))
        mutations.append(m)  # ambiguous duplicated target, even though the string names an existing tag
        for m in mutations:
            put(m)
            out.write_bytes(b"previous graph must survive\n")
            before = {p.name: p.read_bytes() for p in Path(tmp).iterdir()}
            with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                code = gx.main([str(inp), "--out", str(out)])
            require(code == 1, "invalid controller reference was not refused")
            require(before == {p.name: p.read_bytes() for p in Path(tmp).iterdir()}, "refusal altered an input/output")
            refused += 1
        m = copy.deepcopy(model)
        m["controllers"] = []
        m["unplaced"][0]["kind"] = "unknown_role"
        m["unplaced"][0]["dexpi_class"] = "OperatedValve"
        m["unplaced"][1].pop("kind")
        m["unplaced"][1]["actuated"] = True
        legacy = copy.deepcopy(m["unplaced"][0])
        legacy.update(tag="LEGACY-CLASS", dexpi_class="OperatedValve")
        legacy.pop("kind")
        m["unplaced"].append(legacy)
        put(m)
        nodes = {n["id"]: n for n in gx.build(inp)["nodes"]}
        require(nodes["FV-04"]["kind"] == "line_item", "explicit unknown role reinterpreted")
        require(attrs(nodes["FV-04"])["kind"]["value"] == "unknown_role", "unknown role claim lost")
        require(nodes["FT-04"]["kind"] == "final_element", "legacy no-role fallback changed")
        require(nodes["LEGACY-CLASS"]["kind"] == "final_element", "legacy operated-class fallback changed")
        require(nodes["FV-04"]["placement"] == m["unplaced"][0]["unit_basis"], "unknown placement erased")
    return refused


def verify_original(case, packet):
    import dexpi_reader
    path = ROOT / case["original"]["cache_path"]
    require(path.is_file(), "original unavailable: run python scripts/fetch_corpus.py dexpi-ttc-all")
    require(path.stat().st_size == case["original"]["bytes"] and sha(path) == case["original"]["sha256"],
            case["id"] + ": original byte pin differs; refusing source verification")
    root = ET.parse(path).getroot()
    for el in root.iter():
        if isinstance(el.tag, str):
            el.tag = el.tag.split("}")[-1]
    by_id = {}
    for el in root.iter():
        if el.get("ID"):
            require(el.get("ID") not in by_id, "ambiguous original ID")
            by_id[el.get("ID")] = el
    lines = path.read_text(encoding="utf-8").splitlines()
    for assertion in case["xml_assertions"]:
        el = by_id.get(assertion["id"])
        require(el is not None and el.tag == assertion["tag"], "original ID/class locator differs")
        require(all(el.get(k) == v for k, v in assertion["attributes"].items()), "original XML attribute differs")
        require(re.search(r'\bID="' + re.escape(assertion["id"]) + r'"', lines[assertion["line"] - 1]),
                "original physical line locator differs")
        assoc = [[a.get("Type"), a.get("ItemID")] for a in el.findall("Association")]
        require(assoc == assertion["associations"], "original associations differ")
        for k, value in assertion.get("generic_attributes", {}).items():
            require(any(g.get("Name") == k and g.get("Value") == value
                        for g in el.findall("./GenericAttributes/GenericAttribute")), "original generic attribute differs")
    model = dexpi_reader.Reader(path, attribution=packet["attribution"]).read()
    require(model == read_json(HERE / case["model"]), case["id"] + ": complete regenerated reader model differs")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="run the default offline fixture checks explicitly")
    ap.add_argument("--verify-originals", action="store_true", help="require the already fetched pinned XML and LICENSE")
    args = ap.parse_args()
    packet = read_json(HERE / "source_key.json")
    before = {p.name: sha(p) for p in HERE.iterdir() if p.is_file()}
    for case in packet["cases"]:
        check_case(case)
    refused = mutation_checks(read_json(HERE / packet["cases"][0]["model"]))
    print(f"PASS: {len(packet['cases'])} complete derived models reproduce exact graphs; types, references, sources, statements and unknown placement retained")
    print(f"PASS: {refused} synthetic refusal controls preserve existing output; explicit unknown and legacy fallback retained")
    if args.verify_originals:
        license_path = ROOT / packet["license"]["cache_path"]
        require(license_path.is_file() and sha(license_path) == packet["license"]["sha256"], "pinned original LICENSE unavailable or changed")
        for case in packet["cases"]:
            verify_original(case, packet)
        print("PASS: both original byte pins, exact primary XML locators and complete reader regeneration; pinned LICENSE present")
    else:
        print("NOT CHECKED: original XML bytes/locators; add --verify-originals after the documented fetch")
    require(before == {p.name: sha(p) for p in HERE.iterdir() if p.is_file()}, "packet inputs changed")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, StopIteration, ET.ParseError) as exc:
        print("FAIL:", exc, file=sys.stderr)
        sys.exit(1)
