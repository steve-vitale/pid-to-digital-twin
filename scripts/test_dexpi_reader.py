"""Controls for scripts/dexpi_reader.py (any DEXPI 1.x XML -> process model with sourced attributes). Stdlib only.

A small synthetic DEXPI file always runs: attributes with units survive on the right item, a combined bubble becomes a
controller measuring its own nested sensor, every item and record cites an XML element ID that exists, generate.py
and graph_export.py accept the model, and malformed or non-DEXPI files are refused with a clear message.
If the public DEXPI examples are cached (python scripts/adapt_dexpi.py fetch), C01, C02 and C03 are read too and
named values are spot-checked against the XML; without the cache those checks are skipped, never failed.
"""
import contextlib
import io
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import dexpi_reader as R
import generate
import graph_export

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "data" / "dataset_adapters" / "dexpi_examples.json"
SOURCE = ROOT / "data" / "external" / "dexpi" / "source"
KEYS = ROOT / "data" / "external" / "dexpi" / "sheets"
SECTIONS = ("units", "streams", "instruments", "final_elements", "controllers", "manual_valves", "relief_devices",
            "unplaced")

SYNTHETIC = """<?xml version="1.0" encoding="UTF-8"?>
<PlantModel>
 <PlantInformation SchemaVersion="4.1.1" ApplicationVersion="1.3" OriginatingSystem="test"/>
 <MetaData ID="MetaData-1"><GenericAttributes Set="DexpiAttributes">
  <GenericAttribute Name="DrawingNumberAssignmentClass" Value="T-001"/>
  <GenericAttribute Name="CreatorNameAssignmentClass" Value="A. Person"/></GenericAttributes></MetaData>
 <Equipment ID="Tank-1" ComponentClass="Tank">
  <GenericAttributes Set="DexpiAttributes"><GenericAttribute Name="TagNameAssignmentClass" Value="T100"/>
   <GenericAttribute Name="type" Value="custom attribute that must not overwrite the unit type"/></GenericAttributes>
  <Label ID="L-1" ComponentClass="EquipmentTagNameLabel"><Text String="T100"/></Label>
  <Nozzle ID="Nozzle-1" ComponentClass="Nozzle"><ConnectionPoints><Node ID="Node-1"/>
   <Node ID="Node-2"><GenericAttributes Set="DexpiAttributes">
    <GenericAttribute Name="NominalDiameterRepresentationAssignmentClass" Value="DN 50"/></GenericAttributes></Node>
  </ConnectionPoints></Nozzle>
  <Equipment ID="Chamber-1" ComponentClass="Chamber"><GenericAttributes Set="DexpiAttributes">
   <GenericAttribute Name="UpperLimitDesignPressure" Value="6" Units="Bar"/>
   <GenericAttribute Name="EmptyOne" Value=""/></GenericAttributes></Equipment>
 </Equipment>
 <Equipment ID="Pump-1" ComponentClass="CentrifugalPump">
  <GenericAttributes Set="DexpiAttributes"><GenericAttribute Name="TagNameAssignmentClass" Value="P100"/>
   <GenericAttribute Name="DesignVolumeFlowRate" Value="12.5" Units="MetreCubedPerHour"/></GenericAttributes>
  <Nozzle ID="Nozzle-2" ComponentClass="Nozzle"/>
 </Equipment>
 <Equipment ID="Widget-1" ComponentClass="Agglomerator">
  <GenericAttributes Set="DexpiAttributes"><GenericAttribute Name="TagNameAssignmentClass" Value="X100"/></GenericAttributes>
 </Equipment>
 <ActuatingSystem ID="AS-1" ComponentClass="ActuatingSystem">
  <GenericAttributes Set="DexpiAttributes"><GenericAttribute Name="ActuatingSystemNumberAssignmentClass" Value="LV100"/></GenericAttributes>
  <Association Type="fulfills" ItemID="AF-1"/>
  <ActuatingSystemComponent ID="ACT-1" ComponentClass="ControlledActuator"><GenericAttributes Set="DexpiAttributes">
   <GenericAttribute Name="FailActionSpecialization" Value="FailClose"/></GenericAttributes></ActuatingSystemComponent>
  <ActuatingSystemComponent ID="OVR-1" ComponentClass="OperatedValveReference">
   <Association Type="refers to" ItemID="Valve-1"/></ActuatingSystemComponent>
 </ActuatingSystem>
 <PipingNetworkSystem ID="PNS-1" ComponentClass="PipingNetworkSystem">
  <GenericAttributes Set="DexpiAttributes"><GenericAttribute Name="LineNumberAssignmentClass" Value="L1"/>
   <GenericAttribute Name="NominalDiameterRepresentationAssignmentClass" Value="DN 50"/></GenericAttributes>
  <PipingNetworkSegment ID="Seg-1" ComponentClass="PipingNetworkSegment">
   <GenericAttributes Set="DexpiAttributes"><GenericAttribute Name="FluidCodeAssignmentClass" Value="W"/></GenericAttributes>
   <PipingComponent ID="Reducer-1" ComponentClass="PipeReducer"><Label ComponentClass="ValveLabel"><Text String="80/50"/></Label></PipingComponent>
   <PipingComponent ID="Valve-1" ComponentClass="GlobeValve"/>
   <PipingComponent ID="Valve-2" ComponentClass="BallValve"><Label ComponentClass="ValveLabel"><Text String="SPEC-1"/></Label></PipingComponent>
   <PipeFlowArrow ID="Arrow-1"/>
   <Connection FromID="Nozzle-1" ToID="Nozzle-2"/>
  </PipingNetworkSegment>
 </PipingNetworkSystem>
 <ProcessInstrumentationFunction ID="PIF-1" ComponentClass="ProcessInstrumentationFunction">
  <GenericAttributes Set="DexpiAttributes">
   <GenericAttribute Name="ProcessInstrumentationFunctionCategoryAssignmentClass" Value="L"/>
   <GenericAttribute Name="ProcessInstrumentationFunctionsAssignmentClass" Value="IC"/>
   <GenericAttribute Name="ProcessInstrumentationFunctionNumberAssignmentClass" Value="100"/></GenericAttributes>
  <Label ComponentClass="ProcessInstrumentationFunctionLabel"><Text String="LIC"/><Text String="100"/></Label>
  <ProcessSignalGeneratingFunction ID="PSGF-1" ComponentClass="ProcessSignalGeneratingFunction">
   <GenericAttributes Set="DexpiAttributes">
    <GenericAttribute Name="ProcessSignalGeneratingFunctionNumberAssignmentClass" Value="LT100"/></GenericAttributes>
   <Association Type="is located in" ItemID="Nozzle-1"/></ProcessSignalGeneratingFunction>
  <ActuatingFunction ID="AF-1" ComponentClass="ActuatingFunction"><Association Type="is fulfilled by" ItemID="AS-1"/></ActuatingFunction>
  <InformationFlow ID="SCF-1" ComponentClass="SignalConveyingFunction">
   <Association Type="has logical start" ItemID="PIF-1"/><Association Type="has logical end" ItemID="AF-1"/>
   <Connection FromID="PIF-1" ToID="ACT-1"/></InformationFlow>
 </ProcessInstrumentationFunction>
</PlantModel>
"""


