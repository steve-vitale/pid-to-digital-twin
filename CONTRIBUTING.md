# Help the toolkit generalize

This project should improve as engineers contribute new cases, model runs and methods. A useful contribution
leaves a reproducible answer to: **what task improved, on which inputs, compared with what, and what got worse?**
A new symbol, unit type, document family or difficult failure is valuable even before a tool handles it.

The [benchmark guide](benchmarks/README.md) is the entry point for model/task comparisons. The
[corpus matrix](docs/GENERALIZATION.md) measures selected deterministic workflows. The
[feature catalog](docs/FEATURES.md) records software examples and review scope. These are complementary evidence;
none stands in for all the others. Do not turn a passing software example into a model accuracy claim.

## Three ways to contribute

| Contribution | What to include | What it improves |
|---|---|---|
| A new test case | Cleared source, attribution/license, source-family identity, task, answer key and its provenance, uncertainty and split | Where the tools can be tested and where they fail |
| A model or method run | Exact attempted cases, saved answers including failures, model/version/interface, prompt/recipe hashes, settings and run dates | Evidence about which combinations work for a particular task |
| A generalization or fix | The failing case first, code/prompt/model-schema/adapter change, before/after results on the common baseline and affected cases | Capability without hiding regressions or trading away other tasks |

Use a pull request; there is no shared company workspace or account to join. Keep private company documents,
secrets, personal information and operational records out of issues, PRs and public runs. A redacted or synthetic
case must be labelled as such. For internal work, use an approved private copy and working folder.

Engineering-model extensions should carry new equipment, instruments and relationships through their affected
readers, questions, graphs, drawings and exports, with explicit unsupported cases. AI-model comparisons track
which model/version and method handles each task. Both kinds of improvement belong here; they need different tests.

## Add a case

1. Read [what was tried](docs/TRIED.md), then choose a task and the function you want to improve. Keep a source
   family distinct from individual files: ten crops of one drawing are not ten independent plant examples.
2. Freeze the source and key before evaluating the submission. Record source URL/revision, redistribution rights,
   key author/reviewer, unresolved facts, and whether the key is human-reviewed, agent-authored, derived or
   self-generated. For a new public download use the existing checksum-pinned fetcher pattern; CI does not fetch
   arbitrary URLs from benchmark manifests.
3. Add a suite case using the examples in [benchmarks/](benchmarks/). Paths are relative to the selected root.
   File references contain `path` and `sha256`; text hashes (including Python scoring code) normalize CRLF to LF,
   while binary hashes retain raw bytes.
   Input/key changes create a new comparison cohort. Keep old keys and explain corrections rather than silently
   editing them to match a model.

   To compute the fingerprint with the same implementation used by CI, run from the repository root:

   ```sh
   python -c "import sys; sys.path.insert(0, 'scripts'); from pathlib import Path; import benchmark; print(benchmark.file_hash(Path(sys.argv[1])))" path/to/file.json
   ```
4. Run known-answer controls. Drawing cases use the existing perfect/wrong-class/shifted/empty controls.
   Description-fact cases include a reference model matching the explicit fact key, plus an empty control.
   A reference derived from the submission itself is circular: it can test plumbing, not interpretation accuracy.
   Give a model only the declared task inputs and instructions, keeping case keys and reference answers out of
   its inference packet. Public availability is not proof of blindness; record actual exposure and assistance.
5. Add the case to the applicable deterministic matrix workflow or feature regression tests as well. Adding a
   benchmark case does not automatically make it applicable to every tool or add it to the existing eight-row
   matrix. If a task has no evaluator, propose its output contract, source truth, metrics and planted faults first.

For fixed claim judgments, start with the [source-support contract](benchmarks/source-support/prompt.md) and
[development suite](benchmarks/source-support-development.json). Freeze source scope, timestamps, key rationale
and admitted evidence before authoring answers. Keep the key/reference controls out of the inference packet.
Exact label accuracy includes missing claims; admitted citation IDs and a nonempty reason do not verify source
support. The supplied paraphrases scaffold this task, so distinguish it from original-document comprehension,
question usefulness and current installed-state validation. Publish genuine model attempts separately from
synthetic controls, with the actual exposure and provider/version/settings declared.

