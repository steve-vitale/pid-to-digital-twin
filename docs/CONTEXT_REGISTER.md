# Keep engineering context beside the documents

`scripts/context_register.py` is a local, standard-library tool for keeping an engineer's answers beside an existing
model and its questions. It keeps the base model unchanged. It writes a versioned JSON sidecar, a readable report,
and copies of the graph and questions with the context attached. No accounts, network, model calls or plant imports
are involved.

Start with documents worth trusting, an identity model, and questions that an engineer actually needs answered.
The tool does not decide whether a document is authoritative, choose an owner, or infer an answer from nearby prose.
Its job is to make the decision, its responsibility and its evidence travel together, and to reopen the affected
answers when that evidence changes.

Start with the [small offline example](../examples/context-register/illustrative/README.md), then the
[public PRONTO document packet](../examples/context-register/pronto/README.md). The first uses invented training
sources; the second preserves qualified statements from four public originals. Neither is a person's sign-off.
The [question-engine bridge](../examples/context-register/bayer/README.md) also runs an actual generated E18 finding
through this workflow, retaining a source-backed partial answer and the original collection prompts.

## The engineer's steps

1. Keep the original source documents locally. Give each document a stable identity and a revision, and list the
   exact places that can support the questions. Record a drawing detail, report page and paragraph, spreadsheet
   sheet and cell, or event record and timestamp. A locator is an explicit human reference, not an automated check
   that the cited passage supports the answer.
2. Prepare an answer sheet and current evidence choices. Assign a responsible person or role, or leave the question
   marked **needs owner**. Copy a source, locator and fingerprint from the choices into each proposed answer.
3. Record the answer, its scope, and its canonical claim value. A reviewer explicitly records whether the answer
   matches its source. Plant truth stays **unknown** until someone explicitly records a plant check.
4. Apply the sheet. Read the report, including unanswered questions, requests for more data, disputed values and
   stale decisions. Keep `context.json`; it contains the history that the next run needs.
5. When a source or model changes, refresh the register. Affected answers reopen. The named owner reviews the new
   evidence, prepares a fresh sheet and records a new decision. Export the sidecar and enriched graph together for
   another engineer or system to use.

An owner is responsible for resolving the question; a reviewer records a decision about an answer. These are
different fields and responsibilities. The same person may perform both roles. The software does not authenticate
either identity or supply an owner on the engineer's behalf.

## Prepare a sheet

The model can be this repository's process model, an extracted twin, or an existing `twin-graph-1` export. Questions
use the shape produced by `question_engine.py`: a `questions` list containing a stable `id`, `question` wording, and
`assets: [{"id": "P-1"}]`. Use exact graph asset ids, including `stream:S1` for a stream. A question without assets
binds to the `PLANT` node. Explicit `evidence[].id` asset references also become dependencies. Unknown or duplicate
identities are refused; tags are never guessed as aliases.
Identifiers and references with leading or trailing whitespace are refused rather than silently trimmed, so graph
ids and question references keep exact joins. Internal spaces in identifiers and intentional prose are preserved.

An example source manifest (illustrative, not plant evidence):

```json
{
  "schema": "context-sources-1",
  "documents": [
    {
      "id": "operating-manual",
      "revision": "A",
      "path": "manual.pdf",
      "locators": [
        {
          "id": "pump-pressure",
          "locator": "printed page 12, section 3.2, second paragraph",
          "questions": ["pressure@P-1"]
        }
      ]
    }
  ]
}
```

`path` is local configuration, relative to the manifest's folder. Use `--source-root FOLDER` when documents live
under another local root. Paths must resolve within that root, including through symlinks. The tool reads each
source's actual bytes and calculates SHA-256. An optional document `sha256` must match those bytes. A missing file
or mismatched expected hash stops the run. The tool never substitutes a previously recorded hash for missing bytes.
All documents, locators and explicit question bindings are checked before output writes, including unused entries.
Omitting a locator's `questions` makes it available for every current question; list question ids to keep a large
source pack's choices manageable.

```sh
python -S scripts/context_register.py prepare --model plant_model.json --questions questions.json --sources sources.json --out context
```

The command writes:

| File | Use |
|---|---|
| `answers.csv` | One initially unanswered row per current question; edit or duplicate rows for answers |
| `evidence_choices.csv` | Copy `source_id`, `locator_id` and `evidence_fingerprint` from a matching question's row |
| `evidence_choices.md` | The same choices with readable document revision and locator |
| `context.json` | Persistent register, immutable decision snapshots and ownership history |
| `context.md` | Current questions, owners, answers, disputes and staleness reasons |
| `enriched_graph.json` | A graph copy with questions and context attached |
| `enriched_questions.json` | A questions copy with context attached |

The answer sheet has these columns, in this order:

```text
question_id,answer_id,claim_key,value,answer,answer_state,decision,owner,assigned_by,assigned_on,reviewer,reviewed_on,source_id,locator_id,source_match,plant_truth,note,evidence_fingerprint
```

Fill the fields deliberately:

