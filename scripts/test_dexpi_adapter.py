"""Controls for the DEXPI adapter (scripts/adapt_dexpi.py). Synthetic fixtures; stdlib only.

If the real DEXPI sheets have been built locally (adapt_dexpi.py fetch + build), the oracle check also runs on
them: the key converted to a prediction must score zero corrections with the unchanged scorer. It adapts
nothing and says nothing about extraction accuracy; it only shows the key can be matched.
"""
import io
import json
import math
import tempfile
import unittest
import zipfile
from xml.sax.saxutils import escape
from pathlib import Path

import adapt_dexpi as A
import score_pid2graph as sc

XML = """<PlantModel>
  <Equipment ID="Tank-1" ComponentClass="Tank" ComponentName="TANK_SHAPE">
    <Position><Location X="50" Y="50" Z="0"/><Axis X="0" Y="0" Z="1"/><Reference X="1" Y="0" Z="0"/></Position>
    <Label ComponentClass="EquipmentTagNameLabel"><Text String="T100"/></Label>
    <Label ComponentClass="EquipmentBarLabel"><Text String="Ident"/><Text String="T100"/></Label>
    <Nozzle ID="Nozzle-1" ComponentClass="Nozzle"/>
    <Equipment ID="Chamber-1" ComponentClass="Chamber"/>
  </Equipment>
  <Equipment ID="Section-1" ComponentClass="ColumnSection" ComponentName="TANK_SHAPE">
    <Position><Location X="50" Y="50" Z="0"/><Axis X="0" Y="0" Z="1"/><Reference X="1" Y="0" Z="0"/></Position>
  </Equipment>
  <Equipment ID="Pump-1" ComponentClass="CentrifugalPump" ComponentName="PUMP_SHAPE">
    <Position><Location X="150" Y="20" Z="0"/><Axis X="0" Y="0" Z="1"/><Reference X="1" Y="0" Z="0"/></Position>
    <Nozzle ID="Nozzle-2" ComponentClass="Nozzle"/>
  </Equipment>
  <PipingNetworkSystem ID="PNS-1" ComponentClass="PipingNetworkSystem">
    <PipingNetworkSegment ID="Seg-1" ComponentClass="PipingNetworkSegment">
      <PipingComponent ID="Valve-1" ComponentClass="GlobeValve" ComponentName="VALVE_SHAPE">
        <Position><Location X="100" Y="20" Z="0"/><Axis X="0" Y="0" Z="1"/><Reference X="0" Y="1" Z="0"/></Position>
      </PipingComponent>
      <PipingComponent ID="Tee-1" ComponentClass="PipeTee" ComponentName="VALVE_SHAPE">
        <Position><Location X="120" Y="20" Z="0"/><Axis X="0" Y="0" Z="1"/><Reference X="1" Y="0" Z="0"/></Position>
      </PipingComponent>
      <PipeFlowArrow ID="Arrow-1"/>
      <Connection FromID="Nozzle-1" FromNode="1" ToID="Nozzle-2" ToNode="1"/>
    </PipingNetworkSegment>
    <PipingNetworkSegment ID="Seg-2" ComponentClass="PipingNetworkSegment">
      <PipingComponent ID="Blind-1" ComponentClass="BlindFlange" ComponentName="LINE_SHAPE">
        <Position><Location X="120" Y="40" Z="0"/><Axis X="0" Y="0" Z="1"/><Reference X="1" Y="0" Z="0"/></Position>
        <Label ComponentClass="ValveLabel"><Text String="80/25"/><Text String="second line"/></Label>
      </PipingComponent>
      <Connection FromID="Tee-1" FromNode="3" ToID="Blind-1" ToNode="1"/>
    </PipingNetworkSegment>
  </PipingNetworkSystem>
  <ActuatingSystem ID="AS-1" ComponentClass="ActuatingSystem">
    <Label ComponentClass="ActuatingSystemNumberLabel"><Text String="FV"/><Text String="101"/></Label>
    <ActuatingSystemComponent ID="Act-1" ComponentClass="ControlledActuator" ComponentName="VALVE_SHAPE">
      <Position><Location X="100" Y="25" Z="0"/><Axis X="0" Y="0" Z="1"/><Reference X="1" Y="0" Z="0"/></Position>
    </ActuatingSystemComponent>
    <ActuatingSystemComponent ID="Ref-1" ComponentClass="OperatedValveReference">
      <Association Type="refers to" ItemID="Valve-1"/>
    </ActuatingSystemComponent>
  </ActuatingSystem>
  <ProcessInstrumentationFunction ID="PIF-1" ComponentClass="ProcessInstrumentationFunction" ComponentName="BUBBLE">
    <Position><Location X="100" Y="60" Z="0"/><Axis X="0" Y="0" Z="1"/><Reference X="1" Y="0" Z="0"/></Position>
    <Label ComponentClass="ProcessInstrumentationFunctionLabel"><Text String="FIC"/><Text String="101"/><Text String="AREA-1"/></Label>
    <InformationFlow ID="SCF-1" ComponentClass="SignalConveyingFunction">
      <Connection FromID="PIF-1" ToID="Act-1" FromNode="1" ToNode="1"/>
    </InformationFlow>
    <InformationFlow ID="MLF-1" ComponentClass="MeasuringLineFunction">
      <Connection FromID="Nozzle-1" ToID="PIF-1" FromNode="2" ToNode="2"/>
    </InformationFlow>
  </ProcessInstrumentationFunction>
  <PipeOffPageConnector ID="OPC-1" ComponentClass="FlowOutPipeOffPageConnector" ComponentName="VALVE_SHAPE">
    <Position><Location X="190" Y="20" Z="0"/><Axis X="0" Y="0" Z="1"/><Reference X="1" Y="0" Z="0"/></Position>
  </PipeOffPageConnector>
  <Drawing Name="test"><Extent><Min X="0" Y="0"/><Max X="200" Y="100"/></Extent></Drawing>
  <ShapeCatalogue Name="Shapes">
    <Equipment ComponentName="TANK_SHAPE"><PolyLine NumPoints="5"><Coordinate X="-10" Y="-20"/>
      <Coordinate X="10" Y="-20"/><Coordinate X="10" Y="20"/><Coordinate X="-10" Y="20"/><Coordinate X="-10" Y="-20"/></PolyLine></Equipment>
    <Equipment ComponentName="PUMP_SHAPE"><Circle Radius="5"><Position><Location X="0" Y="0" Z="0"/></Position></Circle></Equipment>
    <PipingComponent ComponentName="VALVE_SHAPE"><PolyLine NumPoints="2"><Coordinate X="-4" Y="-2"/><Coordinate X="4" Y="2"/></PolyLine></PipingComponent>
    <PipingComponent ComponentName="LINE_SHAPE"><PolyLine NumPoints="2"><Coordinate X="0" Y="-3"/><Coordinate X="0" Y="3"/></PolyLine></PipingComponent>
    <ProcessInstrumentationFunction ComponentName="BUBBLE"><Circle Radius="4"><Position><Location X="0" Y="0" Z="0"/></Position></Circle></ProcessInstrumentationFunction>
  </ShapeCatalogue>
</PlantModel>"""


