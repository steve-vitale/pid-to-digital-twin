# A reviewed model produces a consistent next bundle

This example follows a correction through the seed model's SVGs, Ignition tags and PI staging. A rejected item
leaves those outputs. Its independently eligible children remain visible with ownership unknown and their original
signal-address claims retained. This makes the next generated packet reflect the recorded review.

The source is the repository's Tennessee Eastman **simulation model**. The decisions in `reject.csv` and
`reconfirm.csv` are **fictional software controls**, not corrections to the simulation's engineering, a person's
plant review, a native import or an operational change. No plant, gateway or historian is contacted.

```sh
python -S examples/review-and-mapping/seed-refresh/demonstrate.py
```

The command copies the model into a temporary directory and uses the actual `apply_review.py` and `generate.py`
CLIs. It checks the three committed [expected files](expected/expected.json); the default never rewrites them.
`--write` deliberately regenerates them after the declared checks pass. Standard library only, offline, no accounts.

| Fictional decision | Next bundle |
|---|---|
| Reject U-100 | Its unit instance, PI element and SVG disappear. Incident streams leave the overview; no battery-limit replacement or new connection is inferred. |
| Reject FT-101 and FV-119 | These two signals leave the platform files and SVGs. Their source records and decisions remain available for review. |
| Reject S9 | Its drawn connection disappears and its decision is retained in the review sheet and projection report. |
| Keep the other U-100 children eligible | FT-102, FT-103, FV-101, FV-102 and FV-103 appear in `_Unassigned`, a display/transport container with unknown engineering ownership. |

Read the [projection report](expected/seed_review_projection.json) for each child's **old → new exported path**
and unchanged OPC server/item and PI point claims. The [unassigned SVG](expected/_Unassigned.svg) labels the
previous owner as rejected. Paths change; address claims do not. Seed addresses follow this model's convention:
they are not proof that the points exist or that a deployed system's overrides have been retained. Deployment
overrides are absent from the source model and must be reconciled separately before a lab import.

The control also checks 13 historical unreviewed artifact contents unchanged, repeats review/generation without
changes, refuses a manual SVG edit without modifying any temporary file, then explicitly reconfirms the four
records. The original paths and addresses return, the obsolete unassigned SVG is retired, and intervening review
history stays in the model. The original source file is unchanged throughout.

## Maintain your own generated bundle

Use a private copy of your model and a **dedicated generated-output directory**. Keep authored documents, source
models and filled review CSVs outside it. The first command establishes its generated-file inventory:

```sh
python -S scripts/generate.py my-model.json --out my-generated
python -S scripts/apply_review.py my-model.json my-review.csv --reviewer "Name and role" --record-dir my-records
python -S scripts/generate.py my-model.json --out my-generated
```

Use the same output directory for later revisions. Inspect `seed_review_projection.json`, the generated review
sheet and the platform files before continuing. UDT and member names are allocated from the complete source before
rejection filtering, so rejecting a naming competitor does not rename a surviving signal. Rejected records and
source/history stay complete. The seed review sheet historically omitted unreviewed streams; a stream with a
supplied review is now retained in the sheet so its decision can be revisited.

`seed_export_manifest.json` lists generated artifacts with SHA-256 over UTF-8 content normalized from CRLF to LF.
Refresh checks existing managed files against it, renders the whole next bundle, then retires obsolete managed
files. Unrelated non-artifact files remain untouched. A changed managed file, an untracked SVG/tag export, an
invalid inventory, conflicting file/parent, output alias or known source-model collision refuses **before writes**.
These checks protect a local invocation; they provide no concurrent-writer lock, atomic transaction, signed
provenance or authenticated approval. Preserve the folder after any filesystem failure and inspect it before retrying.

For a legacy folder without an inventory, adoption succeeds only if existing generated files match the newly
rendered contents. Otherwise preserve that folder and generate into a fresh directory, then compare the packets.
Do not delete edited artifacts or the inventory just to make a refusal pass. Bring accepted edits into their
authoritative source or retain them as separate authored documents, following the [lifecycle guide](../../../docs/CONTEXT_LIFECYCLE.md).
`_Unassigned` is reserved when orphaned children need that container; a source unit with that ID is refused rather
than silently merged. Missing/unverified reviews remain eligible; local names and review statuses do not grant authority.

This repair covers the hand-built model branch of `generate.py`. Extracted twins keep their existing export route.
It does not regenerate the repository-specific Ignition gateway demo, P&ID drafting, mimic/3D tools or an incumbent
system. Use each tool's declared workflow and acceptance checks for those outputs; the bundle remains a draft.