`development` means used for method work; `validation` can inform selection; `held-out` requires an actual
documented separation from tuning. Public keys cannot prove that a model or contributor never saw them. Once a
case informs a fix, retain that history and use new evidence for a subsequent generalization claim. Keep
synthetic controls and corrected results visibly separate.

## Submit model and method results

Start from a [run manifest](benchmarks/runs/claude-r5-rep1.json). Give each genuine attempt a unique ID. Preserve
the actual answer file; do not edit it into the expected answer or commit only the successful cases. Store parsed
answers suitable for public rescoring; avoid raw transcripts containing private content. The existing
[prediction format](predictions/README.md) is supported for drawing runs.

Record the exact model identifier and provider build/version when known; otherwise explicitly say it is unknown.
Also record the client/interface, prompt and recipe, reasoning/temperature/tool settings, preprocessing and
postprocessing, run date and repeat number. A model with a tracer is a pipeline result, not the model alone.
For saved drawing records, `recorded_tool` matches their tool field; recipe files use `role: main_prompt` and,
when tiled, `role: tile_preface`. Their recorded hashes must match the corresponding pinned files, not just any
file in the recipe. This checks known saved metadata; it cannot attest to unrecorded system instructions.
Record additional pinned recipe files for any method/code variant. Cost and timing values from saved records
remain optional reported measurements; unknown is not zero, and per-image time is not end-to-end review time.

The run's `cases` freezes what it attempted. A missing, invalid or failed answer on that set scores as an empty
answer and stays in the report. A newly added case that an old run never attempted is reported as **not attempted**;
it is not scored as an old model failure. Different attempted sets get different comparison cohorts. Reusing the
same answer file as another replicate of the same model/method is refused. Identical answers from independently
recorded runs are allowed; metadata remains contributor-declared rather than provider-attested.

Run scoring locally, with no model calls or accounts:

```sh
python scripts/benchmark.py --suite benchmarks/open100-validation.json --out out/my-model-comparison
python scripts/benchmark.py --suite benchmarks/description-controls.json --out out/my-description-controls
python scripts/benchmark.py --registry benchmarks/registry.json
```

Output parents must exist. Use a new output prefix; the writer refuses existing reports. `--registry` checks the
committed reports without rewriting them. `--root` selects a separate private corpus root when needed.
To add a public report, register its suite and report prefix in `benchmarks/registry.json`.

## Propose an improvement

Keep the baseline run and the candidate run on **the same frozen cases**. Compare individual tasks, source
families and failure types before quoting a pooled number. Reports retain per-case counts and show mean, range
and standard deviation across repeats; a small difference or a single run does not establish a winner. For the
existing drawing experiments, [replicate statistics](scripts/replicate_stats.py) supply the stronger uncertainty
analysis used in the published results. Do not average unrelated metrics into one model ranking.

Run the affected regression tests and benchmark checks. Record the attempted method, result, failures and verdict
in `data/attempts.json`; update generated documentation with the existing scripts. A scorer or answer-key change
needs its own review, separately from a method improvement. Scoring-code hashes enter the comparison cohort, so
an unnoticed scorer change cannot masquerade as a gain. Retain previous benchmark reports in Git history or as
versioned snapshots, and distinguish rescoring old answers from executing new model runs.

The PR should state which cases were inspected during development, what changed on the untouched baseline,
what regressed, and what remains unmeasured. Maintainers review source/key quality and the method before merging.
CI checks saved evidence offline; it does not purchase model runs, verify provider identity, approve engineering
designs or validate a plant. No single case is sufficient to claim generality.

## Keep the documentation navigable

The README introduces the package and routes readers to one first task. Do not append each new feature, case,
result or status there. [docs/README.md](docs/README.md) is the documentation index; [WORKFLOWS](docs/WORKFLOWS.md)
owns format connections, [STATUS](docs/STATUS.md) owns current implementation gaps, and [RESULTS](docs/RESULTS.md)
owns the registered research claims. Put commands in the guide that owns the task. Feature/script catalogs are
generated references; update their registries or generators rather than copying their tables into other pages.
Keep dated plans and experiment history as records. Update a canonical statement instead of adding a second
competing explanation, and check its inbound links and source/evidence bindings after a move.
