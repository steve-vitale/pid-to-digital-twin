# TE instrumentation and boundary coverage

This is an offline prototype inventory, not operating acceptance or a live gateway verification. Source facts below come from `data/te_process_model.json`, its embedded `teprob.f` verification evidence, `out/te_source_check.md` (tag names and units) and `out/te_topology_check.md` (unit ownership, stream endpoints and directions, verified 2026-10-13 against the simulator source; 51 confirmed, 4 corrected, 1 unresolvable). Tap positions and the order of instruments along a line are not in the source and remain unverified. Proposed overview selection is engineering judgment pending operator review.

## Channel accounting and compatibility

The seed has 25 instrument records (22 scalar measurements and three analyzer groups) and 12 final elements: **37 model records**. The recorded dataset has XMEAS 1–41 and XMV 1–11: **52 unique recorded channels**. XMV12/SC-212 agitation is not recorded; its value must remain explicitly unconnected, with no inferred speed or animation.

The expanded display/mapping inventory contains **53 entries: 52 mapped, 1 unconnected**. Each of the 52 zero-based replay columns is mapped exactly once. The three pre-existing scalar analyzer paths retain their original first-component meanings. Sixteen additional component paths complete the recorded analyzer coverage:

- AI-123 is feed component A (XMEAS23); AI-123-B through AI-123-F are XMEAS24–28. Stream S6; owner R-101.
- AI-129 is purge component A (XMEAS29); AI-129-B through AI-129-H are XMEAS30–36. Stream S9; owner V-101 (corrected from K-101: the purge leaves the separator vapour).
- AI-137 is product component D (XMEAS37); AI-137-E through AI-137-H are XMEAS38–41. Stream S11; owner C-101.

Suffixes are project-assigned channel identifiers, not newly discovered physical instrument tags. `scripts/ignition/te_channels.py` expands source metadata without modifying the seed model. New channels use the existing `[provider]TE_Plant/{unit}/{tag}/PV`, `/State` and `/ReviewStatus` convention, with matching read-only `TE/{tag}` replay OPC nodes. `te_ranges[tag].source_item` carries unit, stream, source index, component, parent analyzer, provenance, sampling and verification metadata for display generation.

Analyzer sample periods and source dead time must remain visible context: feed and purge 0.1 h each (6 minutes); product 0.25 h each (15 minutes). A 3-minute replay row does not make an analyzer an instantaneous 3-minute measurement. All analyzers are mol%. The new channels use existing read-only, historical measurement UDT configuration and quality propagation; no new alarm thresholds or control functions are introduced. Existing scalar normal-band K calibration is preserved and applied to the added channels. The generated statistical report includes all 52 channels and discloses that the added components were not used to retune legacy bands. Normal bands are display aids, never site limits.

Parent analyzer operations-review hidden/rejected decisions propagate to derived components. Missing, bad or nonfinite readings must not be rendered as normal values. Configuration tests do not prove live OPC, historian, Jython or Perspective behavior.

## Per-unit detail inventory

Every entry listed is eligible for the respective unit detail, subject to existing operations-review exclusions. All are mapped unless explicitly stated otherwise.

- U-100 Feed System: FI-101, FI-102, FI-103, FV-201, FV-202, FV-203. **6/6 mapped**.
- R-101 Reactor: FI-106, PI-107, LI-108, TI-109, TI-121, AI-123 and AI-123-B/C/D/E/F, TV-210; SC-212 explicitly unconnected. **12/13 mapped**.
- E-101 Product Condenser: TI-122, TV-211. **2/2 mapped**.
- V-101 Separator: TI-111, LI-112, PI-113, FI-114, LV-207, FI-110, AI-129 and AI-129-B/C/D/E/F/G/H, FV-206. **15/15 mapped**.
- K-101 Compressor: FI-105, JI-120, HV-205. **3/3 mapped**.
- C-101 Stripper: FI-104, LI-115, PI-116, FI-117, TI-118, FI-119, AI-137 and AI-137-E/F/G/H, FV-204, LV-208, FV-209. **14/14 mapped**.

TI-122's source description is “Separator Cooling Water Outlet Temp.” It is the outlet of the same cooling-water circuit whose flow is XMV 11 (“Condenser Cooling Water Flow”) and whose inlet disturbance is IDV 5 (“Condenser Cooling Water Inlet Temperature”); the revised TE code calls it the condenser cooling-water outlet. The simulator books condenser duty in the separator energy balance, which is where the “separator” label comes from. It stays on E-101, now verified. It is a cooling-water temperature, not a process temperature. PI-116 (“Stripper Pressure”) is computed in the simulator from the feed-header pressure; its ownership is unresolved in the source and stays flagged on C-101. FI-104 belongs to C-101/S4 and should not appear as a U-100-owned reading.

