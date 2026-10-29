"""Check that the headline numbers in README.md still match the committed result files.

python scripts/check_claims.py            # table to stdout; writes out/claims_check.md and out/claims_check.json
python scripts/check_claims.py --quiet    # print only the claims that fail
python scripts/check_claims.py --no-write # do not write the out/ files

Each claim is one number the README states. For each, this
- confirms the README still contains the phrase that states it (so editing the README is noticed);
- derives the number again from committed files, from the raw per-run or per-item data where the file has it
  (the mean of the five replicates, the rows of a CSV counted by tier), otherwise from the summary field;
- compares the two at the precision the README uses.

Statuses: ok (README and evidence agree), FAIL (they disagree, the README phrase is gone, or an evidence file is
missing or unreadable), prose only (no committed result file holds the number; the claim rests on narrative in a
document, which is named). Exit code 1 if any claim fails. "prose only" is not a failure, so a reader can see
which claims rest on narrative.

Needs no network, API keys or gateway. Stdlib only.
"""
import argparse
import csv
import json
import re
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
OUT_MD = ROOT / "out" / "claims_check.md"
OUT_JSON = ROOT / "out" / "claims_check.json"

HOLDOUT_A = "out/replicates_r5_holdout-a.json"
DEXPI = "out/replicates_r5_dexpi.json"
SCORECARD_A = "out/scorecard_r2-tiles-trace_holdout-a.json"
QUEUE = "out/twin/r2-tiles-trace/codex/review_queue.csv"
FLOW = "out/open100_structural/flow_direction.json"
PLANT = "out/open100_structural/plant_structure.json"
FAULTS = "out/fault_detection/fault_detection.json"
SOURCE_CHECK = "out/te_source_check.md"
TOPOLOGY_CHECK = "out/te_topology_check.md"
FIG10 = "out/bayer_rt/fig10_compare.json"
FIG11 = "out/bayer_rt/fig11_check.json"
WALK = "out/bayer_rt/walkthrough.json"
REVC = "out/te_pid/roundtrip_scores_revC.json"
LOOPS = "data/te_control_loops.json"
BAYER_DOC = "docs/BAYER_RT.md"


class EvidenceError(Exception):
    """An evidence file is missing, unreadable, or does not hold what the claim needs."""


def read_text(rel):
    try:
        return (ROOT / rel).read_text(encoding="utf-8")
    except OSError as error:
        raise EvidenceError(f"evidence file missing or unreadable: {rel} ({error.strerror})")


def load_json(rel):
    try:
        return json.loads(read_text(rel))
    except ValueError as error:
        raise EvidenceError(f"evidence file is not valid JSON: {rel} ({error})")


def at(data, path, rel):
    """Follow a list of keys into parsed JSON; a missing key is an evidence error, not a crash."""
    for key in path:
        try:
            data = data[key]
        except (KeyError, IndexError, TypeError):
            raise EvidenceError(f"{rel}: no field {'/'.join(map(str, path))}")
    return data


# --- derivations: each returns the number the committed files give -------------------------------------------

def replicate_mean(rel, metric, tool, scale=1.0):
    """Mean of the per-run values (not the stored summary mean)."""
    values = at(load_json(rel), ["metrics", metric, tool, "replicates"], rel)
    return statistics.mean(values) * scale


def scorecard_value(tool, *path):
    return at(load_json(SCORECARD_A), [tool, *path], SCORECARD_A)


def queue_rows():
    try:
        with (ROOT / QUEUE).open(encoding="utf-8-sig", newline="") as stream:
            return list(csv.DictReader(stream))
    except OSError as error:
        raise EvidenceError(f"evidence file missing or unreadable: {QUEUE} ({error.strerror})")


def queue_tier(tier):
    return sum(1 for row in queue_rows() if row["tier"] == tier)


def process_streams():
    streams = at(load_json(FLOW), ["streams"], FLOW)
    return [s for s in streams if not s["instrument_link"]]


def directed_process_links():
    return sum(1 for s in process_streams() if s["direction"] in ("forward", "reverse"))


def sheet_links(directed_only):
    links = at(load_json(PLANT), ["area_links"], PLANT)
    return sum(1 for a in links if not directed_only or a["direction"] in ("a_to_b", "b_to_a"))


def fault_summary(key):
    return at(load_json(FAULTS), ["methods", "shipped_bands", "summary", key], FAULTS)


def fault_rows():
    return at(load_json(FAULTS), ["methods", "shipped_bands", "faults"], FAULTS)


def detected_faults():
    return [int(k) for k, v in fault_rows().items() if v["detected"]]


def missed_faults():
    return ", ".join(str(k) for k in sorted(int(k) for k, v in fault_rows().items() if not v["detected"]))


