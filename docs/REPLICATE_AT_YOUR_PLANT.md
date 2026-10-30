# Replicate the approach at your plant

Start with public data on a separate learning copy. Then decide whether a small, reviewed pilot on your own drawings is worthwhile. You can follow the learning path yourself; help from the repository author is optional. A site pilot still needs qualified plant engineering and operations reviewers. Neither path establishes a production-ready twin.

## 1. Know which demonstration you are copying

- **OPEN100:** drawing extraction, measured against published graph labels, followed by draft asset/export files. Its mapped values are synthetic, not plant signals.
- **Tennessee Eastman (TE):** a **hand-built seed model**, verified against the simulator source (tag names and units; units, streams, flow directions and tag ownership), and generated screens driven by **recorded simulation replay**. The TE model and screens were not extracted from OPEN100. Replay is not a live process simulator responding to control changes.
- **PID2Graph Synthetic:** two development sheets through a labeled-dataset adapter. Oracle-label scores test adapter consistency; model scores are development results. Ontology and line-semantics gaps remain. This is not a held-out plant trial. See [the adaptation guide](ADAPT_LABELED_DATASET.md).

**Version matters.** Use the guide and scripts from the same checkout and record its commit (`git rev-parse HEAD`).
Parts of the guide began as development snapshots later published as one sanitized commit, so the short commit
IDs in journal entries 30–32 are not in this repository's history. Historical screenshots, gateway receipts and
the Docker backup do not validate current exports. A 2026-10-13 candidate passed native Ignition acceptance in a
disposable lab gateway, including data-source loss and a 390 px `/m` overview (the control-room screens stay
1600 px); those receipts apply to that candidate. See the [native acceptance page](IGNITION_ACCEPTANCE.md).
PI import has **not** been run.

## 2. Learn without customer drawings or a gateway

The README specifies Python 3.10+; verify the chosen Python and pinned dependencies together rather than assuming every version is tested. Use a disposable checkout. Commands below run from its root; shell examples use bash. Keep `PID2GRAPH_SET` unset for the OPEN100 examples. Dependencies are pinned in [requirements.txt](../requirements.txt); installing them requires package access. Use an approved environment and install process. No model account is needed for this first stage.

### A. Manual seed model → generated files

Read [data/te_process_model.json](../data/te_process_model.json), then:

```sh
python scripts/generate.py
```

This standard-library command writes `out/svg/`, `out/ignition/te_tags.json`, the PI AF staging files in `out/pi/` (sheet, custom units, attribute descriptions, publish steps; not import-tested) and `out/ops_review_sheet.csv`. It overwrites existing seed outputs; use your learning copy. Inspect the model, SVG, review sheet and export side by side. This shows what an explicitly authored asset model can generate, **not drawing extraction**. The generic TE tag export is not the replay-connected `twin_provider.json`.

Optional source checking is a separate, potentially networked step: `python scripts/verify_te_source.py` fetches missing TE source and writes a report. Its `--write` option also changes the seed model. Do not use it merely as an offline viewer. `python scripts/verify_te_topology.py` works the same way for units, streams, directions and tag ownership (report: `out/te_topology_check.md`); it also downloads the revised TE code from N. L. Ricker's archive as a cross-check.

### B. Existing drawing-derived model → draft exports

Copy the committed OPEN100 model before regenerating anything:

```sh
mkdir -p runs/plant-learning
cp out/twin/r2-tiles-trace/codex/plant_model.json runs/plant-learning/plant_model.json
python scripts/generate.py runs/plant-learning/plant_model.json
```

Outputs appear beside that copied model: `svg/`, `ignition/tags.json`, the PI AF staging files in `pi/`, and `review_queue.csv`. Review an original public drawing against its extracted symbols, tags, parents and links. Preserve unknowns and clarification flags. Regeneration replaces SVGs and the review queue, so keep filled review CSVs separately. Both seed and extracted-model generation validate structure and render the complete bundle before creating, replacing or deleting export files. Invalid models exit nonzero and leave existing exports unchanged. This is not an atomic filesystem transaction: a write-time disk or permission failure can still leave partial output. Successful generation is not an engineering or operational gate; independently review the candidate before using exports. [Twin outputs](TWIN_OUTPUTS.md) explains each file.

