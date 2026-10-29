"""Generate docs/TRIED.md: what this project tried for each function, what happened, what was kept or rejected, and
what has not been tried yet, from the ledger in data/attempts.json.

    python scripts/attempts_ledger.py            # write docs/TRIED.md
    python scripts/attempts_ledger.py --check    # exit 1 if docs/TRIED.md is stale, an attempt is missing a field,
                                                 # a verdict or status is unknown, an id repeats, a function is
                                                 # unknown, or a source link points at a file or heading that is gone

Every attempt and every not-yet-tried idea cites its source as a repository-relative link ("docs/JOURNAL.md#44-..."
or "out/trace_variants_dev.md"). A heading anchor is checked against the target file's headings, slugged the way
GitHub slugs them. Stdlib only.
"""
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "attempts.json"
OUT = ROOT / "docs" / "TRIED.md"
VERDICTS = {
    "kept": "adopted, and still how the project works",
    "rejected": "tried and measured, then not adopted",
    "superseded": "adopted at the time, later replaced (the replacement is usually the next row)",
    "inconclusive": "measured, but no decision rests on it: a measurement round, a diagnostic, or a difference "
                    "within noise",
}
STATUSES = {
    "rejected-untested": "rejected on reasoning, never run",
    "not-done": "named in the docs as a next step or a gap, not done",
    "open-question": "a question the sources leave open",
}
ATTEMPT_FIELDS = ("id", "function", "date", "change", "hypothesis", "evidence", "runs", "verdict", "why", "source")
NOT_TRIED_FIELDS = ("id", "function", "status", "idea", "why_not_yet", "source")


def slug(heading):
    """GitHub's heading anchor: lower case, punctuation dropped (word characters, hyphens and spaces kept), spaces
    to hyphens."""
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", heading.strip().lower())
    s = re.sub(r"[^\w\- ]", "", s)
    return s.replace(" ", "-")


_ANCHORS = {}


def anchors(path):
    if path not in _ANCHORS:
        found, seen, fence = {}, Counter(), False
        for line in (ROOT / path).read_text(encoding="utf-8").splitlines():
            if line.lstrip().startswith("```"):
                fence = not fence
            m = None if fence else re.match(r"^#{1,6}\s+(.*?)\s*#*\s*$", line)
            if m:
                base = slug(m.group(1))
                found[base if not seen[base] else f"{base}-{seen[base]}"] = m.group(1)
                seen[base] += 1
        _ANCHORS[path] = found
    return _ANCHORS[path]


def source_problems(where, sources):
    if not isinstance(sources, list) or not sources:
        return [f"{where}: source must be a non-empty list of repository-relative links"]
    out = []
    for s in sources:
        if not isinstance(s, str) or not s.strip():
            out.append(f"{where}: empty source")
            continue
        path, _, frag = s.partition("#")
        if path.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", path) or ".." in Path(path).parts:
            out.append(f"{where}: source {s!r} must be relative to the repository root")
        elif not (ROOT / path).is_file():
            out.append(f"{where}: source file {path} does not exist")
        elif frag and path.endswith(".md") and frag not in anchors(path):
            out.append(f"{where}: no heading in {path} has the anchor #{frag}")
    return out


def problems(led):
    out = []
    funcs = led.get("functions") or {}
    if not isinstance(funcs, dict) or not funcs:
        return ["data/attempts.json: 'functions' must map function ids to titles"]
    ids = Counter(x.get("id") for x in led.get("attempts", []) + led.get("not_tried", []))
    out += [f"id {i} is used {n} times" for i, n in sorted(ids.items(), key=str) if n > 1]
    for x in led.get("attempts", []):
        w = f"attempt {x.get('id', '?')}"
        missing = [k for k in ATTEMPT_FIELDS if k not in x or (k != "hypothesis" and x[k] in (None, "", []))]
        out += [f"{w}: missing {k}" for k in missing]
        if not re.fullmatch(r"A\d{3}", str(x.get("id"))):
            out.append(f"{w}: id must look like A001")
        if x.get("function") not in funcs:
            out.append(f"{w}: unknown function {x.get('function')!r}")
        if "verdict" in x and x["verdict"] not in VERDICTS:
            out.append(f"{w}: verdict {x['verdict']!r} is not one of {', '.join(VERDICTS)}")
        if "date" in x:
            try:
                date.fromisoformat(str(x["date"]))
            except ValueError:
                out.append(f"{w}: date {x['date']!r} is not YYYY-MM-DD")
        if "source" in x:
            out += source_problems(w, x["source"])
    for x in led.get("not_tried", []):
        w = f"not-tried {x.get('id', '?')}"
        out += [f"{w}: missing {k}" for k in NOT_TRIED_FIELDS if not x.get(k)]
        if not re.fullmatch(r"N\d{3}", str(x.get("id"))):
            out.append(f"{w}: id must look like N001")
        if x.get("function") not in funcs:
            out.append(f"{w}: unknown function {x.get('function')!r}")
        if "status" in x and x["status"] not in STATUSES:
            out.append(f"{w}: status {x['status']!r} is not one of {', '.join(STATUSES)}")
        if "source" in x:
            out += source_problems(w, x["source"])
    return out


def single_run(runs):
    m = re.match(r"\s*(\d+)\b", str(runs))
    return bool(m) and int(m.group(1)) == 1


