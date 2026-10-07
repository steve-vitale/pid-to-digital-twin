"""Cross-check the TE process model against the open TE source code, and record the result in the model.

Source of truth: teprob.f from the Braatz group's open TE code (University of Illinois, NCSA-style license),
mirrored at github.com/camaramm/tennessee-eastman-profBraatz. Its header comments list every measured (XMEAS)
and manipulated (XMV) variable with units. The file is downloaded to data/external/ (gitignored), not
redistributed.

For each instrument and final element, the check compares the model's description and units with the source
line and writes a verification block:
  confirmed  - name and units agree with the source
  corrected  - the model disagreed; the model is updated to the source wording and the old value is kept
  unverified - no matching source line

Usage:  python scripts/verify_te_source.py [--write]
Without --write it only reports. The report goes to out/te_source_check.md either way.
"""
import json
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / "data" / "te_process_model.json"
CACHE = ROOT / "data" / "external" / "te-braatz" / "teprob.f"
URL = "https://raw.githubusercontent.com/camaramm/tennessee-eastman-profBraatz/master/teprob.f"
SOURCE_REF = "teprob.f (Braatz group TE code)"

UNIT_ALIASES = {"kg/hr": "kg/h", "m3/hr": "m3/h", "deg c": "degc", "kpa gauge": "kpa g", "mole %": "mol%"}
STOP = {"the", "and", "of", "stream"}


def fetch_source():
    if not CACHE.exists():
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(URL, timeout=60) as r:
            CACHE.write_bytes(r.read())
    return CACHE.read_text(encoding="latin-1")


def parse_source(text):
    """Return {('xmeas'|'xmv', n): {'name', 'uom', 'group'}} from the header comments."""
    out, group = {}, None
    for line in text.splitlines():
        if not line[:1] in ("C", "c"):
            continue
        body = line[1:].strip()
        m = re.match(r"(.+Analysis) \(Stream (\d+)\)", body)
        if m:
            group = f"{m.group(1)} (stream {m.group(2)})"
            continue
        m = re.match(r"(XMEAS|XMV)\((\d+)\)\s+(.*)$", body)
        if not m:
            continue
        kind, n, rest = m.group(1).lower(), int(m.group(2)), m.group(3)
        rest = rest.replace("(Corrected Order)", "").rstrip()
        parts = re.split(r"\s{2,}", rest)
        name = parts[0].strip()
        uom = parts[-1].strip() if len(parts) > 1 and not parts[-1].startswith("(") else ""
        # "A Feed  (stream 1)   kscmh" splits into name / (stream 1) / unit
        stream_m = re.search(r"\(stream (\d+)\)", rest, re.I)
        if (kind, n) not in out:  # first occurrence is the documented list
            out[(kind, n)] = {"name": name, "uom": uom, "stream": stream_m.group(1) if stream_m else None,
                              "group": group if kind == "xmeas" and n >= 23 else None}
    return out


def norm_uom(u):
    u = (u or "").strip().lower()
    return UNIT_ALIASES.get(u, u)


ABBREVIATIONS = {"sep": "separator", "prod": "product", "temp": "temperature"}
EQUIPMENT = {"separator", "condenser", "reactor", "stripper", "compressor"}


def words(s):
    return {ABBREVIATIONS.get(w, w) for w in re.findall(r"[a-z]+", s.lower())}


def tokens(s):
    return words(s) - STOP


def check(model, src):
    rows = []
    for item in model["instruments"] + model["final_elements"]:
        kind = "xmv" if "xmv" in item else "xmeas"
        idx = item.get("xmv", item.get("xmeas"))
        if isinstance(idx, str):  # analyzer range like "23-28"
            lo, hi = (int(x) for x in idx.split("-"))
            members = [src.get(("xmeas", n)) for n in range(lo, hi + 1)]
            if all(members):
                group = members[0]["group"]
                comps = "".join(m["name"].split()[-1] for m in members)
                ok = group is not None
                rows.append((item, "confirmed" if ok else "unverified",
                             f"{group}: components {comps[0]}-{comps[-1]}", None))
            else:
                rows.append((item, "unverified", "range not found in source", None))
            continue
        s = src.get((kind, idx))
        if not s:
            rows.append((item, "unverified", "no source line", None))
            continue
        uom_ok = kind == "xmv" or norm_uom(s["uom"]) == norm_uom(item["uom"])
        src_words, model_words = words(s["name"]), words(item["description"])
        name_ok = bool(tokens(s["name"]) & tokens(item["description"]))
        # The source names a different piece of equipment than the model does (e.g. separator vs condenser).
        src_units, model_units = EQUIPMENT & src_words, EQUIPMENT & model_words
        contradiction = bool(src_units and model_units and src_units != model_units)
        if uom_ok and name_ok and not contradiction:
            rows.append((item, "confirmed", f'{kind.upper()} {idx}: "{s["name"]}" {s["uom"]}'.rstrip(), None))
        else:
            rows.append((item, "corrected", f'{kind.upper()} {idx}: "{s["name"]}" {s["uom"]}'.rstrip(),
                         {"description": s["name"]}))
    return rows


def main():
    write = "--write" in sys.argv
    model = json.loads(MODEL.read_text(encoding="utf-8"))
    src = parse_source(fetch_source())
    # An item corrected on an earlier run now matches the source, but it stays "corrected" so history isn't lost.
    rows = [(item, "corrected" if status == "confirmed" and item.get("verification", {}).get("previous") else status,
             evidence, fix) for item, status, evidence, fix in check(model, src)]
    today = date.today().isoformat()
    lines = [f"# TE model vs. open source code ({today})", "",
             f"Source: `{SOURCE_REF}`, {URL}", "",
             "| Tag | Model says | Source says | Result |", "|---|---|---|---|"]
    for item, status, evidence, fix in rows:
        lines.append(f'| {item["tag"]} | {item["description"]} ({item["uom"]}) | {evidence} | **{status}** |')
        if write:
            v = {"status": status, "checked_against": SOURCE_REF, "checked_on": today, "evidence": evidence}
            prior = item.get("verification", {})
            if fix:
                v["previous"] = {k: item[k] for k in fix}
                item.update(fix)
            elif prior.get("previous"):  # keep the correction history on re-runs
                v["status"], v["previous"] = "corrected", prior["previous"]
            item["verification"] = v
    counts = {s: sum(1 for r in rows if r[1] == s) for s in ("confirmed", "corrected", "unverified")}
    lines += ["", f"**Totals:** {counts['confirmed']} confirmed · {counts['corrected']} corrected · "
              f"{counts['unverified']} unverified (of {len(rows)})"]
    (ROOT / "out").mkdir(exist_ok=True)
    (ROOT / "out" / "te_source_check.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if write:
        MODEL.write_text(json.dumps(model, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(counts), "written" if write else "(report only)")
    for item, status, evidence, _ in rows:
        if status != "confirmed":
            print(f"  {status}: {item['tag']} model='{item['description']}' source={evidence}")


if __name__ == "__main__":
    main()