TEE = """<?xml version="1.0" encoding="UTF-8"?>
<PlantModel>
 <Equipment ID="Tank-1" ComponentClass="Tank"><GenericAttributes Set="DexpiAttributes">
  <GenericAttribute Name="TagNameAssignmentClass" Value="T1"/></GenericAttributes><Nozzle ID="N-1" ComponentClass="Nozzle"/></Equipment>
 <Equipment ID="Pump-1" ComponentClass="CentrifugalPump"><GenericAttributes Set="DexpiAttributes">
  <GenericAttribute Name="TagNameAssignmentClass" Value="P1"/></GenericAttributes><Nozzle ID="N-2" ComponentClass="Nozzle"/></Equipment>
 <Equipment ID="Pump-2" ComponentClass="CentrifugalPump"><GenericAttributes Set="DexpiAttributes">
  <GenericAttribute Name="TagNameAssignmentClass" Value="P2"/></GenericAttributes><Nozzle ID="N-3" ComponentClass="Nozzle"/></Equipment>
 <PipingNetworkSystem ID="PNS-1" ComponentClass="PipingNetworkSystem">
  <PipingNetworkSegment ID="Seg-1" ComponentClass="PipingNetworkSegment">
   <PipingComponent ID="Tee-1" ComponentClass="PipeTee"/>
   <PipingComponent ID="Flange-1" ComponentClass="Flange"/>
   <PipingComponent ID="Valve-A" ComponentClass="BallValve"/>
   <Connection FromID="N-1" ToID="N-2"/></PipingNetworkSegment>
  <PipingNetworkSegment ID="Seg-2" ComponentClass="PipingNetworkSegment">
   <PipingComponent ID="Valve-B" ComponentClass="GateValve"/>
   <Connection FromID="Tee-1" ToID="N-3"/></PipingNetworkSegment>
 </PipingNetworkSystem>
</PlantModel>
"""


def read(xml_path, sheet_id, compare=None):
    with tempfile.TemporaryDirectory() as out, contextlib.redirect_stdout(io.StringIO()):
        model, rep = R.run(xml_path, out, sheet_id, compare=compare, quiet=True)
    return model, rep


def items(model):
    for sec in SECTIONS:
        for it in model.get(sec, []):
            yield sec, it