def cell(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def link(src):
    path, _, frag = src.partition("#")
    m = re.match(r"(\d+)-", frag) if path == "docs/JOURNAL.md" else None
    if m:
        label = f"journal {m.group(1)}"
    elif frag:
        head = re.sub(r"\s*\(.*$", "", anchors(path).get(frag, frag))
        label = f"{Path(path).name}: {head if len(head) <= 40 else head[:39].rstrip() + '...'}"
    else:
        label = Path(path).name
    return f"[{cell(label)}](../{src})"


def render(led):
    funcs, att, nt = led["functions"], led["attempts"], led["not_tried"]
    lines = [
        "# What was tried, and what wasn't", "",
        "Generated by `scripts/attempts_ledger.py` from `data/attempts.json`; edit the ledger, not this page. "
        + led["about"], "",
        "Read this before tuning anything: if a variant is listed as rejected, the number that rejected it is here; "
        "if an idea is under *Not tried yet*, nobody has measured it, whatever its absence from the code suggests.", "",
        "**Verdicts**", "",
    ]
    lines += [f"- **{v}**: {d}." for v, d in VERDICTS.items()]
    lines += ["", "**Not tried yet** marks each idea as " + "; ".join(f"*{k}* ({d})" for k, d in STATUSES.items())
              + ". An idea rejected after it was measured is an attempt, not a not-tried item.", "",
              "**Single runs are flagged.** A *runs* cell that starts with 1 is one run (per tool, per holdout or per "
              "sweep step). Where a model call is involved, that number carries run-to-run noise: five runs of the "
              "declared method moved with a standard deviation of 1.4-1.9 review-load points, more than the ~1 point "
              "assumed earlier. Read a small single-run difference as a tie. Deterministic code (scorer controls, "
              "generators, checks) repeats exactly, but a single run still shows one input, not a sample.", "",
              "## Summary", "",
              "| Function | Attempts | kept | rejected | superseded | inconclusive | single-run | Not tried yet |",
              "|---|---|---|---|---|---|---|---|"]
    tot = Counter()
    for fid, title in funcs.items():
        rows = [x for x in att if x["function"] == fid]
        c = Counter(x["verdict"] for x in rows)
        c["n"], c["single"] = len(rows), sum(single_run(x["runs"]) for x in rows)
        c["nt"] = sum(x["function"] == fid for x in nt)
        tot.update(c)
        lines.append(f"| [{cell(title)}](#{slug(title)}) | {c['n']} | " + " | ".join(str(c[v]) for v in VERDICTS)
                     + f" | {c['single']} | {c['nt']} |")
    lines += [f"| **All** | **{tot['n']}** | " + " | ".join(f"**{tot[v]}**" for v in VERDICTS)
              + f" | **{tot['single']}** | **{tot['nt']}** |", ""]
    for fid, title in funcs.items():
        rows = [x for x in att if x["function"] == fid]
        lines += [f"## {title}", "", f"Function id `{fid}`.", ""]
        if rows:
            lines += ["| Id | Date | Change | Evidence | Runs | Verdict | Why | Source |",
                      "|---|---|---|---|---|---|---|---|"]
            for x in rows:
                runs = cell(x["runs"]) + (" **(single run)**" if single_run(x["runs"]) else "")
                change = cell(x["change"]) + (f" *Hypothesis:* {cell(x['hypothesis'])}" if x.get("hypothesis") else "")
                lines.append(f"| {x['id']} | {x['date']} | {change} | {cell(x['evidence'])} | {runs} | "
                             f"**{x['verdict']}** | {cell(x['why'])} | {', '.join(link(s) for s in x['source'])} |")
        else:
            lines.append("No attempts recorded.")
        todo = [x for x in nt if x["function"] == fid]
        lines += ["", "**Not tried yet**", ""]
        lines += [f"- {x['id']} *{x['status']}*: {x['idea']} {x['why_not_yet']} "
                  f"({', '.join(link(s) for s in x['source'])})" for x in todo] or ["- Nothing recorded."]
        lines.append("")
    return "\n".join(lines)


def load():
    return json.loads(DATA.read_text(encoding="utf-8"))


def main(argv):
    if "-h" in argv or "--help" in argv:  # print usage; never regenerate anything on a help request
        print(__doc__)
        return 0
    unknown = [x for x in argv if x != "--check"]
    if unknown:  # a typo such as --chek must not fall through to the write path
        print(f"unrecognized argument(s): {' '.join(unknown)}\nusage: attempts_ledger.py [--check]", file=sys.stderr)
        return 2
    led = load()
    bad = problems(led)
    text = render(led) if not bad else None
    if "--check" in argv:
        if not bad and (not OUT.exists() or OUT.read_text(encoding="utf-8") != text):
            bad.append("docs/TRIED.md is stale: run python scripts/attempts_ledger.py")
        for b in bad:
            print("FAIL:", b)
        print(f"{len(led.get('attempts', []))} attempts, {len(led.get('not_tried', []))} not tried; "
              f"{len(bad)} problem(s)")
        return 1 if bad else 0
    if bad:
        for b in bad:
            print("FAIL:", b)
        return 1
    OUT.write_text(text, encoding="utf-8", newline="\n")
    c = Counter(x["verdict"] for x in led["attempts"])
    print(f"wrote {OUT.relative_to(ROOT).as_posix()}: {len(led['attempts'])} attempts {dict(c)}, "
          f"{len(led['not_tried'])} not tried")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
