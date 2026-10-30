# Doing this at your plant

Start with one engineering problem and the records available for it. This toolkit helps produce a draft that a
person can inspect and use to plan the next evidence request. Its public examples do not establish accuracy,
review effort or savings at your site. Try the [offline drawing example](../examples/own-drawing/README.md#0-the-worked-example-offline-about-a-minute)
first; it needs only Python, with no accounts, downloads or model calls.

> **Short version:** treat the AI output as a *draft that people check*, not an automated result. Measure the
> draft-plus-review time against your manual baseline. Keep everything read-only and out of the control network until
> it has gone through your normal change process.

---

## Start wherever you are

A plant doesn't need good drawings to start. Choose the route matching your records; each has its own outputs
and review needs:

| Where you are | What you do | Shown here on |
|---|---|---|
| **A drawing image** | Use the [own-drawing intake](../examples/own-drawing/README.md) to turn a supplied extraction into a draft model, review queue, logical SVG and tag/PI staging. A new extraction needs a separately authorized model run. | OPEN100 has 12 sheets: 0–5 were development, 6–11 were validation and also helped select the method. They are not 12 sealed holdouts; see [the scoring record](GOAL.md). |
| **Supported DEXPI XML** | Use the [structured CAD route](../examples/from-dexpi-xml/README.md), then inspect identity, roles and placement uncertainty. | Public DEXPI examples, with failures and unplaced items reported in the [matrix](GENERALIZATION.md). |
| **A written description or process knowledge** | Author a sourced model and cross-check it. Use it directly for [asset/platform drafts](../examples/from-description/README.md) or the [question engine](OPPORTUNITY_SCREEN.md); a generated drawing and image round trip are optional. | Tennessee Eastman and the Bayer historical reconstruction. Authoring a model does not verify the actual plant. |
| **A loop list or historian CSV** | Use the [loop-list comparison](../examples/loop-audit/README.md) or [recorded-data tools](../examples/historian-csv/README.md). Reconcile identities before linking their results to a model. | Supplied-format examples; these lists do not automatically become a complete process model. |

An authored model can support a first question without generating a drawing or paying to extract that drawing
again. Generated sheets are useful when a drawing itself is the intended draft deliverable. Their emitted answer
keys come from the model and layout, so reading them back tests clean generated drawings rather than real-plant
accuracy. The Tennessee Eastman [round trip](EVALUATION.md#6-one-plant-end-to-end-tennessee-eastman) is that experiment.

**Adapting a drafting style is separate work.** The drawing generator uses the OPEN100 style and a manually
authored layout; it is not a general house-style importer. `scripts/style_fidelity.py` records the project's
TE/OPEN100 comparison, not a reusable command for measuring arbitrary site sheets. Adapting title blocks,
symbols, line conventions and sheet splits needs drafting/code work and review; no effort estimate was measured.
Inspect layout-declared drafting additions, including utility symbols and control-valve stations, separately
from model content. They are marked in the emitted key and are not evidence of installed equipment.

**Governance: a generated drawing is not a drawing of record.** It shows what your lists say, not what is in the
field. Until engineering has walked it down and accepted it under your management of change (and, for covered
processes, your PSM process safety information procedure), label it as a draft, keep it out of your document
control system's issued set, and don't let anyone operate, isolate or permit from it. The generated sheets here say
so in their title block.

## What you can do with only drawings, only process knowledge, or both

You may not have everything at once. Drawings are often easier to get than historian access, and the reverse
happens too. This repo has one of each: the OPEN100 track has 12 real drawings and no process data, and the
Tennessee Eastman track has process knowledge (a model and recorded data) and no drawing. What each supports is in
the [deliverables matrix](DELIVERABLES.md).

| What you have | What you can build now | What has to wait |
|---|---|---|
| **Drawings, no historian access** | The reusable intake produces a draft asset model and tag list, placeholder Ignition tags and PI AF staging, a logical SVG and a review report. Flow direction, sheet stitching, mimics, 3D tours and isolation mockups were demonstrated on OPEN100 and require adaptation for your drawings | Values, normal bands, alarms, replay. Every value remains a placeholder until an I/O list or historian mapping arrives; the research visualizations have no generic own-drawing build command |
| **Process knowledge, no usable drawings** | A sourced model authored from the description, logical SVGs, review sheet, tag/PI staging and model-based questions. A P&ID draft also needs an authored layout and drawing dependencies | Native mimics, 3D, alarms and replay need separate adaptation, mappings, configuration and suitable data. The TE demos do not supply these generically for your model. Check authored topology against independent records or field evidence |
| **Both** | Cross-check scoped identities, relationships and observations across the records, then plan the missing evidence | A difference may reflect extraction error, identity/revision mismatch, different operating conditions or a documentation gap. Review its cause before using it to support a decision |

So a drawings-only pilot can start with the draft model, review report and asset-framework staging, and add values
when data access comes through. The OPEN100 mimic, tour and isolation mockup are research examples to adapt, not
deliverables the own-drawing intake already builds. In practice:
- **Ask what the drawing actually shows.** Flow arrows, off-page flags and pump symbols give direction on part of
  the plant only. On these 12 sheets, a third of the process links. Keep the rest undirected and visibly so: a
  screen that guesses directions teaches people to trust arrows that were never drawn.
- **Read the equipment schedules.** Many drawings print what each piece of equipment is for along the bottom of the
  sheet. It is the best source for purpose cards and is easy to miss: the extraction here never read it.
- **Treat the isolation view as a review aid.** A list of block valves, motor-operated valves, motor-driven
  equipment and boundary lines, each pointing at its place on the drawing, may help a qualified reviewer inspect
  the draft. No procedure-writing effort or isolation adequacy was measured. It is not the procedure, and a valve
  the extraction missed is missing from it.

---

## 1. Before you start: decide what you're actually converting

**Check whether you need vision at all.**
- **Structured CAD records:** if a supported structured export is available, start with the
  [DEXPI reader](../examples/from-dexpi-xml/README.md). It avoids rereading available structure from pixels, but its
  interpretation, dropped records and uncertain placement still need review. Other formats need an appropriate adapter.
- **Image-only drawings:** use image extraction for scanned, PDF-only or legacy records without a supported structured export.

**Gather the other lists that describe the same plant:**
- **Instrument index / tag list:** from your DCS or PLC export.
- **Historian point list:** e.g. PI points, or Ignition historian tags.
- **Maintenance asset register:** e.g. SAP PM or Maximo equipment records.
- **Loop sheets and the cause-and-effect matrix**, where they exist.

These are potential cross-checks. Reconcile record identities, revisions and scope before deciding whether an
apparent disagreement is an extraction error or a documentation gap.

**Pick a pilot, not a plant:**
- **Scope:** one useful question about one asset or workflow; for the drawing route, try one representative sheet
  first. Expand the sample only when the initial result and review effort justify a broader evaluation.
- **Choice of unit:** one where an operator or technician will spend an hour reviewing.
- **Priority:** start where the twin would pay off first, such as bad-actor equipment or a unit with frequent upsets.

## 2. Build your own answer key first (small, but real)

This section is for evaluating extraction quality beyond the first worked example. It is not required to try
the committed offline packet or ask an initial model-based question.

- **Hand-annotate 3–5 representative sheets** in the same output format the AI will produce:
  - equipment
  - instruments with tags
  - valves
  - connections
  - off-page connectors

  Include at least one "bad" sheet: a poor scan, heavy markups, or a crowded layout.
- **Time it.** Minutes per sheet for manual capture is your baseline. Without a baseline you can't claim savings.
- **Don't treat the manual result as perfect.** Have a second person check the annotated sheets. Manual capture has
  an error rate too, and that's the fair comparison.

## 3. Prepare a dataset that isn't manicured

Real drawing sets have problems the public datasets don't. Deal with these before you score anything:

| Problem | What to do |
|---|---|
| **Which revision is current?** IFC vs as-built vs "as-built plus field redlines" | Pick one revision per sheet and record it. Collect field redlines and clouded changes; note which haven't been incorporated. |
| **The drawing isn't the plant** | Plan a walkdown sample on the pilot unit. Field-verify a percentage of tags so you know how far the drawings drift from reality. |
| **Scan quality** | Aim for about 300 dpi or better. Deskew, crop borders, and keep originals. Low-resolution scans hurt text reading most. |
| **Large sheets** | Very large images may be downscaled by the model. Tile with overlap and merge, or check that small tag text survives at the resolution you send. |
| **Site-specific symbols** | Include your legend/symbol sheet with every request. Older drawings and different contractors use different symbols. |
| **Continuation sheets** | Off-page connectors link sheets together. Extract per sheet, then stitch by connector ID, and flag any connector that doesn't pair up. |
| **Tag conventions** | Write down your site's tag format (ISA-5.1 variant, KKS, plant-specific) and validate every extracted tag against it. Malformed tags are cheap to catch. |
| **Duplicates and retired equipment** | Expect tags that appear on two sheets, and equipment that was removed but never erased. Flag these; don't silently merge them. |
| **Handwriting and stamps** | Handwritten tags and stamped notes are the least reliable reads. Route them to review by default. |

## 4. Measure whether a draft helps

The useful hypothesis is that a draft plus review needs less effort than manual capture at acceptable quality.
No person's review has been timed here. Use the [review-effort protocol](REVIEW_EFFORT_PROTOCOL.md) if you want to
test that claim; count both effort and remaining errors.

- **Compare review with manual capture.** A pre-filled row may help or may take longer to correct. Measure both
  under comparable conditions rather than assuming a saving.
- **Route by confidence and by cross-checks.**
  - Items that pass the deterministic checks (tag format valid, tag found in the DCS/historian list, units match)
    go into a quick-confirm batch.
  - Items that fail any check, or that the model marks as uncertain, go to careful review.
  - People settle the ties.
- **Partial output still has value.**
  - An accurate equipment list and instrument tag list per unit is already the skeleton of an asset hierarchy:
    PI AF elements, Ignition UDT instances.
  - Graphics and line connectivity are a bonus on top.
- **Count what review catches.** Track corrections by type: missed item, wrong tag, wrong equipment, wrong
  connection. This tells you where the model is weak and whether a prompt change actually helped.
- **Report the observed result:** effort for manual and draft-plus-review workflows, residual errors and what still
  needed a person. Retain an unsuccessful trial or insufficient evidence; neither is a measured saving.

## 5. Safety and security in a production environment

**Safety**
- **The drawing of record doesn't change.**
  - For processes covered by OSHA PSM, P&IDs are part of process safety information; applicable changes require
    the site's update and change procedures. See [29 CFR 1910.119(d)(3) and (l)](https://www.osha.gov/laws-regs/regulations/standardnumber/1910/1910.119).
  - A twin built from them is a *derived* view, not the record. Mark generated graphics and asset models as
    derived/not for construction.
  - When a drawing changes through MOC, rebuild or re-check the twin. Never update the twin in place of the drawing.
- **Monitoring, not control.**
  - These outputs are for visualization and analytics.
  - Operator control graphics follow your HMI standard (e.g. ISA-101) and alarm philosophy (ISA-18.2), and go through
    your normal review.
  - Don't put generated graphics in front of operators for control decisions without that review.
- **Read-only by default.** Generated tags and bindings should be read-only. In Ignition, use read-only tag providers
  or security zones and keep write-back off. Any write path to the process is a separate, engineered, MOC-approved
  change.
- **Make the "why" traceable.** Every extracted item should carry its source (sheet, revision, location on the sheet)
  and who confirmed it. This repo's model stores a verification record per item for that reason.

**Security**
- **P&IDs are sensitive documents.**
  - They show how your process works and where its safeguards are. Some sites are under regulatory programs for
    critical infrastructure or chemical security.
  - Get your security and legal teams' approval before any drawing leaves your network.
- **Know where the images go.** Cloud AI APIs mean data leaves your network. Check, in writing:
  - data retention (prefer zero retention)
  - whether your data can be used for training (it shouldn't be)
  - where the data is processed
  - enterprise terms

  Options include enterprise agreements, private or regional endpoints, or models run on your own hardware.
  Redact title blocks and site names if policy requires it.
- **Keep AI tooling out of the control network.** Follow your zone and conduit design (e.g. ISA/IEC 62443):
  - The extraction and twin-building work belongs on the business network or in the DMZ.
  - Historian data flows *outward* through the DMZ (e.g. a DMZ historian).
  - Nothing inbound to Levels 1–2, and no AI agent with credentials into the control network.
- **Test before production.**
  - Load generated Ignition and PI import files into a development gateway or test AF database first.
  - Keep them under version control, and have an engineer review the diff before anything reaches production.
- **Treat drawing text as data, not instructions.** Text read from a document must never be able to steer the AI
  tool (prompt injection). Keep extracted text inside the structured output; never feed it back as commands.
- **Access and audit.** Limit who can approve a reviewed batch, and keep the approval record with the batch.

---

*Not legal or compliance advice. Your site's PSM, MOC, cybersecurity and data-governance owners have the final say.*

---

## 6. If documents must remain in-house

The first committed drawing example runs locally without calling a model. Creating a fresh extraction is a
separate step. The supplied extraction adapters call model CLIs or a hosted API; this repository does not supply
an evaluated local inference deployment or an air-gap acceptance test.

The recorded Gemma runs used Google's hosted API. Their completion rates, latency and accuracy are observations
of that hosted setup, not measurements of a local GPU, quantized weights or a disconnected deployment. See the
[recorded evaluation](EVALUATION.md#4-round-1-results-12-real-open100-drawings) and the `run_gemini` adapter in
[`scripts/run_extraction.py`](../scripts/run_extraction.py). Do not size hardware or assume local throughput from
those results.

If site policy requires local extraction, ask the responsible IT/security and engineering owners to select and
evaluate a permitted deployment on representative records. Check license, provenance, actual data egress and
resource use for that configuration. Keep the original records and compare its reviewed output with the manual
baseline. Local hosting does not establish engineering correctness or permission to deploy operational outputs.

No hardware purchase or model tuning is needed to try the starter packet. Local hosting, procurement and a
larger annotation study are separate work, justified by the first trial and the site's requirements.

---

Measured costs from this project, and a worked sizing for 1,000 sheets: [COSTS.md](COSTS.md).

## Keep the context current after the first bundle

The first bundle is a starting point. When more people or projects rely on its information and decisions,
establish a shared company home with the appropriate ownership, history and access rules. The toolkit's local
examples demonstrate what needs to travel; [after the first pilot](../examples/first-pilot/README.md#after-the-first-packet)
describes the intended organizational handoff.

Keep the drawings and source documents, the reviewed model, the signal mappings, and the reasons behind the
engineering decisions together. Give unresolved questions an accountable owner. A drawing conversion alone does
not supply the operating sequence, governing limit, current alarm configuration or knowledge held by the people
who maintain the unit.

The [context register](../examples/context-register/README.md) supplies a local return step: fill answers from
procedures, data sheets, logs or other evidence; record their exact source revisions and locations; keep competing
answers visible; and retain who assigned and reviewed the work and when. Source match and plant truth are separate.
It has an offline illustrative example and a public four-document PRONTO packet with unresolved source differences.

At each incoming document revision or engineering change, check the current source pack and refresh the preserved
register. Recheck the affected answers, resolve disputes explicitly, and retain the earlier decisions. The tool
does this comparison when you run it; it does not watch folders or authenticate reviewers. Your organization
chooses the authoritative documents, responsible people, review intervals and access controls.

Transfer the source manifest, register history and enriched graph together when another team or system takes
over. The [versioned handoff guide](CONTEXT_REGISTER.md#versioned-handoff-and-limits) explains the interchange
boundary. No downstream live integration has been tested; a receiving system must preserve identities, evidence,
unfinished states and review history rather than flattening them into an approved asset list.
