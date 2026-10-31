"""Source occurrence, privacy, explicit mapping and same-byte prewrite controls; offline stdlib only."""
import copy
import hashlib
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

import dexpi_reader as R
import source_evidence as S


SIMPLE = b'<PlantModel><Equipment ID="E1" ComponentClass="Tank"><GenericAttributes Set="Custom"><GenericAttribute Name="Pressure" Value="0" Units="Bar"/></GenericAttributes></Equipment></PlantModel>'


def model():
    return {"meta": {"title": "Synthetic source control"}, "units": [{"id": "E1"}], "line_layers": {"unknown": None}}


def seal(record):
    body = {k: v for k, v in record.items() if k not in ("id", "record_version_id")}
    record["record_version_id"] = S.digest(body)
    record["id"] = "source_record:" + record["record_version_id"]


def reseal(packet):
    packet["integrity_sha256"] = S.digest({k: v for k, v in packet.items() if k != "integrity_sha256"})


class CaptureControls(unittest.TestCase):
    def test_strict_duplicate_exception_hands_off_only_same_parse_and_safe_generic_text(self):
        raw = b'<PlantModel><Equipment ID="A"/><Equipment ID="A"/><GenericAttributes><GenericAttribute ID="SYNTHETIC_REPEAT_441" Name="CreatorName" Value="protected"/><GenericAttribute ID="SYNTHETIC_REPEAT_441" Name="CreatorName" Value="protected"/></GenericAttributes></PlantModel>'
        original_parse = S.ET.fromstring; roots = []
        def parse(value):
            root = original_parse(value); roots.append(root); return root
        with patch.object(S.ET, 'fromstring', parse), self.assertRaises(S.SourceEvidenceError) as error:
            S.capture_xml(raw)
        self.assertEqual(len(roots), 1)
        self.assertIs(error.exception._root, roots[0])
        self.assertEqual(str(error.exception), 'live XML IDs used more than once')
        self.assertNotIn('SYNTHETIC_REPEAT_441', repr(error.exception))
        self.assertNotIn('Element', repr(error.exception))
        roots.clear()
        with tempfile.TemporaryDirectory() as tmp:
            xml = Path(tmp) / 'source.xml'; xml.write_bytes(raw)
            with patch.object(S.ET, 'fromstring', parse), self.assertRaisesRegex(R.DexpiError, 'more than once \\(2 duplicate identifier\\(s\\)\\)') as error:
                R.Reader(xml, capture_source=True)
            self.assertEqual(len(roots), 1)
            self.assertNotIn('SYNTHETIC_REPEAT_441', str(error.exception))
            self.assertEqual(xml.read_bytes(), raw)

    def test_source_scope_and_native_live_duplicate_scope_are_not_conflated(self):
        for inner in ('<Drawing><Unknown ID="A"/><Unknown ID="A"/></Drawing>',
                      '<ShapeCatalogue/><ShapeCatalogue><Unknown ID="A"/><Unknown ID="A"/></ShapeCatalogue>'):
            raw = ('<PlantModel><Equipment ID="E1" ComponentClass="Tank"/>' + inner + '</PlantModel>').encode()
            capture = S.capture_xml(raw)
            packet = capture.finalize(model())
            self.assertFalse(any(r['raw_payload']['original_id'].get('value') == 'A' for r in packet['records']))
            with tempfile.TemporaryDirectory() as tmp:
                xml = Path(tmp) / 'source.xml'; xml.write_bytes(raw)
                with self.assertRaisesRegex(R.DexpiError, 'more than once \\(1 duplicate identifier\\(s\\)\\)'):
                    R.Reader(xml, capture_source=True)

    def test_defensive_source_duplicate_handoff_never_invents_native_count_or_continues(self):
        raw = b'<PlantModel><Equipment ID="E1" ComponentClass="Tank"/></PlantModel>'
        failure = S._DuplicateSourceIDs(ET.fromstring(raw))
        with tempfile.TemporaryDirectory() as tmp:
            xml = Path(tmp) / 'source.xml'; xml.write_bytes(raw)
            with patch.object(S, 'capture_xml', side_effect=failure), self.assertRaisesRegex(R.DexpiError, 'live XML IDs used more than once') as error:
                R.run(xml, Path(tmp) / 'out', quiet=True, capture_source=True)
            self.assertNotIn('duplicate identifier(s)', str(error.exception))
            self.assertFalse((Path(tmp) / 'out').exists())
            self.assertEqual(xml.read_bytes(), raw)

    def test_receiving_document_ids_match_capture_admission_without_trimming(self):
        for invalid in (" ", " leading", "trailing ", "\nwrapped\n"):
            with self.subTest(document_id=invalid):
                m = {"meta": {}}
                p = S.capture_xml(b'<PlantModel/>', "valid").finalize(m)
                p["document"]["document_id"] = invalid
                record = p["records"][0]
                record["document_id"] = invalid
                record["occurrence_id"] = S.occurrence(invalid, record["raw_source_sha256"], "element", record["locator"])
                record["mappings"][0]["source_occurrence_id"] = record["occurrence_id"]
                seal(record); reseal(p)
                for receiver in (lambda: S.capture_xml(b'<PlantModel/>', invalid),
                                 lambda: S.validate_packet(p, native_model=m, require_native_targets=True),
                                 lambda: S.binding_payload(record), lambda: S.record_index([record])):
                    with self.assertRaises(S.SourceEvidenceError):
                        receiver()

    def test_all_structural_occurrences_and_qnames_survive_without_role_promotion(self):
        raw = b'''<PlantModel xmlns="urn:plant" xmlns:x="urn:extra" x:schema="quoted.xsd">
          <PlantInformation x:ID="not-authoritative" Note=""/>
          <UnitsOfMeasure><Unit ID="BAR" Name="Pressure" Value="Bar"/></UnitsOfMeasure>
          <Equipment ID="E1"><PersistentID Identifier="same" Context="vendor"/>
            <ConnectionPoints NumPoints="0"/><CenterLine NumPoints="2"/>
            <GenericAttributes Set=""/><GenericAttributes><GenericAttribute x:Name="opaque" x:Value="false" x:Units=""/></GenericAttributes>
            <x:Unknown x:ID="E1" literal="source/status/context/a~b"/>
          </Equipment></PlantModel>'''
        parsed = ET.fromstring(raw)
        c = S.capture_xml(raw, "local-document")
        m = model(); p = c.finalize(m)
        self.assertEqual(p["completeness"]["elements"]["retained"], sum(1 for _ in parsed.iter()))
        self.assertEqual(p["completeness"]["attributes"]["retained"], sum(len(e.attrib) for e in parsed.iter()))
        actual = p["records"]
        for source, record in zip(parsed.iter(), actual):
            self.assertEqual(record["raw_payload"]["element_name"], S.qname(source.tag))
            self.assertEqual([(a["name"], a["value"]) for a in record["raw_payload"]["attributes"]],
                             [(S.qname(k), v) for k, v in source.attrib.items()])
        qualified = next(r for r in actual if r["raw_payload"]["element_name"]["local_name"] == "Unknown")
        self.assertEqual(qualified["raw_payload"]["original_id"], {"present": False})
        self.assertEqual(p["document"]["raw_source_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(p["document"]["document_id"], "local-document")
        self.assertTrue(all(x["disposition"] == "unmapped" for r in actual for x in r["mappings"]))

    def test_repeated_groups_empty_fields_and_literal_keys_keep_distinct_occurrences(self):
        raw = b'<PlantModel><Equipment ID=""><GenericAttributes/><GenericAttributes Set=""><GenericAttribute Name="source" Value=""/><GenericAttribute Name="source" Value="0"/><GenericAttribute Name="source" Value="0"/><GenericAttribute Name="context/a~b"/></GenericAttributes></Equipment></PlantModel>'
        p = S.capture_xml(raw).finalize(model())
        ids = [r["occurrence_id"] for r in p["records"]]
        self.assertEqual(len(ids), len(set(ids)))
        gas = [r for r in p["records"] if r["raw_payload"]["element_name"]["local_name"] == "GenericAttribute"]
        self.assertEqual(len(gas), 4)
        self.assertNotEqual(gas[1]["occurrence_id"], gas[2]["occurrence_id"])
        eq = p["records"][1]
        self.assertEqual(eq["raw_payload"]["original_id"], {"present": True, "value": ""})
        self.assertNotEqual(p["records"][2]["raw_payload"]["attributes"], p["records"][3]["raw_payload"]["attributes"])

    def test_each_role_alias_order_and_empty_value_redact_entire_ga_before_serialization(self):
        for role in ("Approver", "Checker", "Creator", "Designer", "Drafter", "Editor", "Reviewer", "Owner"):
            for reverse in (False, True):
                for value in (None, "", "0", "false"):
                    with self.subTest(role=role, reverse=reverse, value=value):
                        root = ET.Element("PlantModel")
                        eq = ET.SubElement(root, "Equipment", ID="E1", ComponentClass="Tank")
                        group = ET.SubElement(eq, "GenericAttributes", {"{urn:q}CreatorName": "MARKER_QUALIFIER_912"})
                        attrs = [("Name", "TagNameAssignmentClass"), ("{urn:p}nAmE", role.swapcase() + "nAmE")]
                        ga = ET.SubElement(group, "GenericAttribute", dict(reversed(attrs) if reverse else attrs))
                        ga.set("{urn:p}Value", "MARKER_PROTECTED_912")
                        ga.set("{urn:p}Units", "MARKER_PROTECTED_912")
                        if value is not None:
                            ga.set("Value", value)
                        ET.SubElement(ga, "UnknownChild", secret="MARKER_PROTECTED_912")
                        ET.SubElement(group, "GenericAttribute", Name="EngineeringNote", Value="safe")
                        c = S.capture_xml(ET.tostring(root)); p = c.finalize(model())
                        self.assertNotIn("MARKER_", json.dumps(p))
                        self.assertTrue(any(a["value"] == "safe" for r in p["records"] for a in r["raw_payload"]["attributes"]))
                        self.assertEqual(p["completeness"]["elements"]["policy_redacted"], 2)
                        with self.assertRaises(S.SourceEvidenceError):
                            c.source_ref(c.root.find(".//GenericAttribute"))

    def test_scope_first_ancestor_and_text_payload_excluded_without_losing_unknown_structure(self):
        raw = b'<PlantModel><Drawing ID="D"><Text String="MARKER_DRAWING_98"/><GenericAttribute Name="CreatorName" Value="MARKER_DRAWING_98"/></Drawing><Equipment ID="E1"><Unknown a="safe">MARKER_TEXT_98<Empty/>MARKER_TAIL_98</Unknown><Position X="MARKER_GEOMETRY_98"/><ShapeCatalogue><Symbol Name="MARKER_CATALOG_98"/></ShapeCatalogue></Equipment></PlantModel>'
        p = S.capture_xml(raw).finalize(model())
        self.assertNotIn("MARKER_", json.dumps(p))
        self.assertTrue(any(r["raw_payload"]["element_name"]["local_name"] == "Unknown" for r in p["records"]))
        self.assertTrue(any(r["raw_payload"]["element_name"]["local_name"] == "Empty" for r in p["records"]))
        self.assertEqual(p["completeness"]["elements"]["policy_redacted"], 0)
        self.assertEqual(p["completeness"]["text_presence"], {"text": 1, "tail": 1})
        drawing = [x for x in p["exclusions"] if any(y["name"]["local_name"] == "Drawing" for y in x["locator"]["path"])]
        self.assertTrue(all(x["reason"] == "drawing-titleblock" for x in drawing))

    def test_protected_ga_ancestor_wins_over_nested_scope_label(self):
        p = S.capture_xml(b'<PlantModel><GenericAttribute Name="OwnerName" Value="MARKER_77"><Text String="MARKER_77"/></GenericAttribute></PlantModel>').finalize(model())
        self.assertNotIn("MARKER_", json.dumps(p))
        self.assertEqual(p["completeness"]["elements"]["policy_redacted"], 2)
        self.assertEqual(p["completeness"]["elements"]["scope_excluded"], 0)

    def test_reciprocal_assertions_use_occurrences_and_hashes_are_deterministic(self):
        raw = b'<PlantModel><Equipment ID="E1"/><InstrumentationLoopFunction ID="ILF01"><Association Type="refers to" ItemID="PIF01"/></InstrumentationLoopFunction><ProcessInstrumentationFunction ID="PIF01"><Association Type="referenced by" ItemID="ILF01"/></ProcessInstrumentationFunction></PlantModel>'
        a = S.capture_xml(raw).finalize(model()); b = S.capture_xml(raw).finalize(model())
        self.assertEqual(a, b)
        refs = [s for r in a["records"] for s in r["raw_payload"]["source_assertions"]]
        self.assertEqual(len(refs), 2)
        self.assertTrue(all(s["resolution_status"] == "unverified" and len(s["resolved_occurrence_ids"]) == 1 for s in refs))
        self.assertFalse(any(x.startswith("source_record:") for s in refs for x in s["resolved_occurrence_ids"]))
        S.validate_packet(a)
        with self.assertRaisesRegex(S.SourceEvidenceError, "context required"):
            S.validate_packet(a, require_native_targets=True)

    def test_revision_identity_is_not_cross_revision_entity_identity(self):
        a = S.capture_xml(SIMPLE, "local-doc").finalize(model())
        b = S.capture_xml(SIMPLE.replace(b'Value="0"', b'Value="1"'), "local-doc").finalize(model())
        self.assertEqual(a["document"]["document_id"], b["document"]["document_id"])
        self.assertTrue(set(r["occurrence_id"] for r in a["records"]).isdisjoint(r["occurrence_id"] for r in b["records"]))

    def test_controlled_document_scope_distinguishes_same_bytes_without_inventing_org_identity(self):
        default = S.capture_xml(SIMPLE).finalize(model())
        explicit_default = S.capture_xml(SIMPLE, "urn:sha256:" + hashlib.sha256(SIMPLE).hexdigest()).finalize(model())
        self.assertEqual(default, explicit_default)
        first = S.capture_xml(SIMPLE, "companyA:plant1:source47").finalize(model())
        second = S.capture_xml(SIMPLE, "companyA:plant2:source47").finalize(model())
        self.assertEqual(first["native_model_sha256"], second["native_model_sha256"])
        self.assertTrue(set(r["occurrence_id"] for r in first["records"]).isdisjoint(r["occurrence_id"] for r in second["records"]))
        with self.assertRaises(S.SourceEvidenceError):
            S.record_index(default["records"] + explicit_default["records"])
        for bad in ("", " trailing", "trailing ", False, 0, [], {}):
            with self.subTest(bad=type(bad)), self.assertRaises(S.SourceEvidenceError):
                S.capture_xml(SIMPLE, bad)
        for literal in ("null", "None", "0", "false"):
            self.assertEqual(S.capture_xml(SIMPLE, literal).document["document_id"], literal)

    def test_foreign_duplicate_oversize_and_malformed_sources_refuse_without_payload_echo(self):
        for raw in (b'<Other secret="MARKER_PRIVATE_83"/>', b'<PlantModel><bad',
                    b'<PlantModel><Equipment ID="E1"/><Equipment ID="E1"/></PlantModel>'):
            with self.subTest(raw=raw), self.assertRaises(S.SourceEvidenceError) as raised:
                S.capture_xml(raw)
            self.assertNotIn("MARKER_", str(raised.exception))
        with patch.object(S, "MAX_BYTES", 4), self.assertRaises(S.SourceEvidenceError):
            S.capture_xml(SIMPLE)


class MappingControls(unittest.TestCase):
    def setup_capture(self):
        c = S.capture_xml(SIMPLE)
        ga = c.root.find(".//GenericAttribute")
        return c, ga, model()

    def test_exact_attribute_pointer_escaping_and_complete_deep_copy(self):
        c, ga, m = self.setup_capture()
        c.assign((ga, "Value"), m["units"][0], "source/a~b", "0", "direct-copy", "generic-value")
        p = c.finalize(m); m["source_evidence"] = p
        target = next(t for r in p["records"] for e in r["mappings"] for t in e["destinations"])
        self.assertEqual(target["pointer"], "/units/0/source~1a~0b")
        self.assertEqual(target["components"], ["units", "0", "source/a~b"])
        S.validate_packet(p, native_model=m, require_native_targets=True)
        rows = S.records_from_model(m); bound = S.binding_payload(rows[0]); indices = S.record_index(rows)
        self.assertEqual(bound, rows[0]); self.assertEqual(len(indices["versions"]), len(rows))
        bound["raw_payload"]["children"].clear()
        self.assertNotEqual(bound, rows[0])
        rows[0]["raw_payload"]["children"].clear()
        self.assertNotEqual(rows, p["records"])

    def test_equal_value_overwrite_withdraws_earlier_exact_occurrence(self):
        raw = SIMPLE.replace(b'</GenericAttributes>', b'<GenericAttribute Name="Pressure" Value="0"/></GenericAttributes>')
        c = S.capture_xml(raw); gas = c.root.findall(".//GenericAttribute"); m = model()
        c.assign((gas[0], "Value"), m["meta"], "reading", "0", "direct-copy", "metadata-value")
        c.assign((gas[1], "Value"), m["meta"], "reading", "0", "direct-copy", "metadata-value")
        p = c.finalize(m)
        entries = {e["source_occurrence_id"]: e for r in p["records"] for e in r["mappings"]}
        self.assertEqual(entries[c.source_ref((gas[0], "Value"))]["disposition"], "unmapped")
        self.assertEqual(entries[c.source_ref((gas[1], "Value"))]["disposition"], "direct")

    def test_explicit_clone_move_delete_and_list_shift_keep_only_final_targets(self):
        c, ga, m = self.setup_capture()
        old = {}; c.assign((ga, "Value"), old, "reading", "0", "direct-copy", "generic-value")
        new = {}; c.transfer(old, new, [{"old_key": "reading", "new_key": "copied", "mode": "copy"}])
        m["unplaced"] = [new]
        p = c.finalize(m)
        self.assertEqual([t["pointer"] for r in p["records"] for e in r["mappings"] for t in e["destinations"]], ["/unplaced/0/copied"])
        c.transfer(new, new, [{"old_key": "copied", "new_key": "renamed", "mode": "move"}])
        p = c.finalize(m)
        self.assertIn("/unplaced/0/renamed", json.dumps(p))
        c.transfer(new, new, [{"old_key": "renamed", "new_key": None, "mode": "delete"}])
        self.assertEqual(c.finalize(m)["completeness"]["native_mapping"]["mapped_occurrences"], 0)
        values = []
        c.assign((ga, "Value"), values, 0, "first", "legacy-transform", "generic-value")
        c.assign((ga, "Value"), values, 1, "second", "legacy-transform", "generic-value")
        m["meta"]["values"] = values
        c.transfer(values, values, [{"old_key": 0, "new_key": None, "mode": "delete"}])
        self.assertEqual(values, ["second"])
        self.assertIn("/meta/values/0", json.dumps(c.finalize(m)))

    def test_multiple_genuine_alias_paths_are_preserved_without_invented_copies(self):
        c, ga, m = self.setup_capture(); shared = {}
        c.assign((ga, "Value"), shared, "value", "0", "direct-copy", "generic-value")
        m["units"][0]["first"] = shared; m["units"][0]["second"] = shared
        p = c.finalize(m)
        targets = [t["pointer"] for r in p["records"] for e in r["mappings"] for t in e["destinations"]]
        self.assertEqual(targets, ["/units/0/first/value", "/units/0/second/value"])

    def test_explicit_move_permutation_preserves_generations_and_rejects_delete_conflicts(self):
        c, ga, m = self.setup_capture()
        c.assign((ga, "Value"), m["meta"], "a", "0", "direct-copy", "generic-value")
        c.assign((ga, "Units"), m["meta"], "b", "Bar", "direct-copy", "generic-units")
        before = copy.deepcopy(m)
        with self.assertRaises(S.SourceEvidenceError):
            c.transfer(m["meta"], m["meta"], [{"old_key": "a", "new_key": "b", "mode": "copy"},
                                            {"old_key": "b", "new_key": None, "mode": "delete"}])
        self.assertEqual(m, before)
        c.transfer(m["meta"], m["meta"], [{"old_key": "a", "new_key": "b", "mode": "move"},
                                        {"old_key": "b", "new_key": "a", "mode": "move"}])
        self.assertEqual((m["meta"]["a"], m["meta"]["b"]), ("Bar", "0"))
        p = c.finalize(m)
        entries = {e["source_occurrence_id"]: e for r in p["records"] for e in r["mappings"]}
        self.assertEqual(entries[c.source_ref((ga, "Value"))]["destinations"][0]["pointer"], "/meta/b")
        self.assertEqual(entries[c.source_ref((ga, "Units"))]["destinations"][0]["pointer"], "/meta/a")

    def test_detached_changed_alien_excluded_and_forbidden_targets_refuse(self):
        c, ga, m = self.setup_capture(); detached = {}
        c.assign((ga, "Value"), detached, "value", "0", "direct-copy", "generic-value")
        with self.assertRaisesRegex(S.SourceEvidenceError, "detached"):
            c.finalize(m)
        m["units"][0]["nested"] = detached; detached["value"] = "changed"
        with self.assertRaisesRegex(S.SourceEvidenceError, "stale"):
            c.finalize(m)
        for source in (ET.Element("Foreign"), [], (ga, "not-present")):
            with self.subTest(source=type(source)), self.assertRaises(S.SourceEvidenceError):
                c.source_ref(source)
        c, ga, m = self.setup_capture()
        c.assign((ga, "Value"), m["line_layers"], "reading", "0", "direct-copy", "generic-value")
        with self.assertRaisesRegex(S.SourceEvidenceError, "detached"):
            c.finalize(m)

    def test_json_false_zero_null_empty_values_remain_typed_and_model_bound(self):
        c, ga, m = self.setup_capture()
        values = [False, 0, None, "", [], {}]
        for index, value in enumerate(values):
            c.assign((ga, "Value"), m["meta"], str(index), value, "legacy-transform", "generic-value")
        p = c.finalize(m); m["source_evidence"] = p
        original = copy.deepcopy(m)
        S.validate_packet(p, native_model=m, require_native_targets=True)
        self.assertEqual(m, original)
        m["meta"]["0"] = 0
        with self.assertRaisesRegex(S.SourceEvidenceError, "native model changed"):
            S.records_from_model(m)


class ValidationControls(unittest.TestCase):
    def packet(self):
        c = S.capture_xml(SIMPLE); m = model(); ga = c.root.find(".//GenericAttribute")
        c.assign((ga, "Value"), m["meta"], "reading", "0", "direct-copy", "metadata-value")
        return c.finalize(m), m

    def test_unknown_profiles_duplicate_ids_order_and_payload_tampering_refuse(self):
        p, _ = self.packet()
        mutations = [lambda x: x.update(schema="xml-source-evidence-2"),
                     lambda x: x.update(required_capabilities=[]),
                     lambda x: x["policy"].update(id="self-consistent-but-unknown"),
                     lambda x: x["mapping"]["target_roots"].append("line_layers"),
                     lambda x: x["records"].append(copy.deepcopy(x["records"][0])),
                     lambda x: x["records"][1]["raw_payload"]["attributes"].reverse(),
                     lambda x: x["records"][1]["raw_payload"]["attributes"][0].update(value="changed"),
                     lambda x: x["completeness"]["elements"].update(total=0),
                     lambda x: x.update(extra="unrecognized")]
        for mutate in mutations:
            changed = copy.deepcopy(p); mutate(changed); reseal(changed)
            with self.subTest(mutate=mutate), self.assertRaises(S.SourceEvidenceError):
                S.validate_packet(changed)

    def test_escaped_pointer_profile_and_context_required_even_with_self_consistent_hash(self):
        p, m = self.packet()
        record = next(r for r in p["records"] if any(e["destinations"] for e in r["mappings"]))
        target = next(t for e in record["mappings"] for t in e["destinations"])
        target["components"] = ["meta", "absent"]
        target["pointer"] = "/meta/absent"
        seal(record); reseal(p)
        S.validate_packet(p)
        with self.assertRaises(S.SourceEvidenceError):
            S.validate_packet(p, native_model=m, require_native_targets=True)
        target["components"] = ["source_evidence", "records"]
        target["pointer"] = "/source_evidence/records"
        seal(record); reseal(p)
        with self.assertRaises(S.SourceEvidenceError):
            S.validate_packet(p)

    def test_strict_loader_and_legacy_model_behavior(self):
        for text in ('{"a":0,"a":false}', '{"a":NaN}', '{"a":Infinity}', '{bad'):
            with self.subTest(text=text), self.assertRaises(S.SourceEvidenceError):
                S.load_json_strict(text)
        self.assertEqual(S.load_json_strict('{"a":[false,0,null,"",[],{}]}')["a"], [False, 0, None, "", [], {}])
        self.assertEqual(S.records_from_model(model()), [])
        with self.assertRaises(S.SourceEvidenceError):
            S.binding_payload({})
        bad = model(); bad["source_evidence"] = {}
        with self.assertRaises(S.SourceEvidenceError):
            S.records_from_model(bad)

    def test_policy_exclusion_ordinals_model_shapes_and_native_record_collision_refuse(self):
        p, m = self.packet()
        c = S.capture_xml(SIMPLE)
        m["units"][0]["id"] = p["records"][0]["id"]
        # Parent refs use occurrence IDs: a child's mapping does not recursively change the root's version.
        plain = c.finalize(model())
        self.assertEqual(plain["records"][0]["id"], p["records"][0]["id"])
        m["units"][0]["id"] = plain["records"][0]["id"]
        with self.assertRaisesRegex(S.SourceEvidenceError, "identity collision"):
            c.finalize(m)
        p, m = self.packet(); m["units"] = None
        p["native_model_sha256"] = S.digest(m); reseal(p)
        with self.assertRaisesRegex(S.SourceEvidenceError, "native section"):
            S.validate_packet(p, native_model=m)
        p = S.capture_xml(b'<PlantModel OwnerName="protected"/>').finalize(model())
        changed = copy.deepcopy(p); changed["exclusions"][0]["reason"] = "person-designation"; reseal(changed)
        with self.assertRaises(S.SourceEvidenceError):
            S.validate_packet(changed)
        c = S.capture_xml(SIMPLE); ga = c.root.find(".//GenericAttribute")
        for operation in ([{"old_key": [], "new_key": "x", "mode": "copy"}],
                          [{"old_key": "x", "new_key": [], "mode": "copy"}]):
            with self.assertRaises(S.SourceEvidenceError):
                c.transfer({"x": 0}, {}, operation)


class ReaderSnapshotControls(unittest.TestCase):
    def test_unkeyed_metadata_keeps_complete_raw_records_and_unmapped_dispositions(self):
        for tag in ("MetaData", "PlantStructureItem"):
            with self.subTest(tag=tag), tempfile.TemporaryDirectory() as tmp:
                root = ET.Element("PlantModel")
                ET.SubElement(root, "Equipment", ID="E1", ComponentClass="Tank")
                group = ET.SubElement(ET.SubElement(root, tag, ID="M1"), "GenericAttributes")
                for value in ("0", "false", " "):
                    ET.SubElement(group, "GenericAttribute", {"Value": value, "{urn:opaque}Name": "safe-qualified-only", "Format": "supplied"})
                xml = Path(tmp) / "source.xml"; xml.write_bytes(ET.tostring(root))
                m, rep = R.run(xml, Path(tmp) / "out", "unkeyed", quiet=True, capture_source=True)
                self.assertEqual(rep["attributes"]["dropped_by_reason"]["missing metadata Name: not mapped to native metadata"], 3)
                values = m["meta"]["drawing"] if tag == "MetaData" else m["meta"]["plant_structure"][0]["attributes"]
                self.assertEqual(values, {})
                rows = [r for r in m["source_evidence"]["records"] if r["raw_payload"]["element_name"]["local_name"] == "GenericAttribute"]
                self.assertEqual(len(rows), 3)
                self.assertEqual([[a["value"] for a in r["raw_payload"]["attributes"]] for r in rows],
                                 [[value, "safe-qualified-only", "supplied"] for value in ("0", "false", " ")])
                self.assertTrue(all(e["disposition"] == "unmapped" and not e["destinations"] for r in rows for e in r["mappings"]))
                S.validate_packet(m["source_evidence"], native_model=m, require_native_targets=True)

    def test_native_first_last_selection_and_equal_metadata_overwrite_keep_exact_origins(self):
        raw = b'''<PlantModel><MetaData><GenericAttributes>
          <GenericAttribute Name="DrawingNameAssignmentClass" Value="same"/>
          <GenericAttribute Name="DrawingNameAssignmentClass" Value="same"/>
          </GenericAttributes></MetaData><PlantStructureItem ID="PS1" ComponentClass="Plant"><GenericAttributes>
          <GenericAttribute Name="Area" Value="same"/><GenericAttribute Name="Area" Value="same"/>
          </GenericAttributes></PlantStructureItem><Equipment ID="E1" ComponentClass="Tank"><GenericAttributes>
          <GenericAttribute Name="TagNameAssignmentClass" Value="SAFE-1"/>
          <GenericAttribute Name="TagNameAssignmentClass" Value="SAFE-2"/>
          <GenericAttribute Name="EquipmentDescriptionAssignmentClass" Value="first" Language="en"/>
          <GenericAttribute Name="EquipmentDescriptionAssignmentClass" Value="last" Language="en"/>
          </GenericAttributes></Equipment></PlantModel>'''
        with tempfile.TemporaryDirectory() as tmp:
            xml = Path(tmp) / "source.xml"; xml.write_bytes(raw)
            reader = R.Reader(xml, capture_source=True); m = reader.read(); p = m["source_evidence"]
            self.assertEqual(m["units"][0]["id"], "SAFE-1")
            self.assertEqual(m["units"][0]["name"], "last (Tank)")
            entries = {e["source_occurrence_id"]: e for r in p["records"] for e in r["mappings"]}
            for owner_path, pointer in (("MetaData", "/meta/drawing/DrawingNameAssignmentClass"),
                                        ("PlantStructureItem", "/meta/plant_structure/0/attributes/Area")):
                gas = reader.root.find(owner_path).findall(".//GenericAttribute")
                self.assertEqual(entries[reader.source_capture.source_ref((gas[0], "Value"))]["disposition"], "unmapped")
                self.assertEqual([t["pointer"] for t in entries[reader.source_capture.source_ref((gas[1], "Value"))]["destinations"]], [pointer])
            # Native ID/name are existing derived interpretations, not credited as new direct mappings.
            destinations = [t["pointer"] for r in p["records"] for e in r["mappings"] for t in e["destinations"]]
            self.assertNotIn("/units/0/id", destinations)
            self.assertNotIn("/units/0/name", destinations)

    def test_one_native_parse_and_cached_source_digest_even_after_path_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            xml = Path(tmp) / "source.xml"; xml.write_bytes(SIMPLE)
            with patch.object(R.ET, "parse", side_effect=AssertionError("native path reparsed")):
                reader = R.Reader(xml, capture_source=True); m = reader.read()
            xml.write_bytes(SIMPLE.replace(b'Value="0"', b'Value="1"'))
            r = reader.report(m)
            self.assertEqual(r["sha256"], hashlib.sha256(SIMPLE).hexdigest())
            self.assertIn(r["sha256"], m["meta"]["source_document"])
            with self.assertRaisesRegex(R.DexpiError, "source changed"):
                reader.assert_source_unchanged()

    def test_source_mutation_before_output_preserves_absent_and_existing_sentinels(self):
        original = R.Reader.report
        for existing in (False, True):
            with self.subTest(existing=existing), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp); xml = base / "source.xml"; xml.write_bytes(SIMPLE); out = base / "out"
                if existing:
                    out.mkdir(); (out / "sentinel").write_text("unchanged", encoding="utf-8")
                before = {p.name: p.read_bytes() for p in out.iterdir()} if existing else None
                def mutation(reader, m):
                    result = original(reader, m); xml.write_bytes(SIMPLE + b' '); return result
                with patch.object(R.Reader, "report", mutation), self.assertRaisesRegex(R.DexpiError, "source changed"):
                    R.run(xml, out, "fixture", quiet=True, capture_source=True)
                self.assertEqual({p.name: p.read_bytes() for p in out.iterdir()} if out.exists() else None, before)

    def test_optional_geometry_receives_authoritative_reader_and_guard_precedes_retained_image_write(self):
        import dexpi_to_twin as D
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp); xml = base / "source.xml"; xml.write_bytes(SIMPLE)
            image = base / "image.png"; image.write_bytes(b'synthetic image; geometry helper is stubbed')
            out = base / "out"
            def prediction(original, png, sid, title, reader=None):
                self.assertEqual(Path(original), xml)
                self.assertIsNotNone(reader)
                self.assertEqual(reader.raw_bytes, SIMPLE)
                xml.write_bytes(SIMPLE + b' ')
                return {"symbols": [], "connections": [], "source": {"image_sha256": R.sha256(png)}}, {}
            with patch.object(R, "prediction", prediction), patch.object(D, "retain_intake_image") as retained:
                with self.assertRaisesRegex(R.DexpiError, "source changed"):
                    R.run(xml, out, "fixture", png=image, quiet=True, capture_source=True)
                retained.assert_not_called()
            self.assertFalse(out.exists())


