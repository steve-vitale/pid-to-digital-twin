# Timed review kit: OPEN100 sheet 8

**Status: ready to run, not run.** Nothing in this folder is a measurement yet. Review minutes per sheet are the
project's biggest unmeasured number ([COSTS.md](../../../docs/COSTS.md) §3). This kit is how to get the first real
one. The full study design, with a manual baseline and an independent audit, is in
[REVIEW_EFFORT_PROTOCOL.md](../../../docs/REVIEW_EFFORT_PROTOCOL.md). This kit is its first, smallest step: one
reviewer timing one drawing's review.

## What is in the packet

| File | What it is |
|---|---|
| `drawing_sheet8.png` | The drawing (PID2Graph OPEN100 sheet 8, CC BY-SA 4.0) |
| `extracted_overlay_sheet8.svg` | What the method extracted, drawn over the sheet. Open it in a browser |
| `review_queue_sheet8.csv` | 88 rows to review, riskiest first: 2 red, 13 amber, 73 green |
| `timer_log.csv` | Empty timer log. The timer command writes to it |
| `manifest.json` | SHA-256 of the packet files, so the reviewed packet can be shown to be this one |
| `protocol_draft.json` | A draft protocol for `review_effort.py`. Study decisions are left blank on purpose |

The rows are 46 connections, 14 instruments, 11 valves, 11 off-page connectors, 5 in-line items and 1 vessel, from
the published twin (GPT, method M3). Sheet 8 is the smallest holdout-A sheet, so one sitting should be enough.

## Before you start (not timed)

1. Open the drawing, the overlay and the CSV in a spreadsheet. Read [REVIEW_LOOP.md](../../../docs/REVIEW_LOOP.md)
   §1 for what each `OPS_` column means.
2. Do **not** open the answer key (`8.graphml`). It is for the auditor, not the reviewer.
3. Pick a pseudonymous id such as `R1`. Never put a name in the log.

## The timed review

From the repository root:

```sh
python scripts/review_kit.py timer start  --kit out/review_kit/sheet-8 --reviewer R1
# review rows top to bottom; fill OPS_confirm_or_correct with confirm / correct / reject
python scripts/review_kit.py timer pause  --kit out/review_kit/sheet-8 --reviewer R1 --note "phone call"
python scripts/review_kit.py timer resume --kit out/review_kit/sheet-8 --reviewer R1
python scripts/review_kit.py timer stop   --kit out/review_kit/sheet-8 --reviewer R1
```

- Pause for anything that isn't reviewing: breaks, calls, other work. Pauses are not counted.
- Stop when every row has a decision, or when you give up. Giving up is a result too: leave the rest blank.
- Something the draft missed entirely (a symbol or a line not in the queue): note it in `OPS_notes` on the nearest
  row. Missed items are what the risk tiers cannot point at, so they matter.
- Save the filled sheet as `review_queue_sheet8_filled.csv` in this folder. Keep the rows in the same order.

## The summary

```sh
python scripts/review_kit.py summarize --kit out/review_kit/sheet-8 --queue out/review_kit/sheet-8/review_queue_sheet8_filled.csv
```

It prints active minutes, rows decided, decisions by kind, unanswered rows, and minutes per decided row and per
correction or rejection. It refuses a timer log that isn't complete and in order, and a filled sheet whose rows
differ from the packet.

## What the number will and won't mean

- **It will be:** the first measured minutes for one reviewer on one machine-drafted sheet. That replaces the
  assumed "1 minute per correction" in COSTS.md with an observation, labelled as one observation.
- **It won't be:** a saving. A saving needs the manual baseline on a matched sheet by a different reviewer, and an
  independent audit of what was still wrong afterwards. Both are in the protocol. Fill the blank fields in
  `protocol_draft.json`, freeze it, and run `python scripts/review_effort.py validate` before any comparison.
- **One reviewer is not a rate.** Expertise, familiarity with the drawing style and the spreadsheet all move the
  number. Report it with who (role, not name), how experienced, and how many sheets.
