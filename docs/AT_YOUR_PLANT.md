# Doing this at your plant

This repo uses public, unusually clean data. Your drawings won't be. This guide covers what changes when you apply
the approach to your own site: how to prepare, how to get real savings from an imperfect result, and what to protect
in a production environment. It grows as the project does. Each journal entry also ends with an "At your plant" note.

> **Short version:** treat the AI output as a *draft that people check*, not an automated result. Measure the
> draft-plus-review time against your manual baseline. Keep everything read-only and out of the control network until
> it has gone through your normal change process.

---

## 1. Before you start: decide what you're actually converting

**Check whether you need vision at all.**
- **Intelligent P&IDs:** if your drawings were made in a data-centric tool (AVEVA Diagrams, Hexagon Smart P&ID,
  AutoCAD Plant 3D, and similar), the equipment, instruments and connections already exist as data. Export that and
  skip image extraction for those sheets. It's more accurate and cheaper.
- **Image-only drawings:** reading images is for scanned, PDF-only, or legacy drawings, which most older sites have
  plenty of.

**Gather the other lists that describe the same plant:**
- **Instrument index / tag list:** from your DCS or PLC export.
- **Historian point list:** e.g. PI points, or Ignition historian tags.
- **Maintenance asset register:** e.g. SAP PM or Maximo equipment records.
- **Loop sheets and the cause-and-effect matrix**, where they exist.

These are your free cross-checks. Much of the value comes from the *disagreements* between the drawing and these
lists. Each disagreement is either an extraction error or a real documentation gap, and both are worth knowing.

**Pick a pilot, not a plant:**
- **Scope:** one unit or area, about 10–20 sheets.
- **Choice of unit:** one where an operator or technician will spend an hour reviewing.
- **Priority:** start where the twin would pay off first, such as bad-actor equipment or a unit with frequent upsets.

## 2. Build your own answer key first (small, but real)

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

## 4. Get serious savings from an imperfect result

You don't need perfect extraction to save a lot of time. You need a draft that's fast to check.

- **Review is faster than creation.** Confirming or correcting a pre-filled row takes much less time than typing it
  from scratch. Measure both rather than assuming.
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
- **Report honestly:** time per sheet (manual vs draft-plus-review), accuracy after review, and what still needed a
  person. An honest "60% faster, with review" convinces a plant manager more than an unverified "95% accurate".

## 5. Safety and security in a production environment

**Safety**
- **The drawing of record doesn't change.**
  - P&IDs are process safety information, and under OSHA PSM they're managed through Management of Change.
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

## 6. Running an open-weight model in-house (including air-gapped)

If drawings can't leave your network, or policy forbids a third party seeing them, you can run an
**open-weight** vision model on your own hardware. The weights are a file you download once, then run with no
internet connection. This project tests one: **Gemma 4 31B**. It's run through an API here for convenience, but
those are the same weights you could install offline, so its score shows roughly what a self-hosted model of that
size achieves on this task (see `docs/EVALUATION.md`).

**What it takes:**

| Piece | What it involves | Rough cost (Oct 2026, verify before buying) |
|---|---|---|
| **Model** | An open-weight vision-language model in the ~30B class, e.g. Gemma, Qwen-VL or Llama vision families. Check the license (some restrict use or require attribution) and pick one that scores well on *your* sheets | Free to download; license review is staff time |
| **Hardware: pilot** | One workstation with a single high-memory GPU. A ~30B model at reduced precision (quantized) fits in 24–48 GB of GPU memory; 96 GB leaves room for large drawings and for tuning | One 96 GB workstation GPU is about **$14k–$18k** today ([Tom's Hardware](https://www.tomshardware.com/pc-components/gpus/nvidia-doubles-rtx-pro-6000-blackwells-msrp-to-a-staggering-usd16-000-96gb-card-started-pre-orders-below-usd8-000-last-year), [Thunder Compute](https://www.thundercompute.com/blog/nvidia-rtx-pro-6000-pricing)). Whole workstation **~$20k–$30k** |
| **Hardware: production** | Datacenter GPUs for larger models, more users, or faster turnaround | One H100 80 GB is **$25k–$40k** ([IntuitionLabs](https://intuitionlabs.ai/articles/nvidia-ai-gpu-pricing-guide), [CloudZero](https://www.cloudzero.com/blog/h100-gpu-cost/)). Multi-GPU servers run well into six figures |
| **Inference software** | An open-source model server (e.g. vLLM, llama.cpp, Ollama), pinned to a vetted version | Free; setup and patching are staff time |
| **Tuning (optional)** | LoRA fine-tuning (a light, cheap form of tuning) on your own annotated sheets so the model learns your symbols, tag format and drafting style. One 96 GB GPU can do this for a ~30B model | Compute is minor. **Annotation is the real cost**: e.g. 200 sheets at 1–2 engineer-hours each is 200–400 hours |
| **People** | An engineer comfortable with ML tooling to set up and evaluate (weeks, part-time), plus IT/OT security review | The largest line item for most sites |

**Rough totals (my estimates, not quotes):**
- **Pilot:** about $20k–$30k hardware plus a few hundred staff hours.
- **Site program with tuning:** low six figures all-in, most of it people and annotation.

Run either against what the
manual baseline costs (section 2). Throughput is usually fine for a digitization project. Even at a few minutes per
sheet on one GPU, a thousand-sheet backlog is days of unattended runtime, not months.

**Governance for an air-gapped model.** Treat the model like any other piece of software entering the plant:
- **Provenance:**
  - download weights only from the publisher's official source;
  - verify published checksums or signatures;
  - scan the files;
  - record exactly which file version is installed.
- **Change control:** a new model version, a new prompt, or a new fine-tune is a change. Re-run the same
  evaluation suite (with controls and the held-out set, see `docs/EVALUATION.md`) before it replaces the old one,
  and keep the scorecards. That's an MOC-style record for the AI tooling itself.
- **No hidden connections:** confirm the inference software makes no outbound calls (telemetry, update checks).
  On a true air gap, physically and on the firewall.
- **Same safety rules as section 5:** read-only, derived from the drawing of record, reviewed by people before use.
  Running the model locally removes the data-egress question. It doesn't remove the review step.
- **Audit:** log which sheet went in, which model version and prompt produced what, and who approved the reviewed
  result.

**Choosing between cloud and local is a trade-off, not a rule.** Frontier cloud models scored higher in this
project. A local model may score lower but keep every drawing in-house. Measure both on *your* sheets with the
same evaluation, then decide with your security and data-governance owners, not from a vendor slide.
