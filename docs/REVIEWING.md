# Reviewing this project

Three ways in, depending on how much time you have. None of them needs an account or anything sent back.

## Two minutes: read

The "In two minutes" list at the top of the [README](../README.md), including its "Not done" line.

## Ten minutes: have your coding agent check it

Point Codex, Claude Code, Cursor or any other coding agent at a clone of this repository and ask it whether the
README's numbers hold up. [AGENTS.md](../AGENTS.md) at the root tells it which checks to run and which limits to
report back. Or run them yourself:

```sh
python scripts/check_claims.py      # each headline number against the committed file it comes from
python scripts/pipeline.py status   # whether every output is fresh against what made it
```

Both use only the Python standard library and finish in under a minute.

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
