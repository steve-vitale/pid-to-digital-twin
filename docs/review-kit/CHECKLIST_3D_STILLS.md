# Checklist: 3D tour draft stills

**Files:** `drafts/3d-tour/00_overview_normal.jpg`, `02_r-101_normal.jpg`, `21_overview_fault_alarm.jpg`,
`30_flow_legend.jpg`, `40_loto_mockup.jpg`. Context: `drafts/3d-tour/README.md`. Automated checks already run:
`drafts/3d-tour/REVIEW_NOTES.md` (OCR read-back, purpose-card sources, citation check).

Geometry, sizes and pipe routes are placeholders by design. Do not review them as if they were the plant.

## Track A: anyone

View each still at 100 % on a normal monitor.

1. **Every label readable** without zooming? Note any you had to zoom for.
2. **1 versus I.** In this typeface the digit 1 and capital I look alike. Can you tell `TI-109` from `TI-I09`,
   and LOTO tag `1` from `I`? (OCR confused them; see the review notes.)
3. **Labels point at the right thing.** Each tag pill sits next to the marker it names, and each unit label next
   to its unit.
4. **The draft status is visible:** the corner badge ("Prototype · placeholder geometry · recorded replay") and,
   on the LOTO still, "design mockup, not a procedure".
5. **Numbers copied correctly.** On `02` and `21`, PI-107's high alarm reads 2,895 kPa g and the shutdown 3,000;
   TI-109's shutdown reads 175. These match `out/ignition/gateway/build_meta.json`.
6. **Would a newcomer understand what each still is for** from the still and its caption alone? Write what you
   think each one is saying.

## Track B: operations reviewer

1. **Purpose cards** (text on `02`; all six cards in the 3D branch's `data/te_unit_purposes.json`, sourced
   versions in `drafts/3d-tour/3d-content-fixes.patch`): is each unit's purpose and function right, and is
   anything an operator needs missing?
2. **Flow (`30`):** is the order "feeds and recycle meet, react, condense, separate, recycle, strip" how you would
   explain this process? The review notes record one known topology difference (where the purge is taken).
3. **LOTO mockup (`40`):** are these the energy sources you would expect to isolate for these units (process
   feeds, purge, product, motors, cooling water, steam)? What is missing (e.g. the separator and stripper
   liquid outlets, analyser sample lines, instrument air, relief paths)? This is a design question about the view.
   It is not a procedure, and the numbering is not an isolation order.
4. **Hazard citations** (`02` shows one; all are in the review notes): is each incident relevant to that kind of
   equipment, and would it help a new operator understand why the unit deserves care, or mislead them?
5. **Would you use a tour like this for orientation?** What would make it useful, and what would make it
   dangerous?
