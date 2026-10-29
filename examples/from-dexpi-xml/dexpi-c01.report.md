# DEXPI XML read: C01V04-VER.EX01.xml -> dexpi-c01

File: P&ID Toolbox 1.1.0, DEXPI 1.3.1, schema 4.1.1; SHA-256 a2b172f04e0dcf9a668e158c6dee3b5fd0dd4e9027b572dc39e54470562b809c

Items: 5 units, 12 streams, 3 instruments, 3 final_elements, 3 controllers, 7 manual_valves, 1 relief_devices

Attributes (GenericAttribute values): 783 in the file; 727 kept as sourced records on model items, 41 kept in meta only, 0 kept on unplaced items, 15 dropped. (24 in the shape catalogue, not plant data.)
Sourced records (attributes, labels, part classes) by section: units 239, streams 420, instruments 12, final_elements 73, controllers 26, manual_valves 91, relief_devices 12. graph_export.py makes each item's records claims on its node, and each stream's line, segment and fitting records claims on its `connects` edge; the graph file's counts give the total.
- dropped 10: no value in the file
- dropped 5: person name: left out on purpose

Unit types:
- H1007: PlateHeatExchanger -> heat_exchanger (approximate: heat transfer equipment)
- H1008: TubularHeatExchanger -> heat_exchanger (approximate: heat transfer equipment)
- P4711: CentrifugalPump -> pump (exact)
- P4712: ReciprocatingPump -> pump (exact)
- T4750: Tank -> tank (exact)
Folded into streams: 1 FlowInPipeOffPageConnector, 1 PipeReducer, 5 PipeTee, 2 BlindFlange, 1 FlowOutPipeOffPageConnector

Inferred units (through the piping):
- PI-4712.01: first unit upstream through the piping from BlindFlange-1 (5 step(s), via Nozzle-9)
- PT-4712.02: first unit upstream through the piping from BlindFlange-2 (8 step(s), via Nozzle-9)
- TT-4750.03: on Nozzle-17 of the unit
- HV-4750.01: first unit upstream through the piping from GlobeValve-2 (1 step(s), via Nozzle-4)
- PV-4712.02: first unit upstream through the piping from GlobeValve-1 (1 step(s), via Nozzle-11)
- TV-4750.03: first unit upstream through the piping from GlobeValve-3 (1 step(s), via Nozzle-16)
- SV 104.01: first unit upstream through the piping from SpringLoadedGlobeSafetyValve-1 (3 step(s), via Nozzle-9)

Elements with an ID not read:
- 8 x <PipeFlowArrow>: flow arrow (direction comes from segment From/To)
- 1 x <PipeSlopeSymbol>: slope mark
- 1 x <InsulationSymbol>: insulation mark (insulation attributes are on the line)
Drawing title block labels not read: 1

Against the adapt_dexpi.py answer key for this sheet:
- key nodes 30: 10 folded into streams, 20 own item
- tags: 20 drawn key tags; model id equals the key tag on 12; the drawn label is kept on 20
- unit-to-unit links: key 9, model 7, both 7; key only ['BL - H1008', 'BL - T4750']; model only []
  - key only BL - H1008: both fed from P4712: branches of one tee, which the key links pairwise (undirected); the model keeps the drawn direction
  - key only BL - T4750: both fed from P4712: branches of one tee, which the key links pairwise (undirected); the model keeps the drawn direction
- attribute values on the key's items and their parts: 432 (249 distinct names per item, the count dexpi_to_twin.py reports as not carried); kept here: 432 values, 249 distinct
  - not compared (end not in the key): 47130: BL - H1007 (line end with no connector (open-start:PipingNetworkSegment-20): leaves the sheet)
  - not compared (end not in the key): 47131: H1007 - BL (line end with no connector (open-end:PipingNetworkSegment-21): leaves the sheet)
  - not compared (end not in the key): 47140: BL - H1008 (line end with no connector (open-start:PipingNetworkSegment-22): leaves the sheet)
  - not compared (end not in the key): 47141: H1008 - BL (line end with no connector (open-end:PipingNetworkSegment-23): leaves the sheet)
  - ButterflyValve-1: key tag '66KL21-80', model manual_valves ButterflyValve-1 (drawn label kept)
  - SwingCheckValve-1: key tag '75SA21-80', model manual_valves SwingCheckValve-1 (drawn label kept)
  - PipeReducer-1: key tag '80/50', model streams (folded part) 47124 (drawn label kept)
  - BallValve-1: key tag '73KH12-50', model manual_valves BallValve-1 (drawn label kept)
  - BallValve-2: key tag '73KH12-25', model manual_valves BallValve-2 (drawn label kept)
  - BallValve-3: key tag '73KH12-25', model manual_valves BallValve-3 (drawn label kept)
  - BallValve-4: key tag '73KH12-50', model manual_valves BallValve-4 (drawn label kept)
  - BallValve-5: key tag '73KH12-25', model manual_valves BallValve-5 (drawn label kept)

Lossy steps:
- Geometry, presentation and the shape catalogue are not read: the model has no positions (generate.py places units automatically, display only).
- Equipment classes map onto the generator's symbol types; approximate and unmapped ones say so in type_basis.
- Lines become unit-to-unit streams; tees, reducers, flanges, blinds and off-page connectors are folded into the stream they sit on (their attributes kept, keyed by XML ID), not separate nodes.
- A line that ends only at a closed end (blind, plug, vent or drain valve) gets BL as its far end, said in to_end.
- A segment Connection that names an ID the file does not contain (a broken reference) gets BL at that end, said in from_end/to_end and listed under broken_references.
- Units of instruments, final elements and relief devices are inferred through the piping (unit_basis).
- Signal lines between bubbles are kept as signal_from/signal_to lists, not graph edges.
- Items that need a unit but reach none through the piping go to 'unplaced': kept in the model, not exported by generate.py or graph_export.py.
- Person names in the drawing metadata and the title block text are left out on purpose.
- Values are kept as written (text); units of measure as DEXPI names (Bar, DegreeCelsius), not converted.
