# Prepare a single drawing, then collect extraction for review

This bounded workflow connects the [one-sheet local intake](REPLICATE_AT_YOUR_PLANT.md) to the **frozen synthetic-adaptation recipe**: Codex `gpt-6.1-sol`, exact `extraction/prompt.md`, whole sheet, no tiles or tracing, and `linked` parenting for the draft twin. It does not choose a new model or optimize a prompt.

This recipe is the one documented in [Adapt a labeled collection](ADAPT_LABELED_DATASET.md). It is **not** the separate round-2 M3 benchmark winner in [GOAL](GOAL.md), which uses prompt v2, tiling and tracing. No new accuracy comparison is made here. The six-class prediction contract, unknown directional flow and site-domain limitations still apply.

## 1. Prepare locally, without calling a model

Supply exactly one PNG already rasterized from the intended drawing page. Filenames do not need to be numeric or match other files. The drawing ID, revision and page are supplied claims, not independently verified revision authority.

```bash
python scripts/site_extraction_workflow.py prepare --image "private/Utility skid rev A.png" --drawing-id UTIL-PID-A --revision A --page 2 --out runs/site-job --check-only
python scripts/site_extraction_workflow.py prepare --image "private/Utility skid rev A.png" --drawing-id UTIL-PID-A --revision A --page 2 --out runs/site-job
```

The parent output folder must already exist and the output must be new. `--check-only` writes nothing. Preparation snapshots the image and exact prompt, records hashes, drawing identity, repository HEAD when readable, and implementation hashes. Git dirty status is deliberately not inferred: the recorded file hashes identify actual implementation bytes. PNG validation checks bounded container structure and CRCs, not full pixel decoding or drawing readability. This is a narrow input boundary, not hostile-file certification.

Keep the complete job private. File contents and filenames may be sensitive. Preparation neither uploads anything nor grants permission to transmit it. The returned next-action argument list is a suggestion only; it is not executed.

## 2. Execute only after authorization

**External boundary:** the next command sends the drawing and prompt to OpenAI through an already authenticated Codex CLI. Check your data-sharing/organizational authorization, selected account, subscription and possible costs first. A CLI command or retry flag does not grant organizational permission. This workflow neither signs in nor sets up credentials or billing, and it does not verify account charges. No API or Gemini fallback is attempted.

```bash
python scripts/site_extraction_workflow.py execute --job runs/site-job
```

This invokes the existing stricter adapter's Codex command unchanged, with the pinned model, image-only temporary folder, read-only sandbox, ignored user configuration, disabled shell/unified execution/web search, and the exact prepared prompt. It does not use the generic runner's looser defaults. Missing CLI, unavailable authentication, a reported-model mismatch, timeout, invalid prediction or nonzero exit stops the workflow. The CLI's reported model/provider are recorded evidence, not independent verification of server behavior. Reasoning settings are not independently verified. The historical adapter's `api_spend_usd=0` field is retained as a supplied claim, not billing proof or a guarantee of zero cost.

Every invocation creates a new `attempt-0001`-style folder. Existing attempts are never overwritten. Failures retain their available response/log plus a failed status; interruption before final status leaves an incomplete attempt. A partial result or incomplete status cannot be collected. If another external attempt is authorized, name the prior attempt explicitly:

```bash
python scripts/site_extraction_workflow.py execute --job runs/site-job --retry-of attempt-0001
```

No automatic retry or transport substitution occurs. Implementation changes after preparation block execution; prepare a new job under the new code. Local conversion can be retried without executing a model by collecting the same successful record into a new bundle.

## 3. Collect and validate locally

```bash
python scripts/site_extraction_workflow.py collect --job runs/site-job --record runs/site-job/attempts/attempt-0001/0.json --evidence cli-replay --out out/twin/site-review --check-only
python scripts/site_extraction_workflow.py collect --job runs/site-job --record runs/site-job/attempts/attempt-0001/0.json --evidence cli-replay --out out/twin/site-review
```

Collection never calls a model. It checks image/prompt hashes, frozen recipe metadata, reported model and prediction contract, then creates the intake JSON automatically and invokes the existing importer. Check-only tests evidence, **not** conversion or rendering. Collection stages the bundle, validates/renders it and publishes to a new local directory only after success. Concurrent writers to the same destination are unsupported. Existing outputs, including reviewed bundles, are refused; reviewed state is never overwritten or automatically copied to new extraction.

`extraction_handoff.json` retains recipe, source identity/hashes, prepare/collect implementation hashes and supplied execution claims. Original response JSON and prepared prompt are retained in `source/`; local workflow attempts also contribute their status/log. References inside an external record are preserved as text, not followed or materialized. External receipts are supplied evidence, not authenticated producer attestations. Keep the original job/attempts as the full run archive.

The bundle is **unverified and unmapped**. Review columns remain blank; unknowns stay unknown. A false operational-readiness flag is descriptive metadata, **not a technical deployment interlock in independent tools**. Structural validity does not establish engineering correctness. Qualified review, class/role interpretation, point identity/ranges/quality, native import and operational acceptance remain separate. No gateway/deployment entrypoint is provided here. See [Review loop](REVIEW_LOOP.md).

### Preserved native output and offline checks

A supplied native-agent result may be collected with `--evidence native-replay` only when its original access-path, reasoning uncertainty and recipe-deviation fields are present. It is never relabeled as CLI success. The already available Synthetic development sheet 0 plus its preserved native record can test local wiring without new model calls:

```bash
python scripts/site_extraction_workflow.py prepare --image "data/external/pid2graph/PID2Graph/Complete/PID2Graph Synthetic/0.png" --drawing-id PID2GRAPH-SYNTHETIC-0 --revision published-sample --page 1 --out runs/site-synthetic-replay
python scripts/site_extraction_workflow.py collect --job runs/site-synthetic-replay --record runs/pid2graph-synthetic-adaptation/codex-native/0.json --evidence native-replay --out out/twin/site-synthetic-replay
```

These data/receipts are local and ignored by Git, not guaranteed in a source-only checkout. Do not download reserved samples to replace them. Dataset-derived artifacts retain the Synthetic collection's CC BY-SA attribution/licensing described in the adaptation guide. This is a **replay of existing extraction**, not a new model run, accuracy result or generalization test.

```bash
python -S scripts/test_site_extraction_workflow.py
```

Contract tests use authored synthetic predictions and **mock every execute subprocess**. No model, network, installation, gateway or paid operation runs. `--evidence contract-fixture` exists for those explicit fixtures; its bundle is prominently marked synthetic and provides no extraction-quality evidence. Fake process receipts used inside tests remain confined to disposable test folders.