def model():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "t.xml"
        p.write_text(XML, encoding="utf-8")
        return A.convert_xml(p)


class ClassMap(unittest.TestCase):
    def test_classes(self):
        self.assertEqual(A.dexpi_class("Equipment", "CentrifugalPump"), "pump")
        self.assertEqual(A.dexpi_class("Equipment", "ReciprocatingCompressor"), "pump")
        self.assertEqual(A.dexpi_class("Equipment", "PlateHeatExchanger"), "tank")
        self.assertEqual(A.dexpi_class("Equipment", "ProcessColumn"), "tank")
        self.assertIsNone(A.dexpi_class("Equipment", "TaggedColumnSection"))
        self.assertIsNone(A.dexpi_class("Equipment", "Tank", top_level_equipment=False))
        self.assertEqual(A.dexpi_class("PipingComponent", "SpringLoadedGlobeSafetyValve"), "valve")
        self.assertEqual(A.dexpi_class("PipingComponent", "PipeReducer"), "general")
        self.assertEqual(A.dexpi_class("PipingComponent", "PipeTee"), "connector")
        self.assertEqual(A.dexpi_class("PipeOffPageConnector", "FlowInPipeOffPageConnector"), "inlet/outlet")
        self.assertEqual(A.dexpi_class("ProcessInstrumentationFunction", None), "instrumentation")
        self.assertIsNone(A.dexpi_class("Nozzle", "Nozzle"))