def exports_accept(case, model):
    """generate.py (structural validation + full render) and graph_export.py (build + problems) on the model."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "model.json"
        path.write_text(json.dumps(model, ensure_ascii=False), encoding="utf-8")
        prepared = generate._auto_layout(generate._mark_finals(json.loads(path.read_text(encoding="utf-8"))))
        case.assertEqual(generate.validate(prepared), [])
        generate.export_seed(prepared, Path(tmp) / "out")
        case.assertTrue((Path(tmp) / "out" / "ignition" / "tags.json").is_file())
        g = graph_export.build(path)
        case.assertEqual(graph_export.problems(g), [])
        return g


def cites_real_ids(case, model, xml_path):
    root = ET.parse(xml_path).getroot()
    ids = {el.get("ID") for el in root.iter() if el.get("ID")}
    for sec, it in items(model):
        case.assertIn(it.get("dexpi_id"), ids, f"{sec} {it.get('id') or it.get('tag')}")
        case.assertIn(it["dexpi_id"], it.get("source", ""))
        for key, rec in it.items():
            if isinstance(rec, dict) and "source" in rec:
                cited = rec["source"].split()[2]  # "DEXPI XML <ID> ..."
                case.assertIn(cited, ids, f"{sec} {key}: {rec['source']}")


class MetadataPrivacy(unittest.TestCase):
    def test_same_named_person_policy_applies_before_all_metadata_projections(self):
        root = ET.Element("PlantModel")
        roles = ("Approver", "Checker", "Creator", "Designer", "Drafter", "Editor", "Reviewer", "Owner")
        info = ET.SubElement(root, "PlantInformation", SchemaVersion="4.1.1", OwnerTag="false")
        markers = []
        for i, role in enumerate(roles):
            name = (role + "NameAssignmentClass") if i % 2 else (role + "NameAssignmentClass").lower()
            marker = f"PERSON_SENTINEL_INFO_{i}"
            markers.append(marker)
            info.set(name, marker)
        info.set("CreatorNameEmpty", "")
        for tag in ("MetaData", "PlantStructureItem"):
            owner = ET.SubElement(root, tag, ID=tag + "-1", ComponentClass="Plant")
            for i, role in enumerate(roles):
                group = ET.SubElement(owner, "GenericAttributes", Set="DexpiAttributes" if i % 2 else "Vendor")
                marker = f"PERSON_SENTINEL_{tag}_{i}"
                markers.append(marker)
                name = role + "NameAssignmentClass"
                ET.SubElement(group, "GenericAttribute", Name=name.swapcase() if i % 2 else name, Value=marker)
            group = ET.SubElement(owner, "GenericAttributes")
            ET.SubElement(group, "GenericAttribute", Name="CreatorNameEmpty", Value="")
            ET.SubElement(group, "GenericAttribute", Name="EditorNameMissing")
            ET.SubElement(group, "GenericAttribute", Name="EngineeringNote", Value=" 0 ")
            ET.SubElement(group, "GenericAttribute", Name="OwnerTag", Value="false")
        ET.SubElement(root, "Equipment", ID="E1", ComponentClass="Tank")
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            xml = folder / "metadata.xml"
            ET.ElementTree(root).write(xml, encoding="utf-8", xml_declaration=True)
            original = xml.read_bytes()
            with contextlib.redirect_stdout(io.StringIO()):
                model, report = R.run(xml, folder / "reader", "metadata")
            self.assertEqual(xml.read_bytes(), original)
            self.assertEqual(model["meta"]["dexpi_file"], {"SchemaVersion": "4.1.1", "OwnerTag": "false"})
            self.assertEqual(report["person_metadata_attributes_excluded"], 9)
            a = report["attributes"]
            self.assertEqual((a["in_file"], a["kept_in_meta_only"], a["dropped"]), (24, 4, 20))
            self.assertEqual(a["dropped_by_reason"], {"person name: left out on purpose": 16, "no value in the file": 4})
            for attrs in (model["meta"]["drawing"], model["meta"]["plant_structure"][0]["attributes"]):
                self.assertEqual(attrs, {"EngineeringNote": " 0 ", "OwnerTag": "false"})
            self.assertEqual((len(model["units"]), len(model["streams"])), (1, 0))
            import serve_snapshot
            for profile in ("full", "core"):
                graph = graph_export.apply_profile(graph_export.build(folder / "reader/metadata.model.json"), profile)
                self.assertEqual(graph_export.problems(graph), [])
                path = folder / f"{profile}.json"
                path.write_text(json.dumps(graph), encoding="utf-8")
                packet = serve_snapshot.Snapshot(path)
                result = packet.asset("PLANT")
                self.assertIn(" 0 ", json.dumps(result))
                self.assertIn("false", json.dumps(result))
                for marker in markers:
                    self.assertNotIn(marker, json.dumps(result))
            generated = [p for p in folder.rglob("*") if p.is_file() and p != xml]
            for path in generated:
                for marker in markers:
                    self.assertNotIn(marker.encode(), path.read_bytes(), path.name)


class Synthetic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.xml = Path(cls.tmp.name) / "synthetic.xml"
        cls.xml.write_text(SYNTHETIC, encoding="utf-8")
        cls.model, cls.rep = read(cls.xml, "synthetic-01")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def unit(self, uid):
        return next(u for u in self.model["units"] if u["id"] == uid)

    def test_attributes_survive_with_units_and_source(self):
        tank = self.unit("T100")
        rec = tank["Chamber-1:UpperLimitDesignPressure"]
        self.assertEqual((rec["value"], rec["uom"]), ("6", "Bar"))
        self.assertTrue(rec["source"].startswith("DEXPI XML Chamber-1 "))
        self.assertEqual(tank["Nozzle-1:Node-2:NominalDiameterRepresentationAssignmentClass"]["value"], "DN 50")
        self.assertEqual(self.unit("P100")["DesignVolumeFlowRate"]["uom"], "MetreCubedPerHour")
        line = self.model["streams"][0]
        self.assertEqual((line["id"], line["from"], line["to"]), ("L1", "T100", "P100"))
        self.assertEqual(line["Seg-1:FluidCodeAssignmentClass"]["value"], "W")
        self.assertEqual(line["Reducer-1:label:ValveLabel"]["value"], "80/50")

    def test_custom_attribute_cannot_overwrite_a_model_field(self):
        tank = self.unit("T100")
        self.assertEqual(tank["type"], "tank")
        self.assertIn("dexpi:type", tank)

    def test_unmapped_class_kept_and_listed(self):
        x = self.unit("X100")
        self.assertEqual((x["dexpi_class"], x["type"]), ("Agglomerator", "vessel"))
        self.assertIn("no generator type", x["type_basis"])
        self.assertEqual(self.rep["unmapped_equipment_classes"], {"Agglomerator": 1})

    def test_combined_bubble_is_a_controller_measuring_its_own_sensor(self):
        ctrl = self.model["controllers"][0]
        self.assertEqual(ctrl["tag"], "LIC-100")
        self.assertEqual(ctrl["measurement"], "LT-100")
        self.assertEqual(ctrl["output"], {"final_element": "LV-100"})
        inst = next(i for i in self.model["instruments"] if i["tag"] == "LT-100")
        self.assertEqual((inst["part_of"], inst["dexpi_id"], inst["unit"], inst["variable"]),
                         ("LIC-100", "PSGF-1", "T100", "level"))
        fe = self.model["final_elements"][0]
        self.assertEqual((fe["tag"], fe["unit"], fe["stream"]), ("LV-100", "T100", "L1"))
        self.assertEqual(fe["ACT-1:FailActionSpecialization"]["value"], "FailClose")

    def test_manual_valve_without_identifier_uses_xml_id(self):
        mv = self.model["manual_valves"][0]
        self.assertEqual((mv["tag"], mv["label:ValveLabel"]["value"]), ("Valve-2", "SPEC-1"))

    def test_every_item_cites_its_xml_element(self):
        cites_real_ids(self, self.model, self.xml)

    def test_accounting_and_person_names(self):
        a = self.rep["attributes"]
        self.assertEqual(a["in_file"], a["kept_as_sourced_records"] + a["kept_in_meta_only"]
                         + a["kept_on_unplaced_items"] + a["dropped"])
        self.assertEqual(a["dropped_by_reason"], {"person name: left out on purpose": 1, "no value in the file": 1})
        self.assertNotIn("A. Person", json.dumps(self.model))

    def test_generate_and_graph_export_accept(self):
        g = exports_accept(self, self.model)
        node = next(n for n in g["nodes"] if n["id"] == "T100")
        claim = next(c for c in node["attributes"] if c["name"] == "Chamber-1:UpperLimitDesignPressure.value")
        self.assertEqual(claim["value"], "6")
        self.assertIn("Chamber-1", claim["source"]["document"])

    def test_pipe_layer_follows_the_segment_chain(self):
        tag = {it["dexpi_id"]: it["tag"] for sec in ("final_elements", "manual_valves") for it in self.model[sec]}
        ll = self.model["line_layers"]
        want = {tuple(sorted(p)) for p in (("T100", tag["Valve-1"]), (tag["Valve-1"], tag["Valve-2"]),
                                           (tag["Valve-2"], "P100"))}  # the reducer is passed through
        self.assertEqual({tuple(sorted((x["from"], x["to"]))) for x in ll["segments"]}, want)
        self.assertEqual(ll["junctions"], [])
        self.assertTrue(all(len(n["members"]) == 2 for n in ll["networks"]))

    def test_a_pipe_tee_is_a_junction_and_items_beyond_it_are_not_adjacent(self):
        with tempfile.TemporaryDirectory() as d:
            x = Path(d) / "tee.xml"
            x.write_text(TEE, encoding="utf-8")
            model, _ = read(x, "tee-01")
        ll = model["line_layers"]
        self.assertEqual([(j["id"], j["arms"], j["dexpi_id"]) for j in ll["junctions"]], [("tee-01-JN-Tee-1", 3, "Tee-1")])
        segs = {tuple(sorted((x["from"], x["to"]))) for x in ll["segments"]}
        self.assertEqual(segs, {("T1", "tee-01-JN-Tee-1"), ("Valve-A", "tee-01-JN-Tee-1"),
                                ("Valve-B", "tee-01-JN-Tee-1"), ("P1", "Valve-A"), ("P2", "Valve-B")})
        nets = {tuple(n["members"]): n["junctions"] for n in ll["networks"]}
        self.assertEqual(nets[("T1", "Valve-A", "Valve-B")], ["tee-01-JN-Tee-1"])  # three items, one tee
        g = exports_accept(self, model)
        self.assertEqual(sum(n["kind"] == "junction" for n in g["nodes"]), 1)

    def test_malformed_and_foreign_files_refused(self):
        bad = Path(self.tmp.name) / "bad.xml"
        bad.write_text("<PlantModel><Equipment ID='x'>", encoding="utf-8")
        with self.assertRaisesRegex(R.DexpiError, "not well-formed XML"):
            R.Reader(bad)
        other = Path(self.tmp.name) / "other.xml"
        other.write_text("<svg xmlns='http://www.w3.org/2000/svg'/>", encoding="utf-8")
        with self.assertRaisesRegex(R.DexpiError, "not <PlantModel>"):
            R.Reader(other)
        dup = Path(self.tmp.name) / "dup.xml"
        dup.write_text("<PlantModel><Equipment ID='E-1'/><Equipment ID='E-1'/></PlantModel>", encoding="utf-8")
        with self.assertRaisesRegex(R.DexpiError, "more than once"):
            R.Reader(dup)
        out = Path(self.tmp.name) / "refused"
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(R.main(["--xml", str(bad), "--out", str(out)]), 2)
        self.assertIn("refused", err.getvalue())
        self.assertFalse(out.exists())

    def test_dangling_connection_reference_is_a_broken_reference_not_a_closed_end(self):
        # A Connection naming an ID the file does not contain is a defect in the file, not a line that stops.
        xml = Path(self.tmp.name) / "dangling.xml"
        xml.write_text(SYNTHETIC.replace('ToID="Nozzle-2"', 'ToID="zz"'), encoding="utf-8")
        model, rep = read(xml, "dangling-01")
        line = model["streams"][0]
        self.assertEqual((line["from"], line["to"]), ("T100", "BL"))
        self.assertIn("broken reference", line["to_end"])
        self.assertIn("'zz'", line["to_end"])
        self.assertNotIn("closed end", line["to_end"])
        self.assertEqual(rep["broken_references"], [{"element": "Seg-1", "attribute": "ToID", "missing_id": "zz"}])
        self.assertEqual(model["meta"]["broken_references"], rep["broken_references"])
        self.assertTrue(any("zz" in n and "broken reference" in n for n in rep["notes"]), rep["notes"])
        self.assertIn("Broken references", R.report_text(rep))
        self.assertNotIn("broken_references", self.model["meta"])   # a clean file has no such key
        exports_accept(self, model)

    def test_report_text_does_not_say_stream_records_are_lost_from_the_graph(self):
        # graph_export.py carries a line's records on its connects edge; the report must not say otherwise.
        text = R.report_text(self.rep)
        self.assertNotIn("carry no attributes", text)
        self.assertIn("connects", text)
        g = exports_accept(self, self.model)
        edge = next(e for e in g["edges"] if e["type"] == "connects" and e["id"] == "L1")
        self.assertIn("Seg-1:FluidCodeAssignmentClass.value", {c["name"] for c in edge["attributes"]})

    def test_report_prints_on_a_cp1252_console(self):
        # A Windows console is cp1252; a report with a character outside it (C02 has a superscript plus) must print.
        xml = Path(self.tmp.name) / "plus\u207a.xml"
        xml.write_text(SYNTHETIC, encoding="utf-8")
        out = Path(self.tmp.name) / "cp1252-out"
        console = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
        with contextlib.redirect_stdout(console):
            self.assertEqual(R.main(["--xml", str(xml), "--out", str(out), "--sheet-id", "plus"]), 0)
        console.flush()
        self.assertIn("plus", console.buffer.getvalue().decode("utf-8"))


# Instrumentation as other DEXPI exports write it (structures read from the DEXPI 1.2 reference solutions and the 1.3
# single-feature cases E/I/P at even positions; the vendor exports and the other cases were held out). One minimal
# file per structure; each controller here was missed or mis-tagged before 2026-10-29.
TOOL_STRUCTURES = """<?xml version="1.0" encoding="UTF-8"?>
<PlantModel>
 <PlantInformation SchemaVersion="4.0.1" ApplicationVersion="1.2" OriginatingSystem="test"/>
 <Equipment ID="V1" ComponentClass="Tank" TagName="V-4701">
  <Label ComponentClass="EqupipmentTagNameLabel"><Text String="V-4701"/></Label>
  <Nozzle ID="V1-N1" ComponentClass="Nozzle"/><Nozzle ID="V1-N2" ComponentClass="Nozzle"/></Equipment>
 <Equipment ID="P1" ComponentClass="CentrifugalPump"><GenericAttributes Set="DexpiAttributes">
  <GenericAttribute Name="TagNameAssignmentClass" Value="P4711"/></GenericAttributes>
  <Nozzle ID="P1-N1" ComponentClass="Nozzle"/></Equipment>
 <PipingNetworkSystem ID="PNS-1" ComponentClass="PipingNetworkSystem">
  <PipingNetworkSegment ID="S1" ComponentClass="PipingNetworkSegment">
   <PipingComponent ID="V-shutoff" ComponentClass="GlobeValve"/>
   <PipingComponent ID="V-numbered" ComponentClass="GlobeValve"><GenericAttributes Set="DexpiAttributes">
    <GenericAttribute Name="PipingComponentNumberAssignmentClass" Value="FV 04"/></GenericAttributes>
    <Association Type="is referenced by" ItemID="AS2-ref"/></PipingComponent>
   <PipingComponent ID="V-cascade" ComponentClass="GlobeValve"/>
   <Connection FromID="V1-N1" ToID="P1-N1"/></PipingNetworkSegment>
  <PipingNetworkSegment ID="S2" ComponentClass="PipingNetworkSegment">
   <PipingComponent ID="Blind-1" ComponentClass="BlindFlange"><Association Type="is the location of" ItemID="PSGF-L"/></PipingComponent>
   <Connection FromID="V1-N2" ToID="Blind-1"/></PipingNetworkSegment>
 </PipingNetworkSystem>
 <!-- DEXPI 1.2: the valve is a ShutOffValveReference carrying the tag as SubTagName; signal lines are
      SignalConveyingFunction -->
 <ActuatingSystem ID="AS1" ComponentClass="ActuatingSystem"><Association Type="fulfills" ItemID="AF1"/>
  <ActuatingSystemComponent ID="AS1-ref" ComponentClass="ShutOffValveReference">
   <Association Type="refers to" ItemID="V-shutoff"/><GenericAttributes Set="DexpiAttributes">
   <GenericAttribute Name="SubTagNameAssignmentClass" Value="PV 4712.02"/></GenericAttributes></ActuatingSystemComponent>
  <ActuatingSystemComponent ID="AS1-act" ComponentClass="ControlledActuator"><GenericAttributes Set="DexpiAttributes">
   <GenericAttribute Name="FailActionSpecialization" Value="FailClose"/></GenericAttributes></ActuatingSystemComponent>
 </ActuatingSystem>
 <ProcessInstrumentationFunction ID="PIF1" ComponentClass="ProcessInstrumentationFunction">
  <GenericAttributes Set="DexpiAttributes">
   <GenericAttribute Name="ProcessInstrumentationFunctionNumberAssignmentClass" Value="4712.02"/>
   <GenericAttribute Name="ProcessInstrumentationFunctionCategoryAssignmentClass" Value="P"/>
   <GenericAttribute Name="ProcessInstrumentationFunctionsAssignmentClass" Value="ICSA"/></GenericAttributes>
  <ActuatingFunction ID="AF1" ComponentClass="ActuatingFunction"><Association Type="is fulfilled by" ItemID="AS1"/></ActuatingFunction>
  <InformationFlow ID="IF1" ComponentClass="SignalConveyingFunction">
   <Association Type="has logical end" ItemID="AF1"/><Association Type="has logical start" ItemID="PIF1"/></InformationFlow>
  <ProcessSignalGeneratingFunction ID="PSGF1" ComponentClass="ProcessSignalGeneratingFunction">
   <Association Type="is located in" ItemID="V1-N1"/></ProcessSignalGeneratingFunction>
 </ProcessInstrumentationFunction>
 <!-- DEXPI 1.3 small cases: the actuating system has no number; the operated valve carries it -->
 <ActuatingSystem ID="AS2" ComponentClass="ActuatingSystem"><Association Type="fulfills" ItemID="AF2"/>
  <ActuatingSystemComponent ID="AS2-ref" ComponentClass="OperatedValveReference">
   <Association Type="refers to" ItemID="V-numbered"/></ActuatingSystemComponent></ActuatingSystem>
 <ProcessInstrumentationFunction ID="PIF2" ComponentClass="ProcessInstrumentationFunction">
  <GenericAttributes Set="DexpiAttributes">
   <GenericAttribute Name="ProcessInstrumentationFunctionCategoryAssignmentClass" Value="F"/>
   <GenericAttribute Name="ProcessInstrumentationFunctionNumberAssignmentClass" Value="04"/>
   <GenericAttribute Name="ProcessInstrumentationFunctionsAssignmentClass" Value="IC"/></GenericAttributes>
  <ActuatingFunction ID="AF2" ComponentClass="ActuatingFunction"><Association Type="is fulfilled by" ItemID="AS2"/></ActuatingFunction>
  <ProcessSignalGeneratingFunction ID="PSGF2" ComponentClass="ProcessSignalGeneratingFunction">
   <Association Type="is located in" ItemID="V1-N1"/></ProcessSignalGeneratingFunction>
  <InformationFlow ID="SLF2" ComponentClass="SignalLineFunction">
   <Association Type="has logical start" ItemID="PIF2"/><Association Type="has logical end" ItemID="AF2"/></InformationFlow>
 </ProcessInstrumentationFunction>
 <!-- a controlling bubble (C among its functions) that drives no valve in the file -->
 <ProcessInstrumentationFunction ID="PIF-L" ComponentClass="ProcessInstrumentationFunction">
  <GenericAttributes Set="DexpiAttributes">
   <GenericAttribute Name="ProcessInstrumentationFunctionNumberAssignmentClass" Value="470103"/>
   <GenericAttribute Name="ProcessInstrumentationFunctionCategoryAssignmentClass" Value="L"/>
   <GenericAttribute Name="ProcessInstrumentationFunctionsAssignmentClass" Value="ICSA"/></GenericAttributes>
  <ProcessSignalGeneratingFunction ID="PSGF-L" ComponentClass="ProcessSignalGeneratingFunction">
   <GenericAttributes Set="DexpiAttributes">
    <GenericAttribute Name="ProcessSignalGeneratingFunctionNumberAssignmentClass" Value="LT470103 "/></GenericAttributes>
   <Association Type="is located in" ItemID="Blind-1"/></ProcessSignalGeneratingFunction>
 </ProcessInstrumentationFunction>
 <!-- a cascade: FIC 032 signals YCS 033, which drives the valve; a hand switch (category H, modifier S) also drives it -->
 <ActuatingSystem ID="AS3" ComponentClass="ActuatingSystem"><Association Type="fulfills" ItemID="AF3"/>
  <ActuatingSystemComponent ID="AS3-ref" ComponentClass="OperatedValveReference">
   <Association Type="refers to" ItemID="V-cascade"/></ActuatingSystemComponent></ActuatingSystem>
 <ProcessInstrumentationFunction ID="PIF-Y" ComponentClass="ProcessInstrumentationFunction">
  <GenericAttributes Set="DexpiAttributes">
   <GenericAttribute Name="ProcessInstrumentationFunctionCategoryAssignmentClass" Value="Y"/>
   <GenericAttribute Name="ProcessInstrumentationFunctionNumberAssignmentClass" Value="033"/>
   <GenericAttribute Name="ProcessInstrumentationFunctionsAssignmentClass" Value="CS"/></GenericAttributes>
  <ActuatingFunction ID="AF3" ComponentClass="ActuatingFunction"><Association Type="is fulfilled by" ItemID="AS3"/></ActuatingFunction>
  <InformationFlow ID="SLF3" ComponentClass="SignalLineFunction">
   <Association Type="has logical start" ItemID="PIF-Y"/><Association Type="has logical end" ItemID="AF3"/></InformationFlow>
 </ProcessInstrumentationFunction>
 <ProcessInstrumentationFunction ID="PIF-F" ComponentClass="ProcessInstrumentationFunction">
  <GenericAttributes Set="DexpiAttributes">
   <GenericAttribute Name="ProcessInstrumentationFunctionCategoryAssignmentClass" Value="F"/>
   <GenericAttribute Name="ProcessInstrumentationFunctionNumberAssignmentClass" Value="032"/>
   <GenericAttribute Name="ProcessInstrumentationFunctionsAssignmentClass" Value="IC"/></GenericAttributes>
  <ProcessSignalGeneratingFunction ID="PSGF-F" ComponentClass="ProcessSignalGeneratingFunction">
   <Association Type="is located in" ItemID="P1-N1"/></ProcessSignalGeneratingFunction>
  <InformationFlow ID="SLF4" ComponentClass="SignalLineFunction">
   <Association Type="has logical start" ItemID="PIF-F"/><Association Type="has logical end" ItemID="PIF-Y"/></InformationFlow>
 </ProcessInstrumentationFunction>
 <ProcessInstrumentationFunction ID="PIF-H" ComponentClass="ProcessInstrumentationFunction">
  <GenericAttributes Set="DexpiAttributes">
   <GenericAttribute Name="ProcessInstrumentationFunctionNumberAssignmentClass" Value="4750.01"/>
   <GenericAttribute Name="ProcessInstrumentationFunctionCategoryAssignmentClass" Value="H"/>
   <GenericAttribute Name="ProcessInstrumentationFunctionModifierAssignmentClass" Value="S"/></GenericAttributes>
  <InformationFlow ID="SLF5" ComponentClass="SignalLineFunction">
   <Association Type="has logical start" ItemID="PIF-H"/><Association Type="has logical end" ItemID="PIF-Y"/></InformationFlow>
 </ProcessInstrumentationFunction>
