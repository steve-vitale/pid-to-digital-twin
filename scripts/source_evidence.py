"""Bounded opaque XML source occurrences and explicit native assignment provenance.

This module does not interpret source records as physical assets, source authority or engineering approval.
The parser preserves expanded names before the legacy reader normalizes its own interpretation tree.
"""
import copy
import hashlib
import json
import math
import re
import xml.etree.ElementTree as ET
from collections import Counter

SCHEMA = "xml-source-evidence-1"
RECORD_SCHEMA = "source-record-1"
CAPABILITY = "source-record-1"
POLICY_ID = "named-fields-xml-1"
MAX_BYTES = 256 * 1024 * 1024
PERSON_PATTERN = r"(Approver|Checker|Creator|Designer|Drafter|Editor|Reviewer|Owner)Name"
PERSON = re.compile(PERSON_PATTERN, re.I)
SCOPE_EXCLUSIONS = {"ShapeCatalogue": "shape-catalogue", "Drawing": "drawing-titleblock",
                    "Text": "presentation-text", "Extent": "geometry-extent", "Position": "geometry-position",
                    "Presentation": "presentation-style", "Scale": "geometry-scale", "Coordinate": "geometry-coordinate"}
TARGET_ROOTS = ("meta", "units", "streams", "instruments", "final_elements", "controllers", "manual_valves",
                "relief_devices", "unplaced")
KINDS = ("direct-copy", "legacy-transform", "container-transfer")
BASES = ("generic-value", "generic-units", "generic-set", "part-class", "metadata-value", "file-metadata",
         "plant-structure-id", "plant-structure-class")
POLICY = {"id": POLICY_ID, "version": 1, "person_pattern": PERSON_PATTERN, "flags": "IGNORECASE",
          "designation": "any-expanded-local-Name-case-insensitive", "role_names": "exact-unqualified-only",
          "scope_exclusions": SCOPE_EXCLUSIONS, "scope_precedence": "first-excluded-ancestor",
          "text_and_tail": "excluded-no-payload", "default_structure": "retain-every-eligible-element"}
MAPPING = {"id": "native-assignment-1", "version": 1, "target_roots": list(TARGET_ROOTS),
           "mapping_kinds": list(KINDS), "basis_labels": list(BASES), "pointer": "RFC6901",
           "generation": "concrete-container-and-slot-every-write", "composite": "unmapped",
           "excluded_targets": ["line_layers", "report", "prediction", "source_evidence"]}
RECORD_FIELDS = {"schema", "kind", "occurrence_id", "document_id", "raw_source_sha256", "locator", "raw_payload",
                 "mappings", "application_status", "policy_sha256", "mapping_sha256", "record_version_id", "id"}
PAYLOAD_FIELDS = {"element_name", "original_id", "attributes", "children", "parent_occurrence_id", "source_assertions"}
PACKET_FIELDS = {"schema", "required_capabilities", "document", "policy", "mapping", "records", "exclusions",
                 "completeness", "native_model_sha256", "integrity_sha256"}
HEX = re.compile(r"[0-9a-f]{64}\Z")
_NO_ORIGINAL = object()


class SourceEvidenceError(ValueError):
    """A source packet or declared assignment cannot be validated; no raw payload is echoed."""


class _DuplicateSourceIDs(SourceEvidenceError):
    """Internal strict refusal handoff: root is never part of exception text or serialized evidence."""

    def __init__(self, root):
        super().__init__("live XML IDs used more than once")
        self._root = root


def _require(test, message):
    if not test:
        raise SourceEvidenceError(message)


def _json(value, ancestors=None):
    ancestors = set() if ancestors is None else ancestors
    if value is None or type(value) is str or type(value) is bool or type(value) is int:
        return
    if type(value) is float:
        _require(math.isfinite(value), "nonfinite JSON value")
        return
    _require(type(value) is dict or type(value) is list, "unsupported JSON value")
    _require(id(value) not in ancestors, "cyclic JSON value")
    ancestors = ancestors | {id(value)}
    if type(value) is dict:
        _require(all(type(k) is str for k in value), "JSON object keys must be strings")
        for item in value.values():
            _json(item, ancestors)
    else:
        for item in value:
            _json(item, ancestors)


