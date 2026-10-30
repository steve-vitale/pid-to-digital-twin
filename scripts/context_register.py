"""Offline, evidence-bound engineering answers beside an unchanged model. See docs/CONTEXT_REGISTER.md.

    python -S scripts/context_register.py prepare --model model.json --questions questions.json \
        --sources sources.json --out context
    python -S scripts/context_register.py apply --model model.json --questions questions.json \
        --sources sources.json --answers context/answers.csv --register context/context.json --out context

Standard library only. No model calls, accounts, network, plant writes, or legacy review import.
"""
import argparse
import copy
import csv
import datetime
import hashlib
import io
import json
import os
import re
import sys
from pathlib import Path

SCHEMA = "context-register-1"
COLUMNS = ("question_id", "answer_id", "claim_key", "value", "answer", "answer_state", "decision",
           "owner", "assigned_by", "assigned_on", "reviewer", "reviewed_on", "source_id", "locator_id",
           "source_match", "plant_truth", "note",
           "evidence_fingerprint")
CHOICE_COLUMNS = ("question_id", "source_id", "revision", "sha256", "locator_id", "locator",
                  "evidence_fingerprint")
SOURCE_MATCH = ("unknown", "match", "mismatch", "unclear")
PLANT_TRUTH = ("unknown", "confirmed", "wrong")
ANSWER_STATES = ("partial", "needs_data", "answered")
DECISIONS = ("proposed", "accepted", "rejected")
HASH = re.compile(r"^[0-9a-f]{64}$")
# Status fields describe a review, not a change to engineering content. All other content is bound.
BOOKKEEPING = {"status", "context", "context_register"}