### C. Check the pipeline, then optionally rerun public extraction

Start with the explicitly narrower standard-library suite and committed fixtures:

```sh
python scripts/run_tests.py --source-only
```

This includes OPEN100 scorer controls, the Synthetic adapter tests, one-sheet site-intake/workflow controls, OPC/PI mapping and export controls, synthetic exact-candidate preflight checks and review-effort record controls, but excludes TE channel, along-line, gateway-diff, current-artifact and TE topology tests. Its summary explicitly says it is **not a full-suite pass**. No dependencies are installed or data downloaded by the runner.

For the full cached-data suite, use an approved environment with the pinned dependencies already installed and the TE replay files already staged. `python scripts/fetch_te_data.py --all` (replay files, the simulator source, and the rest of the published fault set the 21-fault evaluation needs) and `python scripts/verify_te_topology.py` (the revised TE code used as a second source; report only) are separate network-capable setup commands, not offline tests. Check prerequisites first:

```sh
python scripts/run_tests.py --full --check-prerequisites
python scripts/run_tests.py --full
```

The no-argument command also selects the full suite. CI explicitly stages checksum-verified TE fixtures before this full run; its setup step can use the network. Missing required dependencies/fixtures or missing/hash-mismatched TE cache fail preflight with exit 2 and no test scripts run; test failures exit 1. A successful prerequisite check is not a test pass. Optional source caches, including original/adapted DEXPI files and vendor renders, can be absent without blocking preflight. Those checks can skip even when their scripts exit successfully. The summary reports unittest skips, platform notices and additional skipped-check notices separately and withholds a complete-suite claim when any are reported. Platform notices explain cases in the unittest count; they are not extra cases. See [coverage and optional setup](REVIEWING.md). The runner fetches no missing data. Record the selected mode, omissions and all failures. Full-suite checks may regenerate local normal-band files; use your disposable checkout. Neither mode validates native Ignition runtime, PI import or operations acceptance.

Only after approving the model service, access method, public-data upload and any cost, run a **new development experiment**, for example:

```sh
python scripts/run_extraction.py --tool codex --drawings 0,1,2 --label plant-learning-v1 --prompt extraction/prompt_v2.md --tiles 2x2
python scripts/scorecard.py --label plant-learning-v1 --split dev
python scripts/trace_connections.py --src-label plant-learning-v1 --tool codex --drawings 0,1,2 --label plant-learning-v1-traced
python scripts/scorecard.py --label plant-learning-v1-traced --split dev
python scripts/build_twin.py --label runs/plant-learning-v1-traced/codex/ --sheets 0,1,2 --sheet-register data/sheet_registers/open100_dev.csv --score
```

The runner needs an installed, authenticated supported CLI; it sends images to the model service. Record the actual model/version and transport. A failed CLI launch is not extraction, and the documented native fallback is not a portable CLI recipe. Use a new label for a new attempt: extraction skips existing run files; tracing/building can overwrite outputs. These commands are a learning example, not an exact rerun of the published result tables. Consult [evaluation](EVALUATION.md), [goal/recipes](GOAL.md) and [model access](MODELS.md) before making comparisons. Raw historical model responses may be absent from a source-only checkout.

## 3. Supply the plant inputs before a pilot

Start with one bounded unit and a small representative drawing sample. The plant supplies:

- **Authority and ownership:** pilot sponsor, document owner, process/operations reviewer, controls or historian engineer, IT/OT security owner, permitted use and acceptance criteria.
- **Drawings:** approved current revisions, originals, revision register, legends, tag conventions, sheet links and known redlines. Preserve source/page/box/hash provenance; do not silently replace originals with cleaned images.
- **Engineering context:** equipment register, instrument index, loop sheets, process/signal-line conventions, unit hierarchy and known ambiguities. A drawn callout is not automatically a measured variable.
- **Signal inventory:** authoritative point identifiers and addresses, source system, units, type, range/scaling, timestamps/quality behavior, read permissions and a way to verify them independently. Include points absent from the drawing.
- **Display and alarms:** reviewer-approved roles, ranges, normal bands, alarm limits/priorities and change-control process. Drawing geometry does not establish operating limits or safe control actions.
- **Data policy and lab:** approved local storage, access/retention, an isolated non-production target and rollback plan. Proprietary drawings, exports and credentials stay local unless the specific external-model transmission is approved. A gitignored file is not a security boundary; review the complete outbound file set.

**A site adapter is still engineering work.** The bounded local intake below accepts one PNG and an existing extraction JSON. The [frozen extraction handoff](SITE_EXTRACTION_WORKFLOW.md) additionally stages one arbitrary local PNG for the existing whole-sheet Codex recipe and collects a matching run record. Only its explicit `execute` subcommand calls a model, after separate approval. Neither path accepts `--input my-plant.pdf`; the general tracing/scoring CLIs still use the repository's dataset folder conventions. PDF rasterization, revision selection, image normalization, label/schema conversion, site ontology, tag parsing, confidence recalibration and source reconciliation must be supplied and tested. There is no bundled local-inference adapter: the current Claude/Codex paths use hosted services, and the Gemma experiment also uses the Google API. A genuinely offline model requires a separately implemented and validated adapter. Do not overwrite benchmark folders with customer data. [From demo to a real site](FROM_DEMO_TO_A_REAL_SITE.md) is the detailed gap list; [At your plant](AT_YOUR_PLANT.md) covers governance and cost tradeoffs.

### Bounded local intake: one PNG + an existing extraction

Use this only after approving the drawing's local use and obtaining its extraction through an independently approved process. The intake makes **no model, network, line-tracing or confidence-calibration call**. It converts supplied content into an **unverified review bundle**, with no signal connection or production approval. Python's standard library is sufficient:

1. In a private local folder, retain the original PNG and extraction JSON. Filenames need not be numeric or match; spaces are supported. Rasterize PDFs and select the authorized revision/page separately.
2. Save an intake manifest alongside them, for example `intake.json`:

```json
{
  "schema_version": "site-drawing-intake-1",
  "drawing_id": "Utilities water loop",
  "revision": "B",
  "page": 1,
  "image": "Water loop revision B.png",
  "extraction": "Water loop reviewed extraction.json",
  "extraction_format": "prediction",
  "producer": {
    "method": "Supplied extraction for engineering review",
    "tool": "site-process",
    "model": null
  },
  "drawing_number": "UT-101",
  "system_code": "UT",
  "system_name": "Utilities"
}
```

`drawing_number`, `system_code` and `system_name` are optional supplied register claims. Image/extraction paths resolve relative to the manifest, or may be absolute local paths. `producer.method` and `producer.tool` are required; `model` may be null/omitted. These claims and the drawing identity are retained, not independently authenticated. A positive integer `page` records provenance; this command still handles only one PNG.

`prediction` means the JSON itself contains `symbols` and `connections`, following [the extraction contract](../extraction/prompt_v2.md). Use `run-record` for an existing run wrapper containing `prediction`; records marked with extraction/parse errors are refused. When the wrapper supplies `image_sha256`, it must match the PNG. Extra source fields are retained in the original JSON but are not automatically understood or converted into model semantics.

3. Choose a **new output directory with an existing parent**, then validate and build:

```sh
python -S scripts/import_site_drawing.py --manifest '/private/pilot/intake.json' --out '/private/pilot/review-bundle' --check-only
python -S scripts/import_site_drawing.py --manifest '/private/pilot/intake.json' --out '/private/pilot/review-bundle'
```

Replace these illustrative paths with your own. `--check-only` checks inputs without writing; it does **not** run conversion or render exports. The build refuses an existing output, validates before publishing the directory, and stages its bundle beside the destination. Do not run concurrent writers to the same destination. Invalid input fails nonzero rather than skipping symbols or links. An intake success is not engineering approval.

