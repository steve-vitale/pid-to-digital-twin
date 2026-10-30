# NIST SMS Test Bed context packet

This small example links original NIST manufacturing evidence from a source family separate from PRONTO and Bayer: two published Hurco04 device configurations and an archived raw operating log. Eight questions carry ten AI-authored proposed answers. A fourth pinned file preserves the upstream repository description and reuse notice. The originals total 121,831 bytes and stay in the ignored cache.

The discovery opened these files before the packet criteria were declared. This is a development example, not a held-out transfer result. [ACCEPTANCE.md](ACCEPTANCE.md) states the prospective packet checks and the observations already seen. The model, questions, answer proposals and checks are coding-agent work with no human sign-off.

The two configurations both publish machine name `Hurco04` and UUID `mtc_adapter008`. That machine identity joins the documents. Data-item identities need their document revision: the older `Hurco04-path_7` means `current_tool` / `TOOL_NUMBER`; the later one means `Program_Runtime_Seconds` / `ACCUMULATED_TIME` / `SECOND`. The packet assigns different revision-scoped claim keys to these observations. It creates no permanent signal alias and no automatic simultaneous contradiction.

The log has actual recorded spindle/feed values and explicit missing-state controls. `UNAVAILABLE`, numeric zero and a single blank program-name space remain different values. Its filename is not the boundary of all timestamps inside it. A recorded `READY` status and later missing status do not establish a named production job or complete operating-state coverage. The log does not identify the deployed configuration revision; that question remains open.

The [prior register](history/before-appearances.context.json) retains ten original proposal snapshots. Ten new
AI re-proposals bind expanded item evidence, preserving all twenty snapshots and the same active answers.
The [old sheet](history/before-appearances.answers.csv) refuses against the revised evidence; no human review,
owner assignment or plant-truth verdict was added.

## Start with one source question

The [plain first-question brief](first-question.md) asks which deployed configuration and adapter mapping explain
the selected archive. It keeps the revision-scoped signal meanings, partial answer, missing records and intended
recipient together. No asset model, generated question or context register is needed for that first handoff.

From the repository root, fetch the four pinned originals once:

```sh
python -S examples/context-register/nist-smstestbed/fetch_sources.py --max-mb 1
```

The packet-local `fetch.json` registry calls the existing public pinned-file fetcher as a library and checks byte counts and SHA-256. It changes no global matrix fetch registry and adds no HTTP implementation. It requires no account or agreement. The live VDS endpoints were unavailable during discovery; this example uses the immutable official archive and makes no live-service claim. Missing cached originals cause a clear failure; the derived key is not substituted for them.

Check the originals offline before interpreting them:

```sh
python -S examples/context-register/nist-smstestbed/verify_sources.py
```

That command checks original bytes and the existing explicit XML/raw-record expectations. It does not establish
the deployed configuration or approve a mapping. Read the cited lines, retain the originals and source manifest
with the brief, and ask the intended owner for the missing deployment record. Carry the draft into the company's
shared context and decision system as others contribute. The [first-question guide](../../first-pilot/README.md)
explains the recipient, evidence and handoff fields; unassigned ownership stays **needs owner**.

## Optional: reproduce the local context example

The commands below exercise the existing model/register example and its dependency checks. The plain first
question and company handoff above do not require this local setup. Run offline with Python's standard library:

```sh
python -S scripts/context_register.py prepare --model examples/context-register/nist-smstestbed/model.json --questions examples/context-register/nist-smstestbed/questions.json --sources examples/context-register/nist-smstestbed/sources.json --source-root data/external/nist-smstestbed --out examples/context-register/nist-smstestbed/run
python -S scripts/context_register.py apply --model examples/context-register/nist-smstestbed/model.json --questions examples/context-register/nist-smstestbed/questions.json --sources examples/context-register/nist-smstestbed/sources.json --source-root data/external/nist-smstestbed --register examples/context-register/nist-smstestbed/history/before-appearances.context.json --answers examples/context-register/nist-smstestbed/proposed_answers.csv --out examples/context-register/nist-smstestbed/run
python -S examples/context-register/nist-smstestbed/verify_sources.py
python -S examples/context-register/nist-smstestbed/check_packet.py
```

