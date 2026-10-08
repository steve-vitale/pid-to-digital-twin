# From a clean demo set to 40 years of drawings

This project runs on public drawings that are unusually kind: consistently drafted, current, with independent
answer keys. A large site's P&ID archive is none of those things. This document is the honest gap list: what the demo
assumes, what a real archive looks like, and what has to be added to get from one to the other. It complements
[AT_YOUR_PLANT.md](AT_YOUR_PLANT.md) (preparation, savings, safety and security) and
[EVALUATION.md](EVALUATION.md) / [GOAL.md](GOAL.md) (how results are judged).

> The core idea doesn't change at scale: **the AI drafts, deterministic checks catch what they can, people decide.**
> What changes is that the "checks" grow from one scorer into several independent sources of truth, and the people
> need a process, not a spreadsheet.

## 1. What the demo assumes vs what a real archive looks like

| The demo assumes | A 40-year archive actually has |
|---|---|
| One drafting style | Several eras and contractors: hand-drafted mylar, early CAD, modern intelligent P&IDs, vendor skid packages, each with its own symbol library and tag habits |
| Clean digital images | Scans of scans, faded lines, coffee stains, skew, stamps, sheet sizes from A3 to E-size |
| The drawing is current | Redlines never incorporated, "as-built" sheets that were never updated, equipment removed in the field but still drawn, and the reverse |
| One copy per sheet | Superseded revisions in the same folder, duplicates across departments, sheets that no longer have a home unit |
| Consistent tags | Renumbering campaigns, legacy tags in the DCS, tags reused across units, placeholder "XXX" tags never filled in |
| An answer key exists | Nothing to score against except other imperfect sources |
| 12 sheets | Thousands to tens of thousands |

Each row needs its own countermeasure. They're below, roughly in pipeline order.

## 2. What has to be added

### 2.1 Document control comes before extraction
- **Inventory and de-duplicate:** hash every file, cluster near-duplicates, and record each sheet's number, revision
  and date from its title block. AI is good at reading title blocks.
- **Pick the revision of record per sheet,** and record why. If document control can't say which revision is
  current, that is the first finding of the project, not a detail.
- **Classify the document type:** P&ID vs PFD vs isometric vs loop sheet vs vendor drawing. Only the P&IDs (and
  the vendor P&IDs inside skid packages) feed the twin.
- **Link each sheet to its legend:** every era and contractor has its own symbols. Keep a legend library and
  attach the right legend to every extraction request.

### 2.2 Normalize images
- Deskew, de-speckle, check resolution (about 300 dpi minimum for tag text), and tile large sheets. Tiling is one
  of the round-2 methods measured in this repo.
- Keep originals. Every extracted item points back to the original file, page and box.

### 2.3 Extraction that knows which era it's reading
- **Calibrate by era and contractor:** annotate a small sample (3–5 sheets) per drafting style and measure review
  load per style. A single site-wide accuracy number hides the eras where the tool doesn't work.
- **Make the hard parts deterministic:** read symbols and text with AI; trace lines and connectivity with computer
  vision (round 2 measures this); check tag syntax against the site's tag standard with code.

### 2.4 Triangulate against other sources of truth
At a real site there's no answer key. There are several partial ones, and they disagree. That disagreement is the
most valuable output of the whole project:

| Source | What it confirms |
|---|---|
| DCS / PLC configuration export | Which instrument tags are actually live |
| Historian point list (PI, Ignition) | Which tags are archived, with units and ranges |
| Maintenance asset register (SAP PM, Maximo) | Which equipment exists, with equipment numbers and criticality |
| Instrument index, loop sheets | Instrument types, ranges, loop membership |
| PSM records (PHA, MOC history) | Safety-critical items and recent changes |

Every extracted item gets an agreement profile: which sources confirm it. Items confirmed by the drawing and two
other sources can be fast-tracked. Items only on the drawing, or missing from the drawing but live in the DCS, go to
review. That second group is often real **documentation drift**, which is worth reporting to engineering on its own.

