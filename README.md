# P&ID → Digital Twin Jumpstart

[![tests](https://github.com/steve-vitale/pid-to-digital-twin/actions/workflows/tests.yml/badge.svg)](https://github.com/steve-vitale/pid-to-digital-twin/actions/workflows/tests.yml)

**Turn engineering records into a starting point your team can inspect and build on.**

Start with one equipment question and the documents you already have. Use the toolkit to organize draft assets
and connections, trace claims to their sources, and identify the evidence still needed. The result is a small
engineering packet: source references, draft outputs, open questions and a clear next step.

This is one foundation for future digital twins and manufacturing applications: a shared understanding of what
equipment exists, how it connects, what the records support and what remains unknown. A drawing is one view of it.

## Start with one question

**Using company-approved Copilot, with no local software?** Copy the
[first-question brief](examples/first-pilot/README.md), select permitted sources and check the cited evidence.
You can begin with a document clarification; no asset model or custom agent is required.

**Want to see the tools connect?** [Follow one pump through the actual files](examples/from-description/assisted/PUMP_WALKTHROUGH.md):
description → authored model → draft drawing → investigation question → evidence request.
The example is illustrative. The [description guide](examples/from-description/README.md#try-the-connected-route-offline)
has the commands to build it offline with Python and the drawing dependencies; no model account is needed.

![Illustrative pump and tank draft produced by the description workflow](examples/from-description/assisted/result/pid/D1.png)

## Start wherever you are

Choose the guide for your starting records. Each guide states its setup, outputs and review needs.

| Your starting point | Start here |
|---|---|
| Documents and one question | [Investigate the sources and prepare a first brief](examples/first-pilot/README.md) |
| A written process description | [Author, check and build a draft model/drawing bundle](examples/from-description/README.md) |
| A P&ID image | [Try the supplied extraction offline, then use your own drawing](examples/own-drawing/README.md) |
| Supported DEXPI XML | [Read the structured export and inspect omissions](examples/from-dexpi-xml/README.md) |
| A controls loop list | [Compare the listed loops with the model or drawing](examples/loop-audit/README.md) |
| Historian CSVs | [Analyze recorded history and its false alarms](examples/historian-csv/README.md) |
| Labelled sheets and saved model answers | [Score an extraction against known answers](examples/vendor-evaluation/README.md) |

## What connects today: the hub and spokes

The tools have different input contracts. Descriptions need an engineer or approved assistant to author the
interpretation; a detailed draft P&ID also needs authored layout. Supported model JSON can feed questions,
platform staging and a portable graph. The graph supports source review, context packets and optional read-only
MCP access. It cannot currently regenerate every tool's input.

Use the [workflow and format map](docs/WORKFLOWS.md) to see the supported connections and manual steps.
The [feature reference](docs/FEATURES.md) lists the individual tools and reviewed examples.

## From a first packet to company context

Use the packet to make one investigation understandable to another engineer. As people rely on it, the company
needs to maintain source revisions, accepted decisions, owners, access and history in its shared systems.
The toolkit supplies the starting workflow and portable files. Company-system adapters and continuing document
updates require separate integration and acceptance. See the [handoff and lifecycle](docs/CONTEXT_LIFECYCLE.md).

## Status

These are prototypes tested on public inputs. Outputs are drafts for engineering review. No plant's own data,
operations review, PI import or measured operational benefit is established. The Ignition lab demonstration is
specific to Tennessee Eastman; its build command does not build your plant.

- **Use it:** [Documentation map](docs/README.md) · [Plan a company pilot](docs/AT_YOUR_PLANT.md)
- **Connect it:** [Approved Copilot, internal MCP and data boundaries](docs/INTERNAL_CONNECTIVITY.md)
- **Assess it:** [Results and limits](docs/RESULTS.md) · [Review the evidence](docs/REVIEWING.md)
- **Improve it:** [Contribute cases, model runs and tested changes](CONTRIBUTING.md)

Code is MIT; drawing-derived assets have their own terms in [NOTICE.md](NOTICE.md).
AI coding agents wrote most of the implementation; the [journal](docs/JOURNAL.md) records authorship and mistakes.

Read the [state of the toolkit](docs/STATUS.md) for working parts, open defects and unfinished integrations.

<details>
<summary>Links retained for earlier research references</summary>

### Results (held-out drawings, and how they were used)

Moved to [results and interpretation](docs/RESULTS.md#results-held-out-drawings-and-how-they-were-used).

### Drawings only, process knowledge only, or both

See [supported workflows](docs/WORKFLOWS.md) and the [TE/OPEN100 demo comparison](docs/DELIVERABLES.md).

### Tutorial: reproduce it

Use the [research reproduction guide](docs/REPLICATE_AT_YOUR_PLANT.md).

### What's a tool and what's a record

Use the [documentation map](docs/README.md#reference-and-research-records) and [script reference](docs/SCRIPTS.md).

</details>