class InputError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def read_json(path, what):
    def unique_pairs(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate JSON object key")
            value[key] = item
        return value
    try:
        with Path(path).open(encoding="utf-8-sig") as f:
            value = json.load(f, object_pairs_hook=unique_pairs,
                              parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    except (OSError, ValueError) as exc:
        reason = (exc.strerror or type(exc).__name__) if isinstance(exc, OSError) else str(exc)
        raise InputError(f"cannot read {what} {Path(path).name}: {reason}") from exc
    if not isinstance(value, dict):
        raise InputError(f"{what} must be a JSON object")
    return value


def text(value, where):
    if not isinstance(value, str) or not value.strip():
        raise InputError(f"{where} must be nonempty text")
    return value.strip()


def semantic(value):
    if isinstance(value, dict):
        # Original evidence records are opaque content, including fields named status/context. Stripping
        # bookkeeping inside them would hide an evidence change from the context freshness comparison.
        return {k: copy.deepcopy(v) if k in ("provenance", "citations") else semantic(v)
                for k, v in value.items() if k not in BOOKKEEPING}
    if isinstance(value, list):
        # Lists can carry engineering order (curves, split ranges); preserve that order.
        return [semantic(v) for v in value]
    return value


def load_inputs(model_path, question_path):
    graph = read_json(model_path, "model")
    if graph.get("schema") != "twin-graph-1":
        import graph_export
        try:
            graph = graph_export.build(model_path)
        except (ValueError, KeyError, TypeError) as exc:
            raise InputError(f"model cannot be exported: {exc}") from exc
    if not isinstance(graph.get("nodes"), list) or not isinstance(graph.get("edges", []), list):
        raise InputError("graph needs nodes and edges lists")
    assets = {}
    for node in graph["nodes"]:
        if not isinstance(node, dict):
            raise InputError("every graph node must be an object")
        aid = identifier(node.get("id"), "asset id")
        if aid in assets:
            raise InputError(f"ambiguous duplicate asset id {aid}")
        assets[aid] = {"id": aid, "content": semantic(node), "relations": []}
    edge_ids = set()
    for edge in graph.get("edges", []):
        if not isinstance(edge, dict):
            raise InputError("every graph edge must be an object")
        eid = identifier(edge.get("id"), "edge id")
        identifier(edge.get("type"), "edge type")
        if eid in edge_ids:
            raise InputError(f"ambiguous duplicate edge id {eid}")
        edge_ids.add(eid)
        if edge.get("type") == "connects":
            aid = "stream:" + identifier(edge.get("id"), "stream id")
            if aid in assets:
                raise InputError(f"ambiguous duplicate asset id {aid}")
            assets[aid] = {"id": aid, "content": semantic(edge), "relations": []}
    for edge in graph.get("edges", []):
        if not isinstance(edge, dict):
            raise InputError("every graph edge must be an object")
        for end in ("from", "to"):
            ref = identifier(edge.get(end), f"edge {end}")
            # Stream nodes are represented by connects edges in twin-graph-1.
            if ref not in assets:
                raise InputError(f"unknown graph {end} asset {ref}")
        relation = semantic({k: v for k, v in edge.items() if k != "id"})
        for ref in {edge["from"], edge["to"]}:
            if ref in assets:
                assets[ref]["relations"].append(relation)
    for asset in assets.values():
        asset["relations"].sort(key=canonical)
    qdoc = read_json(question_path, "questions")
    if not isinstance(qdoc.get("questions"), list):
        raise InputError("questions file needs a questions list")
    questions = {}
    for question in qdoc["questions"]:
        if not isinstance(question, dict):
            raise InputError("every question must be an object")
        qid = identifier(question.get("id"), "question id")
        if "question_id" in question:
            identifier(question["question_id"], f"question {qid} catalog question_id")
        text(question.get("question"), f"question {qid} wording")
        if qid in questions:
            raise InputError(f"ambiguous duplicate question id {qid}")
        refs = question.get("assets", [])
        if not isinstance(refs, list) or any(not isinstance(r, dict) for r in refs):
            raise InputError(f"question {qid} assets must be a list of id objects")
        ids = [identifier(r.get("id"), f"question {qid} asset id") for r in refs] or ["PLANT"]
        if len(set(ids)) != len(ids):
            raise InputError(f"question {qid} repeats an asset id")
        evidence = question.get("evidence", [])
        if not isinstance(evidence, list) or any(not isinstance(r, dict) for r in evidence):
            raise InputError(f"question {qid} evidence must be a list of objects")
        ids = sorted(set(ids) | {identifier(r["id"], f"question {qid} evidence asset id")
                                 for r in evidence if "id" in r})
        for aid in ids:
            if aid not in assets:
                raise InputError(f"question {qid} has unknown asset id {aid}; use an exact graph id")
        # Asset presentation order is not engineering content.
        content = semantic(question)
        if "assets" in content:
            content["assets"] = sorted(content["assets"], key=lambda r: r["id"])
        questions[qid] = {"question": content, "assets": [copy.deepcopy(assets[a]) for a in sorted(ids)]}
    return graph, qdoc, questions


def load_sources(path, questions, source_root=None):
    manifest = read_json(path, "source manifest")
    if manifest.get("schema") != "context-sources-1" or not isinstance(manifest.get("documents"), list):
        raise InputError("source manifest needs schema context-sources-1 and a documents list")
    root = Path(source_root).resolve() if source_root else Path(path).resolve().parent
    sources, choices, local_paths = {}, {}, []
    for doc in manifest["documents"]:
        if not isinstance(doc, dict):
            raise InputError("each manifest document must be an object")
        did = identifier(doc.get("id"), "source id")
        if did in sources:
            raise InputError(f"ambiguous duplicate source id {did}")
        revision = text(doc.get("revision"), f"source {did} revision")
        rel = text(doc.get("path"), f"source {did} path")
        local = (root / rel).resolve()
        if Path(rel).is_absolute() or re.match(r"^[A-Za-z]:", rel) or not local.is_relative_to(root):
            raise InputError(f"source {did} path must stay inside --source-root")
        try:
            sha = hashlib.sha256(local.read_bytes()).hexdigest()
        except OSError as exc:
            raise InputError(f"source {did} file unavailable; current raw bytes are required") from exc
        local_paths.append(local)
        if "sha256" in doc and doc["sha256"] != sha:
            raise InputError(f"source {did} raw-byte sha256 disagrees with manifest")
        locators = doc.get("locators")
        if not isinstance(locators, list) or not locators:
            raise InputError(f"source {did} needs a nonempty locators list")
        sources[did] = {"id": did, "revision": revision, "sha256": sha, "locators": []}
        seen = set()
        for loc in locators:
            if not isinstance(loc, dict):
                raise InputError(f"source {did} locator must be an object")
            lid = identifier(loc.get("id"), f"source {did} locator id")
            if lid in seen:
                raise InputError(f"ambiguous duplicate locator {did}/{lid}")
            seen.add(lid)
            locator = text(loc.get("locator"), f"source {did}/{lid} exact locator")
            bound = loc.get("questions", sorted(questions))
            if not isinstance(bound, list) or any(not isinstance(q, str) for q in bound):
                raise InputError(f"source {did}/{lid} questions must be a list of question ids")
            bound = [identifier(q, f"source {did}/{lid} question reference") for q in bound]
            if len(set(bound)) != len(bound) or any(q not in questions for q in bound):
                raise InputError(f"source {did}/{lid} has unknown or repeated question bindings")
            sources[did]["locators"].append({"id": lid, "locator": locator, "questions": sorted(bound)})
            source = {"id": did, "revision": revision, "sha256": sha, "locator_id": lid, "locator": locator}
            for qid in bound:
                evidence = dict(copy.deepcopy(questions[qid]), source=source)
                choices[(qid, did, lid)] = {"evidence": evidence, "fingerprint": digest(evidence)}
    return sources, choices, local_paths


def empty_register():
    return {"schema": SCHEMA, "decisions": [], "ownership_history": [], "current": {}}


def record_id(record, prefix):
    return prefix + digest({k: v for k, v in record.items() if k != "id"})


def identifier(value, where):
    """Never trim an identity map key while preserving a different id in its exported record."""
    normalized = text(value, where)
    if normalized != value:
        raise InputError(f"{where} must not have leading or trailing whitespace")
    return value


def validate_snapshot(evidence, question_id):
    if not isinstance(evidence, dict) or set(evidence) != {"question", "assets", "source"}:
        raise InputError("unbound decision evidence in register")
    src = evidence["source"]
    if (not isinstance(src, dict) or set(src) != {"id", "revision", "sha256", "locator_id", "locator"}
            or any(not isinstance(src.get(k), str) or not src[k].strip() for k in src)
            or not HASH.fullmatch(src["sha256"])):
        raise InputError("unbound document/revision/hash/locator in register")
    identifier(src["id"], "register source id")
    identifier(src["locator_id"], "register locator id")
    question = evidence["question"]
    assets = evidence["assets"]
    if not isinstance(question, dict) or question.get("id") != question_id:
        raise InputError("unbound question in register evidence snapshot")
    identifier(question["id"], "register question id")
    if "question_id" in question:
        identifier(question["question_id"], "register catalog question_id")
    text(question.get("question"), "register question wording")
    refs, cited = question.get("assets", []), question.get("evidence", [])
    if (not isinstance(refs, list) or not isinstance(cited, list)
            or any(not isinstance(r, dict) for r in refs + cited)):
        raise InputError("register question assets/evidence must be lists of objects")
    explicit = [identifier(r.get("id"), "register question asset id") for r in refs]
    if len(set(explicit)) != len(explicit):
        raise InputError("ambiguous duplicate asset reference in register question")
    expected = set(explicit or ["PLANT"])
    expected.update(identifier(r["id"], "register question evidence asset id") for r in cited if "id" in r)
    if not isinstance(assets, list) or not assets:
        raise InputError("unbound assets in register evidence snapshot")
    ids = set()
    for asset in assets:
        if not isinstance(asset, dict) or set(asset) != {"id", "content", "relations"}:
            raise InputError("register asset snapshot needs id, content object and relations list")
        aid = identifier(asset["id"], "register asset id")
        if aid in ids:
            raise InputError("ambiguous duplicate asset id in register evidence snapshot")
        ids.add(aid)
        content, relations = asset["content"], asset["relations"]
        if not isinstance(content, dict) or not isinstance(relations, list):
            raise InputError("register asset snapshot content must be an object and relations a list")
        content_id = identifier(content.get("id"), "register asset content id")
        stream = content.get("type") == "connects" and aid == "stream:" + content_id
        if content_id != aid and not stream:
            raise InputError("register asset content id disagrees with its snapshot id")
        if stream:
            for key in ("from", "to"):
                identifier(content.get(key), f"register stream {key} reference")
        for relation in relations:
            if not isinstance(relation, dict):
                raise InputError("register asset relations must contain objects")
            identifier(relation.get("type"), "register relation type")
            start = identifier(relation.get("from"), "register relation from reference")
            end = identifier(relation.get("to"), "register relation to reference")
            if aid not in (start, end):
                raise InputError("register asset relation is not incident to its snapshot asset")
    if ids != expected:
        raise InputError("register evidence assets disagree with the question's explicit references")


def validate_register(register):
    """Refuse legacy/unbound or edited history, including a fabricated accepted record with no snapshot."""
    if register.get("schema") != SCHEMA:
        raise InputError("unbound or legacy register; expected context-register-1 (no automatic legacy import)")
    for field in ("decisions", "ownership_history"):
        if not isinstance(register.get(field), list):
            raise InputError(f"register needs {field} history")
    seen, last = set(), {}
    required = set(COLUMNS) - {"source_id", "locator_id", "assigned_by", "assigned_on"}
    for rec in register["decisions"]:
        if not isinstance(rec, dict) or set(rec) != required | {"id", "evidence", "previous"}:
            raise InputError("unbound decision in register; a complete immutable evidence snapshot is required")
        for field in ("question_id", "answer_id", "claim_key"):
            identifier(rec[field], f"register decision {field}")
        if rec["owner"] is not None:
            text(rec["owner"], "register decision owner")
        validate_snapshot(rec["evidence"], rec["question_id"])
        evidence = rec["evidence"]
        if rec["evidence_fingerprint"] != digest(evidence) or rec.get("id") != record_id(rec, "d-"):
            raise InputError("register decision snapshot/hash mismatch")
        validate_answer(rec, "register decision")
        key = (rec["question_id"], rec["answer_id"])
        if rec["id"] in seen or rec["previous"] != last.get(key):
            raise InputError("register decision history has duplicate or broken predecessor")
        seen.add(rec["id"])
        last[key] = rec["id"]
    last = {}
    for rec in register["ownership_history"]:
        if (not isinstance(rec, dict) or set(rec) != {"id", "question_id", "owner", "by", "on", "previous"}
                or not isinstance(rec["question_id"], str) or not isinstance(rec["id"], str)
                or rec["id"] != record_id(rec, "o-") or rec["previous"] != last.get(rec["question_id"])
                or rec["id"] in seen
                or not (rec["owner"] is None or isinstance(rec["owner"], str) and rec["owner"])):
            raise InputError("register ownership history has invalid or broken record")
        identifier(rec["question_id"], "ownership history question_id")
        if rec["owner"] is not None:
            text(rec["owner"], "ownership history owner")
        text(rec["by"], "ownership history assigned_by")
        iso_date(rec["on"], "ownership history assigned_on")
        seen.add(rec["id"])
        last[rec["question_id"]] = rec["id"]


def iso_date(value, where):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise InputError(f"{where} must be an ISO date YYYY-MM-DD")
    try:
        datetime.date.fromisoformat(value)
    except ValueError as exc:
        raise InputError(f"{where} must be a valid ISO date YYYY-MM-DD") from exc


def validate_answer(row, where):
    for field in ("question_id", "answer_id", "claim_key", "value", "answer"):
        text(row.get(field), f"{where} {field}")
    for field in ("reviewer", "reviewed_on", "note", "evidence_fingerprint"):
        if not isinstance(row.get(field), str):
            raise InputError(f"{where} {field} must be text")
    if not (row.get("owner") is None or isinstance(row.get("owner"), str)):
        raise InputError(f"{where} owner must be text or null")
    for field, values in (("answer_state", ANSWER_STATES), ("decision", DECISIONS),
                          ("source_match", SOURCE_MATCH), ("plant_truth", PLANT_TRUTH)):
        if row.get(field) not in values:
            raise InputError(f"{where} {field} must be one of {', '.join(values)}")
    if bool(row["reviewer"]) != bool(row["reviewed_on"]):
        raise InputError(f"{where} reviewer and reviewed_on must be supplied together")
    if row["reviewer"]:
        text(row["reviewer"], f"{where} reviewer")
    if row["reviewed_on"]:
        iso_date(row["reviewed_on"], f"{where} reviewed_on")
    if row["decision"] in ("accepted", "rejected") and not row["reviewer"]:
        raise InputError(f"{where} accepted/rejected requires reviewer and reviewed_on")
    if row["plant_truth"] != "unknown":
        if not row["reviewer"]:
            raise InputError(f"{where} explicit plant truth requires reviewer and reviewed_on")
        if row["source_match"] != "match":
            raise InputError(f"{where} explicit plant truth requires source_match=match")
    if row["decision"] == "accepted" and row["answer_state"] == "answered" and row["source_match"] != "match":
        raise InputError(f"{where} accepted answered response requires source_match=match")


def read_answers(path, questions, choices):
    try:
        with Path(path).open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if tuple(reader.fieldnames or ()) != COLUMNS:
                raise InputError("answer CSV header must match the prepared sheet; legacy/unbound CSV refused")
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as exc:
        raise InputError("cannot read answer CSV") from exc
    seen = set()
    for n, row in enumerate(rows, 2):
        where = f"CSV row {n}"
        if None in row or any(v is None for v in row.values()):
            raise InputError(f"{where} has the wrong number of columns")
        for field in ("question_id", "answer_id", "claim_key", "source_id", "locator_id"):
            if row[field]:
                identifier(row[field], f"{where} {field}")
        row.update({k: v.strip() for k, v in row.items()})
        qid = row["question_id"]
        if qid not in questions:
            raise InputError(f"{where} unknown question_id {qid}")
        if not row["answer"]:
            allowed = {"question_id", "owner", "assigned_by", "assigned_on", "answer_state", "decision",
                       "source_match", "plant_truth"}
            if any(v for k, v in row.items() if k not in allowed):
                raise InputError(f"{where} has evidence/answer fields without an answer")
            if (row["decision"] not in ("", "proposed") or row["plant_truth"] not in ("", "unknown")
                    or row["source_match"] not in ("", "unknown")
                    or row["answer_state"] not in ("", "needs_data")):
                raise InputError(f"{where} cannot decide an unanswered question")
            continue
        for field, default in (("answer_state", "partial"), ("decision", "proposed"),
                               ("source_match", "unknown"), ("plant_truth", "unknown")):
            row[field] = row[field] or default
        validate_answer(row, where)
        key = (qid, row["answer_id"])
        if key in seen:
            raise InputError(f"{where} repeats question/answer_id; use distinct ids for independent answers")
        seen.add(key)
        evidence_key = (qid, row["source_id"], row["locator_id"])
        if evidence_key not in choices:
            raise InputError(f"{where} unknown/unbound source or locator for {qid}")
        if row["evidence_fingerprint"] != choices[evidence_key]["fingerprint"]:
            raise InputError(f"{where} stale or missing evidence_fingerprint; prepare current evidence and review again")
    # Conflicting ownership in a single batch is ambiguous; no row wins by ordering.
    owners = {}
    for row in rows:
        owner = row["owner"]
        if bool(row["assigned_by"]) != bool(row["assigned_on"]):
            raise InputError("assigned_by and assigned_on must be supplied together")
        if row["assigned_on"]:
            iso_date(row["assigned_on"], "assigned_on")
        if row["assigned_by"] and not owner:
            raise InputError("assigned_by requires an explicit owner or needs_owner")
        if owner:
            if row["question_id"] in owners and owners[row["question_id"]] != owner:
                raise InputError(f"conflicting owner assignments for {row['question_id']}")
            owners[row["question_id"]] = owner
    return rows


def reconcile(register, questions, sources, choices, rows):
    out = copy.deepcopy(register)
    validate_register(out)
    owners = {r["question_id"]: r for r in out["ownership_history"]}
    latest = {(r["question_id"], r["answer_id"]): r for r in out["decisions"]}
    for row in rows:
        qid = row["question_id"]
        if row["owner"]:
            owner = None if row["owner"] == "needs_owner" else row["owner"]
            previous_owner = owners.get(qid, {}).get("owner")
            if previous_owner != owner:
                if not row["assigned_by"] or not row["assigned_on"]:
                    raise InputError(f"ownership change for {qid} requires explicit assigned_by and assigned_on")
                rec = {"question_id": qid, "owner": owner, "by": row["assigned_by"], "on": row["assigned_on"],
                       "previous": owners.get(qid, {}).get("id")}
                rec["id"] = record_id(rec, "o-")
                out["ownership_history"].append(rec)
                owners[qid] = rec
        if not row["answer"]:
            continue
        key = (qid, row["answer_id"])
        old = latest.get(key)
        rec = {k: row[k] for k in COLUMNS if k not in ("source_id", "locator_id", "owner", "assigned_by", "assigned_on")}
        rec["owner"] = owners.get(qid, {}).get("owner")
        rec["evidence"] = copy.deepcopy(choices[(qid, row["source_id"], row["locator_id"])]["evidence"])
        rec["previous"] = old["id"] if old else None
        if old and {k: v for k, v in old.items() if k not in ("id", "previous")} == {
                k: v for k, v in rec.items() if k != "previous"}:
            continue
        rec["id"] = record_id(rec, "d-")
        out["decisions"].append(rec)
        latest[key] = rec
    current = {}
    all_ids = set(questions) | {r["question_id"] for r in out["decisions"]} | set(owners)
    for qid in sorted(all_ids):
        answers = []
        for (question_id, _), rec in sorted(latest.items()):
            if question_id != qid:
                continue
            old = rec["evidence"]
            choice = choices.get((qid, old["source"]["id"], old["source"]["locator_id"]))
            changed = []
            if qid not in questions:
                changed.append("question removed")
            else:
                for part in ("question", "assets"):
                    if old[part] != questions[qid][part]:
                        changed.append(part + " content")
            if choice is None:
                changed.append("source/locator removed or binding withdrawn")
            elif choice["evidence"]["source"] != old["source"]:
                changed.append("source revision/bytes/locator")
            answers.append({"decision_id": rec["id"], "answer_id": rec["answer_id"],
                            "freshness": "stale" if changed else "current", "changed": changed})
        active = [latest[(qid, a["answer_id"])] for a in answers
                  if a["freshness"] == "current" and latest[(qid, a["answer_id"])]["decision"] != "rejected"]
        values = {}
        for rec in active:
            values.setdefault(rec["claim_key"], set()).add(rec["value"])
        conflicts = sorted(k for k, v in values.items() if len(v) > 1)
        state = ("disputed" if conflicts else "needs_data" if any(r["answer_state"] == "needs_data" for r in active)
            else "answered" if any(r["answer_state"] == "answered" and r["decision"] == "accepted" for r in active)
            else "partial" if active else "unanswered")
        owner = owners.get(qid, {}).get("owner")
        current[qid] = {"present": qid in questions, "question": questions.get(qid, {}).get("question"),
                        "owner": owner, "ownership": "assigned" if owner else "needs_owner",
                        "assigned_by": owners.get(qid, {}).get("by"), "assigned_on": owners.get(qid, {}).get("on"),
                        "state": state, "disputed_claims": conflicts, "answers": answers}
    out["sources"] = [sources[k] for k in sorted(sources)]
    out["current"] = current
    validate_register(out)
    return out


def csv_text(columns, rows):
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def md(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def report(register):
    lines = ["# Engineering context register", "", "Draft for engineering review. Source match and plant truth "
             "are separate explicit verdicts; unknown is never upgraded by this tool.", ""]
    by_id = {r["id"]: r for r in register["decisions"]}
    for qid, q in register["current"].items():
        question = q["question"] or {}
        wording = question.get("question", "Question removed from the current input")
        lines += [f"## {md(qid)}: {md(wording)}", "",
                  f"State: **{q['state']}**; owner: **{md(q['owner'] or 'needs owner')}**; "
                  f"present in current input: {'yes' if q['present'] else 'no'}.", ""]
        if q["assigned_by"]:
            lines += [f"Owner assigned by {md(q['assigned_by'])} on {md(q['assigned_on'])}.", ""]
        if question.get("data_requests"):
            lines += ["Collection prompts from the screen. These are not per-request completion records; "
                      "an answer does not automatically satisfy or clear them.", ""]
            for request in question["data_requests"]:
                if not isinstance(request, dict):
                    lines += [f"- {md(request)}", ""]
                    continue
                lines.append(f"- **{md(request.get('item', 'Collection prompt'))}**")
                fields = request.get("fields") or []
                for field in fields if isinstance(fields, list) else [fields]:
                    lines.append(f"  Field: {md(field)}")
                if request.get("how"):
                    lines.append(f"  How: {md(request['how'])}")
                where = request.get("where") or []
                for location in where if isinstance(where, list) else [where]:
                    if isinstance(location, dict):
                        parts = [md(location[k]) for k in ("kind", "description") if location.get(k)]
                        lines.append("  Where: " + ": ".join(parts))
                    else:
                        lines.append(f"  Where: {md(location)}")
                lines.append("")
        if question.get("decision_rule"):
            lines += [f"Decision rule from the screen: {md(question['decision_rule'])}", ""]
        if question.get("limits"):
            lines += [f"Limits from the screen: {md(question['limits'])}", ""]
        if not q["answers"]:
            lines += ["No answer recorded. The question remains visible.", ""]
        for answer in q["answers"]:
            rec = by_id[answer["decision_id"]]
            src = rec["evidence"]["source"]
            lines += [f"- `{md(rec['answer_id'])}`: **{answer['freshness']}**, {rec['decision']}, "
                      f"{rec['answer_state']}; `{md(rec['claim_key'])}` = **{md(rec['value'])}**.",
                      f"  {md(rec['answer'])}",
                      f"  Source: {md(src['id'])}, revision {md(src['revision'])}, {md(src['locator'])}; "
                      f"SHA-256 `{src['sha256']}`.",
                      f"  Source match: {rec['source_match']}; plant truth: {rec['plant_truth']}; "
                      f"reviewer: {md(rec['reviewer'] or 'not recorded')}, "
                      f"reviewed on: {md(rec['reviewed_on'] or 'not recorded')}; "
                      f"owner at decision: {md(rec['owner'] or 'needs owner')}."]
            if answer["changed"]:
                lines.append("  Reopened because: " + ", ".join(answer["changed"]) + ".")
            if rec["note"]:
                lines.append("  Note: " + md(rec["note"]))
            lines.append("")
    lines += [f"Immutable history: {len(register['decisions'])} decisions, "
              f"{len(register['ownership_history'])} ownership assignments. Full old evidence snapshots are in context.json.", "",
              "A repeated answer_id explicitly revises that answer. Independent answers need different answer ids. "
              "Different canonical values under one claim_key remain disputed until an engineer explicitly revises "
              "or rejects an answer. Prose wording is not compared for agreement.", ""]
    return "\n".join(lines)


def outputs(graph, qdoc, register, choices, prepare=False):
    g, qs = copy.deepcopy(graph), copy.deepcopy(qdoc)
    for doc in (g, qs):
        doc["context_register"] = {"schema": SCHEMA, "sidecar": "context.json"}
        for question in doc.get("questions", []):
            if question.get("id") in register["current"]:
                question["context"] = copy.deepcopy(register["current"][question["id"]])
    # The supplied questions are attached to a copy of the graph, never applied as plant facts.
    g["questions"] = copy.deepcopy(qs["questions"])
    if isinstance(g.get("counts"), dict):
        g["counts"]["questions"] = len(g["questions"])
    files = {"context.json": json.dumps(register, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
             "context.md": report(register), "enriched_graph.json": json.dumps(g, indent=2, ensure_ascii=False) + "\n",
             "enriched_questions.json": json.dumps(qs, indent=2, ensure_ascii=False) + "\n"}
    if prepare:
        rows = []
        for qid in sorted(register["current"]):
            q = register["current"][qid]
            if q["present"]:
                row = {c: "" for c in COLUMNS}
                row.update(question_id=qid, owner=q["owner"] or "needs_owner", answer_state="needs_data",
                           decision="proposed", source_match="unknown", plant_truth="unknown")
                rows.append(row)
        files["answers.csv"] = csv_text(COLUMNS, rows)
        rows = []
        lines = ["# Current evidence choices", "", "Copy source_id, locator_id and evidence_fingerprint from one "
                 "row into an answer. Check the cited document yourself. Fingerprints bind raw bytes and context, "
                 "not the correctness of an answer.", ""]
        for (qid, did, lid), choice in sorted(choices.items()):
            src = choice["evidence"]["source"]
            rows.append(dict(question_id=qid, source_id=did, revision=src["revision"], sha256=src["sha256"],
                             locator_id=lid, locator=src["locator"], evidence_fingerprint=choice["fingerprint"]))
            lines += [f"- **{md(qid)}** — source_id `{md(did)}`, locator_id `{md(lid)}`; "
                      f"revision {md(src['revision'])}; {md(src['locator'])}.",
                      f"  evidence_fingerprint: `{choice['fingerprint']}`", ""]
        files["evidence_choices.csv"] = csv_text(CHOICE_COLUMNS, rows)
        files["evidence_choices.md"] = "\n".join(lines)
    return files


def preserve_destination_history(destination, register, supplied_register):
    """A local refresh may extend retained history, never silently replace or merge it."""
    if not destination.exists() and not destination.is_symlink():
        return
    guidance = ("use --register pointing to the current destination context.json "
                "or choose a new output directory")
    try:
        existing = read_json(destination, "destination register")
        validate_register(existing)
    except InputError as exc:
        raise InputError(f"existing destination context.json is invalid: {exc}; "
                         "choose a new output directory and preserve the existing file") from exc
    histories = ("decisions", "ownership_history")
    if not supplied_register and any(existing[field] for field in histories):
        raise InputError(f"existing destination has retained history; {guidance}")
    for field in histories:
        retained = existing[field]
        if register[field][:len(retained)] != retained:
            raise InputError(f"existing destination {field} must remain an unchanged ordered history prefix; "
                             f"{guidance}. Older or divergent histories are not merged or reset")


def run(args):
    graph, qdoc, questions = load_inputs(args.model, args.questions)
    sources, choices, source_paths = load_sources(args.sources, questions, args.source_root)
    register = read_json(args.register, "register") if args.register else empty_register()
    validate_register(register)
    rows = read_answers(args.answers, questions, choices) if getattr(args, "answers", None) else []
    register = reconcile(register, questions, sources, choices, rows)
    files = outputs(graph, qdoc, register, choices, args.command == "prepare")
    folder = Path(args.out)
    preserve_destination_history(folder / "context.json", register, args.register)
    if args.command == "prepare" and (folder / "answers.csv").exists():
        raise InputError("prepare would overwrite answers.csv; choose a new folder to refresh evidence")
    inputs = [Path(p) for p in (args.model, args.questions, args.sources, getattr(args, "answers", None)) if p]
    inputs += source_paths
    targets = [folder / name for name in files]

    def aliases(first, second):
        if first.resolve() == second.resolve():
            return True
        try:
            return first.samefile(second)
        except FileNotFoundError:
            return False

    for target in targets:
        if any(aliases(target, source) for source in inputs):
            raise InputError("output would overwrite an input model/questions/manifest/answer sheet/source document")
        if args.register and aliases(target, Path(args.register)):
            # The one intentional overwrite is refreshing the explicitly supplied context.json in place.
            intended = (target.name == "context.json" and
                        Path(os.path.abspath(args.register)) == Path(os.path.abspath(target)))
            if not intended:
                raise InputError("output would overwrite/alias the supplied register outside context.json refresh")
    for i, target in enumerate(targets):
        if any(aliases(target, other) for other in targets[i + 1:]):
            raise InputError("output files alias each other; refusing to overwrite linked outputs")
    # All inputs, references, evidence bindings and output collisions are validated before the first write.
    folder.mkdir(parents=True, exist_ok=True)
    for name, value in files.items():
        with (folder / name).open("w", encoding="utf-8", newline="") as f:
            f.write(value)
    return register


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("prepare", "apply"):
        sub = commands.add_parser(command)
        for flag in ("model", "questions", "sources", "out"):
            sub.add_argument("--" + flag, required=True)
        sub.add_argument("--source-root", help="local root containing manifest document paths; default manifest folder")
        sub.add_argument("--register", help="existing context.json; required to retain nonempty destination history")
        if command == "apply":
            sub.add_argument("--answers", help="filled prepared CSV; omit to refresh staleness only")
    args = parser.parse_args(argv)
    try:
        register = run(args)
    except (InputError, OSError, ValueError) as exc:
        print(f"context register: {exc}", file=sys.stderr)
        return 2
    states = {}
    for question in register["current"].values():
        states[question["state"]] = states.get(question["state"], 0) + 1
    print("Context register: " + ", ".join(f"{n} {state}" for state, n in sorted(states.items()))
          + f"; {len(register['decisions'])} historical decisions. Draft for review.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
