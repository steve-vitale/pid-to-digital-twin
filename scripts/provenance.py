"""Per-element provenance: how sure we are about one model item, read only from fields the model already carries.

Every output built from a model element inherits this record, and nothing on the way upgrades it. Fields read (all
optional, so a model that lacks one simply reports it as missing):

  verification.status  a machine check against a source: confirmed / corrected / unresolvable / unverified.
                       Tennessee Eastman: checked against the simulator code (scripts/verify_te_source.py).
                       Extracted twin: always "unverified" until a person reviews the item.
  ops_review           a person's decision, written by scripts/apply_review.py: status confirmed / corrected /
                       rejected / unverified, the reviewer string in `by`, and scoped `field_decisions`.
  risk.tier            green / amber / red (extracted twin only, scripts/confidence.py)
  tag_status           as_extracted / missing / placeholder (extracted twin only)
  open_question        a recorded doubt that nobody has settled

Who reviewed matters. A reviewer string only counts as an operations review when it names an operations role
(operator, process engineer, ...). A string that says non-operations, or names no role at all, keeps that label:
"confirmed by a non-process-expert" is never rolled up as an operations confirmation. See
docs/review-kit/FEEDBACK.md (Track A / Track B) once the review kit is merged.

Stdlib only.
"""
from collections import Counter

NON_EXPERT_MARKERS = ("non-operations", "non operations", "non-process", "non process", "track a",
                      "text and legibility only")
OPERATIONS_MARKERS = ("operator", "process engineer", "controls engineer", "control engineer",
                      "process-safety", "process safety", "operations", "shift supervisor", "track b")
# offpage_pairs are left out: each pair is also a cross-sheet link in streams, so counting both would double it.
COLLECTIONS = ("units", "streams", "instruments", "final_elements", "line_items", "offpage_connectors")


def reviewer_track(by):
    """'operations', 'non-operations' or 'role not stated'; None when nobody reviewed."""
    if not by:
        return None
    low = str(by).lower()
    if any(m in low for m in NON_EXPERT_MARKERS):
        return "non-operations"
    if any(m in low for m in OPERATIONS_MARKERS):
        return "operations"
    return "role not stated"


def element(item):
    """The provenance record one output inherits from one model item."""
    review = item.get("ops_review") or {}
    status = review.get("status", "unverified")
    track = reviewer_track(review.get("by")) if review else None
    if status in ("confirmed", "corrected", "rejected") and track not in (None, "operations"):
        status = f"{status} ({track} reviewer)"
    record = {"source_check": (item.get("verification") or {}).get("status", "unverified"),
              "ops_review": status}
    if track:
        record["reviewer_track"] = track
    if review.get("field_decisions"):
        record["field_corrections"] = sorted(review["field_decisions"])
    if item.get("risk"):
        record["risk_tier"] = item["risk"].get("tier")
    if item.get("tag_status"):
        record["tag_status"] = item["tag_status"]
    if item.get("open_question"):
        record["open_question"] = True
    return record


def rollup(model):
    """Per element class: counts of each provenance value. Deterministic (sorted keys)."""
    out = {}
    for collection in COLLECTIONS:
        items = model.get(collection)
        if not items:
            continue
        counts = {"total": len(items)}
        for key in ("source_check", "ops_review", "reviewer_track", "risk_tier", "tag_status"):
            c = Counter(element(x).get(key, "n/a") for x in items)
            if set(c) != {"n/a"}:
                counts[key] = dict(sorted(c.items()))
        counts["open_question"] = sum(bool(x.get("open_question")) for x in items)
        counts["field_corrections"] = sum(bool((x.get("ops_review") or {}).get("field_decisions")) for x in items)
        out[collection] = counts
    return out