| Field | Meaning |
|---|---|
| `question_id` | Exact prepared question instance id, not just its catalog category |
| `answer_id` | Stable id for this answer; different independent answers need different ids |
| `claim_key` | Engineer-defined comparable claim slot, such as `alarm-high-limit` |
| `value` | Canonical value for that slot, including units where needed, such as `50 kPa` |
| `answer` | Explanation, scope and qualifications in the engineer's own words |
| `answer_state` | `partial`, `needs_data` or explicitly `answered` |
| `decision` | `proposed`, `accepted` or `rejected`; acceptance/rejection requires reviewer and review date |
| `owner` | Responsible person or role; `needs_owner` explicitly clears assignment; blank preserves it |
| `assigned_by`, `assigned_on` | Explicit assigner and ISO date `YYYY-MM-DD` for an actual ownership change |
| `reviewer` | Person or role explicitly recording the verdict; may be the owner |
| `reviewed_on` | Explicit review date `YYYY-MM-DD`; required with a reviewer |
| `source_id`, `locator_id` | One prepared document/locator choice for this question |
| `source_match` | `unknown`, `match`, `mismatch` or `unclear` |
| `plant_truth` | `unknown`, `confirmed` or `wrong`; nonunknown requires source match, reviewer and review date |
| `note` | Reason for the decision, remaining work, or how a plant check was made |
| `evidence_fingerprint` | Copy the current fingerprint; do not recompute it to carry an old approval forward |

For a nonblank answer, blank state/verdict fields default to `partial`, `proposed`, `unknown`, `unknown`. The
prepared empty rows use `needs_data` to invite collection. A row with just the question and owner assigns ownership
without creating an answer. A change to the responsible owner also requires the actual assigner and assignment
date; the tool never treats the owner or reviewer as the assigner by inference. An initially unassigned question
needs no invented assignment event. No acceptance is implied by filling prose that says "complete" or "yes".

The `claim_key` and `value` are explicit comparison inputs. Different explanatory wording with the same canonical
value does not create a dispute. Different nonrejected values for the same question and claim slot do. The software
does not normalize units, decide that two phrases are equivalent, or determine which source wins. Use separate
claim slots for different aspects of a question. Canonicalization is an engineer's responsibility.

## Apply and keep the history

```sh
python -S scripts/context_register.py apply --model plant_model.json --questions questions.json --sources sources.json --answers context/answers.csv --register context/context.json --out context
```

The existing register is explicit. A new output directory, or a prepared directory whose register has no decision
or ownership history, can start without `--register`. Once either history exists at the destination, omitting
`--register` refuses before writing. Pass its current `context.json` as above. An invalid existing destination
register also refuses rather than being replaced.

If the destination already holds history, every retained decision and ownership record must be an unchanged,
ordered prefix of the computed result. An older or divergent register cannot silently replace later work.
Use the destination's current register to continue, or a fresh output directory for an intentional fork. There is
no automatic merge or reset option. These checks protect known files during a single local invocation; they are
not locking, atomic publication or protection against concurrent writers. Keep backups and coordinate edits.

Identical input and identical decisions produce identical files without duplicate history entries.
Reusing an `answer_id` explicitly revises that answer; the previous record and its evidence remain in history. Use
a different id for another source's independent answer. To resolve a dispute, an engineer can explicitly revise or
reject the unsupported answer; rejection remains visible in the history. Unmentioned answers and owners persist.

Question state is `unanswered`, `partial`, `needs_data`, `answered` or `disputed`. Only an explicit **accepted**
answer with state **answered** and source match **match** can make a current question answered. Accepted partial
or needs-data responses can retain unclear or mismatching source verdicts. A conflicting canonical claim keeps it
disputed. "Answered" records an accepted response's completeness; it is not a certificate of source correctness,
plant truth, safe operation or regulatory compliance. A source match alone never confirms plant truth. Explicit
plant truth **confirmed** or **wrong** requires a source match plus an attributed, dated review. The two verdicts
remain visible separately, including an unknown plant truth. Historical plant truth records a check made on the
recorded review date; current matching source bytes do not make it a fresh site verification. Ownership remains
visible independently of question state.

Any current, nonrejected response explicitly marked `needs_data` keeps the question in `needs_data` even if another
response was accepted as answered. An engineer must settle that outstanding request explicitly. Disputes take
precedence over both states.

For question-engine screens, the report also keeps each collection prompt's item, detailed fields, how and where,
with structured collection locations shown as readable kind and description, plus the original decision rule and
limits. These are the screen's collection prompts, not per-request completion tracking;
recording an answer does not automatically satisfy or clear them. Their exact content remains in the enriched
question JSON for the engineer to carry forward.

Each immutable decision includes its question id, answer id, owner at the time, reviewer, review date, verdicts, note,
predecessor decision id, and the full evidence snapshot. That snapshot binds:

- Question content and every explicitly referenced asset's content and incident graph relations.
- Document identity, revision, SHA-256 of raw source bytes, locator id and exact locator text.
- An evidence fingerprint over that snapshot. The decision's own id hashes the complete decision and predecessor.