Recorded XMV values are controller outputs, not independently measured valve positions. HV-205 is a compressor recycle (spill-back) valve output; the simulator computes the spill-back only as a reduction of net compressor flow, so no stream is assigned. SC-212 is neither a recorded speed measurement nor a running-status signal.

## Essential overview choices: engineering judgment

These choices are a proposed review baseline, not a source-prescribed HMI or safety assessment.

- U-100: FI-101/102/103 show each incoming feed supply. Keep different engineering units explicit rather than adding incomparable rates.
- R-101: PI-107 and TI-109 expose available pressure/temperature and the existing published alarm context; LI-108 inventory; FI-106 throughput. TI-121 and TV-210 provide cooling context on unit detail. SC-212's unavailable state on detail avoids a misleading agitator animation.
- E-101: TI-122 and TV-211 are the only signals the source assigns to the condenser. Do not invent condenser process temperature, pressure, level or duty.
- V-101: PI-113, TI-111, LI-112 and FI-114 show separation conditions, inventory and liquid transfer; FI-110 shows the purge on the process overview. LV-207, FV-206 and the purge analyzer are on unit detail.
- K-101: FI-105 recycle, JI-120 compressor work and HV-205 recorded recycle output show available circulation/work context. Do not infer operating status, compressor speed or pressure ratio.
- C-101: PI-116, TI-118, LI-115 and FI-117 show product-section conditions, inventory and output. FI-104 incoming A/C feed and FI-119 steam flow on unit detail expose key supply/utility context; steam flow is not calculated heat duty.

Detailed analyzer components, final-element outputs and sampling caveats belong on unit details and relevant boundary context without overcrowding the overview.

## Complete boundary inventory

Each endpoint and direction is verified against the simulator source (`out/te_topology_check.md`). It is still not measured flow, validated piping or responsive process physics. Peer links should navigate to the other asset; BL is an external/model boundary, not a fabricated equipment page.

- S1 A feed: BL → U-100; FI-101, FV-203.
- S2 D feed: BL → U-100; FI-102, FV-201.
- S3 E feed: BL → U-100; FI-103, FV-202.
- S4 A/C feed: BL → C-101; FI-104, FV-204.
- S5 stripper overhead: C-101 → U-100; no stream instrument in the source.
- S6 reactor feed: U-100 → R-101; FI-106, AI-123 A–F.
- S7 reactor product: R-101 → E-101; no stream instrument in the source.
- S7b condensed product: E-101 → V-101; no stream instrument in the source. (The simulator computes S7 and S7b as one flow; the split at the condenser follows the published flowsheet.)
- S8 recycle: V-101 → K-101; no stream instrument. FI-105 is placed on S8b; the simulator has one flow for S8 and S8b, so which segment carries the tap is a model choice.
- S8b recycle to feed: K-101 → U-100; FI-105.
- S9 purge: V-101 → BL; FI-110, FV-206, AI-129 A–H (corrected 2026-10-13 from K-101 → BL).
- S10 separator underflow: V-101 → C-101; FI-114, LV-207.
- S11 product: C-101 → BL; FI-117, LV-208, AI-137 D–H.

Per-unit link counts: U-100 six; R-101 two; E-101 two; V-101 four; K-101 two; C-101 four. Total 20 equipment endpoint appearances across 13 edges (seven equipment-to-equipment, six involving BL).

Utility instrumentation exists without modeled utility edges: reactor cooling water TI-121/TV-210; condenser cooling water TV-211/TI-122; stripper steam FI-119/FV-209. Expose these as utility instrumentation with unspecified boundary topology. No cooling-supply node, cooling return edge, condensate return, compressor bypass edge, utility flow direction, inlet temperature, energy balance or drive state should be invented.

## Offline verification

`python scripts/test_te_channels.py` checks 52 unique source columns; 53 display entries; legacy path/index compatibility; all 19 analyzer components; unchanged model; preserved component source/sampling metadata; historical/read-only measurement UDT configuration; no bad-quality fallback to normal; unchanged alarm list; 52-channel summary inclusion; and parent hidden/rejected propagation.

Live server/gateway import, historical values, quality transitions and display runtime remain unverified. No deployment, external publication or process write is authorized by this document.