class OriginalIdentityAndScopeControls(unittest.TestCase):
    raw = b'<PlantModel><Equipment ID="E1" ComponentClass="Tank"><Position><Nozzle ID="N1" ComponentClass="Nozzle" OwnerName="PROTECTED_DIRECT_991" xmlns:q="urn:q" q:Class="opaque"><GenericAttributes><GenericAttribute Name="Engineering" Value="SAFE"/><GenericAttribute Name="CreatorName" Value="PROTECTED_GA_991"><Unknown/></GenericAttribute></GenericAttributes></Nozzle></Position></Equipment></PlantModel>'

    def reader(self, base):
        xml = base / 'scope.xml'; xml.write_bytes(self.raw)
        return R.Reader(xml, 'scope', capture_source=True)

    def test_all_raw_scope_partitions_remain_excluded_when_native_folds_their_values(self):
        for scope in S.SCOPE_EXCLUSIONS:
            for qualified in (False, True):
                with self.subTest(scope=scope, qualified=qualified), tempfile.TemporaryDirectory() as tmp:
                    root = ET.Element('PlantModel'); eq = ET.SubElement(root, 'Equipment', ID='E1', ComponentClass='Tank')
                    parent = ET.SubElement(eq, '{urn:scope}' + scope if qualified else scope)
                    nozzle = ET.SubElement(parent, 'Nozzle', ID='N1', ComponentClass='Nozzle')
                    group = ET.SubElement(nozzle, 'GenericAttributes', Set='Custom')
                    ET.SubElement(group, 'GenericAttribute', Name='Engineering', Value='SAFE-SCOPE', Units='Bar')
                    base = Path(tmp); xml = base / 'scope.xml'; xml.write_bytes(ET.tostring(root))
                    native, _ = R.run(xml, base / 'out', 'scope', quiet=True, capture_source=True)
                    self.assertEqual(native['units'][0]['N1:Engineering']['value'], 'SAFE-SCOPE')
                    packet = native['source_evidence']
                    self.assertEqual(packet['completeness']['elements'], {'total': 6, 'retained': 2, 'policy_redacted': 0, 'scope_excluded': 4})
                    self.assertEqual(packet['completeness']['attributes'], {'total': 8, 'retained': 2, 'policy_redacted': 0, 'scope_excluded': 6})
                    self.assertFalse(any(m['destinations'] for r in packet['records'] for m in r['mappings']))

    def test_foreign_identity_and_qname_equality_cannot_register_or_mutate(self):
        cap = S.capture_xml(b'<PlantModel><Equipment ID="E1" ComponentClass="Tank" xmlns:q="urn:q" q:ID="qualified"/></PlantModel>')
        real = cap.root.find('Equipment'); callbacks = []
        class Foreign:
            def __hash__(self): callbacks.append('hash'); return hash(real)
            def __eq__(self, other): callbacks.append('eq'); return other is real
            def __repr__(self): callbacks.append('repr'); return 'FOREIGN_REPR'
        class ForeignElement(ET.Element):
            def __hash__(self): callbacks.append('ET-hash'); return hash(real)
            def __eq__(self, other): callbacks.append('ET-eq'); return other is real
        class ForeignName(str):
            def __hash__(self): callbacks.append('name-hash'); return hash('ID')
            def __eq__(self, other): callbacks.append('name-eq'); return True
        class ForeignTuple(tuple):
            def __hash__(self): callbacks.append('tuple-hash'); return hash(real)
            def __eq__(self, other): callbacks.append('tuple-eq'); return other is real
        other = S.capture_xml(b'<PlantModel><Equipment ID="E1"/></PlantModel>')
        foreign = Foreign()
        cases = [None, object(), ET.fromstring(b'<Equipment ID="E1"/>'), other.root.find('Equipment'), foreign,
                 (foreign, 'ID'), ForeignElement('Equipment'), (ForeignElement('Equipment'), 'ID'),
                 (real, ForeignName('NOT_ID')), ForeignTuple((real, 'ID')), (real, 'missing'), [real, 'ID']]
        for number, handle in enumerate(cases):
            with self.subTest(case=number):
                native = {'meta': {'unchanged': False}}
                generation = cap._generation
                with self.assertRaises(S.SourceEvidenceError): cap.source_ref(handle)
                with self.assertRaises(S.SourceEvidenceError):
                    cap.assign(handle, native['meta'], 'spoof', 'FOREIGN-WRITE', 'legacy-transform', 'generic-value')
                self.assertEqual(native, {'meta': {'unchanged': False}})
                self.assertEqual(cap._generation, generation)
                self.assertEqual(callbacks, [])
        self.assertNotEqual(cap.source_ref((real, 'ID')), cap.source_ref((real, '{urn:q}ID')))
        native = {'meta': {}}
        cap.assign(real, native['meta'], 'actual', 'supported', 'legacy-transform', 'part-class')
        packet = cap.finalize(native)
        self.assertEqual(sum(len(m['destinations']) for r in packet['records'] for m in r['mappings']), 1)

    def test_unsupported_profile_subclasses_and_whole_operations_refuse_before_mutation(self):
        callbacks = []
        class Profile(str):
            __hash__ = str.__hash__
            def __eq__(self, other): callbacks.append('eq'); return True
            def __repr__(self): callbacks.append('repr'); return 'UNKNOWN_PROFILE'
        for policy in (Profile('UNKNOWN'), Profile(S.POLICY_ID)):
            with self.assertRaises(S.SourceEvidenceError): S.capture_xml(SIMPLE, policy_id=policy)
        cap = S.capture_xml(SIMPLE); origin = cap.root.find('Equipment')
        for position in ('kind', 'basis'):
            for supplied in ('UNKNOWN', 'direct-copy' if position == 'kind' else 'generic-value'):
                native = {'meta': {'first': 0, 'target': False, 'last': None}}
                original = copy.deepcopy(native); generation = cap._generation
                args = [origin, native['meta'], 'target', 'mutated', 'direct-copy', 'generic-value']
                args[4 if position == 'kind' else 5] = Profile(supplied)
                with self.assertRaises(S.SourceEvidenceError): cap.assign(*args)
                self.assertEqual(native, original); self.assertEqual(list(native['meta']), ['first', 'target', 'last'])
                self.assertEqual(cap._generation, generation)
        for mode in (Profile('UNKNOWN'), Profile('copy'), Profile('move'), Profile('delete')):
            old, new = {'a': 'one', 'b': 'two'}, {'x': 'existing'}
            operations = [{'old_key': 'a', 'new_key': 'first', 'mode': 'copy'},
                          {'old_key': 'b', 'new_key': 'second', 'mode': mode}]
            generation = cap._generation
            with self.assertRaises(S.SourceEvidenceError): cap.transfer(old, new, operations)
            self.assertEqual(old, {'a': 'one', 'b': 'two'}); self.assertEqual(new, {'x': 'existing'})
            self.assertEqual(cap._generation, generation)
        self.assertEqual(callbacks, [])
        old, new = {'a': False, 'b': 0, 'c': None, 'd': ''}, {}
        cap.transfer(old, new, [{'old_key': k, 'new_key': k, 'mode': 'copy'} for k in old])
        self.assertEqual(list(new), ['a', 'b', 'c', 'd'])
        self.assertIs(type(new['a']), bool); self.assertIs(type(new['b']), int)

    def test_scope_replacement_withdraws_equal_generation_and_later_track_is_exact(self):
        for value in (False, 0, None, '', 'same', [], {}):
            with self.subTest(type=type(value).__name__), tempfile.TemporaryDirectory() as tmp:
                reader = self.reader(Path(tmp)); cap = reader.source_capture
                eligible = cap.root.find('Equipment'); scoped = cap.root.find('Equipment/Position/Nozzle')
                original_source = (eligible, 'ComponentClass'); untracked_source = (scoped, 'ComponentClass')
                native = {'meta': {'first': 'a'}}
                cap.assign(original_source, native['meta'], 'value', copy.deepcopy(value), 'legacy-transform', 'generic-value')
                native['meta']['last'] = 'z'
                before = cap.finalize(native)
                old_record = next(r for r in before['records'] if any(m['destinations'] for m in r['mappings']))
                reader._assign_scope_excluded_native(untracked_source, native['meta'], 'value', value, 'legacy-transform', 'generic-value')
                self.assertEqual(list(native['meta']), ['first', 'value', 'last'])
                self.assertIs(type(native['meta']['value']), type(value))
                after = cap.finalize(native)
                new_record = next(r for r in after['records'] if r['occurrence_id'] == old_record['occurrence_id'])
                self.assertFalse(any(m['destinations'] for r in after['records'] for m in r['mappings']))
                self.assertNotEqual(old_record['record_version_id'], new_record['record_version_id'])
                self.assertEqual(before['completeness']['elements'], after['completeness']['elements'])
                self.assertEqual(before['completeness']['attributes'], after['completeness']['attributes'])
                self.assertNotIn((id(native['meta']), 'value'), cap._slots)
                with self.assertRaises(S.SourceEvidenceError): cap.source_ref(untracked_source)
                reader._assign_native(original_source, native['meta'], 'value', 'new tracked', 'legacy-transform', 'generic-value')
                final = cap.finalize(native)
                pointers = [d['pointer'] for r in final['records'] for m in r['mappings'] for d in m['destinations']]
                self.assertEqual(pointers, ['/meta/value'])
                self.assertEqual(list(native['meta']), ['first', 'value', 'last'])

    def test_first_untracked_and_changed_overwrite_have_no_invented_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            reader = self.reader(Path(tmp)); cap = reader.source_capture
            eligible = cap.root.find('Equipment'); scoped = cap.root.find('Equipment/Position/Nozzle')
            native = {'meta': {}}
            reader._assign_native((scoped, 'ComponentClass'), native['meta'], 'first', 'untracked', 'direct-copy', 'generic-value')
            self.assertFalse(any(m['destinations'] for r in cap.finalize(native)['records'] for m in r['mappings']))
            cap.assign(eligible, native['meta'], 'changed', 'old', 'legacy-transform', 'part-class')
            reader._assign_scope_excluded_native(scoped, native['meta'], 'changed', 'different', 'legacy-transform', 'part-class')
            self.assertEqual(native['meta'], {'first': 'untracked', 'changed': 'different'})
            packet = cap.finalize(native)
            self.assertFalse(any(m['destinations'] for r in packet['records'] for m in r['mappings']))
            self.assertEqual(packet['native_model_sha256'], S.digest(native))

    def test_scope_only_privacy_foreign_new_deleted_and_eligible_refuse_without_callbacks(self):
        with tempfile.TemporaryDirectory() as tmp:
            reader = self.reader(Path(tmp)); cap = reader.source_capture
            eligible = cap.root.find('Equipment'); scoped = cap.root.find('Equipment/Position/Nozzle')
            protected = next(g for g in scoped.iter('GenericAttribute') if g.get('Name') == 'CreatorName')
            callbacks = []
            class Foreign:
                def __hash__(self): callbacks.append('hash'); return hash(scoped)
                def __eq__(self, other): callbacks.append('eq'); return other is scoped
            scoped.set('added', 'new')
            cases = [eligible, (eligible, 'ID'), protected, (protected, 'Value'), protected.find('Unknown'),
                     (scoped, 'OwnerName'), Foreign(), (Foreign(), 'ComponentClass'), (scoped, 'added'),
                     (scoped, 'absent'), (scoped, 'q:Class'), None]
            native = {'meta': {'first': 0, 'value': False, 'last': None}}
            original = copy.deepcopy(native); generation = cap._generation
            for number, source in enumerate(cases):
                with self.subTest(case=number), self.assertRaises(S.SourceEvidenceError):
                    reader._assign_scope_excluded_native(source, native['meta'], 'value', 'PRIVATE-MUTATION', 'direct-copy', 'generic-value')
                self.assertEqual(native, original); self.assertEqual(list(native['meta']), ['first', 'value', 'last'])
                self.assertEqual(cap._generation, generation)
            self.assertEqual(callbacks, [])
            # A protected direct attribute excludes that attribute, not the safe element/class handle.
            reader._assign_scope_excluded_native(scoped, native['meta'], 'safe-element', 0, 'legacy-transform', 'part-class')
            reader._assign_scope_excluded_native((scoped, '{urn:q}Class'), native['meta'], 'safe-expanded', 'opaque', 'direct-copy', 'generic-value')
            del scoped.attrib['ComponentClass']
            with self.assertRaises(S.SourceEvidenceError):
                reader._assign_scope_excluded_native((scoped, 'ComponentClass'), native['meta'], 'value', 'deleted', 'direct-copy', 'generic-value')
            cap.root.find('Equipment/Position').remove(scoped)
            with self.assertRaises(S.SourceEvidenceError):
                reader._assign_scope_excluded_native(scoped, native['meta'], 'value', 'detached', 'direct-copy', 'generic-value')
            self.assertFalse(any(m['destinations'] for r in cap.finalize(native)['records'] for m in r['mappings']))


