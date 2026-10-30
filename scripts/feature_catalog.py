"""Generate docs/FEATURES.md: every feature by category with its evidence (guide, example outputs, tests,
independent reviews), labelled as a reviewed example only when a passing review still matches its outputs.

    python scripts/feature_catalog.py            # write docs/FEATURES.md and the README's use matrix
    python scripts/feature_catalog.py --check    # exit 1 on a structural problem or a stale docs/FEATURES.md
    python scripts/feature_catalog.py --hashes FEATURE   # print the hashes a review of FEATURE should record

Features live in data/features.json, reviews in data/reviews.json. A review records the sha256 (line endings
normalised) of every file it looked at; when a reviewed output changes, the review no longer counts and the feature
drops back to "needs review". Structural problems (a listed file missing, an unknown category, a tool in
data/script_index.json that belongs to no feature, a review naming an unknown feature) fail --check. Evidence gaps
don't fail it: they are listed on the page, in red, for anyone to see. Stdlib only.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FEATURES = ROOT / "data" / "features.json"
REVIEWS = ROOT / "data" / "reviews.json"
SCRIPT_INDEX = ROOT / "data" / "script_index.json"
OUT = ROOT / "docs" / "FEATURES.md"
README = ROOT / "README.md"
MARK = ("<!-- use-matrix:start -->", "<!-- use-matrix:end -->")


def file_hash(rel):
    return hashlib.sha256((ROOT / rel).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def load():
    feats = json.loads(FEATURES.read_text(encoding="utf-8"))
    reviews = json.loads(REVIEWS.read_text(encoding="utf-8"))["reviews"] if REVIEWS.exists() else []
    tools = json.loads(SCRIPT_INDEX.read_text(encoding="utf-8"))["scripts"]
    return feats, reviews, tools


def review_state(feature, reviews):
    """-> (state, review or None). state: proven / needs review / stale review / findings open."""
    mine = sorted((r for r in reviews if r["feature"] == feature["id"]), key=lambda r: r["date"])
    if not feature["example_outputs"]:
        return "no example output", None
    current = {p: file_hash(p) for p in feature["example_outputs"] if (ROOT / p).exists()}
    for r in reversed(mine):
        covered = all(r.get("files", {}).get(p) == h for p, h in current.items())
        if not covered:
            continue
        return ("proven" if r["verdict"] == "pass" else "findings open"), r
    return ("stale review" if mine else "needs review"), (mine[-1] if mine else None)


def gaps(feature, state):
    out = []
    if not feature["example_outputs"]:
        out.append("no committed example output")
    if not feature["tests"]:
        out.append("no test")
    if state != "proven" and feature["example_outputs"]:
        out.append(state)
    return out


def problems(feats, reviews, tools):
    out = []
    ids = [f["id"] for f in feats["features"]]
    out += [f"feature id {i!r} repeats" for i in sorted({i for i in ids if ids.count(i) > 1})]
    claimed = set()
    for f in feats["features"]:
        if f["category"] not in feats["categories"]:
            out.append(f"{f['id']}: unknown category {f['category']!r}")
        for p in f["tools"] + f["example_outputs"] + f["tests"] + [f["guide"]]:
            if not (ROOT / p).exists():
                out.append(f"{f['id']}: {p} does not exist")
        claimed.update(f["tools"])
    for p, e in tools.items():
        if e["kind"] == "tool" and p not in claimed:
            out.append(f"{p}: a tool that belongs to no feature in data/features.json")
    for r in reviews:
        if r["feature"] not in ids:
            out.append(f"review of unknown feature {r['feature']!r}")
        if r["verdict"] not in ("pass", "findings"):
            out.append(f"review of {r['feature']} on {r['date']}: verdict {r['verdict']!r}")
    return out


def use_matrix(feats, reviews, link_prefix):
    """The table a busy engineer reads first: one row per job, what it needs, how long, what you get, evidence."""
    lines = ["| I need to... | Why it matters | You need | Time | You get | Evidence |", "|---|---|---|---|---|---|"]
    for f in feats["features"]:
        state, _ = review_state(f, reviews)
        g = gaps(f, state)
        ev = "reviewed example" if state == "proven" and not g else "not yet: " + "; ".join(g)
        lines.append(f"| [{f['job']}]({link_prefix}{f['guide']}) | {f['why']} | {f['you_need']} | {f['time']} | "
                     f"{f['you_get']} | {ev} |")
    return "\n".join(lines)


def readme_text(feats, reviews):
    text = README.read_text(encoding="utf-8")
    a, b = text.index(MARK[0]) + len(MARK[0]), text.index(MARK[1])
    return text[:a] + "\n" + use_matrix(feats, reviews, "") + "\n" + text[b:]


def render(feats, reviews):
    rows, sections = [], []
    for cat, desc in feats["categories"].items():
        fs = [f for f in feats["features"] if f["category"] == cat]
        if not fs:
            continue
        sections += [f"## {cat.capitalize()}: {desc}", ""]
        for f in fs:
            state, rev = review_state(f, reviews)
            g = gaps(f, state)
            mark = "**reviewed example**" if state == "proven" and not g else "not yet: " + "; ".join(g)
            rows.append(f"| [{f['title']}](#{f['id']}) | {cat} | {mark} |")
            sections += [f'<a id="{f["id"]}"></a>', f"### {f['title']}", "",
                         f"Status: {mark}", "", f"**Why it matters:** {f['why']}", "",
                         "- **Tools:** " + ", ".join(f"`{t.removeprefix('scripts/')}`" for t in f["tools"]),
                         f"- **How to use it:** [{Path(f['guide']).name}](../{f['guide']})",
                         "- **Example outputs:** " + (", ".join(f"[`{Path(p).name}`](../{p})" for p in f["example_outputs"])
                                                     or "none committed yet"),
                         "- **Tests:** " + ", ".join(f"`{Path(t).name}`" for t in f["tests"])]
            if rev:
                sections.append(f"- **Independent review:** {rev['reviewer']}, {rev['date']}: {rev['verdict']}"
                                + (f" ({len(rev.get('findings', []))} finding(s); {rev.get('resolution', '')})"
                                   if rev.get("findings") else "")
                                + ("" if state in ("proven", "findings open") else " (outputs changed since)"))
            else:
                sections.append("- **Independent review:** none yet")
            sections.append("")
    head = ["# Features: what this repository does, and the evidence that each part works", "",
            "Generated by `scripts/feature_catalog.py` from `data/features.json` and `data/reviews.json`. "
            "**Reviewed example** means committed example outputs, tests that pin them, and an independent review whose "
            "recorded file hashes still match those outputs. It does not mean the complete route is automated, all "
            "input formats connect, or a plant deployment has been accepted. Missing evidence is listed as a gap. "
            "Reviews here are independent coding-agent or model checks; each record states its scope and limits. "
            "They can include corrective review after findings and are not a person's sign-off.", "",
            "## What you can do with it", "",
            "Each row is a job (click it for the guide), why it matters, what it needs from you, how long it "
            "takes (measured where it says so), what you get back, and its example evidence. The same table is in the README; both are generated. "
            "Use the [connection map](../README.md#what-connects-today-the-hub-and-spokes) to distinguish runnable routes, assisted authoring and missing integrations.",
            "", use_matrix(feats, reviews, "../"), "",
            "## By category", "", "| Feature | Category | Status |", "|---|---|---|"] + rows + [""]
    return "\n".join(head + sections)


def main(argv):
    if "-h" in argv or "--help" in argv:  # print usage; never regenerate anything on a help request
        print(__doc__)
        return 0
    unknown = [x for i, x in enumerate(argv) if x not in ("--check", "--hashes")
               and not (i and argv[i - 1] == "--hashes")]
    if unknown:  # a typo such as --chek must not fall through to the write path
        print(f"unrecognized argument(s): {' '.join(unknown)}\nusage: feature_catalog.py [--check | --hashes FEATURE]",
              file=sys.stderr)
        return 2
    feats, reviews, tools = load()
    if "--hashes" in argv:
        f = next(x for x in feats["features"] if x["id"] == argv[argv.index("--hashes") + 1])
        print(json.dumps({p: file_hash(p) for p in f["example_outputs"]}, indent=1))
        return 0
    bad = problems(feats, reviews, tools)
    text = render(feats, reviews) if not bad else None
    if "--check" in argv:
        if not bad and (not OUT.exists() or OUT.read_text(encoding="utf-8") != text):
            bad.append("docs/FEATURES.md is stale: run python scripts/feature_catalog.py")
        if not bad and README.read_text(encoding="utf-8") != readme_text(feats, reviews):
            bad.append("the README's use matrix is stale: run python scripts/feature_catalog.py")
        for b in bad:
            print("FAIL:", b)
        print(f"{len(feats['features'])} features; {len(bad)} problem(s)")
        return 1 if bad else 0
    if bad:
        for b in bad:
            print("FAIL:", b)
        return 1
    README.write_text(readme_text(feats, reviews), encoding="utf-8", newline="\n")
    OUT.write_text(text, encoding="utf-8", newline="\n")
    states = [review_state(f, reviews)[0] for f in feats["features"]]
    print(f"wrote docs/FEATURES.md: {sum(s == 'proven' for s in states)} of {len(states)} have reviewed examples")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
