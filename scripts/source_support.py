"""Validate bounded source-review packets and score supplied claim judgments; never infer support from prose."""
from collections import Counter
import re

LABELS = ("supported", "contradicted", "insufficient-evidence")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text(value, label):
    require(isinstance(value, str) and value.strip(), label + " must be nonempty text")
    return value


def identity(value, label):
    text(value, label)
    require(value == value.strip(), label + " must preserve an exact, unpadded identity")
    return value


def indexed(rows, label):
    require(isinstance(rows, list) and rows, label + " must be a nonempty list")
    result = {}
    for row in rows:
        require(isinstance(row, dict), label + " entry must be an object")
        ident = identity(row.get("id"), label + " id")
        require(ident not in result, "Duplicate " + label + " id: " + ident)
        result[ident] = row
    return result


def references(values, allowed, label):
    require(isinstance(values, list) and values, label + " must be a nonempty list")
    require(all(isinstance(v, str) and v in allowed for v in values), label + " contains an unknown identity")
    require(len(set(values)) == len(values), label + " repeats an identity")


def validate(packet, key):
    require(isinstance(packet, dict) and packet.get("schema") == "source-support-input-1",
            "Expected source-support-input-1 packet")
    sources = indexed(packet.get("sources"), "source")
    for row in sources.values():
        for name in ("title", "identity", "url", "time_scope", "admitted_scope"):
            text(row.get(name), "source " + name)
        require(isinstance(row.get("sha256"), str) and re.fullmatch(r"[0-9a-f]{64}", row["sha256"]),
                "source needs a declared original SHA256; originals are not fetched or read by this scorer")
    evidence = indexed(packet.get("evidence"), "evidence")
    for row in evidence.values():
        for name in ("paraphrase", "locator", "time_scope"):
            text(row.get(name), "evidence " + name)
        references(row.get("source_ids"), sources, "evidence source_ids")
    items = indexed(packet.get("items"), "claim")
    for row in items.values():
        for name in ("candidate_claim", "claim_time_scope", "family"):
            text(row.get(name), "claim " + name)
        references(row.get("admitted_evidence_ids"), evidence, "claim admitted_evidence_ids")
    require(isinstance(key, dict) and set(key) == {"judgments"} and isinstance(key["judgments"], dict),
            "Source-support key needs exactly a judgments object")
    truth = key["judgments"]
    require(set(truth) == set(items), "Source-support key must label every exact claim id and no others")
    require(all(isinstance(v, str) and v in LABELS for v in truth.values()), "Key has an unknown judgment label")
    return items, truth


def score(packet, key, prediction):
    items, truth = validate(packet, key)
    supplied = {}
    if prediction is not None:
        require(isinstance(prediction, dict) and set(prediction) == {"schema", "decisions"} and
                prediction["schema"] == "source-support-answer-1" and isinstance(prediction["decisions"], list),
                "Expected source-support-answer-1 with a decisions list")
        for row in prediction["decisions"]:
            require(isinstance(row, dict) and set(row) == {"id", "judgment", "evidence_ids", "reason"},
                    "Decision needs exactly id, judgment, evidence_ids and reason")
            ident = identity(row["id"], "decision id")
            require(ident in items and ident not in supplied, "Unknown or duplicate decision id: " + ident)
            require(isinstance(row["judgment"], str) and row["judgment"] in LABELS, "Unknown judgment label")
            references(row["evidence_ids"], items[ident]["admitted_evidence_ids"], "decision evidence_ids")
            text(row["reason"], "decision reason")
            supplied[ident] = row["judgment"]
    correct = sum(truth[ident] == label for ident, label in supplied.items())
    counts = {"judgments": {"tp": correct, "predicted": len(supplied), "truth": len(truth)}}
    predicted_counts, truth_counts = Counter(supplied.values()), Counter(truth.values())
    for label in LABELS:
        counts[label] = {"tp": sum(supplied.get(i) == label and expected == label for i, expected in truth.items()),
                         "predicted": predicted_counts[label], "truth": truth_counts[label]}
    diagnostics = {"correct_judgments": correct, "expected_judgments": len(truth),
                   "exact_label_accuracy": correct / len(truth),
                   "missing_judgments": sorted(set(truth) - set(supplied)),
                   "incorrect_judgments": [{"id": i, "expected": truth[i], "predicted": label}
                                           for i, label in supplied.items() if label != truth[i]],
                   "reason_quality_scored": False,
                   "scope": "Fixed supplied claim labels only; citation IDs checked structurally. No automatic prose, source-validity or plant-truth judgment."}
    return counts, diagnostics


def controls(packet, key):
    items, truth = validate(packet, key)
    def answer(labels):
        return {"schema": "source-support-answer-1", "decisions": [
            {"id": i, "judgment": label, "evidence_ids": [items[i]["admitted_evidence_ids"][0]],
             "reason": "Synthetic evaluator control; reasoning quality is not scored."} for i, label in labels.items()]}
    predictions = {"reference": answer(truth), "empty": None}
    predictions.update({"all_" + label: answer(dict.fromkeys(items, label)) for label in LABELS})
    return {name: score(packet, key, prediction)[0] for name, prediction in predictions.items()}
