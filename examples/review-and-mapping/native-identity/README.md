# Correct native identities without losing the evidence

This fictional training packet follows two tag corrections through the local review tool. It checks software
behavior; it supplies no plant configuration, human approval, useful-question accuracy or new source family.

| Supplied record | Fictional decision | What must remain |
|---|---|---|
| PT-900, auxiliary ID `pressure-record` | Correct tag to PT-902 | Its recorded setpoints `[123,456]`, source quotations, original tag and all control/limit/line-layer relationships |
| PV-900 | Correct tag to PV-902 | Direct and split-range controller outputs, interlock action and line-layer references |
| TT-900 | Confirm the record | Its unreadable alarm metadata; confirmation does not make that metadata usable |

The [initial model](model.json), [review sheet](review.csv), [resulting model](expected/model.json) and
[change record](expected/change_record.md) are committed. The [JSON record](expected/change_record.json)
lists every migrated reference with its exact path and old/new value. Source prose still names the old tags;
review history records the correction separately. The reviewer name and decisions are explicitly fictional.

## Follow the correction offline

Python 3.10+, standard library only. Run from the repository root, using a new working folder:

```sh
python -c "from pathlib import Path; import shutil; p=Path('out/native-review'); p.mkdir(); shutil.copyfile('examples/review-and-mapping/native-identity/model.json', p/'model.json')"
python scripts/apply_review.py out/native-review/model.json examples/review-and-mapping/native-identity/review.csv --reviewer "Fictional example reviewer" --date 2026-10-30 --record-dir out/native-review/records
python scripts/graph_export.py out/native-review/model.json --out out/native-review/graph.json
python scripts/question_engine.py --model out/native-review/model.json --question C2 --out out/native-review/questions
python scripts/generate.py out/native-review/model.json --out out/native-review/exports
```

Inspect the full model diff and the named `Record:` JSON/Markdown pair. This example migrates thirteen live
references. Graph export remains valid, and C2 does not invent a missing controller for the renamed pressure
instrument. The generated seed SVG/platform staging uses the corrected tags. The committed record's `model`
location differs from the `out/native-review` working-copy location; every other record field reproduces.
The regression checks the complete resulting model and both records with only that location substitution.

Repeat the apply command: the model stays byte-identical. The first dated records stay intact; a different
run result gets a fingerprint suffix, and another identical replay reuses that record. A later decision adds
history rather than replacing the old record. Contradictory instructions, collisions, swaps/chains and ambiguous
CSV/JSON input refuse. Independent valid rows can still apply when another row refuses; inspect the exit and record.

## Reconcile the companions explicitly

This command changes this working model only. Native instrument/final-element tags are identities; extracted
twins instead keep stable asset IDs when their tag text changes. Controllers, manual valves, relief devices and
unplaced records are not additional editable collections in this review tool.

Separate detailed drawing and presentation layouts, external loop/mapping files, prior graphs/questions/context
and saved answers are not updated. Keep the original source packet. Review the exact old tag references in a
working copy of each applicable companion, then regenerate and check that output:

| Companion | Fields to reconcile |
|---|---|
| Detailed drawing layout | `units.*.mount` and route `place` tag keys, controller/interlock keys where applicable, and sheet `signals[].from/to`. Follow the layout's actual nesting. `signal_flags.*.loop` is a derived loop label; do not replace it merely because a tag changed. |
| Presentation/display layout | Unit card tag keys, unit `level`, `unavailable[].tag`, utility tag lists and analyzer parent references, where present. |
| External loop/mapping records | Explicit asset/tag joins, keeping actual point addresses and mapping provenance intact until separately reviewed. A generated address is still staging. |
| Prior graph, questions and context | Regenerate from the corrected model and refresh against retained context history; do not copy old verdicts onto new evidence. Restart a selected MCP snapshot explicitly. |

For a known TE development control, renaming FT-102/FV-102 to FT-998/FV-998 leaves the original detailed layout
invalid: sheet 101 still names FT-102 in a signal. Reconcile `sheets[0].signals[2].from` and
`sheets[0].signals[3].to` in a copied layout, retaining every other field and the derived loop labels. Then run:

```sh
python scripts/draw_pid_from_model.py --model your-reviewed-model.json --layout your-reconciled-layout.json --check
```

That specific manual reconciliation passes the layout check; it is not an automatic companion migration or a
claim of correct engineering layout. Other models/layouts need their own reviewed reconciliation.

Use [the review guide](../../../docs/REVIEW_LOOP.md) for limits and the wider workflow.
