"""The deliverables matrix: what the TE track (process knowledge, no drawing) and the OPEN100 track (drawings, no
process data) can each deliver. docs/deliverables_matrix.json is the source; the README table is generated from it.

  python scripts/deliverables_matrix.py            # print the table
  python scripts/deliverables_matrix.py --write    # replace the table in README.md between its markers
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs" / "deliverables_matrix.json"
README = ROOT / "README.md"
START, END = "<!-- deliverables-matrix:start -->", "<!-- deliverables-matrix:end -->"
WORDS = {"done": "Done", "done_offline": "Done offline (not in a gateway)", "partial": "Partial", "draft": "Draft",
         "mockup": "Mockup", "synthetic_demo": "Synthetic demo", "not_done": "Not done yet",
         "not_possible": "Not possible", "not_applicable": "Not applicable"}


def load():
    return json.loads(MATRIX.read_text(encoding="utf-8"))


def problems(doc, root=ROOT):
    """Matrix rules: known statuses, a reason wherever something is not fully done, evidence that exists."""
    out = []
    for r in doc["rows"]:
        for t in ("te", "open100"):
            c = r[t]
            if c["status"] not in doc["statuses"] or c["status"] not in WORDS:
                out.append("%s / %s: unknown status %r" % (r["deliverable"], t, c["status"]))
            if c["status"] != "done" and not c.get("note", "").strip():
                out.append("%s / %s: %s needs a reason" % (r["deliverable"], t, c["status"]))
            if c["status"] in ("not_possible", "not_applicable") and c.get("evidence"):
                out.append("%s / %s: %s cannot cite evidence of being done" % (r["deliverable"], t, c["status"]))
            if c["status"] not in ("not_possible", "not_applicable") and not c.get("evidence"):
                out.append("%s / %s: %s needs evidence" % (r["deliverable"], t, c["status"]))
            for e in c.get("evidence", []):
                if not (root / e).exists():
                    out.append("%s / %s: evidence missing: %s" % (r["deliverable"], t, e))
    return out


def cell(c):
    text = "**%s**" % WORDS[c["status"]]
    if c.get("note"):
        text += ": " + c["note"]
    links = ["[%s](%s)" % (Path(e).name, e) for e in c.get("evidence", [])[:2]]
    if links:
        text += " (" + ", ".join(links) + ")"
    return text.replace("|", "\\|")


def markdown(doc):
    lines = ["| Deliverable | TE: process knowledge, no original drawing | OPEN100: drawings, no process data |",
             "|---|---|---|"]
    for r in doc["rows"]:
        lines.append("| %s | %s | %s |" % (r["deliverable"], cell(r["te"]), cell(r["open100"])))
    return "\n".join(lines)


def write_readme(doc):
    text = README.read_text(encoding="utf-8")
    a, b = text.index(START) + len(START), text.index(END)
    README.write_text(text[:a] + "\n" + markdown(doc) + "\n" + text[b:], encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    doc = load()
    bad = problems(doc)
    if bad:
        raise SystemExit("\n".join(bad))
    if a.write:
        write_readme(doc)
        print("README matrix updated")
    else:
        print(markdown(doc))


if __name__ == "__main__":
    main()
