# Reviewing this project

Three ways in, depending on how much time you have. None of them needs an account or anything sent back.

## Two minutes: read

Read [the project status](STATUS.md) for implementation gaps and [results and limits](RESULTS.md) for research evidence.

## Ten minutes: have your coding agent check it

Point Codex, Claude Code, Cursor or any other coding agent at a clone of this repository and ask it whether the
published numbers hold up. [AGENTS.md](../AGENTS.md) at the root tells it which checks to run and which limits to
report back. Or run them yourself:

```sh
python scripts/check_claims.py      # each headline number against the committed file it comes from
python scripts/pipeline.py status   # whether every output is fresh against what made it
```

Both use only the Python standard library and finish in under a minute. To go one step further and re-score the
results instead of reading them:

```sh
python scripts/rescore.py --check   # re-score the committed predictions; diff every scorecard and replicate table
```

It rebuilds each table from `predictions/` (the parsed per-drawing answers, without the raw model text) and the
committed answer keys, and exits 1 if any differs from the file in `out/`. It takes a few minutes. Tables
whose predictions have not been located (five earlier round-2 diagnostic tables) are listed as `GAP` with the
reason. The round-5 headline replicates and both TE round trips now reproduce after records were recovered from
preserved research working copies; [predictions/README.md](../predictions/README.md) gives the exact coverage and
historical formatting adjustments.

To run the test suite too:

```sh
python scripts/run_tests.py --check-prerequisites   # what is missing, if anything (runs no tests)
python scripts/run_tests.py --full                  # every registered test (the default mode)
python scripts/run_tests.py --source-only           # stdlib + committed fixtures only; NOT a full-suite pass
```

`--full` runs every test registered in `scripts/run_tests.py` (unit, round-trip and agreement tests across the
tools), offline: it needs the packages in `requirements.txt` and the cached public data (Tennessee Eastman runs,
PID2Graph OPEN100 drawings), and stops with exit code 2 naming what is missing instead of downloading anything.
`--source-only` is the subset a bare clone with only the standard library can run.

Read the case-level omissions as well as script success. The summary counts unittest skipped cases from either
output stream. Platform notices explain specific cases already in that total; do not add them again. Other
`SKIP` notices describe checks or groups and have their own count. A successful script exit can include skips;
the runner withholds its complete full-suite message whenever any of these omissions is reported. Exit 0 means
the selected runnable checks passed; failures still exit 1 and missing required prerequisites exit 2. The runner
reports child-program results, not proof that arbitrary test code cannot silently omit work. See the
[reproducible illustrative example](../examples/test-coverage/README.md).

Some original-source checks are optional, beyond the preflight's required data. Missing DEXPI TrainingTestCases
XML, adapted DEXPI sheets/keys or the SPPID vendor-render fixture can skip those checks. The default CI setup
fetches the required TE data and revised code, not these optional caches. Committed-fixture checks still run;
their success does not establish that the missing originals were reread. To inspect an affected unittest's exact
case and reason, run that script with `-v` (for example, `python scripts/test_dexpi_reader.py -v`).

For original-source coverage, prepare the relevant cache separately: the
[pinned corpus fetcher](CORPUS_FETCH.md) covers TrainingTestCases, and the
[DEXPI adapter guide](../examples/from-dexpi/README.md) covers source fetch and rendered sheets/keys. Rendering
requires the guide's optional PyMuPDF dependency. The vendor-render check uses the staged corpus described in
the [generalization guide](GENERALIZATION.md). Preparation can use the network and is separate from this offline
runner. Do not relabel a cached local run or a historical receipt as coverage of a different CI environment.

## One hour: time a review of one drawing

The biggest number this project hasn't measured is how long a person takes to check what the extraction produced.
"Review load" in the results counts differences from an answer key; it is not minutes. If you review P&IDs for a
living, one hour with the kit in [`out/review_kit/sheet-8`](../out/review_kit/sheet-8/README.md) gives you that
number for one public drawing (88 rows, riskiest first, with a timer that writes its own log).

What it's good for, for you: a rough answer to "would this save my team time on drawings like these", from your own
hands rather than from anyone's claim. What it isn't: a study. One reviewer on one sheet tells you about that sheet.
[REVIEW_EFFORT_PROTOCOL.md](REVIEW_EFFORT_PROTOCOL.md) is the full design, with a manual baseline and an independent
audit.

If you do run it and want to share the result, open an issue with your timer log and filled sheet (use a
pseudonymous reviewer id such as R1, never your name). Not required.

## If something doesn't hold up

Open an issue with the claim, the file and line, and what you expected. Corrections go in the journal with the date
they were found and who (or what) found them.