The bundle contains `plant_model.json`, `intake_manifest.json`, preserved sources under `source/`, `READ_ME.txt`, `review_queue.csv`, `svg/sheet_0.svg`, `ignition/tags.json` and the PI staging files: `pi/pi_builder_af.csv`, `pi/custom_uoms.csv`, `pi/attribute_descriptions.csv`, `pi/IMPORT_STEPS.txt` and `pi/reconciliation.json`. The PI sheet uses schema v2, including `AttributeType`; it has not been import-tested. Internal sheet `0` is a staging key, not the original page number. The original manifest, extraction JSON and image bytes are retained, alongside source and implementation SHA-256 hashes, supplied producer information, original filenames and drawing/revision/page evidence. The original manifest may contain private absolute paths; inspect the complete bundle before sharing. Keep the whole bundle together: its SVG background and provenance use bundle-relative source paths. Do not redistribute proprietary sources merely because they are in an export folder.

**Input boundaries:** supported classes are `tank`, `pump`, `valve`, `instrumentation`, `inlet/outlet` and `general`; site-specific symbols/ontology need explicit adaptation. IDs are bounded ASCII letters/digits/dot/underscore/hyphen, starting with a letter or digit, at most 128 characters. Supplying both `box` and `bbox` is refused. Coordinates must be finite, ordered, nondegenerate boxes on the 0–1000 scale; tiny boxes that collapse at converter precision are refused. Confidence may be absent/null or a finite number in [0, 1]. Duplicate JSON keys/IDs, duplicate undirected connections, self-links, missing endpoints and unsupported classes are refused. Duplicate plant tags remain separate review questions; never rename them simply to remove ambiguity. Text values are limited to 4,096 characters; invalid XML characters and leading spreadsheet-formula prefixes (`=`, `+`, `-`, `@`, after whitespace) are refused. Tags may contain tab/newline whitespace, which the converter normalizes; other supplied text fields cannot contain ASCII controls. These restrictions can reject legitimate site text and are not a security certification for arbitrary hostile files. Each JSON input is limited to 16 MiB; the PNG is limited to 100 MiB and 50 million pixels. PNG container/CRC checks do not establish pixel decodability, readability or revision authority; review the actual image separately.

**Interpretation limits:** parent assignment uses the existing linked/geometry heuristics, not tracing. Stable identifier ordering breaks distance/branch ties for repeatability; it does not resolve their engineering ambiguity. ISA-style tag parsing and equipment-role promotion can be wrong for a site's conventions. Connections are undirected adjacency with unknown flow direction, drawn as straight logical SVG links rather than pipe routes. Supplied confidence and the inherited 0.75 highlight rule are uncalibrated for this drawing; no trained green/amber/red risk model is transferred. All items start unverified, mappings remain absent, and PI/Ignition files are drafts. The model's blocked operational-readiness metadata is descriptive, not an enforced interlock in other scripts. Continue only through qualified engineering review and separately authorized target-system acceptance.

### Frozen single-PNG extraction handoff

If you need an extraction rather than already having one, follow [the complete single-PNG workflow](SITE_EXTRACTION_WORKFLOW.md). `prepare` snapshots one PNG, drawing/revision/page, the pinned prompt and implementation hashes into a new private job; `--check-only` writes nothing. `collect` validates a supplied result against that job and publishes a new unverified review bundle. Both are local standard-library operations.

The selected recipe is `synthetic-adaptation-whole-sheet-v1`: GPT `gpt-6.1-sol`, the frozen original `extraction/prompt.md`, whole sheet, no tiling/tracing and linked-parent conversion. It is distinct from the published M3 tiled/traced method and is not a new generalization result. Native replay retains its transport/reasoning deviation; contract fixtures are labeled synthetic and cannot establish extraction performance.