def median_delay():
    return statistics.median(v["delay_min"] for v in fault_rows().values() if v["detected"])


def count_statuses(rel, status):
    """Table rows with a cell that starts '**status**' (a correction may add '(previously ...)') in a generated markdown check report."""
    cell = f"**{status}**"
    return sum(1 for line in read_text(rel).splitlines() if line.startswith("|")
               and any(c.strip().startswith(cell) for c in line.strip().strip("|").split("|")))


def totals_line(rel, word):
    """The number before a word in the report's own **Totals:** line (a cross-check on the row count)."""
    for line in read_text(rel).splitlines():
        if line.startswith("**Totals:**"):
            found = re.search(r"(\d+) " + word, line)
            if found:
                return int(found.group(1))
    raise EvidenceError(f"{rel}: no Totals line with '{word}'")


def rows_ok(rel, rows_key, ok_key="ok"):
    rows = at(load_json(rel), [rows_key], rel)
    return sum(1 for r in rows if r[ok_key]), len(rows)


def walk_checks():
    steps = at(load_json(WALK), ["steps"], WALK)
    checks = [c for s in steps for c in s["checks"]]
    return sum(1 for c in checks if c["agrees"]), len(checks)


def revc_clean_load(tool):
    """Mean review load over the clean-sheet runs, recomputed from each run."""
    runs = [r["review_load"] for r in at(load_json(REVC), ["runs"], REVC)
            if r["tool"] == tool and "-clean-" in r["label"]]
    if len(runs) != 5:
        raise EvidenceError(f"{REVC}: expected 5 clean runs for {tool}, found {len(runs)}")
    return statistics.mean(runs)


def running_loops():
    loops = at(load_json(LOOPS), ["loops"], LOOPS)
    return sum(1 for loop in loops if loop["runs"])


def prose_in_doc(rel, pattern):
    """A number that only a document's prose holds: return it, or None if the sentence is gone."""
    found = re.search(pattern, " ".join(read_text(rel).split()))
    return int(found.group(1)) if found else None


# --- the claims ---------------------------------------------------------------------------------------------

@dataclass
class Claim:
    id: str
    phrase: str             # the README claim, short
    needles: list           # strings that must all appear in README (whitespace-normalised)
    stated: object          # the value as the README writes it
    derive: object          # function () -> value from committed files
    files: list             # evidence files (shown in the table)
    decimals: int = 0       # precision the README uses; the evidence is rounded to it before comparing
    prose: bool = False     # True: no result file holds the number; evidence is a document's prose
    te: bool = False        # Tennessee Eastman output that another process may be rebuilding
    note: str = field(default="")


