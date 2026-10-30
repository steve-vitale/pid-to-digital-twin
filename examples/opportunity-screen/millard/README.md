# Start a refrigeration question from a public report

A useful first investigation can start with a short description and a simplified diagram. This example turns
two source-authored model records into an actual E30 question and a [first-question brief](first-question.md).
It demonstrates preparation of a handoff; no company recipient, accepted ownership or measured benefit exists.

The source is the CSB's January 2015 [Millard hydraulic-shock safety bulletin](https://www.csb.gov/file.aspx?DocumentId=5933),
No. 2010-13-A-AL. Figure 5 on printed page 9 names a hot-gas main valve; section 5.2.1 on page 11 describes the
evaporator group. [model.json](model.json) keeps only that group and valve. `EVAP-GROUP` and `HG-MAIN` are authored
labels, not plant tags. The aggregate is not a complete inventory, piping model, control sequence or current plant.
The report is historical; matching its bytes does not establish which revision governs a company today.

## Ask the existing question offline

From the repository root, with Python 3.10+ and no packages, accounts or network:

```sh
python -S scripts/question_engine.py --model examples/opportunity-screen/millard/model.json --question E30 --out out/millard-first-question
```

Read `out/millard-first-question/screen.md` alongside the brief. The committed [screen](screen/screen.md) and
[question JSON](screen/questions.json) show the same result: `E30@EVAP-GROUP`, its two exact asset references and
three collection requests. Only E30 was selected. Other questions and safety functions have not been screened.

The engine finds a modeled evaporator and defrost valve without a modeled demand-initiation device. Its
"none found" statement applies to this incomplete subset. It does not prove fixed-timer operation or a missing
plant instrument. No historian signal is mapped. The energy question does not assess the incident's control logic.

## Inspect the original

Download the pinned 656,148-byte bulletin explicitly, then repeat without network:

```sh
python -S examples/opportunity-screen/millard/verify_source.py --fetch
python -S examples/opportunity-screen/millard/verify_source.py
```

The default location is `data/external/millard/bulletin.pdf` (ignored). Use `--source PATH` for a different copy.
The original URL returned HTTP 403 during preparation; the official `file.aspx` link above supplied the pinned
bytes. Future access can change. The helper refuses changed or missing bytes; it does not interpret the PDF.
[source.json](source.json) records the revision, hash and locations. Keep the original and its notices with the packet.
The CSB is a US government agency; credited third-party material can retain separate rights. The PDF is not vendored.

## Carry the result forward

Use the brief to distinguish the engine's energy request from the separate controls-record question. Keep the
source, model, generated files, unresolved requests and toolkit revision together. Assign an actual recipient and
record their acceptance in the company's chosen system when one exists. That shared system takes over continuing
ownership, access, decisions and revision history. This example adds no local governance service or connector.

[ACCEPTANCE.md](ACCEPTANCE.md) states the narrow checks. This is an additional historical refrigeration case,
inspected during development, outside the eight-workflow matrix. It does not validate real food-plant drawings,
all refrigeration questions, safe operation, engineer adoption or a company-system round trip.