`execute` is a separate external action sending the PNG/prompt through an authenticated Codex CLI. Confirm source rights, data egress, service access and cost authority before using it. This integration did not execute a model. Every attempt has its own preserved directory; prior attempts require an explicit `--retry-of` and never silently resume or overwrite. Changed code or inputs require a new prepared job. A CLI flag does not grant organizational permission, and a run record's billing or producer fields are supplied claims. Keep completed reviews separate from regeneration destinations.

## 4. Review and map on copies

Once an adapted model exists, copy it into a private working location, back it up, and have a qualified reviewer fill the generated `OPS_` columns. For the public learning copy above, copy its review queue to `runs/plant-learning/reviewed.csv`, complete actual decisions, then preview:

```sh
python scripts/apply_review.py runs/plant-learning/plant_model.json runs/plant-learning/reviewed.csv --reviewer "Name, role" --dry-run
```

Resolve every error, inspect the proposed diff, and only then repeat without `--dry-run` to apply those decisions. Regenerate with `generate.py` after the approved changes. This writes the model in place and creates a change record. A class-role change may require a reviewed rebuild rather than editing a class string. Never prefill approvals to clear a gate. See [the review loop](REVIEW_LOOP.md).

To inspect point mapping on the public model:

```sh
python scripts/map_points.py runs/plant-learning/plant_model.json data/io_lists/open100_sheet0_demo.csv --sheets 0 --dry-run
```

**Mapping defaults to a partial update.** Existing unrelated mappings are preserved. `--sheets` restricts eligible targets; an out-of-scope resolved target rejects the whole update. Tags remain globally ambiguity-checked, so a sheet filter does not settle duplicate identity. To intentionally replace all non-rejected mappings within the selected sheets (all sheets if omitted), use `--replace-all` only with the complete authoritative list for that scope and separately approve any removals. Replacement refuses unresolved, ambiguous or blocked rows rather than clearing mappings around them. The synthetic demo CSV deliberately contains unresolved rows and is not a valid replacement list.

Dry-run writes nothing and displays every added, changed and removed mapping with before/after values plus complete mapping snapshots. Add `--json` for a machine-readable report. Have the qualified reviewer inspect the complete diff and approve application before repeating without `--dry-run`. Unknown or rejected explicit `asset_id` values never fall back to tag matching; duplicate target rows, empty addresses and invalid sheet scopes reject the whole update without model/report writes. Required CSV columns remain `tag,server,base_path,point`; optional `asset_id` pins an explicitly reviewed target. Ambiguous tags, unmatched tags and reviewed valve callouts are reported but receive no new assignment in partial mode; existing mappings are preserved. A successful partial plan does not mean every row matched. The mapper checks nonempty address fields, not OPC syntax, connectivity or signal identity. It does not validate units, types, scaling or ranges; optional `units`/`description` do not establish those properties in the model. Never resolve a duplicate merely to make it connect.

### Separately reviewed PI references

Use [the PI-only mapping contract](PI_MAPPING.md) when a qualified reviewer has supplied the real PI Data Archive, point, requested AF type and UOM for an exact instrument `asset_id`. Do not derive these from OPC addresses or tags. On a copied extracted model:

```sh
python -S scripts/map_pi_points.py /private/pilot/plant_model.json /private/pilot/reviewed_pi.csv --dry-run
```

Inspect the complete before/after mapping report and approve its scope before applying without `--dry-run`; regenerate exports afterward. Default updates preserve other PI mappings. `--replace-all` removes omitted PI mappings, and a header-only replacement clears them all, so removals require deliberate review. Rejected instruments, reviewed valve callouts, unsupported types/config strings and malformed rows fail the entire plan. Reviewer strings are attestations, not authenticated approval. Unmapped attributes remain placeholders, and the reviewed MS 14010 callout retains no PI signal reference.

Generated `pi/reconciliation.json` identifies the staged mapping inventory, schema-v2 columns and remaining native checks. Use `pi/pi_builder_af.csv`, which now writes `AttributeType`; regeneration removes the obsolete separate v1 candidate file. Read `pi/IMPORT_STEPS.txt`, reconcile `pi/custom_uoms.csv` with the site's UOM database, and use `pi/attribute_descriptions.csv` for descriptions kept outside the sheet. These changes follow the documented sheet conventions but have not been tested in a licensed PI system. No PI connection or import occurs here. See [the schema-v2 handoff](PI_MAPPING.md#generated-pi-files-sheet-schema-v2-and-native-handoff).