CLAIMS = [
    Claim("A-symbols-f1", "symbols F1 0.93 on held-out drawings, mean of five round-5 runs (GPT)", ["F1 0.93"], 0.93,
          lambda: replicate_mean(HOLDOUT_A, "symbol_f1_rough_classified", "codex"), [HOLDOUT_A], 2,
          note="rough_classified F1; the single round-2 run's rough_located F1 was 0.97"),
    Claim("A-connections-f1", "connections F1 0.87, mean of five round-5 runs (GPT)", ["connections 0.87"], 0.87,
          lambda: replicate_mean(HOLDOUT_A, "connection_f1", "codex"), [HOLDOUT_A], 2),
    Claim("A-gpt-load-r5", "GPT review load 20.1 per 100, mean of five round-5 runs", ["**20.1**"], 20.1,
          lambda: replicate_mean(HOLDOUT_A, "review_load_per_100", "codex"), [HOLDOUT_A], 1),
    Claim("A-claude-load-r5", "Claude review load 29.8 per 100, mean of five round-5 runs", ["**29.8**"], 29.8,
          lambda: replicate_mean(HOLDOUT_A, "review_load_per_100", "claude"), [HOLDOUT_A], 1),
    Claim("A-gpt-load-r2", "earlier single round-2 run, GPT review load 17.8", ["48.8 → 17.8"], 17.8,
          lambda: scorecard_value("codex", "review_load_per_100"), [SCORECARD_A], 1),
    Claim("Q-items", "2,886 extracted OPEN100 items", ["2,886"], 2886,
          lambda: len(queue_rows()), [QUEUE]),
    Claim("Q-green", "1,833 green items", ["1,833"], 1833, lambda: queue_tier("green"), [QUEUE]),
    Claim("Q-amber", "676 amber items", ["676"], 676, lambda: queue_tier("amber"), [QUEUE]),
    Claim("Q-red", "377 red items", ["377"], 377, lambda: queue_tier("red"), [QUEUE]),
    Claim("F-directed", "flow direction on 361 process links", ["361 of 1,133"], 361,
          directed_process_links, [FLOW]),
    Claim("F-process-links", "of 1,133 process links", ["361 of 1,133"], 1133,
          lambda: len(process_streams()), [FLOW]),
    Claim("F-sheet-links", "38 sheet-to-sheet connections", ["38 sheet-to-sheet connections"], 38,
          lambda: sheet_links(False), [PLANT]),
    Claim("F-sheet-links-directed", "36 of them with a direction", ["36 with a direction"], 36,
          lambda: sheet_links(True), [PLANT]),
    Claim("D-gpt-tags", "DEXPI tags read exactly: GPT 29 of 33", ["29 of 33"], 29,
          lambda: replicate_mean(DEXPI, "tag_end_to_end_recall_strict", "codex", 33), [DEXPI]),
    Claim("D-claude-tags", "DEXPI tags read exactly: Claude 28 of 33", ["28 of 33"], 28,
          lambda: replicate_mean(DEXPI, "tag_end_to_end_recall_strict", "claude", 33), [DEXPI]),
    Claim("X-detected", "17 of 21 faults flagged", ["flag 17 (median 48 min"], 17,
          lambda: len(detected_faults()), [FAULTS]),
    Claim("X-of", "of all 21 published faults", ["all 21 published faults"], 21,
          lambda: len(fault_rows()), [FAULTS]),
    Claim("X-false-alarms", "0 false alarms", ["0 false alarms in 193 h"], 0,
          lambda: at(load_json(FAULTS), ["methods", "shipped_bands", "false_alarms", "alarm_events"], FAULTS),
          [FAULTS]),
    Claim("X-hours", "in 193 h of normal running", ["0 false alarms in 193 h"], 193,
          lambda: at(load_json(FAULTS), ["methods", "shipped_bands", "false_alarms", "plant_hours"], FAULTS),
          [FAULTS]),
    Claim("X-misses", "misses faults 3, 9, 15 and 19", ["miss faults 3, 9, 15 and 19"], "3, 9, 15, 19",
          missed_faults, [FAULTS]),
    Claim("X-median", "median 48 min after onset", ["median 48 min"], 48, median_delay, [FAULTS]),
    Claim("T-source-confirmed", "TE source check: 36 confirmed", ["36 confirmed, 1 corrected"], 36,
          lambda: count_statuses(SOURCE_CHECK, "confirmed"), [SOURCE_CHECK], te=True,
          note="rows counted; test_check_claims cross-checks the report's own totals line"),
    Claim("T-source-corrected", "TE source check: 1 corrected", ["36 confirmed, 1 corrected"], 1,
          lambda: count_statuses(SOURCE_CHECK, "corrected"), [SOURCE_CHECK], te=True),
    Claim("T-topology-confirmed", "TE topology: 51 confirmed", ["51 confirmed, 4 corrected"], 51,
          lambda: count_statuses(TOPOLOGY_CHECK, "confirmed"), [TOPOLOGY_CHECK], te=True),
    Claim("T-topology-corrected", "TE topology: 4 corrected", ["51 confirmed, 4 corrected"], 4,
          lambda: count_statuses(TOPOLOGY_CHECK, "corrected"), [TOPOLOGY_CHECK], te=True),
    Claim("T-topology-unresolvable", "TE topology: 1 unresolvable", ["1 unresolvable of 56"], 1,
          lambda: count_statuses(TOPOLOGY_CHECK, "unresolvable"), [TOPOLOGY_CHECK], te=True),
    Claim("B-fig10-first", "Figure 10 comparison: 10 of 21 agreed at first", ["10 of 21 checks agreed at first"], 10,
          lambda: prose_in_doc(BAYER_DOC, r"The first run agreed on (\d+) of 21 checks"), [BAYER_DOC], prose=True,
          note="not in a committed result file (fig10_compare.json holds only the corrected run)"),
    Claim("B-fig10-corrected", "Figure 10 comparison: 20 of 21 corrected", ["corrected, 20 of 21"], 20,
          lambda: rows_ok(FIG10, "rows")[0], [FIG10]),
    Claim("B-fig10-total", "Figure 10 comparison: of 21 checks", ["corrected, 20 of 21"], 21,
          lambda: rows_ok(FIG10, "rows")[1], [FIG10]),
    Claim("B-fig11-agree", "Figure 11: 8 of 11 checks agree", ["8 of 11 checks"], 8,
          lambda: rows_ok(FIG11, "checks")[0], [FIG11]),
    Claim("B-fig11-total", "Figure 11: of 11 checks", ["8 of 11 checks"], 11,
          lambda: rows_ok(FIG11, "checks")[1], [FIG11]),
    Claim("B-walk-agree", "walkthrough: 13 of 16 checks agree", ["13 of 16 checks agree"], 13,
          lambda: walk_checks()[0], [WALK]),
    Claim("B-walk-total", "walkthrough: of 16 checks", ["13 of 16 checks agree"], 16,
          lambda: walk_checks()[1], [WALK]),
    Claim("R-revC-gpt", "revision C clean read-back review load 1.26 (GPT)", ["1.26 · 1.38"], 1.26,
          lambda: revc_clean_load("codex"), [REVC], 2, te=True),
    Claim("R-revC-claude", "revision C clean read-back review load 1.38 (Claude)", ["1.26 · 1.38"], 1.38,
          lambda: revc_clean_load("claude"), [REVC], 2, te=True),
    Claim("L-loops", "19 control loops running in the simulator code", ["19 of 19 on revision B"], 19,
          running_loops, [LOOPS], te=True),
]