</PlantModel>
"""


class ToolExportStructures(unittest.TestCase):
    """How DEXPI 1.2 exports and the 1.3 single-feature cases write controllers and their valves."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.xml = Path(cls.tmp.name) / "tools.xml"
        cls.xml.write_text(TOOL_STRUCTURES, encoding="utf-8")
        cls.model, cls.rep = read(cls.xml, "tools-01")
        cls.ctrl = {c["dexpi_id"]: c for c in cls.model["controllers"]}
        cls.fe = {f["dexpi_id"]: f for f in cls.model["final_elements"]}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_shutoff_valve_reference_is_an_operated_valve_tagged_by_its_subtag(self):
        fe = self.fe["V-shutoff"]
        self.assertEqual(fe["tag"], "PV-4712.02")
        self.assertIn("SubTagNameAssignmentClass", fe["tag_basis"])
        self.assertEqual(fe["AS1-act:FailActionSpecialization"]["value"], "FailClose")
        c = self.ctrl["PIF1"]
        self.assertEqual((c["tag"], c["output"]), ("PICSA-4712.02", {"final_element": "PV-4712.02"}))

    def test_operated_valve_number_tags_the_final_element_when_the_system_has_none(self):
        self.assertEqual(self.fe["V-numbered"]["tag"], "FV-04")
        self.assertEqual(self.ctrl["PIF2"]["output"], {"final_element": "FV-04"})

    def test_a_controlling_bubble_that_drives_no_valve_is_still_a_controller(self):
        c = self.ctrl["PIF-L"]
        self.assertEqual((c["tag"], c["measurement"], c["output"]), ("LICSA-470103", "LT-470103", {}))
        self.assertNotIn("PIF-L", {i["dexpi_id"] for i in self.model["instruments"]})

    def test_cascade_and_hand_switch(self):
        self.assertEqual(self.ctrl["PIF-Y"]["output"], {"final_element": self.fe["V-cascade"]["tag"]})
        self.assertEqual(self.ctrl["PIF-F"]["output"], {"setpoint_of": "YCS-033"})
        self.assertEqual(self.ctrl["PIF-F"]["measurement"], "FT-032")
        # category H + modifier S, no functions attribute: tagged HS (it signals a controller, drives no valve itself)
        self.assertIn("HS-4750.01", {it.get("tag") for _, it in items(self.model)})

    def test_equipment_tag_from_the_tagname_attribute(self):
        self.assertIn("V-4701", {u["id"] for u in self.model["units"]})

    def test_cites_ids_and_exports(self):
        cites_real_ids(self, self.model, self.xml)
        exports_accept(self, self.model)