## 5. Adapt the target system, then test it in isolation

- **Ignition:** supply the exact gateway/module versions, non-production provider/project names, OPC server and namespace/address rules, certificates, read-only identity, history configuration and approved display/alarm definitions. The current builder is a TE/OPEN100 demonstration with fixed assumptions, not a general plant deployment tool. Follow [quickstart](IGNITION_QUICKSTART.md) for loading by hand and [native acceptance page](IGNITION_ACCEPTANCE.md) for current-artifact acceptance. Builder/import/verifier commands change the gateway; verifier fault controls intentionally mutate lab state. Do not point them at production. Do not treat `demo.py --build --verify` as a harmless file check.
- **AVEVA PI / AF:** supply a licensed development environment, PI Builder/Excel and PI System Explorer access, AF database/template/hierarchy conventions, units/data types and actual PI Data Archive/point identities. The CSV is a **PI Builder-style draft**, not a validated native import. Unmapped `%Server%`/placeholder point references require site-specific reconciliation; [the separate PI mapper](PI_MAPPING.md) stages explicitly reviewed literal references, while `map_points.py`'s OPC mapping does **not** supply them. The current `pi/pi_builder_af.csv` uses schema v2 and `AttributeType`. Still compare its headers and row conventions with a sheet retrieved from the installed PI Builder version, confirm or create/map the units in `pi/custom_uoms.csv`, and follow `pi/IMPORT_STEPS.txt`. Have the PI engineer test import and verify point resolution, types, units, attribute values and quality in the development AF database. PI Vision graphics are a separate integration, not a supplied custom-SVG import path.
- **Other historians, SCADA, CMMS or platforms:** supply their supported import/API schema, stable IDs, units/types, quality/time conventions and read-only access contract. Implement and test an exporter/adapter with reject logs and count reconciliation; there is no universal connector in this repository.

**Network stop:** both supplied replay servers bind `0.0.0.0` (all host interfaces), with anonymous/unencrypted lab endpoints. A `localhost` URL or log line does not restrict their listener. Do not start them on plant or corporate networks; use a separately approved isolated lab with verified network containment. Do not weaken host security to make the demo work.

Keep observation read-only toward process systems: no PLC/DCS writes, control logic, setpoint changes or automatic alarm creation. Lab configuration changes are still changes requiring the site's approval. A later production pilot requires separate security, licensing, management-of-change and operations sign-off; it is outside this learning workflow.

### Offline exact-candidate Ignition preflight

This optional platform step is separate from a [first source question and evidence packet](../examples/first-pilot/README.md).
It needs no company-context application, and a source investigation needs no gateway.

**Required evidence is not in a public checkout.** The default paths
`out/review/current-gateway-2026-10-10/manifest.json` and `browser-contract.json` are not committed. The bare
preflight command therefore exits 2 for missing inputs. The public repository does not supply a complete
candidate-package creator for them. Do not replace missing evidence with the synthetic test fixture or relabel
historical receipts as a current run.

If you already hold a matching candidate package, point the read-only checker at that folder and its actual
root-relative manifest/contract paths (replace these illustrative paths):

```sh
python -S scripts/ignition/acceptance_preflight.py --root /path/to/held-candidate --manifest review/manifest.json --contract review/browser-contract.json
python -S scripts/ignition/acceptance_preflight.py --root /path/to/held-candidate --manifest review/manifest.json --contract review/browser-contract.json --require-native
```

For a supplied matching package, the checker verifies the manifest-listed build inputs, exact provider/project/build
metadata and bound browser contract. Its inventory and expected counts are specific to the TE/OPEN100 demonstration;
`--root` does not adapt it to another plant. It needs the already staged files and never downloads missing inputs.
It prints JSON and changes nothing. Historical test/handoff hash drift is reported separately, not treated as a
current test run. Manifest-listed input checking is not a complete upstream source-dependency audit. The original
receipts remain historical even where output bytes are unchanged.

