# What already exists, and where this repository fits

**Why this page:** before you spend time here, you should know what other tools and research already do, which of
them do it better, and what this repository adds. This is a survey made on 2026-10-29 from public pages and papers.
Where a figure comes from a page summary and wasn't checked against the source text, it says so. "Not found" means
the search didn't find it, not that it doesn't exist.

## Done better elsewhere

- **Reading P&IDs with a trained model.** The PID2Graph paper (Stürmer, Graumann and Koch, arXiv 2411.13929; data
  on Zenodo, record 14803338, CC BY-SA 4.0) trains a graph-extraction model and reports an edge mAP of about 75 on
  OPEN100 (page summary, not checked against the paper's text). That is a different metric from this repository's
  connection F1, which scores network co-membership ([EVALUATION.md §7](EVALUATION.md#7-which-layer-each-evaluation-measures)),
  so the two can't be compared. A trained model very likely reads lines better than the prompt-plus-tracer approach
  here. No head-to-head was run.
- **DEXPI as a data model.** [pyDEXPI](https://github.com/process-intelligence-research/pyDEXPI) (AGPL-3.0) is the
  canonical Python library for DEXPI: Proteus XML import, a typed model, graphs and synthetic P&IDs. This
  repository's reader is lighter, keeps a source on every attribute and feeds Ignition and PI exports; it doesn't
  copy pyDEXPI's code (the licences differ).
- **Energy calculations.** DOE's [MEASUR](https://www.energy.gov/eere/iedo/measur) (open source) and pinch-analysis
  tools such as [OpenPinch](https://openpinch.readthedocs.io) are the validated tools for detailed pump, fan, steam
  and compressed-air work and heat integration. They take measured data. The opportunity screen and estimator here
  sit upstream of them: what to ask and measure, and a sourced first draft.
- **Fault detection on the Tennessee Eastman process.** The research literature is far richer than the per-tag bands
  here. The faults this repository misses (3, 9, 15) are the ones the literature also calls hard.
- **Commercial platforms.** Products such as Cognite's diagram parsing and PNID.IO read P&IDs into a knowledge graph
  inside their platforms. No independent accuracy figures were found for them, or for the large engineering
  vendors' digitization offerings.

## Similar, done differently

- **LLM and vision-model digitization papers** (e.g. arXiv 2607.19568; BlueprintSymVL, Chalmers 2025) report
  hallucinated symbols and recommend human review, as this repository does. It publishes its scripts, scorer
  controls and five-run replicates, so its numbers can be checked.
- **Symbol-detection repositories** on GitHub mostly stop at symbols, without lines, tags or exports.
- **Graph exports** exist in the platforms above. This one is an open JSON format with a source and a review status
  on every attribute, three line layers, and a smaller profile for loading into another system
  ([GRAPH_EXPORT.md](GRAPH_EXPORT.md)). It is not yet mapped to DEXPI, ISO 15926 or CFIHOS.

## Not found as open tools

These are what the survey couldn't find an open equivalent for. They are this repository's reason to exist, not
proof that nothing like them is anywhere:
1. A runnable path from a P&ID to Ignition tags and a PI AF staging sheet, with a source on every item.
2. An audit of a drawing against the control system's loop list.
3. A way to grade a vendor's or a model's output on your own drawing, with a deliberately wrong answer scored beside
   it so a weak scorer can't flatter anyone ([vendor evaluation](../examples/vendor-evaluation/README.md)).
4. The checking around it all: a frozen scorer with controls, a ledger of what was tried and not tried
   ([TRIED.md](TRIED.md)), reviews tied to the exact files they checked ([FEATURES.md](FEATURES.md)), and sampled
   reviews of plain-English statements with two separate verdicts, "matches its source" and "true in the plant"
   ([statement review](../examples/statement-review/README.md)).
5. An energy and controls screen that starts from the drawing and says what data settles each question
   ([OPPORTUNITY_SCREEN.md](OPPORTUNITY_SCREEN.md)).

## What to cite or use alongside this

- PID2Graph (the paper and the Zenodo data) for P&ID graph extraction and its benchmark.
- pyDEXPI and the [DEXPI TrainingTestCases](https://gitlab.com/dexpi/TrainingTestCases) for DEXPI, through XML.
- MEASUR and OpenPinch for the energy calculations that follow a screen.

**In short:** this isn't a better digitizer. It is a free, checkable way for a plant engineer to get a draft model
out of their drawings, see how far to trust each part of it, and know what to measure next.