class CanonicalWritePreflight(unittest.TestCase):
    literal = "native write is not canonically UTF-8 encodable"

    def test_assign_encoding_refusal_preserves_values_order_and_slot_generations(self):
        bad = [('x', chr(0xD800)), (chr(0xD800), 'safe'),
               ('x', {'nested': [{chr(0xD800): 'safe'}]}), ('x', 10 ** 5000)]
        for key, value in bad:
            for is_list in (False, True):
                if is_list and key != 'x':
                    continue
                cap = S.capture_xml(SIMPLE); origin = cap.root.find('Equipment')
                target = [] if is_list else {'before': 0}
                slot = 0 if is_list else 'x'
                cap.assign(origin, target, slot, 'same', 'legacy-transform', 'part-class')
                if not is_list:
                    target['after'] = False
                before = copy.deepcopy(target); state = copy.deepcopy(cap._slots); generation = cap._generation
                with self.assertRaises(S.SourceEvidenceError) as error:
                    cap.assign(origin, target, slot if is_list else key, value, 'legacy-transform', 'part-class')
                self.assertEqual(error.exception.args, (self.literal,))
                self.assertTrue(error.exception.__suppress_context__)
                self.assertEqual(target, before)
                self.assertEqual(list(target), list(before))
                self.assertEqual(cap._slots, state)
                self.assertEqual(cap._generation, generation)

    def test_transfer_preflights_later_key_value_before_copy_move_or_delete(self):
        for mode in ('copy', 'move', 'delete'):
            for tracked in (False, True):
                for kind in ('value', 'key'):
                    cap = S.capture_xml(SIMPLE); origin = cap.root.find('Equipment')
                    old = {'a': 'first', 'b': 'same'}; new = {'before': False}
                    if tracked:
                        for key in old:
                            cap.assign(origin, old, key, old[key], 'legacy-transform', 'part-class')
                    if kind == 'value':
                        old['b'] = {'nested': [chr(0xD800)]}
                    old_key = 'b'
                    new_key = 'b'
                    if kind == 'key':
                        if mode == 'delete':
                            old_key = chr(0xD800); old[old_key] = old.pop('b')
                        else:
                            new_key = chr(0xD800)
                    operations = [{'old_key': 'a', 'new_key': None if mode == 'delete' else 'a', 'mode': mode},
                                  {'old_key': old_key, 'new_key': None if mode == 'delete' else new_key, 'mode': mode}]
                    before = copy.deepcopy((old, new, cap._slots)); generation = cap._generation
                    with self.assertRaises(S.SourceEvidenceError) as error:
                        cap.transfer(old, new, operations)
                    self.assertEqual(error.exception.args, (self.literal,))
                    self.assertEqual((old, new, cap._slots), before)
                    self.assertEqual(cap._generation, generation)

    def test_scope_preflight_refuses_without_hashing_or_withdrawing_equal_mapping(self):
        raw = b'<PlantModel><Equipment ID="E1"><Position><Unknown ScopeAttr="raw"/></Position></Equipment></PlantModel>'
        with tempfile.TemporaryDirectory() as tmp:
            xml = Path(tmp) / 'source.xml'; xml.write_bytes(raw)
            reader = R.Reader(xml, capture_source=True); cap = reader.source_capture
            eligible = cap.root.find('Equipment'); scoped = cap.root.find('Equipment/Position/Unknown')
            target = {'before': 0}
            cap.assign(eligible, target, 'x', 'same', 'legacy-transform', 'part-class')
            target['after'] = False
            before = copy.deepcopy((target, cap._slots)); generation = cap._generation
            for key, value in [('x', chr(0xD800)), (chr(0xD800), 'same'), ('x', 10 ** 5000)]:
                with patch.object(S.hashlib, 'sha256', side_effect=AssertionError('excluded value hashed')), \
                     patch.object(S, 'digest', side_effect=AssertionError('excluded value digested')), \
                     self.assertRaises(S.SourceEvidenceError) as error:
                    reader._assign_scope_excluded_native((scoped, 'ScopeAttr'), target, key, value,
                                                         'legacy-transform', 'part-class')
                self.assertEqual(error.exception.args, (self.literal,))
                self.assertEqual((target, cap._slots), before)
                self.assertEqual(cap._generation, generation)
            with patch.object(S.hashlib, 'sha256', side_effect=AssertionError('excluded value hashed')), \
                 patch.object(S, 'digest', side_effect=AssertionError('excluded value digested')):
                reader._assign_scope_excluded_native((scoped, 'ScopeAttr'), target, 'x', 'same',
                                                     'legacy-transform', 'part-class')
            self.assertEqual(list(target), ['before', 'x', 'after'])
            self.assertNotIn((id(target), 'x'), cap._slots)
            self.assertEqual(xml.read_bytes(), raw)


if __name__ == "__main__":
    unittest.main()
