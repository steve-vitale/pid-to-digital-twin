# P&ID → Digital Twin Jumpstart

A personal showcase of how AI tools can speed up the first part of a manufacturing digital twin.
The usual first step is weeks of someone redrawing P&IDs and typing tag lists by hand. This project
replaces that step with **extraction, review, and export**.

```
 Public P&ID ──► Structured process model ──► Verification with Operations ──► Platform-ready output
 (drawing/PDF)   (equipment, instruments,      (review sheet, sign-off,         • SVG graphics (paste into HMI / twin)
                  lines, tags, provenance)      corrections loop)               • Ignition tag/UDT import JSON
                                                                                • AVEVA PI AF hierarchy (PI Builder sheet)
```

## Why this exists

A digital twin is only as good as its asset model, and the asset model usually starts as P&IDs that someone redraws
by hand. That step is slow, error-prone, and boring, which makes it a natural job for AI tools. But only if the
output is **checked** and **shaped by the people who run the plant.** This repo is an open, reproducible attempt at
both: speed from AI, trust from measurement and operations review.

The reasoning behind every design choice, including what was rejected and why, is in
**[`docs/JOURNAL.md`](docs/JOURNAL.md)**.

## How it works

1. **Start from a public P&ID.** No proprietary data. The first case is the **Tennessee Eastman (TE) process**
   (Downs & Vogel, 1993). It is the standard public benchmark plant in process control: 5 major units,
   41 measured variables, and 12 manipulated variables. Public simulated historian data also exists for
   it, so the twin can show live-looking values later.
2. **Extract a structured model.** AI tools read the drawing and produce a machine-readable model. Every
   item records **where it came from** (the drawing region or source document) and **how confident we are**.
3. **Verify accuracy. Don't trust it blindly.** The model drives a review sheet that operations and
   engineering mark up line by line (confirm / correct / missing). Corrections go back into the model,
   and accuracy is measured: % of items confirmed without change, by item type.
4. **Collaborate with operations so the twin serves them.** Operators decide what matters on the
   screen: which tags, which alarms, and which grouping matches how they actually run the unit.
   Their input is captured in the model, not lost in email.
5. **Generate platform-ready artifacts.**
   - Clean, layered **SVG** for each equipment item plus an overview. Each element carries `data-tag`
     attributes, so tag binding is a mapping step, not a redraw.
   - **Ignition**: UDT definitions plus tag instances in Ignition's tag JSON import format.
   - **AVEVA PI**: an AF element hierarchy with attributes ready for PI Point data references
     (PI Builder-style sheet).

The output isn't a finished implementation. It's an organization's **head start**: a verified asset model
and graphics, ready for real equipment tags to be connected.

## Layout

| Path | What |
|---|---|
| `data/te_process_model.json` | Structured process model for the TE plant (units, instruments, streams, provenance, verification status) |
| `scripts/generate.py` | Model → SVGs + Ignition tag JSON + PI AF sheet + Operations review sheet (Python stdlib only) |
| `out/` | Generated artifacts (regenerate anytime) |
| `docs/PLAN.md` | Decisions, phases with completion criteria, comparison fairness rules, risks, sources |
| `docs/JOURNAL.md` | Build journal: the how and why behind each step |

## Status

Early. The pipeline runs end to end on a hand-built seed model, and every seed item is marked **unverified** until
it's checked against published sources. AI extraction, scoring, the Ignition import and live values are planned; see
`docs/PLAN.md`.

## License

Code: MIT. Third-party datasets keep their own licenses and are downloaded by script, not redistributed.

## Run

```
python scripts/generate.py
```
