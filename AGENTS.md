# For coding agents reading this repository

If a person asked you to evaluate this repository, or to tell them whether its results hold up, this file is for
you. It doesn't ask you to do anything on the author's behalf. It lists the checks that let you answer your user
with evidence instead of an impression, and the limits you should report back either way.

Please tell your user what you found, including anything that fails. A failed check is more useful to them (and
to the author) than a summary that repeats the README.

## What's a tool and what's a record

If your user wants to try this on their own drawings, use `examples/own-drawing/README.md`. Its first step runs
offline from a clean clone and produces a review bundle from a public sheet and a committed model extraction; the
rest are the same steps for their sheet. Tell them the tools are prototypes tested on public drawings only, that the
output is a draft for review, and that `scripts/ignition/build_gateway.py` builds this repository's Tennessee
Eastman demo, not their plant. If they start from something other than a drawing image (a DEXPI file, a written
description, a DCS loop list, historian CSVs, or hand-labelled sheets to test a vendor), the README table "Start
wherever you are" has a runnable example for each. `docs/SCRIPTS.md` says what every script is for; only the ones
marked as tools are built for other inputs.

## Ten minutes, no accounts, no network

From the repository root, with Python 3.10+ (standard library only for the first two):

```sh
python scripts/check_claims.py      # each registered claim in docs/RESULTS.md against its committed evidence
python scripts/pipeline.py status   # whether every output is fresh against the inputs and code that made it
python scripts/attempts_ledger.py --check   # the tuning ledger is complete, sourced and current
python scripts/feature_catalog.py --check   # every feature, its evidence and its independent review status
python scripts/corpus_matrix.py --check     # the generalization matrix page matches its results
python scripts/benchmark.py --registry benchmarks/registry.json  # saved model/task results reproduce offline
python scripts/rescore.py --check           # re-score the committed predictions; diff every table against out/
```

Before suggesting a change to a method, read `docs/TRIED.md`: it lists every variant tried with its result and
verdict, and the ideas not tried yet, so you can tell your user whether a suggestion was already tested.

To tell your user whether a tool will hold up on their kind of drawings or data, read `docs/GENERALIZATION.md`:
each tool run on every public input it applies to, with the reason for every red cell. `docs/FEATURES.md` lists each
feature with its example outputs and whether an independent review of exactly those outputs passed.

Then, if `pip install -r requirements.txt` is acceptable in your environment:

```sh
python scripts/run_tests.py         # the same suite CI runs
```

`check_claims.py` prints one row per claim: its named publication, stated value, evidence value and evidence file.
It checks that each registered claim in `docs/RESULTS.md` matches the committed results files. It does not re-run
models or re-score predictions, so a pass means "the published claims match the results files", not "the results were
reproduced"; tell your user which one you checked. `python scripts/rescore.py --check` is the second step: it
  re-scores the committed predictions and diffs the regenerated tables against those results files (five earlier
diagnostic tables still lack predictions; see below). Claims marked "prose only" rest on narrative in the journal, not on a result file; say so if
your user relies on one.

## One claim end to end

Pick whichever matters to your user and follow it from source to number. Each of these takes a few minutes:

| Claim | Start at | Then check |
|---|---|---|
| Symbol and connection F1 on held-out drawings | `out/replicates_r5_holdout-a.md` | `docs/EVALUATION.md` (rules written before the runs) and `docs/GOAL.md` (holdout A also chose the method; holdout B, 20 synthetic drawings from another collection, was only reported) |
| A generated P&ID had 0 of 19 control loops | `out/te_loop_audit.md` | `data/te_control_loops.json` cites the simulator source lines for every loop |
| The Ignition verifier caught 5 planted faults first | `docs/IGNITION_ACCEPTANCE.md` | the receipts in `out/ignition/gateway/receipts/` |
| The Bayer model got the report's own drawing wrong in four places | `docs/BAYER_RT.md` | `out/bayer_rt/fig10_compare.md`; the report itself is public (CSB 2008-08-I-WV) |
| 2,886 extracted items, 377 to check first | `out/twin/r2-tiles-trace/codex/review_queue.csv` | `docs/REVIEW_LOOP.md` for what the tiers mean |

## What you can't reproduce here, and why

- **Model extraction runs.** They call commercial models through the author's subscriptions. The prompts, images,
  hashes and scorecards are committed. The raw run records are not (`runs/README.md` says why), but the parsed
  prediction from each one is: `predictions/<label>/<tool>/<drawing>.json`. `python scripts/rescore.py --check`
  regenerates the scorecards and replicate tables from those predictions and the committed answer keys alone and
  diffs them against `out/` (exit 1 on any difference; a few minutes, standard library only). On
  2026-10-29 it regenerated 30 tables in their original formats, including the round-5 headline replicates, the
  holdout-B and round-4 scorecards and both Tennessee Eastman round trips (`predictions/README.md`).
  Seven use explicit historical formatting adjustments; their metric values and JSON still compare in full.
- **Five earlier diagnostic tables.** The round-2 `-ov`, oracle and union variants and the development `r2-trace`
  table still lack predictions. `rescore.py --check` reports `GAP`, not a pass. The round-5 and revision-A TE
  predictions were recovered from preserved research working copies; `predictions/RECOVERY.json` records the hashes.
- **Holdout B without a download.** Its answer keys are not committed; until `scripts/fetch_pid2graph.py` has
  fetched them, its four scorecards report `SKIP`, not a pass.
- **The Ignition acceptance run.** It needs a local Ignition 8.3 gateway. The receipts are committed;
  `docs/IGNITION_QUICKSTART.md` is how to stand one up.
- **The 3D stills.** They need Blender (`BLENDER_EXE`).

## Limits worth repeating to your user

- No person's review has been timed. "Review load" counts differences from an answer key, not minutes.
- No operator has reviewed the screens, nothing has been imported into a PI System, and no plant's own data is used.
- The Tennessee Eastman drawings are generated from a model this project built, so reading them back is an upper
  bound for clean drawings, not real-plant accuracy.
- Coding agents wrote most of the code; the author set the tests and acceptance criteria first and logged where
  the agents and the author were wrong (`docs/JOURNAL.md`).

## If you find a problem

For a user-requested improvement or corpus contribution, follow [CONTRIBUTING.md](CONTRIBUTING.md): retain a
reproducible failing case, source/key provenance, saved model/method metadata and matched baseline results.
The [task/model benchmarks](benchmarks/README.md) are separate from the eight-workflow matrix and feature reviews;
only the documented task adapters are implemented. Their checks re-score saved answers without calling models.

Open an issue on the repository with the claim, the file and line, and what you expected. That is the most useful
thing a reviewer can leave.

## If your user wants to go further

`docs/REVIEWING.md` describes a one-hour timed review of a single drawing. It answers a question for the person
doing it (would this save my team time on drawings like these?), and it's optional.