class Geometry(unittest.TestCase):
    def item(self, x, y, rx, ry, z=1, sx=1, sy=1):
        import xml.etree.ElementTree as ET
        return ET.fromstring(f'<I><Position><Location X="{x}" Y="{y}" Z="0"/><Axis X="0" Y="0" Z="{z}"/>'
                             f'<Reference X="{rx}" Y="{ry}" Z="0"/></Position><Scale X="{sx}" Y="{sy}"/></I>')

    def test_rotation_scale_mirror(self):
        rot = A.place([(2, 1)], self.item(10, 10, 0, 1))[0]          # 90 degrees: (2,1) -> (-1,2)
        self.assertAlmostEqual(rot[0], 9); self.assertAlmostEqual(rot[1], 12)
        sc_ = A.place([(2, 1)], self.item(0, 0, 1, 0, sx=3, sy=2))[0]
        self.assertAlmostEqual(sc_[0], 6); self.assertAlmostEqual(sc_[1], 2)
        mir = A.place([(2, 1)], self.item(0, 0, 1, 0, z=-1))[0]       # Axis Z = -1 mirrors local y
        self.assertAlmostEqual(mir[0], 2); self.assertAlmostEqual(mir[1], -1)

    def test_boxes_and_pixels(self):
        m = model()
        self.assertEqual(m["nodes"]["Tank-1"]["box"], (40.0, 30.0, 60.0, 70.0))
        vx = m["nodes"]["Valve-1"]["box"]   # rotated 90 degrees: x span 4, y span 8
        self.assertAlmostEqual(vx[2] - vx[0], 4); self.assertAlmostEqual(vx[3] - vx[1], 8)
        px = A.to_pixels((40, 30, 60, 70), m["extent"], 10)    # y flips: top of page is max Y
        self.assertEqual(px, (400, 300, 600, 700))
        self.assertEqual(A.to_pixels((0, 90, 10, 100), m["extent"], 1), (0, 0, 10, 10))

    def test_min_size(self):
        self.assertEqual(A.min_size((10, 0, 10, 30), 4), (8, 0, 12, 30))
        self.assertEqual(A.min_size((0, 0, 20, 20), 4), (0, 0, 20, 20))


class Topology(unittest.TestCase):
    def test_nodes(self):
        m = model()
        self.assertEqual(sorted(m["nodes"]), ["Blind-1", "OPC-1", "PIF-1", "Pump-1", "Tank-1", "Tee-1", "Valve-1"])
        self.assertEqual(m["nodes"]["Tee-1"]["class"], "connector")
        self.assertNotIn("Section-1", m["nodes"])   # internal drawn inside other equipment

    def test_edges(self):
        e = set(model()["edges"])
        # segment chain: Tank (via nozzle) - Valve - Tee - Pump (via nozzle); arrow skipped
        self.assertIn(("Tank-1", "Valve-1"), e)
        self.assertIn(("Tee-1", "Valve-1"), e)
        self.assertIn(("Pump-1", "Tee-1"), e)
        self.assertIn(("Blind-1", "Tee-1"), e)
        # signal line to the actuator lands on the valve it operates; measuring line on the tank nozzle
        self.assertIn(("PIF-1", "Valve-1"), e)
        self.assertIn(("PIF-1", "Tank-1"), e)
        self.assertEqual(model()["unresolved"], [])

    def test_collapsed_links_through_tee(self):
        m = model()
        with tempfile.TemporaryDirectory() as d:
            g = Path(d) / "k.graphml"
            A.write_graphml(g, m, 10.0, 16.0)
            nodes, adj = sc.load_key(g, 2000, 1000)
            links = {tuple(sorted(l)) for l in sc.asset_links(nodes, adj)}
        self.assertIn(("Pump-1", "Valve-1"), links)     # joined through the tee
        self.assertIn(("Blind-1", "Pump-1"), links)
        self.assertNotIn(("Pump-1", "Tank-1"), links)   # the valve is in between