TTC = ROOT / "data" / "external" / "dexpi-ttc-all" / "extracted" / (
    "TrainingTestCases-a23d61e2e089eb2ca464cd552f9ae580a2785963-a23d61e2e089eb2ca464cd552f9ae580a2785963")


class TrainingTestCaseFiles(unittest.TestCase):
    """Two development files of the DEXPI TrainingTestCases (scripts/fetch_corpus.py; skipped if not fetched)."""

    def file(self, rel):
        path = TTC / rel
        if not path.is_file():
            self.skipTest(f"{rel} not fetched (python scripts/fetch_corpus.py); skipped")
        return path

    def test_dexpi_12_reference_c02_controllers_drive_their_valves(self):
        model, _ = read(self.file("dexpi 1.2/example pids/C02 DEXPI Example Complete E+P/C02V01-VER.EX01.xml"), "c02-12")
        ctrls = {c["tag"]: c for c in model["controllers"]}
        self.assertEqual(ctrls["PICSA-4712.02"]["output"], {"final_element": "PV-4712.02"})
        self.assertEqual(ctrls["TICSA-4750.03"]["output"], {"final_element": "TV-4750.03"})

    def test_dexpi_13_i04_flow_controller_drives_fv_04(self):
        # The file has no equipment, so FV 04 reaches no unit: it stays in `unplaced` (generate.py needs a unit) and
        # the controller names it as output_unplaced. Before 2026-10-29 it was tagged by its XML ID, GlobeValve-1.
        model, _ = read(self.file("dexpi 1.3/example pids/I04 Measurement and Control/I04V01-VER.EX01.xml"), "i04-13")
        self.assertEqual([(c["tag"], c.get("output_unplaced")) for c in model["controllers"]], [("FIC-04", "FV-04")])
        self.assertIn("FV-04", {u["tag"] for u in model["unplaced"]})

    def test_comos_c01_controllers_and_valves(self):
        model, _ = read(self.file("dexpi 1.2/example pids/C01 the complete DEXPI PnID/C01V01-SAG.EX01.XML"), "c01-comos")
        ctrls = {c["tag"]: c for c in model["controllers"]}
        self.assertEqual(ctrls["PICSA-4712.02"]["output"], {"final_element": "PV-4712.02"})
        self.assertEqual(ctrls["TICSA-4750.03"]["output"], {"final_element": "TV-4750.03"})

    def test_proteus_333_sppid_c01_controllers_and_valves(self):
        model, _ = read(self.file("dexpi 1.2/example pids/C01 the complete DEXPI PnID/C01V01-HEX.EX01.xml"), "c01-333")
        ctrls = {c["tag"]: c for c in model["controllers"]}
        self.assertEqual(ctrls["PICSA-4712.02"]["output"], {"final_element": "PV-4712.02"})
        self.assertEqual(ctrls["TICSA-4750.03"]["output"], {"final_element": "TV-4750.03"})
        self.assertEqual(ctrls["HS-4750.01"]["output"], {"final_element": "HV-4750.01"})


