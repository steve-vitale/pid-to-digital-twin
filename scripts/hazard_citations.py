"""PROTOTYPE: match the twin's equipment kinds to public incident records and load the curated citations.

Two jobs:
1. `load_citations()` / `citations_for_kind()` read data/hazard_citations_prototype.json, the curated, committed
   output. That file is what the 3D orientation tour cites. It holds only PUBLIC agency records (CSB, OSHA/DOL,
   NTSB, EPA RMP) with the URL exactly as recorded in the corpus it came from, plus a one-line hazard summary
   written by Claude. No private or company data.
2. `--corpus-repo PATH` (optional, read-only) re-runs the keyword heuristic over a local checkout of the corpus
   repository (`git show <ref>:<file>`; nothing is written there, nothing is fetched) and prints the ranked
   candidates per equipment kind. This is how the curated file was shortlisted. It mirrors that system's own
   precedent matcher in spirit: lowercase substring keyword hits, and a precision floor (a record only counts if
   at least one equipment-specific term hits; generic words like "startup" never count alone).

This is a heuristic shortlist, not a hazard analysis. A matched incident shows that a hazard MECHANISM has hurt
people in the public record; it does not say the mechanism applies to this unit at this plant. A PHA/HAZOP team
decides that.

  python scripts/hazard_citations.py                       # print the curated citations per kind
  python scripts/hazard_citations.py --corpus-repo <checkout> --corpus-config <local.json> --ref origin/main
                                                           # rerun the shortlist (needs the untracked local config)

The corpus repository's file layout and any terms that must never be read or published (a deny-list) are private
to that repository's owner. They live in an untracked local JSON file passed with --corpus-config, never in this
repository:
  {"files": {"csb_corpus": "...json", "epa_rmp": "...json", "precedent_cards": "...ts"},
   "public_fixture_dir": ".../", "deny_terms": ["..."]}
The environment variable HAZARD_DENY_TERMS (comma-separated) adds deny terms for the tests and the validator.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CITATIONS = ROOT / "data" / "hazard_citations_prototype.json"

# Equipment-specific terms per 2D/3D symbol kind (the twin's vocabulary). Chosen by Claude; a prototype.
KIND_TERMS = {
    "feed": ["feed line", "feed valve", "plug valve", "dead leg", "remote isolation", "isolation valve", "blind",
             "leak", "piping"],
    "reactor": ["reactor", "runaway", "exothermic", "decomposition", "overpressur", "pressure-relief",
                "pressure relief", "refrigeration", "temperature limit"],
    "condenser": ["condenser", "heat exchanger", "exchanger", "reboiler", "cooling water"],
    "separator": ["separator", "knockout", "flash drum", "mix drum", "surge drum", "drum overflow",
                  "vapor-liquid", "two-phase", "carryover"],
    "compressor": ["compressor"],
    "stripper": ["stripper", "distillation", "splitter", "tower", "column", "reboiler"],
}
GENERIC_TERMS = ["startup", "shutdown", "restart", "refinery", "release", "fire", "explosion", "maintenance"]
ALLOWED_DOMAINS = ("csb.gov", "osha.gov", "dol.gov", "ntsb.gov", "epa.gov")
JUNK_URL = ("privacy-policy", "csb.gov/investigations/")
CORPUS_KEYS = ("csb_corpus", "epa_rmp", "precedent_cards")


def deny_terms(config=None):
    """Terms that must never be read or published. Only from outside the repository: the local corpus config and the
    HAZARD_DENY_TERMS environment variable. Lowercased; empty if neither is set."""
    terms = list((config or {}).get("deny_terms", [])) + os.environ.get("HAZARD_DENY_TERMS", "").split(",")
    return tuple(t.strip().lower() for t in terms if t.strip())


def load_corpus_config(path):
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    missing = [k for k in CORPUS_KEYS if k not in config.get("files", {})] +               ([] if config.get("public_fixture_dir") else ["public_fixture_dir"])
    if missing:
        raise ValueError(f"corpus config is missing {missing}")
    return config


def domain_ok(url):
    m = re.match(r"https?://(?:www\.)?([^/?#]+)", url or "")
    return bool(m) and any(m.group(1) == d or m.group(1).endswith("." + d) for d in ALLOWED_DOMAINS)


def is_forbidden(*texts, terms=None):
    terms = deny_terms() if terms is None else terms
    return any(f in (t or "").lower() for t in texts for f in terms)


def score(text, kind):
    """Precedent-matcher score: specific hits weigh 2, generic 1; zero unless a specific term hits."""
    low = (text or "").lower()
    specific = sorted({t for t in KIND_TERMS[kind] if t in low})
    generic = sorted({t for t in GENERIC_TERMS if t in low})
    return (2 * len(specific) + len(generic) if specific else 0), specific, generic


def incident_key(url):
    """Collapse the same incident recorded under different slugs (trailing '-' or '/')."""
    return re.sub(r"[-/]+$", "", (url or "").split("?")[0].lower()) + ("?" + url.split("?")[1] if "?" in (url or "") else "")


def rank(records, kind, top=8, terms=None):
    best = {}
    for r in records:
        if not domain_ok(r["url"]) or is_forbidden(r["url"], r.get("text"), r.get("where"), terms=terms):
            continue
        if any(j in r["url"] for j in JUNK_URL):
            continue
        s, specific, generic = score(r.get("text", ""), kind)
        if not s:
            continue
        key = incident_key(r["url"])
        if key not in best or s > best[key]["score"]:
            best[key] = {"score": s, "specific": specific, "generic": generic, **r}
    return sorted(best.values(), key=lambda x: (-x["score"], x["url"]))[:top]


def _git_show(repo, ref, path):
    return subprocess.run(["git", "-C", str(repo), "show", f"{ref}:{path}"], capture_output=True, text=True,
                          encoding="utf-8", check=True).stdout


def corpus_records(repo, ref, config):
    """Read-only: public records from the corpus repository at ref, at the paths in the local config. Never reads a
    path containing a deny term."""
    files, terms = config["files"], deny_terms(config)
    records = []
    for name in ("csb_corpus", "epa_rmp"):
        data = json.loads(_git_show(repo, ref, files[name]))
        for f in data["fixtures"] if isinstance(data, dict) else data:
            records.append({"url": f.get("source_url", ""), "text": f.get("text", ""), "where": name,
                            "title": (f.get("metadata") or {}).get("slug") or f.get("id", "")})
    ts = _git_show(repo, ref, files["precedent_cards"])
    for block in re.findall(r"\{\s*id: \"[^\"]+\",.*?linked_regulation[^\n]*\n\s*\}", ts, re.S):
        url = re.search(r"source_url: \"([^\"]+)\"", block)
        title = re.search(r"title: \"([^\"]+)\"", block)
        if url:
            records.append({"url": url.group(1), "text": block, "where": "precedent_cards",
                            "title": title.group(1) if title else ""})
    listing = subprocess.run(["git", "-C", str(repo), "ls-tree", "--name-only", ref, config["public_fixture_dir"]],
                             capture_output=True, text=True, check=True).stdout.split()
    for path in listing:
        if is_forbidden(path, terms=terms) or not path.endswith(".json"):
            continue
        f = json.loads(_git_show(repo, ref, path))
        meta = f.get("metadata") or {}
        if not str(meta.get("source", "")).startswith("external"):
            continue  # only fixtures marked as public-source specimens
        records.append({"url": meta.get("source_url", ""), "text": f.get("input_text", ""), "where": path.rsplit("/", 1)[-1],
                        "title": f.get("id", "")})
    return records


def load_citations(path=CITATIONS):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def citations_for_kind(data, kind):
    return (data.get("kinds", {}).get(kind) or {}).get("citations", [])


def validate(data, kinds_needed):
    """Problems with the curated file (empty list = fine). Used by the tests and the verifier."""
    problems = []
    if "prototype" not in data.get("status", "").lower():
        problems.append("status must say this is a prototype heuristic")
    for kind in kinds_needed:
        cites = citations_for_kind(data, kind)
        if not 3 <= len(cites) <= 5:
            problems.append(f"{kind}: {len(cites)} citations (want 3-5)")
        for c in cites:
            if not domain_ok(c.get("url")):
                problems.append(f"{kind}: non-agency URL {c.get('url')}")
            if is_forbidden(json.dumps(c)):
                problems.append(f"{kind}: forbidden private-data reference in {c.get('id')}")
            for field in ("id", "title", "agency", "url", "hazard", "corpus", "matched_terms"):
                if not c.get(field):
                    problems.append(f"{kind}: {c.get('id')} missing {field}")
    if is_forbidden(json.dumps(data)):
        problems.append("file mentions forbidden private data")
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus-repo", help="local checkout of the corpus repository (read-only, via git show)")
    ap.add_argument("--corpus-config", help="untracked local JSON: corpus file layout and deny terms (see above)")
    ap.add_argument("--ref", default="origin/main")
    ap.add_argument("--top", type=int, default=8)
    args = ap.parse_args(argv)
    if args.corpus_repo:
        if not args.corpus_config:
            ap.error("--corpus-repo needs --corpus-config (the corpus layout is not stored in this repository)")
        config = load_corpus_config(args.corpus_config)
        records = corpus_records(args.corpus_repo, args.ref, config)
        sha = subprocess.run(["git", "-C", args.corpus_repo, "rev-parse", args.ref], capture_output=True, text=True).stdout.strip()
        print(json.dumps({"ref": args.ref, "commit": sha, "records_scanned": len(records), "candidates": {
            k: [{"score": c["score"], "url": c["url"], "title": c["title"], "corpus": c["where"],
                 "specific": c["specific"], "generic": c["generic"]} for c in rank(records, k, args.top, deny_terms(config))]
            for k in KIND_TERMS}}, indent=1))
        return 0
    data = load_citations()
    for kind, entry in data["kinds"].items():
        print(f"{kind}:")
        for c in entry["citations"]:
            print(f"  - {c['title']} ({c['agency']}) {c['url']}")
    problems = validate(data, list(data["kinds"]))
    for p in problems:
        print("PROBLEM", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