### 2.5 Stitch sheets into one plant
- **Pair off-page connectors** ("to PID 210-1") across sheets into one plant-wide graph.
- **Unpaired connectors** point at missing, superseded or renumbered sheets. That's another drift signal.
- **Build the asset hierarchy** (site → area → unit → equipment → instrument) from the stitched graph and the
  asset register, not from one sheet at a time.

### 2.6 Verify in the field, by sample
- **Walk down a statistical sample per unit and era** to measure how far drawings drift from the plant. That drift
  rate sets how much the twin can be trusted, and where a full walkdown is worth paying for.
- **Record the outcome per item:** confirmed / different in field / not found / found but not drawn.

### 2.7 Make human review a process, not a spreadsheet
- **Order the queue by risk:** red, amber and green tiers from independent cross-checks (do other models and
  passes agree, is the symbol on a line, is the tag well-formed), not the model's own confidence. Then source
  disagreements, unpaired connectors, placeholder tags, and instruments with no parent. The converter in this repo
  produces exactly this queue.
- **Calibrate the reviewers:** double-review a sample, and track agreement between reviewers. A tired reviewer
  has an error rate too.
- **Measure review time per sheet:** that, not model accuracy, is the cost line that matters (`GOAL.md`'s
  "review load" is the lab version of it).

### 2.8 Keep the twin true after go-live
- **The drawing of record never changes because of the twin.** The twin is derived from it.
- **Re-extract on every revision:** when an MOC issues a new P&ID revision, re-extract that sheet, diff it against
  the twin, and route the differences through the same review. The twin's version history then mirrors the
  drawing's.
- **Re-run the evaluation for every model or prompt change** on the site's own sealed sample sheets. The
  scorecards are the change record for the AI tooling itself.

### 2.9 Security and governance at scale
- See [AT_YOUR_PLANT.md](AT_YOUR_PLANT.md) §5–§6 for data egress, OT network zoning, read-only use, and running
  models offline.
- At scale, add access control on the drawing archive itself, retention rules for model inputs and outputs, and a
  named owner for the twin data. Engineering document control, operations, and OT/IT each want to own it; decide
  that before the first import.

## 3. A phased path

| Phase | Scope | Exit criterion (decided before starting) |
|---|---|---|
| Pilot | One unit, ~20 sheets, one drafting era | Review load and review minutes per sheet beat the manual baseline; drift rate measured by walkdown sample |
| Style coverage | One sample unit per era / contractor | Review load per style known; styles where it doesn't pay are routed to manual capture |
| Area | All units in one area, stitched | Off-page pairing rate; tag agreement with DCS and historian above an agreed threshold |
| Site | Everything, with MOC re-extraction in place | Twin diff runs automatically on each new drawing revision |

**The rule that keeps this honest at every phase:** the success criteria are written down before the phase starts,
measured on units nobody tuned on, and reported with the failures, exactly as in this repo.

## 4. What this repo demonstrates vs what it doesn't

| Demonstrated here | Not demonstrated (needs a real site) |
|---|---|
| How quality drops on simulated old scans (round 4): little effect at photocopy quality, 3–4× review load on old and bad scans, mostly from the line tracer | Real scans: skew, stamps, handwriting, torn and annotated sheets; an image clean-up step tuned on them |
| Operations review applied back to the model with a change record; I/O-list mapping that flags drawings that may be out of date | A real review and a real I/O list; how often drawings and I/O disagree at that site |
| Extraction scored against independent keys, with controls and sealed holdouts | Calibration across drafting eras and contractors |
| Review load as the cost measure; a risk-tiered review queue checked on unseen drawings | Real review minutes per sheet, reviewer agreement |
| Cross-sheet stitching on one design's sheet set | Stitching across an archive with missing and superseded sheets |
| Ignition build verified in a running gateway ([IGNITION_BUILD.md](IGNITION_BUILD.md)); PI AF sheet generated, not import-tested | Reconciliation against a live DCS, historian and maintenance system |
| A governance model (read-only, MOC-tied, audited) | Running it inside a site's MOC and document control |