# --- checking ------------------------------------------------------------------------------------------------

def normalise(text):
    return " ".join(text.split())


def show(value):
    if isinstance(value, float):
        return f"{value:g}"
    return "-" if value is None else str(value)


def check(claim, readme):
    """Run one claim. readme is the normalised README text."""
    result = {"id": claim.id, "phrase": claim.phrase, "readme_says": show(claim.stated),
              "evidence_says": "-", "files": ", ".join(claim.files), "te": claim.te, "note": claim.note}
    missing = [n for n in claim.needles if normalise(n) not in readme]
    try:
        value = claim.derive()
    except EvidenceError as error:
        result.update(status="FAIL", detail=str(error))
        return result
    if value is None:
        result.update(status="prose only", detail="the sentence in the document was not found" if claim.prose
                      else "no value", evidence_says="-")
        if not claim.prose:
            result["status"] = "FAIL"
        return result
    shown = value
    if isinstance(value, (int, float)):
        shown = round(value, claim.decimals) if claim.decimals else int(round(value))
    result["evidence_says"] = show(shown)
    if missing:
        result.update(status="FAIL", detail="README no longer contains: " + "; ".join(missing))
    elif shown != claim.stated:
        result.update(status="FAIL", detail=f"README says {show(claim.stated)}, evidence says {show(shown)}")
    elif claim.prose:
        result.update(status="prose only", detail="matches the document's prose; no result file holds it")
    else:
        result.update(status="ok", detail="")
    return result


def run(claims=None, readme_text=None):
    """Check every claim. readme_text lets a test patch the README in memory."""
    if readme_text is None:
        readme_text = README.read_text(encoding="utf-8")
    readme = normalise(readme_text)
    return [check(c, readme) for c in (CLAIMS if claims is None else claims)]


def table(results, only_failures=False):
    lines = ["| claim | README says | evidence says | file | ok |", "|---|---|---|---|---|"]
    for r in results:
        if only_failures and r["status"] != "FAIL":
            continue
        mark = {"ok": "ok", "FAIL": "**FAIL**", "prose only": "prose only"}[r["status"]]
        lines.append(f"| {r['phrase']} | {r['readme_says']} | {r['evidence_says']} | {r['files']} | {mark} |")
    return "\n".join(lines)


def details(results):
    out = []
    for r in results:
        if r["status"] != "ok":
            out.append(f"- {r['id']} ({r['status']}): {r['detail']}" + (f" [{r['note']}]" if r["note"] else ""))
    return "\n".join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quiet", action="store_true", help="print only failures")
    parser.add_argument("--no-write", action="store_true", help="do not write out/claims_check.{md,json}")
    args = parser.parse_args(argv)
    results = run()
    failed = [r for r in results if r["status"] == "FAIL"]
    prose = [r for r in results if r["status"] == "prose only"]
    summary = (f"{len(results) - len(failed) - len(prose)} ok, {len(prose)} prose only, {len(failed)} FAIL "
               f"of {len(results)} claims")
    if not args.no_write:
        body = ["# README claims against committed evidence", "", "Generated by `scripts/check_claims.py`. "
                "Each README number is derived again from the files named; \"prose only\" means no committed "
                "result file holds it.", "", table(results), "", f"**{summary}**"]
        if details(results):
            body += ["", "Notes:", details(results)]
        OUT_MD.parent.mkdir(exist_ok=True)
        OUT_MD.write_text("\n".join(body) + "\n", encoding="utf-8")
        OUT_JSON.write_text(json.dumps({"summary": summary, "claims": results}, indent=2) + "\n", encoding="utf-8")
    if args.quiet:
        if failed:
            print(table(results, True))
            print(details(failed))
    else:
        print(table(results))
        print(f"\n{summary}")
        if details(results):
            print("\nNotes:\n" + details(results))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