History hashes detect accidental or uncoordinated edits. They are not signatures or tamper-proof storage: anyone
with write access can replace a register and recalculate hashes. Keep backups and use the organization's document
and access controls when records need stronger assurance.

Hash agreement is separate from structural validity. The tool also checks record fields, nonempty identities,
explicit dates and actors, asset content objects, question-to-asset references and incident relation structures.
A correctly hashed malformed record is still refused before output writes. Relations may cite neighboring asset
identities outside the question's asset set; the historical snapshot does not claim to contain an entire old plant.

## Incoming revisions reopen affected answers

Refresh currentness without submitting answers:

```sh
python -S scripts/context_register.py apply --model plant_model.json --questions questions.json --sources sources.json --register context/context.json --out context
```

A document's revision, bytes or locator changing makes dependent decisions stale. Changing a question's wording,
request or referenced asset content does the same. Removing a question or its source binding preserves the old
decision and marks its absence. A different question, an unrelated asset or a review `status` change does not stale
unaffected decisions. Generated edge numbering and relation ordering are ignored; changed relations incident to a
referenced asset are bound. Because raw bytes are bound at document level, changing any part of a cited document
reopens every decision citing that document. This is deliberately conservative.

When a manifest pins an expected `sha256`, a changed file first causes a hash-mismatch refusal. Check the incoming
document, deliberately update its revision and expected hash, then refresh the preserved register. Do not remove
the pin just to make a failed run pass. This release step identifies which current source pack the owner is reviewing.

Old accepted decisions never become approvals for different current evidence. The report excludes stale decisions
from current answers and says why they reopened. An old answer CSV submitted against changed evidence is refused
before any output write. Prepare a fresh review folder, preserving the register:

```sh
python -S scripts/context_register.py prepare --model plant_model.json --questions questions.json --sources sources.json --register context/context.json --out context-review-B
```

The owner checks the current source, copies its fresh fingerprint, and explicitly records the response and decision
again. Apply the new sheet using the preserved current register:

```sh
python -S scripts/context_register.py apply --model plant_model.json --questions questions.json --sources sources.json --answers context-review-B/answers.csv --register context/context.json --out context
```

`prepare` refuses to overwrite an existing `answers.csv` so a refresh
cannot silently erase an engineer's work. **Current** means the evidence matches the recorded snapshot. Exact
evidence reversion matches its previous snapshot again, as an explicit software control verifies. There is no source
watcher, expiry, record of every intervening change, irreversible approval revocation or formal change-control state
machine. A source file changing and changing back between runs is not observed.

## Versioned handoff and limits

The interchange contract is `context-register-1`, with source manifests `context-sources-1`, a `twin-graph-1` enriched
graph, and the original questions format plus a `context` field. Asset, question, document and locator ids come from
the supplied inputs and must be maintained across revisions. Answer ids identify an engineer's logical answer;
decision ids identify immutable versions. `current` is a rebuildable view of present questions and each latest
answer's freshness. `decisions` and `ownership_history` are the persistent records. Consumers should preserve all
history, verify the schema, show unknown/disputed/stale states and keep source-match separate from plant-truth.
Ownership history carries explicit assigner and assignment date; decision history carries explicit reviewer and
review date. A receiving system must not replace either with an inferred identity or a file modification time.

For an organization using a central authority, this local register is a workbench and return packet. Its
user-entered acceptance/ownership fields do not become authenticated organizational approval on import. Preserve
the local history, reconcile identities and stage changes through the receiving authority. The
[context lifecycle](CONTEXT_LIFECYCLE.md) explains the versioned snapshot and generation-return pattern, including
the different update rules for original records, generated views and authored documents.

Export `context.json`, the enriched graph and questions, and the source pack under the receiving organization's
document controls. Manifest roots and local file paths are not automatically embedded in exports. Intentionally
entered names, role identifiers and prose are preserved; choose what is appropriate to share. There is no live
sync, connector, automatic approval, ontology alignment or downstream-system integration in this tool. Unknown,
ambiguous, malformed or unbound legacy records are refused; existing statement-review approvals are not imported.

This first version supports one source locator per answer, explicit string values for comparison, and whole-asset
dependencies. It is not a multi-source proof system, an engineering calculation engine or an authority to operate
a plant. Replacing the register loses history. Output validation happens before writing; filesystem failures can
still interrupt a multi-file write, so retain the previous register when moving files between systems.

Run the self-contained offline controls:

```sh
python -S scripts/test_context_register.py
```

They create **illustrative** documents and people in a temporary folder, prepare and apply answers, plant a
conflicting canonical value, explicitly reject it, revise the source bytes, and verify that the old approval cannot
be applied. Other controls check unchanged base files, unknown references, malformed legacy records, independent
verdicts, ownership, idempotence and selective staleness. These are software controls, not measured engineering
review time or a plant validation. The public PRONTO transfer packet in `examples/context-register/pronto/` uses
actual source documents and requires their separately fetched local bytes; its proposed answers do not claim a
human owner or current plant truth.