`--require-native` always returns nonzero: invalid/missing inputs return 2; a valid offline-only package returns 3
with native acceptance **NOT RUN**. The 2026-10-13 native run used the separate harness in
`scripts/ignition/acceptance/` and is recorded in its own receipt. Future `--observations` input must be a
root-relative local JSON file matching the exact candidate identity; synthetic fixtures and supplied native-capture
claims remain clearly separated. Offline sample checks cover expected paths and quality: only the 52 recorded TE
and 24 mapped OPEN100 paths require Good finite values and advancing/fresh source timestamps. SC-212 must remain
Bad; 334 placeholders must remain non-Good and may have null/absent values and source timestamps. The metadata-only
callout has no PV sample. These checks cannot authenticate provenance or substitute for actual gateway/browser
observation. Import fidelity, history, navigation, display/alarm behavior, read-only configuration, write rejection,
fault recovery and operator acceptance remain distinct gates. Only separately authorized isolated tests may perform
imports, write probes or fault injection. See the [native acceptance page](IGNITION_ACCEPTANCE.md).

## 6. Acceptance evidence and stop conditions

Agree thresholds **before** extracting the plant sample. The [prospective review-effort protocol](REVIEW_EFFORT_PROTOCOL.md) supplies a blank registration and local record validator for a future manual/current-tool versus AI-assisted workflow study. It measures observed preparation plus review labor and independently audited residual critical errors, preserves incomplete/failed assignments and separates synthetic tests from supplied human observations. Hashes cannot prove actual preregistration, equal information access or auditor independence. No human study, time saving, ROI, quality equivalence or operator-usability improvement is established by this kit; benchmark review-load counts are not reviewer minutes. Retain:

- [ ] Exact code/data/prompt/model versions, hashes, source licenses, attempted runs, errors, costs and transport differences.
- [ ] Independently reviewed sample per drafting style; item/link/tag/parent corrections and reviewer minutes, with held-out drawings reserved for a frozen method. Public benchmark scores do not replace this.
- [ ] Provenance and unresolved-item list, including duplicates, missing/off-page links, unknown flow direction and process-versus-signal semantics. No hidden auto-acceptance based on transferred confidence tiers.
- [ ] Reviewed model, full before/after mapping diff, units/types/scaling/range checks and evidence for each connected signal; unknowns remain visibly unavailable.
- [ ] Export structural checks **and** native import reconciliation; timestamp/quality behavior, connection-loss display, read-only enforcement, alarm/display review, rollback and operator acceptance on the exact candidate build.

Stop at a draft if revision authority is missing, source rights or model egress are uncertain, scans are unreadable, semantics/identity remain ambiguous, data quality is masked, reviewer effort misses the agreed threshold, or native imports fail. Reduce scope or fix and re-evaluate before expanding. An attractive screen, zero-error oracle score or passing offline test suite cannot waive these gates.

## 7. Self-guided or assisted

For a self-guided pilot, nominate the owners above, follow the public learning path, freeze one small site trial and use the checklist to decide whether to continue. You do not need to send drawings or wait for the repository author to begin learning.

If engineering assistance is useful, a bounded scope could cover input readiness, one site adapter, sample labeling/evaluation, review facilitation, a target-system draft export, and an acceptance handoff. Agree responsibilities, data access, deliverables and exclusions before sharing material. This describes possible work, not a promise of availability, services, pricing or production approval.

Code is MIT; PID2Graph/OPEN100-derived data and outputs have separate CC BY-SA obligations; TE sources/data have their own terms. Read [NOTICE.md](../NOTICE.md) and [LICENSE](../LICENSE), preserve attribution, and check rights before redistributing derived packages. Repository licensing does not grant rights to customer drawings, proprietary symbols or vendor software. Model subscriptions, API charges and platform licenses are separate costs; see [Costs](COSTS.md).