# Three more export dialects, found in the 2026-10-29 held-out run (so not held out any more): one file each.
COMOS = """<?xml version="1.0" encoding="UTF-8"?>
<PlantModel>
 <PlantInformation SchemaVersion="4.0.1" OriginatingSystem="test"/>
 <Equipment ID="X1" ComponentClass="Tank" TagName="T100"><Nozzle ID="X2" ComponentClass="Nozzle" TagName="N1"/>
  <Nozzle ID="X3" ComponentClass="Nozzle" TagName="N2"/></Equipment>
 <!-- the loop holds the number; the bubble holds only its letters, as a TagName -->
 <InstrumentationLoopFunction ID="X10" TagName="04"><Association Type="is a collection including" ItemID="X11"/></InstrumentationLoopFunction>
 <ProcessInstrumentationFunction ID="X11" TagName="FIC" ComponentClass="MeasurementFunctionFlow">
  <GenericAttributes><GenericAttribute Name="TagName" Value="FIC"/></GenericAttributes>
  <Association Type="is a part of" ItemID="X10"/>
  <InformationFlow><Association Type="has logical start" ItemID="X21"/><Association Type="has logical end" ItemID="X11"/>
   <Connection FromID="X21" ToID="X11"/></InformationFlow>
  <InformationFlow><Association Type="has logical start" ItemID="X23"/><Association Type="has logical end" ItemID="X11"/>
   <Connection FromID="X23" ToID="X11"/></InformationFlow>
 </ProcessInstrumentationFunction>
 <!-- an interlock bubble wired only to the controller: no place of its own in the file -->
 <InstrumentationLoopFunction ID="X13" TagName="05"/>
 <ProcessInstrumentationFunction ID="X12" TagName="US"><Association Type="is a part of" ItemID="X13"/>
  <InformationFlow><Connection FromID="X12" ToID="X11"/></InformationFlow></ProcessInstrumentationFunction>
 <PipingNetworkSystem ID="X20" TagName="Q001"><PipingNetworkSegment ID="X30">
  <PipingComponent ID="X21" TagName="FT 04" ComponentClass="FlowLimiterWithPressureRecuperation"/>
  <!-- the actuator is equipment inside the valve; no ActuatingSystem -->
  <PipingComponent ID="X22" TagName="FV 04" ComponentClass="TightShutOffValve">
   <Equipment ID="X23" TagName="NC" ComponentClass="Diaphragm"/></PipingComponent>
  <Connection FromID="X2" ToID="X3"/></PipingNetworkSegment></PipingNetworkSystem>
</PlantModel>
"""

AUTOCAD = """<?xml version="1.0" encoding="UTF-8"?>
<PlantModel>
 <PlantInformation SchemaVersion="4.0.1" OriginatingSystem="test"/>
 <Equipment ID="A1" ComponentClass="Tank" TagName="T-123"><Nozzle ID="A2" ComponentClass="FlangedNozzle" TagName="N-1"/>
  <Nozzle ID="A3" ComponentClass="FlangedNozzle" TagName="N-2"/><Nozzle ID="A4" ComponentClass="FlangedNozzle" TagName="N-3"/></Equipment>
 <!-- a bubble tied to its tank by a Leader information flow -->
 <ProcessInstrumentationFunction ID="A10" ComponentClass="ProcessInstrumentationFunction" TagName="LI-123">
  <GenericAttributes>
   <GenericAttribute Name="ProcessInstrumentationFunctionCategoryAssignmentClass" Value="LI"/>
   <GenericAttribute Name="ProcessInstrumentationFunctionNumberAssignmentClass" Value="123"/></GenericAttributes>
  <InformationFlow ID="A11" ComponentClass="Leader"><Connection FromID="A10" ToID="A1"/></InformationFlow>
 </ProcessInstrumentationFunction>
 <!-- a bubble tied to a nozzle by a leader drawn as a pipe segment: not pipe -->
 <ProcessInstrumentationFunction ID="A20" ComponentClass="ProcessInstrumentationFunction" TagName="LI-124">
  <GenericAttributes>
   <GenericAttribute Name="ProcessInstrumentationFunctionCategoryAssignmentClass" Value="LI"/>
   <GenericAttribute Name="ProcessInstrumentationFunctionNumberAssignmentClass" Value="124"/></GenericAttributes>
 </ProcessInstrumentationFunction>
 <PipingNetworkSystem ID="A30"><PipingNetworkSegment ID="A31">
  <GenericAttributes><GenericAttribute Name="FunctionalObjectDescriptionAssignmentClass" Value="LEADER"/></GenericAttributes>
  <Connection FromID="A20" ToID="A2"/></PipingNetworkSegment></PipingNetworkSystem>
 <!-- a control valve written as a ProcessInstrumentationFunction (class ControlValve), a pipe end; a controller tied
      to it by a leader segment -->
 <ProcessInstrumentationFunction ID="A40" ComponentClass="ControlValve" TagName="FV-004">
  <GenericAttributes><GenericAttribute Name="ProcessInstrumentationFunctionCategoryAssignmentClass" Value="FV"/>
   <GenericAttribute Name="Tag" Value="FV-004"/></GenericAttributes></ProcessInstrumentationFunction>
 <ProcessInstrumentationFunction ID="A41" ComponentClass="ProcessInstrumentationFunction" TagName="FIC-004">
  <GenericAttributes>
   <GenericAttribute Name="ProcessInstrumentationFunctionCategoryAssignmentClass" Value="FIC"/>
   <GenericAttribute Name="ProcessInstrumentationFunctionNumberAssignmentClass" Value="004"/></GenericAttributes>
 </ProcessInstrumentationFunction>
 <PipingNetworkSystem ID="A50">
  <PipingNetworkSegment ID="A51"><Connection FromID="A3" ToID="A40"/></PipingNetworkSegment>
  <PipingNetworkSegment ID="A52"><Connection FromID="A40" ToID="A4"/></PipingNetworkSegment></PipingNetworkSystem>
 <PipingNetworkSystem ID="A60"><PipingNetworkSegment ID="A61">
  <GenericAttributes><GenericAttribute Name="FunctionalObjectDescriptionAssignmentClass" Value="LEADER"/></GenericAttributes>
  <Connection FromID="A40" ToID="A41"/></PipingNetworkSegment></PipingNetworkSystem>
</PlantModel>
"""

G = {k: f"{n:032X}" for n, k in enumerate(("PV", "PICSA", "ACT", "LOOP", "SL", "T", "N1", "N2", "N3", "P1", "P2", "P3",
                                            "S1", "S2", "S3"), start=1)}
PROTEUS_333 = """<?xml version="1.0" encoding="UTF-8"?>
<PlantModel>
 <PlantInformation SchemaVersion="3.3.3" OriginatingSystem="test"/>
 <Equipment ID="SP{T}" ComponentClass="VerticalDrums" TagName="T4750">
  <Nozzle ID="SP{N1}" ComponentClass="Nozzle" TagName="N1"/><Nozzle ID="SP{N2}" ComponentClass="Nozzle" TagName="N2"/>
  <Nozzle ID="SP{N3}" ComponentClass="Nozzle" TagName="N3"/></Equipment>
 <PipingNetworkSystem ID="SY{P1}"><PipingNetworkSegment ID="SG{S1}">
  <!-- the control valve is a ProcessInstrument in line -->
  <ProcessInstrument ID="SP{PV}" TagName="PV 4712.02" ComponentClass="Controlvalvesandregulators">
   <GenericAttributes><GenericAttribute Name="IsInline" Value="True"/></GenericAttributes>
   <Association Type="is a part of" TagName="{LOOP}"/></ProcessInstrument>
  <Connection FromID="SP{N1}" ToID="SP{N2}"/></PipingNetworkSegment></PipingNetworkSystem>
 <!-- the controller is an off-line ProcessInstrument on an instrument pipe run to the tank -->
 <PipingNetworkSystem ID="SY{P2}"><PipingNetworkSegment ID="SG{S2}" ComponentClass="LS802_DIN19227">
  <ProcessInstrument ID="SP{PICSA}" TagName="PICSA 4712.02" ComponentClass="Off-lineinstruments">
   <GenericAttributes><GenericAttribute Name="IsInline" Value="False"/></GenericAttributes>
   <Association Type="is a part of" TagName="{LOOP}"/></ProcessInstrument>
  <Connection FromID="SP{PICSA}" ToID="SP{N3}"/></PipingNetworkSegment></PipingNetworkSystem>
 <!-- the actuator: a loop member, wired to the controller by a SignalLine; associations name GUIDs by TagName -->
 <InstrumentComponent ID="SP{ACT}" TagName="P 4712.02" ComponentClass="Actuator">
  <Association Type="is a part of" TagName="{LOOP}"/></InstrumentComponent>
 <InstrumentLoop ID="SP{LOOP}" TagName="P-4712.02">
  <Association Type="is a collection including" TagName="{PV}"/>
  <Association Type="is a collection including" TagName="{PICSA}"/>
  <Association Type="is a collection including" TagName="{ACT}"/></InstrumentLoop>
 <SignalLine ID="SP{SL}" ComponentClass="SignalRun"><Connection FromID="SP{PICSA}" ToID="SP{ACT}"/></SignalLine>
</PlantModel>
""".format(**G)