def canonical(value):
    _json(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _native_encoding_bytes(value):
    """Validate unchanged canonical encoding without exposing caller payload in codec diagnostics."""
    try:
        return canonical(value)
    except SourceEvidenceError:
        raise
    except (UnicodeError, ValueError, OverflowError):
        raise SourceEvidenceError("native write is not canonically UTF-8 encodable") from None


def _native_write_encoding(container, key_or_index, value):
    """After slot/profile admission, validate the complete touched key/value without changing state."""
    if type(container) is dict:
        _native_encoding_bytes(key_or_index)
    return _native_encoding_bytes(value)


POLICY_SHA256 = digest(POLICY)
MAPPING_SHA256 = digest(MAPPING)


def load_json_strict(text):
    def pairs(items):
        out = {}
        for key, value in items:
            _require(key not in out, "duplicate JSON object key")
            out[key] = value
        return out
    def nonfinite(_):
        raise SourceEvidenceError("nonfinite JSON value")
    try:
        value = json.loads(text, object_pairs_hook=pairs, parse_constant=nonfinite)
    except (ValueError, UnicodeError, TypeError) as exc:
        raise SourceEvidenceError("invalid strict JSON input") from exc
    _json(value)
    return value


def qname(name):
    _require(type(name) is str and bool(name), "invalid expanded XML name")
    if name.startswith("{") and "}" in name:
        namespace, local = name[1:].split("}", 1)
        return {"namespace_uri": namespace, "local_name": local}
    return {"namespace_uri": "", "local_name": name}


def _name(name):
    _require(type(name) is dict and set(name) == {"namespace_uri", "local_name"}, "invalid QName fields")
    _require(type(name["namespace_uri"]) is str and type(name["local_name"]) is str and bool(name["local_name"]),
             "invalid QName values")


def _positive(value):
    return type(value) is int and value > 0


def _hash(value):
    return type(value) is str and HEX.fullmatch(value) is not None


def _locator(locator, kind):
    expected = {"path"} if kind == "element" else {"path", "attribute"}
    _require(type(locator) is dict and set(locator) == expected, "invalid occurrence locator fields")
    _require(type(locator["path"]) is list and bool(locator["path"]), "empty occurrence path")
    for component in locator["path"]:
        _require(type(component) is dict and set(component) == {"name", "ordinal"}, "invalid path component")
        _name(component["name"])
        _require(_positive(component["ordinal"]), "invalid path ordinal")
    _require(locator["path"][0]["ordinal"] == 1, "invalid root ordinal")
    if kind == "attribute":
        a = locator["attribute"]
        _require(type(a) is dict and set(a) == {"name", "ordinal"}, "invalid attribute locator")
        _name(a["name"])
        _require(_positive(a["ordinal"]), "invalid attribute ordinal")


def occurrence(document_id, source_sha, kind, locator):
    return digest({"document_id": document_id, "raw_source_sha256": source_sha, "kind": kind, "locator": locator})


def _body(record):
    return {k: v for k, v in record.items() if k not in ("id", "record_version_id")}


def _document(document):
    _require(type(document) is dict and set(document) == {"document_id", "raw_source_sha256", "raw_size_bytes", "root_name"},
             "invalid document envelope")
    _require(type(document["document_id"]) is str and bool(document["document_id"])
             and document["document_id"] == document["document_id"].strip(), "invalid document identity")
    _require(_hash(document["raw_source_sha256"]), "invalid raw source digest")
    _require(type(document["raw_size_bytes"]) is int and 0 <= document["raw_size_bytes"] <= MAX_BYTES, "invalid raw source size")
    _name(document["root_name"])


def _descriptor(value, expected, name):
    _require(type(value) is dict and canonical(value) == canonical(expected), "unknown " + name + " descriptor")


def _pointer(components):
    return "/" + "/".join(s.replace("~", "~0").replace("/", "~1") for s in components)


def _resolve(model, components):
    current = model
    for component in components:
        if type(current) is dict:
            _require(component in current, "missing native pointer destination")
            current = current[component]
        elif type(current) is list:
            _require(component.isdecimal() and str(int(component)) == component, "invalid native array pointer")
            i = int(component)
            _require(i < len(current), "missing native array destination")
            current = current[i]
        else:
            raise SourceEvidenceError("native pointer crosses a scalar")
    return current


def validate_record(record, document, *, policy, mapping):
    _json(record)
    _document(document)
    _descriptor(policy, POLICY, "policy")
    _descriptor(mapping, MAPPING, "mapping")
    _require(type(record) is dict and set(record) == RECORD_FIELDS, "invalid source record fields")
    _require(record["schema"] == RECORD_SCHEMA and record["kind"] == "source_record", "unknown source record schema/kind")
    _require(record["application_status"] == "unverified", "source record must remain unverified")
    _require(record["document_id"] == document["document_id"] and record["raw_source_sha256"] == document["raw_source_sha256"],
             "source document identity mismatch")
    _require(record["policy_sha256"] == POLICY_SHA256 and record["mapping_sha256"] == MAPPING_SHA256,
             "unknown source policy/mapping hash")
    _locator(record["locator"], "element")
    _require(not any(c["name"]["local_name"] in SCOPE_EXCLUSIONS for c in record["locator"]["path"]),
             "scope-excluded source path")
    _require(record["locator"]["path"][0]["name"] == document["root_name"], "source root mismatch")
    _require(record["occurrence_id"] == occurrence(record["document_id"], record["raw_source_sha256"], "element", record["locator"]),
             "source element identity mismatch")
    payload = record["raw_payload"]
    _require(type(payload) is dict and set(payload) == PAYLOAD_FIELDS, "invalid raw source payload fields")
    _name(payload["element_name"])
    _require(payload["element_name"] == record["locator"]["path"][-1]["name"], "payload element name mismatch")
    original = payload["original_id"]
    _require(type(original) is dict and type(original.get("present")) is bool, "invalid original ID presence")
    _require(set(original) == ({"present", "value"} if original["present"] else {"present"}), "invalid original ID fields")
    if original["present"]:
        _require(type(original["value"]) is str, "invalid original ID value")
    _require(type(payload["attributes"]) is list and type(payload["children"]) is list and type(payload["source_assertions"]) is list,
             "invalid ordered source payload arrays")
    owned = [record["occurrence_id"]]
    previous = 0
    names = set()
    attributes = {}
    for a in payload["attributes"]:
        _require(type(a) is dict and set(a) == {"occurrence_id", "name", "ordinal", "value"}, "invalid raw attribute fields")
        _name(a["name"])
        _require(_positive(a["ordinal"]) and a["ordinal"] > previous, "raw attribute order mismatch")
        previous = a["ordinal"]
        _require(type(a["value"]) is str, "XML attribute values must remain strings")
        key = canonical(a["name"])
        _require(key not in names and not PERSON.search(a["name"]["local_name"]), "duplicate or protected raw attribute")
        names.add(key)
        loc = dict(record["locator"], attribute={"name": a["name"], "ordinal": a["ordinal"]})
        _require(a["occurrence_id"] == occurrence(record["document_id"], record["raw_source_sha256"], "attribute", loc),
                 "source attribute identity mismatch")
        owned.append(a["occurrence_id"])
        attributes[a["occurrence_id"]] = a
    ids = [a for a in payload["attributes"] if a["name"] == {"namespace_uri": "", "local_name": "ID"}]
    _require(original == ({"present": True, "value": ids[0]["value"]} if ids else {"present": False}), "original ID role mismatch")
    if payload["element_name"]["local_name"] == "GenericAttribute":
        _require(not any(a["name"]["local_name"].casefold() == "name" and PERSON.search(a["value"])
                         for a in payload["attributes"]), "protected source designation")
    _require(payload["element_name"]["local_name"] not in SCOPE_EXCLUSIONS, "scope-excluded source element")
    _require(all(_hash(x) for x in payload["children"]) and len(set(payload["children"])) == len(payload["children"]),
             "invalid child occurrence references")
    _require(payload["parent_occurrence_id"] is None or _hash(payload["parent_occurrence_id"]), "invalid parent occurrence")
    for assertion in payload["source_assertions"]:
        _require(type(assertion) is dict and set(assertion) == {"attribute_occurrence_id", "role", "target_text",
                 "resolution_status", "resolved_occurrence_ids"}, "invalid source assertion")
        _require(payload["element_name"]["local_name"] in ("Connection", "Association"), "assertion on nonassertion source")
        _require(_hash(assertion["attribute_occurrence_id"]) and assertion["attribute_occurrence_id"] in attributes
                 and assertion["role"] in ("FromID", "ToID", "ItemID", "TagName"),
                 "invalid source assertion origin")
        a = attributes[assertion["attribute_occurrence_id"]]
        _require(a["name"] == {"namespace_uri": "", "local_name": assertion["role"]} and assertion["target_text"] == a["value"],
                 "source assertion role/value mismatch")
        _require(assertion["resolution_status"] == "unverified" and type(assertion["resolved_occurrence_ids"]) is list
                 and all(_hash(x) for x in assertion["resolved_occurrence_ids"]), "invalid source assertion resolution")
    _require(type(record["mappings"]) is list and len(record["mappings"]) == len(owned), "incomplete mapping dispositions")
    mapped = []
    for entry in record["mappings"]:
        _require(type(entry) is dict and set(entry) == {"source_occurrence_id", "disposition", "destinations"}, "invalid mapping fields")
        mapped.append(entry["source_occurrence_id"])
        dests = entry["destinations"]
        _require(type(dests) is list and entry["disposition"] == ("direct" if dests else "unmapped"), "invalid mapping disposition")
        pointers = []
        for destination in dests:
            _require(type(destination) is dict and set(destination) == {"pointer", "components", "mapping_kind", "basis", "destination_sha256"},
                     "invalid native destination fields")
            components = destination["components"]
            _require(type(components) is list and len(components) >= 2 and all(type(c) is str for c in components)
                     and components[0] in TARGET_ROOTS, "forbidden native pointer root")
            _require(destination["pointer"] == _pointer(components), "native pointer/components mismatch")
            _require(destination["mapping_kind"] in KINDS and destination["basis"] in BASES and _hash(destination["destination_sha256"]),
                     "invalid native mapping profile")
            pointers.append(destination["pointer"])
        _require(len(set(pointers)) == len(pointers), "duplicate native mapping destination")
    _require(mapped == owned, "mapping occurrence order/identity mismatch")
    version = digest(_body(record))
    _require(record["record_version_id"] == version and record["id"] == "source_record:" + version, "source record version mismatch")


def _native_digest(model):
    _require(type(model) is dict, "native model must be an object")
    return digest({k: v for k, v in model.items() if k != "source_evidence"})


def validate_packet(packet, *, native_model=None, require_native_targets=False):
    _json(packet)
    _require(type(packet) is dict and set(packet) == PACKET_FIELDS, "invalid source packet fields")
    _require(packet["schema"] == SCHEMA and packet["required_capabilities"] == [CAPABILITY], "unknown source packet schema/capability")
    doc = packet["document"]
    _document(doc)
    _descriptor(packet["policy"], POLICY, "policy")
    _descriptor(packet["mapping"], MAPPING, "mapping")
    _require(type(packet["records"]) is list and bool(packet["records"]) and type(packet["exclusions"]) is list,
             "invalid source packet record/exclusion arrays")
    records, all_ids, versions = {}, set(), set()
    element_paths, attribute_slots = {}, {}
    counts = {"elements": Counter(), "attributes": Counter()}
    for record in packet["records"]:
        validate_record(record, doc, policy=packet["policy"], mapping=packet["mapping"])
        rid = record["occurrence_id"]
        _require(rid not in records and record["record_version_id"] not in versions, "duplicate source record identity/version")
        records[rid] = record
        element_paths[canonical(record["locator"]["path"])] = record["locator"]["path"]
        for a in record["raw_payload"]["attributes"]:
            attribute_slots.setdefault(canonical(record["locator"]["path"]), []).append(a["ordinal"])
        versions.add(record["record_version_id"])
        owned = [rid] + [a["occurrence_id"] for a in record["raw_payload"]["attributes"]]
        _require(not (all_ids & set(owned)), "duplicate source occurrence identity")
        all_ids.update(owned)
        counts["elements"]["retained"] += 1
        counts["attributes"]["retained"] += len(owned) - 1
    for excluded in packet["exclusions"]:
        _require(type(excluded) is dict and set(excluded) == {"occurrence_id", "kind", "locator", "disposition", "reason"},
                 "invalid safe exclusion fields")
        kind, disposition = excluded["kind"], excluded["disposition"]
        _require(kind in ("element", "attribute") and disposition in ("policy-redacted", "scope-excluded"), "unknown exclusion disposition")
        _require(type(excluded["reason"]) is str and excluded["reason"] in set(SCOPE_EXCLUSIONS.values()) | {"person-designation", "person-field"}, "unknown exclusion reason")
        _locator(excluded["locator"], kind)
        path = excluded["locator"]["path"]
        _require(path[0]["name"] == doc["root_name"], "exclusion root mismatch")
        scopes = [SCOPE_EXCLUSIONS[c["name"]["local_name"]] for c in path if c["name"]["local_name"] in SCOPE_EXCLUSIONS]
        if disposition == "scope-excluded":
            _require(bool(scopes) and excluded["reason"] == scopes[0], "scope exclusion precedence mismatch")
        else:
            if excluded["reason"] == "person-field":
                _require(not scopes and kind == "attribute" and bool(PERSON.search(excluded["locator"]["attribute"]["name"]["local_name"])),
                         "person-field exclusion role mismatch")
            else:
                ga_indices = [i for i, c in enumerate(path) if c["name"]["local_name"] == "GenericAttribute"]
                scope_indices = [i for i, c in enumerate(path) if c["name"]["local_name"] in SCOPE_EXCLUSIONS]
                _require(excluded["reason"] == "person-designation" and bool(ga_indices)
                         and (not scope_indices or ga_indices[0] < scope_indices[0]),
                         "person-designation exclusion path mismatch")
        oid = occurrence(doc["document_id"], doc["raw_source_sha256"], kind, excluded["locator"])
        _require(excluded["occurrence_id"] == oid and oid not in all_ids, "duplicate or malformed exclusion identity")
        all_ids.add(oid)
        if kind == "element":
            element_paths[canonical(path)] = path
        else:
            attribute_slots.setdefault(canonical(path), []).append(excluded["locator"]["attribute"]["ordinal"])
        counts["elements" if kind == "element" else "attributes"][disposition.replace("-", "_")] += 1
    sibling_ordinals = {}
    for path in element_paths.values():
        if len(path) > 1:
            _require(canonical(path[:-1]) in element_paths, "missing structural source parent")
            sibling_ordinals.setdefault((canonical(path[:-1]), canonical(path[-1]["name"])), []).append(path[-1]["ordinal"])
    for path, ordinals in attribute_slots.items():
        _require(path in element_paths, "attribute without source element")
        _require(sorted(ordinals) == list(range(1, len(ordinals) + 1)), "duplicate or missing original attribute ordinal")
    for ordinals in sibling_ordinals.values():
        _require(sorted(ordinals) == list(range(1, len(ordinals) + 1)), "duplicate or missing source sibling ordinal")
    roots = []
    for rid, record in records.items():
        payload = record["raw_payload"]
        parent = payload["parent_occurrence_id"]
        if parent is None:
            roots.append(rid)
            _require(len(record["locator"]["path"]) == 1, "nonroot missing source parent")
        else:
            _require(parent in records and rid in records[parent]["raw_payload"]["children"], "broken source parent/child reference")
            _require(record["locator"]["path"][:-1] == records[parent]["locator"]["path"], "invalid source parent locator")
        for child in payload["children"]:
            _require(child in records and records[child]["raw_payload"]["parent_occurrence_id"] == rid, "broken source child reference")
        for assertion in payload["source_assertions"]:
            _require(all(x in records for x in assertion["resolved_occurrence_ids"]), "unknown source assertion occurrence")
    _require(len(roots) == 1 and records[roots[0]]["locator"]["path"][0]["name"] == doc["root_name"], "missing unique source root")
    complete = packet["completeness"]
    _require(type(complete) is dict and set(complete) == {"elements", "attributes", "text_presence", "native_mapping"}, "invalid completeness fields")
    for name in ("elements", "attributes"):
        c = complete[name]
        _require(type(c) is dict and set(c) == {"total", "retained", "policy_redacted", "scope_excluded"}, "invalid completeness counts")
        _require(all(type(v) is int and v >= 0 for v in c.values()), "invalid occurrence count")
        _require(all(c[k] == counts[name][k] for k in ("retained", "policy_redacted", "scope_excluded"))
                 and c["total"] == sum(c[k] for k in ("retained", "policy_redacted", "scope_excluded")), "occurrence disposition partition mismatch")
    text = complete["text_presence"]
    _require(type(text) is dict and set(text) == {"text", "tail"} and all(type(v) is int and v >= 0 for v in text.values()), "invalid text-presence counts")
    _require(all(v <= complete["elements"]["total"] for v in text.values()), "impossible text-presence count")
    entries = [m for r in records.values() for m in r["mappings"]]
    wanted = {"retained_occurrences": len(entries), "mapped_occurrences": sum(bool(m["destinations"]) for m in entries),
              "unmapped_occurrences": sum(not m["destinations"] for m in entries),
              "destinations": sum(len(m["destinations"]) for m in entries),
              "excluded_target_roots": ["line_layers", "report", "prediction"]}
    _require(complete["native_mapping"] == wanted, "native mapping coverage mismatch")
    _require(_hash(packet["native_model_sha256"]), "invalid native model digest")
    _require(packet["integrity_sha256"] == digest({k: v for k, v in packet.items() if k != "integrity_sha256"}), "source packet integrity mismatch")
    _require(not require_native_targets or native_model is not None, "native target context required")
    if native_model is not None:
        _require(_native_digest(native_model) == packet["native_model_sha256"], "selected native model changed")
        native_ids = set()
        for root in TARGET_ROOTS:
            if root == "meta":
                _require(root not in native_model or type(native_model[root]) is dict, "native metadata must be an object")
                continue
            items = native_model.get(root, [])
            _require(type(items) is list, "native section must be an array")
            native_ids.update(item[key] for item in items if type(item) is dict for key in ("id", "tag") if type(item.get(key)) is str)
        _require(not (native_ids & {r["id"] for r in records.values()}), "native/source record identity collision")
        for entry in entries:
            for target in entry["destinations"]:
                value = _resolve(native_model, target["components"])
                _require(digest(value) == target["destination_sha256"], "native destination content changed")


def _record_document(record):
    _require(type(record) is dict and type(record.get("locator")) is dict
             and type(record["locator"].get("path")) is list and bool(record["locator"]["path"])
             and type(record["locator"]["path"][0]) is dict, "invalid source record envelope")
    return {"document_id": record.get("document_id"), "raw_source_sha256": record.get("raw_source_sha256"),
            "raw_size_bytes": 0, "root_name": record.get("locator", {}).get("path", [{}])[0].get("name")}


def records_from_model(model):
    _require(type(model) is dict, "native model must be an object")
    if "source_evidence" not in model:
        return []
    validate_packet(model["source_evidence"], native_model=model, require_native_targets=True)
    return copy.deepcopy(model["source_evidence"]["records"])


def record_index(records):
    _require(type(records) is list, "source records must be an array")
    occurrences, versions = {}, {}
    for record in records:
        _require(type(record) is dict, "source record must be an object")
        validate_record(record, _record_document(record), policy=POLICY, mapping=MAPPING)
        _require(record["occurrence_id"] not in occurrences and record["id"] not in versions, "duplicate source record index identity")
        occurrences[record["occurrence_id"]] = copy.deepcopy(record)
        versions[record["id"]] = copy.deepcopy(record)
    return {"occurrences": occurrences, "versions": versions}


def binding_payload(record):
    _require(type(record) is dict, "source record must be an object")
    validate_record(record, _record_document(record), policy=POLICY, mapping=MAPPING)
    return copy.deepcopy(record)


class Capture:
    def __init__(self, raw_bytes, document_id, policy_id):
        _require(type(raw_bytes) is bytes and len(raw_bytes) <= MAX_BYTES, "invalid or overlimit source bytes")
        _require(type(policy_id) is str and policy_id == POLICY_ID, "unknown source policy")
        self.raw_sha256 = hashlib.sha256(raw_bytes).hexdigest()
        self.raw_size = len(raw_bytes)
        if document_id is None:
            document_id = "urn:sha256:" + self.raw_sha256
        _require(type(document_id) is str and bool(document_id) and document_id == document_id.strip(), "invalid source document identity")
        try:
            self.root = ET.fromstring(raw_bytes)
        except ET.ParseError as exc:
            raise SourceEvidenceError("not well-formed XML") from exc
        _require(qname(self.root.tag)["local_name"] == "PlantModel", "source root is not <PlantModel>")
        # Ownership is actual original object identity, never user-defined equality/hash membership.
        self._original_elements_by_id = {id(element): element for element in self.root.iter()}
        self._original_attribute_names = {id(element): frozenset(element.attrib) for element in self.root.iter()}
        self.document = {"document_id": document_id, "raw_source_sha256": self.raw_sha256,
                         "raw_size_bytes": self.raw_size, "root_name": qname(self.root.tag)}
        self._records, self._elements, self._attributes, self._slots = [], {}, {}, {}
        self._by_occurrence = {}
        self._exclusions, self._generation = [], 0
        self._counts = {"elements": Counter(), "attributes": Counter()}
        self._text = Counter()
        self._ids = {}
        reader_scope_handles = set()
        def visit(element, path, parent, inherited=None, private_ancestor=False):
            name = qname(element.tag)
            private = private_ancestor or (name["local_name"] == "GenericAttribute" and any(
                qname(k)["local_name"].casefold() == "name" and PERSON.search(v) for k, v in element.attrib.items()))
            scope = inherited
            if scope is None and name["local_name"] in SCOPE_EXCLUSIONS:
                scope = ("scope-excluded", SCOPE_EXCLUSIONS[name["local_name"]])
            if scope is None and name["local_name"] == "GenericAttribute" and any(
                    qname(k)["local_name"].casefold() == "name" and PERSON.search(v) for k, v in element.attrib.items()):
                scope = ("policy-redacted", "person-designation")
            if scope is not None and scope[0] == "scope-excluded" and not private:
                reader_scope_handles.add(element)
            loc = {"path": path}
            oid = occurrence(document_id, self.raw_sha256, "element", loc)
            self._counts["elements"]["total"] += 1
            self._text["text"] += int(element.text is not None)
            self._text["tail"] += int(element.tail is not None)
            if scope:
                self._exclude(oid, "element", loc, *scope)
            else:
                self._counts["elements"]["retained"] += 1
                original = {"present": True, "value": element.attrib["ID"]} if "ID" in element.attrib else {"present": False}
                record = {"schema": RECORD_SCHEMA, "kind": "source_record", "occurrence_id": oid,
                          "document_id": document_id, "raw_source_sha256": self.raw_sha256, "locator": loc,
                          "raw_payload": {"element_name": name, "original_id": original, "attributes": [], "children": [],
                                          "parent_occurrence_id": parent, "source_assertions": []},
                          "mappings": [], "application_status": "unverified", "policy_sha256": POLICY_SHA256,
                          "mapping_sha256": MAPPING_SHA256}
                self._records.append(record)
                self._by_occurrence[oid] = record
                self._elements[element] = record
                if original["present"] and original["value"]:
                    self._ids.setdefault(original["value"], []).append(oid)
            for ordinal, (key, value) in enumerate(element.attrib.items(), 1):
                aname = qname(key)
                aloc = {"path": path, "attribute": {"name": aname, "ordinal": ordinal}}
                aid = occurrence(document_id, self.raw_sha256, "attribute", aloc)
                self._counts["attributes"]["total"] += 1
                reason = scope or (("policy-redacted", "person-field") if PERSON.search(aname["local_name"]) else None)
                if scope is not None and scope[0] == "scope-excluded" and not private and not PERSON.search(aname["local_name"]):
                    reader_scope_handles.add((element, key))
                if reason:
                    self._exclude(aid, "attribute", aloc, *reason)
                else:
                    self._counts["attributes"]["retained"] += 1
                    attr = {"occurrence_id": aid, "name": aname, "ordinal": ordinal, "value": value}
                    record["raw_payload"]["attributes"].append(attr)
                    self._attributes[(element, key)] = (record, attr)
            if scope is None and parent is not None:
                # parent is always eligible if this element is eligible.
                self._by_occurrence[parent]["raw_payload"]["children"].append(oid)
            siblings = Counter()
            for child in element:
                child_name = qname(child.tag)
                siblings[child.tag] += 1
                visit(child, path + [{"name": child_name, "ordinal": siblings[child.tag]}], oid, scope, private)
        visit(self.root, [{"name": qname(self.root.tag), "ordinal": 1}], None)
        self._reader_scope_handles = frozenset(reader_scope_handles)
        if any(len(v) != 1 for v in self._ids.values()):
            raise _DuplicateSourceIDs(self.root)
        for element, record in self._elements.items():
            payload = record["raw_payload"]
            if payload["element_name"]["local_name"] in ("Connection", "Association"):
                for attr in payload["attributes"]:
                    name = attr["name"]
                    if name["namespace_uri"] == "" and name["local_name"] in ("FromID", "ToID", "ItemID", "TagName"):
                        payload["source_assertions"].append({"attribute_occurrence_id": attr["occurrence_id"],
                            "role": name["local_name"], "target_text": attr["value"], "resolution_status": "unverified",
                            "resolved_occurrence_ids": list(self._ids.get(attr["value"], []))})

    def _exclude(self, oid, kind, locator, disposition, reason):
        self._counts["elements" if kind == "element" else "attributes"][disposition.replace("-", "_")] += 1
        self._exclusions.append({"occurrence_id": oid, "kind": kind, "locator": locator, "disposition": disposition, "reason": reason})

    def _original_source_handle(self, source):
        """Private ownership witness only; original ownership does not grant retention or privacy eligibility."""
        if type(source) is tuple and len(source) == 2:
            element, name = source
            _require(self._original_elements_by_id.get(id(element), _NO_ORIGINAL) is element,
                     "alien source attribute")
            _require(type(name) is str and name in self._original_attribute_names[id(element)],
                     "alien or unknown source attribute")
            return element, name
        _require(self._original_elements_by_id.get(id(source), _NO_ORIGINAL) is source, "alien source element")
        return source

    def source_ref(self, source):
        source = self._original_source_handle(source)
        if type(source) is tuple and len(source) == 2:
            _require(source in self._attributes, "alien or excluded source attribute")
            return self._attributes[source][1]["occurrence_id"]
        _require(source in self._elements, "alien or excluded source element")
        return self._elements[source]["occurrence_id"]

    def assign(self, source, container, key_or_index, value, mapping_kind, basis):
        oid = self.source_ref(source)
        _require(type(mapping_kind) is str and type(basis) is str and mapping_kind in KINDS and basis in BASES,
                 "unknown native assignment profile")
        _require(type(container) is dict or type(container) is list, "invalid native assignment container")
        _require((type(container) is dict and type(key_or_index) is str) or
                 (type(container) is list and type(key_or_index) is int and 0 <= key_or_index <= len(container)), "invalid native assignment slot")
        value_bytes = _native_write_encoding(container, key_or_index, value)
        value_digest = hashlib.sha256(value_bytes).hexdigest()
        if type(container) is list and key_or_index == len(container):
            container.append(value)
        else:
            container[key_or_index] = value
        self._generation += 1
        self._slots[(id(container), key_or_index)] = {"container": container, "key": key_or_index, "source": oid,
            "generation": self._generation, "value_digest": value_digest, "kind": mapping_kind, "basis": basis,
            "explicit_transfer": False}
        return value

    def transfer(self, old_container, new_container, explicit_slot_map):
        _require((type(old_container) is dict or type(old_container) is list)
                 and (type(new_container) is dict or type(new_container) is list) and type(explicit_slot_map) is list,
                 "invalid explicit transfer")
        # The WHOLE metadata list is preflighted before any operation writes/deletes a native value.
        _json(explicit_slot_map)
        operations, old_keys, new_keys = [], set(), set()
        for entry in explicit_slot_map:
            _require(type(entry) is dict and set(entry) == {"old_key", "new_key", "mode"}, "invalid transfer operation")
            old, new, mode = entry["old_key"], entry["new_key"], entry["mode"]
            _require((type(old) is str or type(old) is int)
                     and (new is None or type(new) is str or type(new) is int), "invalid transfer slot types")
            _require(type(mode) is str and mode in ("copy", "move", "delete") and old not in old_keys,
                     "ambiguous transfer source")
            old_keys.add(old)
            _require((type(old_container) is dict and type(old) is str and old in old_container) or
                     (type(old_container) is list and type(old) is int and 0 <= old < len(old_container)), "missing transfer source")
            _require((mode == "delete" and new is None) or (mode != "delete" and new not in new_keys), "ambiguous transfer destination")
            if mode != "delete":
                _require((type(new_container) is dict and type(new) is str) or
                         (type(new_container) is list and type(new) is int and 0 <= new <= len(new_container)), "invalid transfer destination")
                new_keys.add(new)
            slot = self._slots.get((id(old_container), old))
            operations.append((old, new, mode, old_container[old], slot))
        if old_container is new_container:
            _require(not any(mode == "delete" and old in new_keys for old, _, mode, _, _ in operations),
                     "delete conflicts with transfer destination")
        _native_encoding_bytes(explicit_slot_map)
        for old, new, mode, value, slot in operations:
            value_bytes = _native_encoding_bytes(value)
            if slot:
                _require(slot["value_digest"] == hashlib.sha256(value_bytes).hexdigest(),
                         "stale source transfer generation")
        for old, new, mode, value, slot in operations:
            if mode == "delete":
                continue
            if type(new_container) is list and new == len(new_container):
                new_container.append(value)
            else:
                new_container[new] = value
            self._slots.pop((id(new_container), new), None)
            if slot:
                self._generation += 1
                self._slots[(id(new_container), new)] = dict(slot, container=new_container, key=new,
                    generation=self._generation, kind="container-transfer", explicit_transfer=False)
                slot["explicit_transfer"] = True
        deletes = [old for old, _, mode, _, _ in operations if mode in ("move", "delete")
                   and not (mode == "move" and old_container is new_container and old in new_keys)]
        if type(old_container) is list:
            deletes.sort(reverse=True)
        for old in deletes:
            del old_container[old]
            self._slots.pop((id(old_container), old), None)
            if type(old_container) is list:
                changes = [(key, slot) for key, slot in self._slots.items() if key[0] == id(old_container) and key[1] > old]
                for key, slot in changes:
                    del self._slots[key]
                    slot["key"] -= 1
                    self._slots[(key[0], key[1] - 1)] = slot

    def finalize(self, native_model):
        _native_digest(native_model)
        paths = {}
        def walk(value, path, ancestors):
            if type(value) not in (dict, list):
                return
            _require(id(value) not in ancestors, "cyclic native model")
            ancestors = ancestors | {id(value)}
            items = value.items() if type(value) is dict else enumerate(value)
            for key, child in items:
                child_path = path + [str(key)]
                paths.setdefault((id(value), key), []).append(child_path)
                walk(child, child_path, ancestors)
        for root in TARGET_ROOTS:
            if root in native_model:
                walk(native_model[root], [root], set())
        destinations = {}
        for slot_key, slot in self._slots.items():
            container, key = slot["container"], slot["key"]
            valid_key = (key in container) if type(container) is dict else (0 <= key < len(container))
            _require(valid_key and digest(container[key]) == slot["value_digest"], "stale native assignment generation")
            concrete = paths.get(slot_key, [])
            _require(bool(concrete) or slot["explicit_transfer"], "detached native assignment target")
            for path in concrete:
                destinations.setdefault(slot["source"], []).append({"pointer": _pointer(path), "components": path,
                    "mapping_kind": slot["kind"], "basis": slot["basis"], "destination_sha256": digest(container[key])})
        records = copy.deepcopy(self._records)
        for record in records:
            owned = [record["occurrence_id"]] + [a["occurrence_id"] for a in record["raw_payload"]["attributes"]]
            record["mappings"] = [{"source_occurrence_id": oid, "disposition": "direct" if destinations.get(oid) else "unmapped",
                "destinations": sorted(destinations.get(oid, []), key=lambda d: d["pointer"])} for oid in owned]
            version = digest(record)
            record["record_version_id"], record["id"] = version, "source_record:" + version
        entries = [m for r in records for m in r["mappings"]]
        complete = {name: {k: self._counts[name][k] for k in ("total", "retained", "policy_redacted", "scope_excluded")}
                    for name in ("elements", "attributes")}
        complete["text_presence"] = {key: self._text[key] for key in ("text", "tail")}
        complete["native_mapping"] = {"retained_occurrences": len(entries), "mapped_occurrences": sum(bool(m["destinations"]) for m in entries),
            "unmapped_occurrences": sum(not m["destinations"] for m in entries), "destinations": sum(len(m["destinations"]) for m in entries),
            "excluded_target_roots": ["line_layers", "report", "prediction"]}
        packet = {"schema": SCHEMA, "required_capabilities": [CAPABILITY], "document": copy.deepcopy(self.document),
                  "policy": copy.deepcopy(POLICY), "mapping": copy.deepcopy(MAPPING), "records": records,
                  "exclusions": copy.deepcopy(self._exclusions), "completeness": complete,
                  "native_model_sha256": _native_digest(native_model)}
        packet["integrity_sha256"] = digest(packet)
        validate_packet(packet, native_model=native_model, require_native_targets=True)
        return packet


def capture_xml(raw_bytes, document_id=None, policy_id=POLICY_ID):
    return Capture(raw_bytes, document_id, policy_id)
