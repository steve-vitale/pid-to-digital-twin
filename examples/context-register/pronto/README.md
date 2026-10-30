# PRONTO linked-document context packet

This example attaches 22 proposed source statements to 21 engineering questions over 11 stable asset identities. It links four original documents from the existing public PRONTO corpus: the technical report and schematic, DeltaV alarm settings, operation log, and day-3 alarm/event journal. It adds linked-document coverage within PRONTO, not a new source family or new plant.

The packet, questions and decisions are illustrative AI-authored drafts. No engineer has signed them off. Every proposed answer leaves its human owner and reviewer blank and its plant-truth verdict unknown. The identity model is deliberately incomplete: it asserts no complete topology or resolved control-loop pairing.

Read the [committed context report](expected/context.md) before downloading anything. It is the proposed packet's
readable result, with every answer's source revision, exact locator and remaining uncertainty.

The [prior register](history/before-appearances.context.json) retains the original 22 proposal snapshots unchanged.
The current 22 AI re-proposals bind expanded item evidence; 44 snapshots remain in history with the same active
answers and unresolved questions. The [old answer sheet](history/before-appearances.answers.csv) refuses against
the revised evidence. No human review or plant-truth verdict was carried onto a new fingerprint.

From the repository root, fetch the pinned originals if they are not cached:

```sh
python scripts/fetch_corpus.py pronto
python scripts/fetch_corpus.py pronto-more
```

The public fetch is the only network step. It selectively retrieves pinned members of the Zenodo ZIP and checks their hashes. Original files stay in ignored `data/external/`; missing files cause a clear failure. The derived key is not substituted for missing originals. The separate small illustrative example in the parent directory provides the no-download route.

Run the register offline:

```sh
python -S scripts/context_register.py prepare --model examples/context-register/pronto/model.json --questions examples/context-register/pronto/questions.json --sources examples/context-register/pronto/sources.json --source-root data/external --out examples/context-register/pronto/run
python -S scripts/context_register.py apply --model examples/context-register/pronto/model.json --questions examples/context-register/pronto/questions.json --sources examples/context-register/pronto/sources.json --source-root data/external --register examples/context-register/pronto/history/before-appearances.context.json --answers examples/context-register/pronto/proposed_answers.csv --out examples/context-register/pronto/run
python -S examples/context-register/pronto/check_packet.py
```

`prepare` refuses to overwrite an existing `answers.csv`; choose a new folder when preparing a fresh revision. The supplied proposed-answer CSV is a reproducible example bound to the pinned files. It was not completed by an engineer. Open `run/context.md` for the readable register or `run/context.json` for the retained decisions and evidence snapshots. The enriched questions and graph use the same asset identities; the original model is unchanged.

Freshness `current` means the present inputs match the answer's recorded snapshot. Restoring the exact old document and revision can make its answer current again. Refreshes do not capture intervening changes, and a recorded plant-truth verdict remains a dated historical judgment.

The declared checks are in [ACCEPTANCE.md](ACCEPTANCE.md). The first run returned one disputed question, two requiring data, and eighteen partial questions. All 22 proposals remained unapproved and all 21 questions needed an owner. Synthetic report revision copies made exactly six dependent answers stale while sixteen unrelated answers stayed current. Synthetic alarm-setting revision copies made exactly seven dependent answers stale while fifteen stayed current. Both refreshes retained the original decision history. These are deterministic development checks, not a measurement of engineer review time or extraction accuracy.

Three examples explain why the context stays qualified:

- PT312 has numerical HiHi/Hi entries 95/90 in `Sheet1!C16:D16`, while `G16` says scale 0-15 bar and **not enabled**. The packet preserves the values and their uncertain engineering interpretation. It does not manufacture an enabled pressure alarm. FIC301 and FT305 supply two more disabled-limit controls. LI101 and TT402 lack positive enablement evidence; silence is not treated as an enabled flag.
- Figure 1 on PDF page 5 draws FT302 with FIC301. Journal record 216, physical line 217 including the header, describes FIC301 as operating via FIR305 (High). Both statements remain visible under the same question. FIR305 is not silently equated with FT305. The authoritative measurement pairing and distinct output tags remain unresolved.
- The Test5_0 opening field names V11, while later movement fields name V10. They stay separate IDs. The example does not decide whether the log contains an error or refers to different valves. Historical module-health alarm events also remain separate from process-limit enable flags and current alarm state.

`source_key.json` records every document ID, record version, raw-byte SHA-256, exact cell/page/record locator, expected primary-source value, and limitation. To check its transcriptions against the originals:

```sh
python examples/context-register/pronto/verify_sources.py
```

The verifier uses the standard library for raw hashes, XLSX cells and TSV records; PDF text checks also require `pypdf`. With the bundled runtime it verified four original hashes and 21 facts automatically with no mismatches. Figure 1's FIC301 branch is explicitly left for separate visual verification. A fresh independent coding agent checked all 22 facts against the originals, including a separately rendered Figure 1. That is independent agent review, not human sign-off. A zero exit code from this verifier means the available automatic checks matched; it does not count that figure as automatically verified.

The Zenodo API was checked on 2026-10-29: record `1341583`, publication date `2019-05-16`, access `open`, license `cc-by-4.0`. Document revisions use that immutable record plus the actual file hash; they do not invent a manufacturer revision. Derived key, questions and transcriptions are provided under CC BY 4.0 with this attribution:

A. Stief, R. Tan, Y. Cao, J. R. Ottewill, N. F. Thornhill, J. Baranowski, *A heterogeneous benchmark dataset for data analytics: Multiphase flow facility case study*, Journal of Process Control 79 (2019), 41-55, [doi:10.1016/j.jprocont.2019.04.009](https://doi.org/10.1016/j.jprocont.2019.04.009). Data: [PRONTO heterogeneous benchmark dataset, doi:10.5281/zenodo.1341583](https://zenodo.org/records/1341583), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The source files have not been modified; the packet extracts selected facts, adds explicit limits, and creates illustrative questions and proposed answers.