class MoreExportDialects(unittest.TestCase):
    """Comos, AutoCAD and Proteus 3.3.3 (SPPID) ways of writing instruments, valves and their links."""

    def model(self, text, sid):
        with tempfile.TemporaryDirectory() as d:
            x = Path(d) / f"{sid}.xml"
            x.write_text(text, encoding="utf-8")
            model, rep = read(x, sid)
            cites_real_ids(self, model, x)
        exports_accept(self, model)
        return model, rep

    def test_comos_letters_on_the_bubble_number_on_the_loop_actuator_inside_the_valve(self):
        model, _ = self.model(COMOS, "comos-01")
        (c,) = model["controllers"]
        self.assertEqual((c["tag"], c["output"]), ("FIC-04", {"final_element": "FV-04"}))
        (fe,) = model["final_elements"]
        self.assertEqual((fe["tag"], fe["dexpi_id"], fe["unit"]), ("FV-04", "X22", "T100"))
        self.assertEqual(c.get("location"), "X21")   # located at the flow element FT 04, on the tank's line

    def test_a_bubble_wired_only_to_a_controller_takes_the_unit_of_the_bubble_it_signals(self):
        model, _ = self.model(COMOS, "comos-02")
        us = next(i for i in model["instruments"] if i["dexpi_id"] == "X12")
        self.assertEqual((us["tag"], us["unit"], us["unit_basis"]), ("US-05", "T100", "unit of the bubble it signals"))
        self.assertEqual(us["signal_to"], ["FIC-04"])

    def test_autocad_leader_flow_and_leader_segment_locate_the_bubble(self):
        model, rep = self.model(AUTOCAD, "autocad-01")
        insts = {i["tag"]: i for i in model["instruments"]}
        self.assertEqual(insts["LI-123"]["unit"], "T-123")
        self.assertEqual(insts["LI-124"]["unit"], "T-123")
        self.assertFalse([s for s in model["streams"] if "A30" in s["dexpi_id"] or "A60" in s["dexpi_id"]])
        self.assertIn("A31:FunctionalObjectDescriptionAssignmentClass", insts["LI-124"])

    def test_autocad_control_valve_written_as_an_instrument_function(self):
        model, _ = self.model(AUTOCAD, "autocad-02")
        fe = {f["dexpi_id"]: f for f in model["final_elements"]}
        self.assertEqual((fe["A40"]["tag"], fe["A40"]["unit"]), ("FV-004", "T-123"))
        self.assertIn("bubble A40", fe["A40"]["source"])
        ctrl = {c["tag"]: c for c in model["controllers"]}
        self.assertEqual(ctrl["FIC-004"]["output"], {"final_element": "FV-004"})

    def test_proteus_333_process_instruments_signal_line_and_loop(self):
        model, _ = self.model(PROTEUS_333, "proteus-01")
        ctrl = {c["tag"]: c for c in model["controllers"]}
        self.assertEqual(ctrl["PICSA-4712.02"]["output"], {"final_element": "PV-4712.02"})
        fe = {f["tag"]: f for f in model["final_elements"]}
        self.assertEqual((fe["PV-4712.02"]["dexpi_id"], fe["PV-4712.02"]["unit"]), ("SP" + G["PV"], "T4750"))
        self.assertEqual(ctrl["PICSA-4712.02"].get("location"), "SP" + G["N3"])
        self.assertEqual(len(model["streams"]), 1)   # the instrument run is not a process line


def cached(sheet_id):
    if not CONFIG.is_file():
        return None
    spec = next((s for s in json.loads(CONFIG.read_text(encoding="utf-8"))["geometry_keyed"] if s["id"] == sheet_id), None)
    path = SOURCE / spec["xml"] if spec else None
    return path if path and path.is_file() else None


class PublicExamples(unittest.TestCase):
    def setUp(self):
        self.sheets = {sid: cached(sid) for sid in ("dexpi-c01", "dexpi-c02", "dexpi-c03")}
        if not all(self.sheets.values()):
            self.skipTest("DEXPI examples not cached (python scripts/adapt_dexpi.py fetch); public-file checks skipped")

    def test_c01_named_values_survive(self):
        model, rep = read(self.sheets["dexpi-c01"], "dexpi-c01")
        by = {it.get("id") or it.get("tag"): it for _, it in items(model)}
        # Values read by hand from C01V04-VER.EX01.xml
        self.assertEqual(by["47124"]["PipingNetworkSegment-6:NominalDiameterRepresentationAssignmentClass"]["value"], "DN 50")
        self.assertEqual(by["47121"]["FluidCodeAssignmentClass"]["value"], "MNb")
        dp = by["H1007"]["Chamber-1:UpperLimitDesignPressure"]
        self.assertEqual((dp["value"], dp["uom"]), ("60", "Bar"))
        self.assertEqual(by["T4750"]["Chamber-8:UpperLimitDesignPressure"]["value"], "0.05")
        self.assertEqual(by["SV 104.01"]["SetPressureHigh"]["value"], "6")
        self.assertEqual(by["P4711"]["DesignShaftPower"]["uom"], "Kilowatt")
        self.assertEqual(by["PV-4712.02"]["ControlledActuator-1:FailActionSpecialization"]["value"], "FailClose")
        self.assertEqual(by["47127"]["InsulationThickness"]["value"], "80")
        a = rep["attributes"]
        self.assertEqual(a["in_file"], a["kept_as_sourced_records"] + a["kept_in_meta_only"]
                         + a["kept_on_unplaced_items"] + a["dropped"])
        self.assertEqual(set(a["dropped_by_reason"]), {"no value in the file", "person name: left out on purpose"})

    def test_c01_combined_bubbles_measure_their_own_sensors(self):
        model, _ = read(self.sheets["dexpi-c01"], "dexpi-c01")
        ctrls = {c["tag"]: c for c in model["controllers"]}
        insts = {i["tag"]: i for i in model["instruments"]}
        for ctag, stag, valve in (("PICSA-4712.02", "PT-4712.02", "PV-4712.02"), ("TICSA-4750.03", "TT-4750.03", "TV-4750.03")):
            self.assertEqual(ctrls[ctag]["measurement"], stag)
            self.assertEqual(ctrls[ctag]["output"], {"final_element": valve})
            self.assertEqual(insts[stag]["part_of"], ctag)
            self.assertEqual(insts[stag]["dexpi_class"], "ProcessSignalGeneratingFunction")
        self.assertEqual(insts["TT-4750.03"]["unit"], "T4750")

    def test_all_three_cite_ids_and_export(self):
        for sid, path in self.sheets.items():
            with self.subTest(sheet=sid):
                model, rep = read(path, sid)
                cites_real_ids(self, model, path)
                exports_accept(self, model)
                self.assertFalse([k for k in rep["elements_not_read"] if k.endswith("no rule")], rep["elements_not_read"])

    def test_c01_pipe_layer_has_the_files_five_tees(self):
        model, _ = read(self.sheets["dexpi-c01"], "dexpi-c01")
        ll = model["line_layers"]
        self.assertEqual(sorted(j["dexpi_id"] for j in ll["junctions"]), [f"PipeTee-{i}" for i in range(1, 6)])
        nodes = {u["id"] for u in model["units"]} | {"BL"} | {j["id"] for j in ll["junctions"]} | {
            it["tag"] for sec in ("final_elements", "manual_valves", "relief_devices", "unplaced") for it in model.get(sec, [])}
        self.assertTrue(all(x["from"] in nodes and x["to"] in nodes for x in ll["segments"]))
        self.assertFalse({i["tag"] for i in model["instruments"]} & {e for x in ll["segments"] for e in (x["from"], x["to"])})

    def test_agreement_with_adapt_dexpi_keys(self):
        for sid, path in self.sheets.items():
            if not (KEYS / f"{sid}.graphml").is_file():
                self.skipTest("adapt_dexpi keys not built (python scripts/adapt_dexpi.py build)")
            with self.subTest(sheet=sid):
                _, rep = read(path, sid, compare=KEYS)
                c = rep["comparison"]
                self.assertNotIn("MISSING", c["items"])
                self.assertEqual(c["tags_drawn_label_kept"], c["tags_compared"])
                self.assertEqual(c["unit_links"]["model_only"], [])
                self.assertEqual(set(c["unit_links"]["key_only"]), set(c["unit_links"]["key_only_explained"]))
                ka = c["key_item_attributes"]
                self.assertEqual((ka["values_kept"], ka["distinct_per_item_kept"]), (ka["values"], ka["distinct_per_item"]))