`prepare` refuses to overwrite an existing prepared CSV; choose another output folder to prepare a fresh revision. The supplied proposal CSV is an illustrative record bound to these exact inputs. No human filled it in. All owner, assigner, reviewer and review-date fields are blank, every decision is proposed, and every plant-truth verdict is unknown.

The first apply above follows an empty prepared register. Subsequent applies into `run` must include
`--register examples/context-register/nist-smstestbed/run/context.json`. The tool refuses to replace retained
decision or ownership history with a missing, older or divergent register. Use a new directory for a deliberate
fork; it does not merge histories.

The separate history regression check uses these actual pinned originals and disposable working folders:

```sh
python -S examples/context-register/nist-smstestbed/check_history.py
```

[expected_history_checks.json](expected_history_checks.json) records the development result: ten initial proposals,
an eleven-decision synthetic note revision, refusal of omitted or older registers with all working files unchanged,
byte-identical refresh using the current register, and an explicitly separate older-history fork. The original
sources remain unchanged. This checks local software preservation, not authenticated approval, concurrent writers
or organizational adoption.

Read `run/context.md` for the questions, answers, missing data and exact evidence bindings; `run/context.json` retains the decisions and evidence snapshots. `run/enriched_questions.json` and `run/enriched_graph.json` carry the same machine identity and contexts. [expected_context.md](expected_context.md) records the expected readable development report for the pinned inputs. The original identity model is unchanged.

`verify_sources.py` parses the original XML and raw records using explicit primary-source expectations; it never reads the generated answer CSV or derived key. `check_packet.py` checks the ten bindings, machine join, revision-scoped meanings and missing-state controls. It copies and revises each actual source in turn: the expected stale-answer counts are three for the older configuration, three for the later one, four for the raw log and zero for an unrelated reuse-notice change. It also checks that history survives and that a mismatched raw hash or an unregistered reused signal-as-asset is rejected. Synthetic copies stay under ignored `.work/`; the original files are unchanged.

The development run on 2026-10-29 matched those checks: all four original hashes and ten parsed primary-check groups passed. The register had five partial questions, three requiring data and no disputed questions. All eight needed an owner and all ten decisions remained proposals. Synthetic source changes produced exactly the 3/3/4/0 stale-answer counts above, preserved decision history and passed both rejection controls. The readable report also matches the committed expected record. These are development consistency results; independent original-source review is a separate check.

Freshness `current` means the present inputs match a decision's evidence snapshot. Exact restoration of an old source and revision can match that snapshot again. The tool captures no intervening changes between refreshes. Historical judgments remain dated records. This packet establishes no current machine condition, human ownership, approval, production truth, complete deployment history or measured review-time benefit.

## Source and attribution

The [official NIST SMS Test Bed page](https://www.nist.gov/laboratories/tools-instruments/smart-manufacturing-systems-sms-test-bed) describes the facility and its data services. Source bytes come from the [official usnistgov/smstestbed repository](https://github.com/usnistgov/smstestbed); `sources.json` and `source_key.json` contain immutable source URLs, revisions, hashes and exact physical-line/XML locators. The source key is a derived transcription, not an independent source or replacement for the originals.

The [pinned upstream notice](https://github.com/usnistgov/smstestbed/blob/968279f14ebe96c03c8877eeb1901cf6b4c8fbab/README.md#L28-L46) permits copying or distributing its public information, with an exception for material marked copyrighted, and requests appropriate credits. It separately specifies notices for NIST-developed software and its status within the United States. The selected files contain no copyright marking. This example preserves that notice and attributes the source to the National Institute of Standards and Technology, Smart Manufacturing Systems Test Bed. It assigns no SPDX license or blanket public-domain label to the source material. No original source file is redistributed here; the packet extracts selected facts and adds illustrative questions, limits and proposed answers.