class Tags(unittest.TestCase):
    def test_truth(self):
        n = model()["nodes"]
        self.assertEqual(n["Tank-1"]["tag"], "T100")          # tag-name label, not the data bar
        self.assertEqual(n["Blind-1"]["tag"], "80/25")        # first line only
        self.assertEqual(n["PIF-1"]["tag"], "FIC 101")        # first two lines; area line left out
        self.assertEqual(n["Valve-1"]["tag"], "FV 101")       # from the actuating system number label
        self.assertIsNone(n["Pump-1"]["tag"])                 # no label: no truth


class TagLists(unittest.TestCase):
    def xlsx(self, rows):
        buf = io.BytesIO()
        strings = sorted({c for r in rows for c in r})
        idx = {s: i for i, s in enumerate(strings)}
        ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
        sheet = "".join(f'<row r="{i + 1}">' + "".join(
            f'<c r="{chr(65 + j)}{i + 1}" t="s"><v>{idx[c]}</v></c>' for j, c in enumerate(r) if c) + "</row>"
            for i, r in enumerate(rows))
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("xl/sharedStrings.xml", f"<sst {ns}>" + "".join(f"<si><t>{escape(s)}</t></si>" for s in strings) + "</sst>")
            z.writestr("xl/workbook.xml", f'<workbook {ns} xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                       '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>')
            z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                       '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
            z.writestr("xl/worksheets/sheet1.xml", f"<worksheet {ns}><sheetData>{sheet}</sheetData></worksheet>")
        return buf.getvalue()

    def test_list_filtering(self):
        rows = [["Technical Item", "Equipment Type", "P&ID Name"],
                ["PA100", "Pump general", "DWG-1"], ["BA100", "Vessel", "DWG-1"],
                ["BA200", "Vessel", "DWG-2"], ["No Itemtag!", "Vessel", "DWG-1"], ["KA009", "Column", "DWG-1"]]
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "eq.xlsm"
            p.write_bytes(self.xlsx(rows))
            self.assertEqual(A.xlsx_rows(p)[1], ["PA100", "Pump general", "DWG-1"])
            cfg = {"tag_list_keyed": {"lists": {"equipment": {"path": "eq.xlsm"}}}}
            old = A.SOURCE
            A.SOURCE = Path(d)
            try:
                class Page:
                    def get_text(self, _):
                        return [(0, 0, 0, 0, w) for w in ("PA100", "BA-100", "BA200", "note")]
                key = A.build_taglist(cfg, {"id": "s", "drawing_name": "DWG-1"}, Page())
            finally:
                A.SOURCE = old
        self.assertEqual([(i["identifier"], i["class"]) for i in key["items"]], [("PA100", "pump"), ("BA100", "tank")])
        self.assertEqual([e["identifier"] for e in key["excluded_not_printed"]], ["KA009"])


class OracleOnBuiltSheets(unittest.TestCase):
    def test_oracle_scores_zero_corrections(self):
        built = [s["id"] for s in A.config()["geometry_keyed"] if (A.SHEETS / f"{s['id']}.graphml").exists()]
        if not built:
            self.skipTest("DEXPI sheets not built; run python scripts/adapt_dexpi.py fetch then build")
        for sid in built:
            g, png = A.SHEETS / f"{sid}.graphml", A.SHEETS / f"{sid}.png"
            w, h = sc.png_size(png)
            nodes, adj = sc.load_key(g, w, h)
            pred = {"symbols": [{"id": k, "class": v["class"], "box": v["box"]} for k, v in nodes.items()
                                if v["class"] in sc.SCORED],
                    "connections": [{"from": a, "to": b} for a, b in (tuple(l) for l in sc.asset_links(nodes, adj))]}
            r = sc.score(g, pred, png)
            self.assertEqual(r["review_load"]["corrections"], 0, sid)
            self.assertEqual(r["strict"]["classified"]["f1"], 1.0, sid)
            empty = sc.score(g, {"symbols": [], "connections": []}, png)
            self.assertAlmostEqual(empty["review_load"]["per_100"], 100.0, places=1)


if __name__ == "__main__":
    unittest.main()