class QualifiedDesignationPrivacy(unittest.TestCase):
    def read_root(self, root):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.xml"
            ET.ElementTree(root).write(source, encoding="utf-8")
            reader = R.Reader(source, "qualified-privacy")
            # Assertions below identify the exact reparsed source occurrence, not the pre-serialization ET object.
            reader._test_source_elements = dict(zip(root.iter(), reader.root.iter()))
            model = reader.read()
            return reader, model, reader.report(model)

    def root_and_owner(self):
        root = ET.Element("PlantModel")
        owner = ET.SubElement(root, "Equipment", ID="E1", ComponentClass="Tank")
        return root, owner

    def test_any_expanded_name_blocks_records_and_derived_identity_before_reads(self):
        for role in ("Approver", "Checker", "Creator", "Designer", "Drafter", "Editor", "Reviewer", "Owner"):
            for namespace in ("urn:privacy:first", "urn:privacy:second"):
                for reverse in (False, True):
                    with self.subTest(role=role, namespace=namespace, reverse=reverse):
                        root, owner = self.root_and_owner()
                        group = ET.SubElement(owner, "GenericAttributes", Set="DexpiAttributes")
                        pairs = [("Name", "TagNameAssignmentClass"),
                                 (f"{{{namespace}}}nAmE", role.swapcase() + "nAmEAssignmentClass")]
                        marker = "SYNTHETIC_PRIVATE_DERIVATION_6327"
                        ga = ET.SubElement(group, "GenericAttribute", dict(reversed(pairs) if reverse else pairs))
                        ga.set("Value", marker)
                        ga.set(f"{{{namespace}}}Units", marker)
                        ga.set("Language", marker)
                        ET.SubElement(group, "GenericAttribute", Name="TagNameAssignmentClass", Value="SAFE-17")
                        reader, model, report = self.read_root(root)
                        self.assertEqual(reader.ga(reader._test_source_elements[owner], "TagNameAssignmentClass"), "SAFE-17")
                        self.assertEqual(model["units"][0]["id"], "SAFE-17")
                        self.assertEqual(reader.ga_state[reader._test_source_elements[ga]],
                                         ("dropped", "person name: left out on purpose"))
                        self.assertEqual(report["attributes"]["in_file"], 2)
                        self.assertNotIn(marker, json.dumps([model, report]) + R.report_text(report))

    def test_empty_and_missing_native_values_keep_precedence_and_no_qualified_payload(self):
        root, owner = self.root_and_owner()
        group = ET.SubElement(owner, "GenericAttributes")
        protected = []
        marker = "SYNTHETIC_PRIVATE_QUALIFIED_PAYLOAD_914"
        for value in (None, "", "0", "false"):
            attrs = {"Name": "Description", "{urn:test}Name": "CreatorNameAssignmentClass",
                     "{urn:test}Value": marker, "{urn:test}Units": marker}
            if value is not None:
                attrs["Value"] = value
            protected.append(ET.SubElement(group, "GenericAttribute", attrs))
        ET.SubElement(group, "GenericAttribute", Name="Description", Value="0", Units="Bar")
        reader, model, report = self.read_root(root)
        self.assertEqual([reader.ga_state[reader._test_source_elements[g]][1] for g in protected],
                         ["no value in the file"] * 2 + ["person name: left out on purpose"] * 2)
        self.assertEqual(report["attributes"]["in_file"], 5)
        self.assertEqual(model["units"][0]["Description"]["value"], "0")
        self.assertNotIn(marker, json.dumps([model, report]) + R.report_text(report))

    def test_metadata_unsupported_and_node_routes_keep_target_drop_and_safe_neighbor(self):
        root, owner = self.root_and_owner()
        nodes = [owner, ET.SubElement(root, "MetaData"), ET.SubElement(root, "PlantStructureItem", ID="PS1"),
                 ET.SubElement(root, "UnsupportedOwner", ID="U1")]
        cp = ET.SubElement(owner, "ConnectionPoints")
        nodes.append(ET.SubElement(cp, "Node", ID="N1"))
        marker = "SYNTHETIC_PRIVATE_ALL_ROUTES_981"
        protected = []
        for node in nodes:
            group = ET.SubElement(node, "GenericAttributes")
            protected.append(ET.SubElement(group, "GenericAttribute",
                {"Name": "Description", "{urn:one}Name": "Benign", "{urn:two}Name": "ReviewerName",
                 "Value": marker, "Units": marker}))
            ET.SubElement(group, "GenericAttribute", Name="EngineeringNote", Value="benign note")
        reader, model, report = self.read_root(root)
        self.assertTrue(all(reader.ga_state[reader._test_source_elements[g]] ==
                            ("dropped", "person name: left out on purpose") for g in protected))
        self.assertEqual(report["attributes"]["in_file"], 10)
        self.assertEqual(model["meta"]["drawing"]["EngineeringNote"], "benign note")
        self.assertNotIn(marker, json.dumps([model, report]) + R.report_text(report))

    def test_ga_lang_cannot_select_protected_english_before_safe_alternative(self):
        root, owner = self.root_and_owner()
        group = ET.SubElement(owner, "GenericAttributes")
        ET.SubElement(group, "GenericAttribute", {"Name": "Description", "Language": "en", "Value": "PRIVATE_9147",
                                                "{urn:test}Name": "OwnerName"})
        ET.SubElement(group, "GenericAttribute", Name="Description", Language="en", Value="safe engineering")
        reader, model, report = self.read_root(root)
        self.assertEqual(reader.ga_lang(reader._test_source_elements[owner], "Description"), "safe engineering")
        self.assertNotIn("PRIVATE_9147", json.dumps([model, report]))

    def test_nonperson_qualified_designations_do_not_gain_schema_meaning(self):
        root, owner = self.root_and_owner()
        group = ET.SubElement(owner, "GenericAttributes")
        qualified_only = ET.SubElement(group, "GenericAttribute", {"{urn:test}Name": "TagNameAssignmentClass",
                                                                  "Value": "ordinary opaque value"})
        ET.SubElement(group, "GenericAttribute", {"Name": "Description", "{urn:test}Name": "urn:ordinary:review",
                                                  "Value": "safe engineering", "Units": "0"})
        reader, model, _ = self.read_root(root)
        self.assertFalse(R.person_designated(qualified_only))
        self.assertEqual(model["units"][0]["id"], "E1")
        self.assertEqual(model["units"][0]["unnamed"]["value"], "ordinary opaque value")
        self.assertEqual(model["units"][0]["Description"]["value"], "safe engineering")


if __name__ == "__main__":
    unittest.main()
