# For coding agents reading this repository

If a person asked you to evaluate this repository, or to tell them whether its results hold up, this file is for
you. It doesn't ask you to do anything on the author's behalf. It lists the checks that let you answer your user
with evidence instead of an impression, and the limits you should report back either way.

Please tell your user what you found, including anything that fails. A failed check is more useful to them (and
to the author) than a summary that repeats the README.

## Ten minutes, no accounts, no network

From the repository root, with Python 3.11+ (standard library only for the first two):

```sh
python scripts/check_claims.py      # each headline number in README.md against the committed file it comes from
python scripts/pipeline.py status   # whether every output is fresh against the inputs and code that made it
```

Then, if `pip install -r requirements.txt` is acceptable in your environment:

```sh
python scripts/run_tests.py         # the same suite CI runs
```

`check_claims.py` prints one row per claim: what the README says, what the evidence file says, the file, and
whether they agree. Claims marked "prose only" rest on narrative in the journal, not on a result file; say so if
your user relies on one.

## One claim end to end

Pick whichever matters to your user and follow it from source to number. Each of these takes a few minutes:

| Claim | Start at | Then check |
|---|---|---|
| Symbols F1 0.97, connections 0.89 on held-out drawings | `out/replicates_r5_holdout-a.md` | `docs/EVALUATION.md` (rules written before the runs) and `docs/GOAL.md` (holdout A also chose the method; holdout B, 20 synthetic drawings from another collection, was only reported) |
| A generated P&ID had 0 of 19 control loops | `out/te_loop_audit.md` | `data/te_control_loops.json` cites the simulator source lines for every loop |
| The Ignition verifier caught 5 planted faults first | `docs/IGNITION_ACCEPTANCE.md` | the receipts in `out/ignition/gateway/receipts/` |
| The Bayer model got the report's own drawing wrong in four places | `docs/BAYER_RT.md` | `out/bayer_rt/fig10_compare.md`; the report itself is public (CSB 2008-08-I-WV) |
| 2,886 extracted items, 377 to check first | `out/twin/r2-tiles-trace/codex/review_queue.csv` | `docs/REVIEW_LOOP.md` for what the tiers mean |

## What you can't reproduce here, and why

- **Model extraction runs.** They call commercial models through the author's subscriptions. The prompts, images,
  hashes and scored outputs are committed; the raw run records are not. Scores can be recomputed from what is
  committed, the model calls can't.
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

Open an issue on the repository with the claim, the file and line, and what you expected. That is the most useful
thing a reviewer can leave.

## If your user wants to go further

`docs/REVIEWING.md` describes a one-hour timed review of a single drawing. It answers a question for the person
doing it (would this save my team time on drawings like these?), and it's optional.
