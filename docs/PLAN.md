# Plan: P&ID → Digital Twin Jumpstart

Planning locked 2026-10-06. The reasoning behind each decision is in [`JOURNAL.md`](JOURNAL.md).

## Decisions

| Question | Decision |
|---|---|
| Who it's for | Engineers and teams starting digital twin work, and anyone judging whether AI can be trusted with plant data |
| Hero case | Tennessee Eastman (TE) end to end **plus** a public P&ID dataset with ground truth for an honest accuracy number |
| Platform proof | **Ignition trial**: real import + live values. **PI**: AF structure generated and explained, labeled "not import-tested" |
| Operations reviewer | The author, who has process-plant operations experience. Stated plainly wherever review results appear |
| Extraction comparison | **Claude vs Gemini vs GPT** on the same drawings, same output schema, same answer key |
| Budget | Claude and GPT through existing subscriptions · Gemini through its API with a **hard $25 cap** |
| Live values | Yes, as the finale: replay public TE simulation data so the graphics animate |
| Deliverables | This repo + README · a short screen-recorded demo · a write-up |
| License | MIT for code; dataset-derived files keep their source license |

## Acceptance criteria (how we'll know the showcase worked)

1. **Honest accuracy table:** per tool, symbol precision/recall and connection accuracy on real public P&IDs, scored
   automatically against third-party ground truth (not a key we wrote ourselves).
2. **Review-loop number:** for TE, % of items correct on the first pass, then after operations review, with every
   correction traceable to a row in the review sheet.
3. **"It loaded" proof:** Ignition screenshots and video of the UDTs imported, the SVG in a Perspective view, and values moving.
4. **Reproducible:** a stranger can clone the repo, run documented commands, and regenerate every artifact and score
   (API keys aside).
5. **No overclaims:** every number in the post traces to a file in the repo.

## What the research changed (verified 2026-10-06; sources in Appendix)

- **Scoring dataset = PID2Graph** (Zenodo 14803338, CC BY-SA 4.0). It includes **12 annotated drawings from the public
  OPEN100 reactor design** and 60 annotated real industrial P&IDs, with graph ground truth (symbols plus connections).
  The OPEN100 subset is ideal because a viewer can inspect the source design. Labels are generic symbol classes, **not
  ISA tags**, so tag-reading accuracy can only be scored on TE.
- **It's an 8.66 GB single zip**, and C: has ~11 GB free while Ignition wants ~10 GB free to install. **Plan:** read the
  zip's index over HTTP range requests and pull only the OPEN100 and real-P&ID entries. Never download the whole thing.
- **PI Vision dropped plain custom-SVG import (2023+).** The SVG story goes to Ignition Perspective, where drag-and-drop
  SVG becomes a Drawing component with element ids kept, so styles can bind to tags. For PI, only the AF hierarchy is
  shown (the asset model is PI's real value anyway).
- **There's no free PI environment.** The only route is a 45-day PI Developers Club trial. Not in scope; maybe later.
- **Ignition:** the 2-hour trial resets for free (fine for a demo). Maker Edition is personal-use only. The built-in
  **Programmable Device Simulator** can replay CSV data, so live values need no PLC and no external OPC server.
- **TE references:** the original paper is paywalled. Open sources are the `tennessee-eastman-profBraatz` GitHub repos
  (code plus data) and the **Rieth et al. 2017 Harvard Dataverse** simulation set (doi:10.7910/DVN/6C3JR1, ~1.3 GB, check
  the license tab). We redraw the flowsheet ourselves; we don't republish the copyrighted figure.

## Phases

Each phase ends with a commit, a STORY_LOG entry, and at least one screenshot.

| # | Phase | Done when |
|---|---|---|
| 0 | Sketch: TE seed model → SVG / Ignition / PI / review sheet | ✅ 2026-10-06 |
| 1 | **Ground truth.** (a) TE variable list verified against open sources; seed model corrected; mismatches logged in the story. (b) Fetch the OPEN100 + real P&ID subset of PID2Graph via range download and convert its graphml to our schema. | Answer keys committed (or a fetch script where the license requires it); every TE row `confirmed` or `corrected` |
| 2 | **Extraction harness.** One prompt and one JSON schema; adapters for Claude, Codex/GPT, and Gemini; a scorer for symbols (P/R by class) and connections; a cost meter with a hard $25 stop for Gemini. Record `{model, prompt, adapter, date}` per run. | One command reruns a tool on a drawing set and writes the scorecard |
| 3 | **Comparison runs.** All three tools on the PID2Graph subset plus a TE drawing (our redrawn flowsheet as an image). Report real vs. synthetic separately if both are used. | `out/scorecard.md` plus failure-example images (what each tool got wrong) |
| 4 | **Operations review.** Best extraction of TE → review sheet → the operations reviewer marks it up → merge script applies corrections → re-score. | First-pass vs. post-review numbers; the marked-up review sheet committed |
| 5 | **Ignition proof.** Install trial; fix the import JSON against current docs; import UDTs; drop SVGs into a Perspective view; bind the valve and instrument styles. | Screenshots: tag browser + Perspective view |
| 6 | **Live values.** Fault-free TE run from Rieth 2017 → CSV → Programmable Device Simulator → UDT instances. Optional: replay a fault case so an alarm visibly trips. | 1–2 min screen recording |
| 7 | **PI artifact.** PI Builder sheet with headers checked against AVEVA's workbook doc; README explains the AF mapping and that it isn't import-tested. | Sheet + explanation |
| 8 | **Write-up.** README with results, demo video, and the journal tidied into a readable narrative. | Results section filled; every number links to a file |

## Comparison fairness (so the numbers hold up)

- Same input images (same resolution), same prompt text, same output schema, same scorer for every tool.
- Different access paths (Claude Code, Codex subscription, Gemini API) are recorded per run. If a harness difference
  could explain a gap, say so. Don't call a winner off one run: repeat each tool at least twice on a subset to show variance.
- Report the score of each tool's first try, not the best of many attempts.

## Risks

| Risk | Mitigation |
|---|---|
| Disk (~11 GB free) | Range-download only the needed subset; keep datasets out of git; Ignition install checked against free space first |
| Gemini spend | Pre-run cost estimate plus a hard stop at $25 in the harness |
| License | PID2Graph is CC BY-SA: credit it, keep any derived data files under CC BY-SA, keep the code MIT. Don't republish the D&V figure |
| Overclaiming | Every number links to a file; "not import-tested" labels on PI; reviewer-was-me stated plainly |
| Import format drift | Check Ignition JSON field names (`binding` vs `parameter`) and PI Builder headers against current docs in phases 5 and 7 |
| Data provenance | Public sources only; no proprietary or real-site drawings |

## Configuration

- Gemini runs read the key from the `GEMINI_API_KEY` environment variable. Keys are never committed.

## Appendix: sources (verified 2026-10-06; recheck before publishing)

- PID2Graph: https://zenodo.org/records/14803338 · arXiv:2411.13929
- Digitize-PID: arXiv:2109.03794 (download link unconfirmed, not used)
- TE open code/data: github.com/camaramm/tennessee-eastman-profBraatz
- Rieth et al. 2017 TE data: https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/6C3JR1
- Ignition licensing/trial: docs.inductiveautomation.com/docs/8.1/platform/licensing-and-activation
- Ignition tag import/export: docs.inductiveautomation.com/docs/8.1/platform/tags/exporting-and-importing-tags
- PI Builder: AVEVA "Building PI System Assets" workbook (cdn.osisoft.com)
