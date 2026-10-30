# Start with one engineering question, then decide whether to pilot

Start with one useful question and the records needed to answer it. The question engine can suggest investigations
from a supported model; a manually authored question about existing documents is equally valid. The engine does
not choose the company's priority, authorize a trial or demonstrate value.

Copy [pilot-brief.md](pilot-brief.md) into the team's working documents. Begin with its source-investigation
sections. Extend the same brief if the team later chooses a measured pilot. Missing information stays unknown;
the template neither validates completion nor supplies an approval, threshold or achieved result.

For a filled source-only example, read the [Covestro first-question brief](../loop-audit/covestro/first-question.md).
It shows exact source citations, a qualified partial explanation and missing evidence in one handoff document.
The main behavior question stays unresolved, with no assigned recipient, accepted handoff or trial result.

For a generated question, the [Millard refrigeration brief](../opportunity-screen/millard/first-question.md)
starts with an actual E30 screen on a deliberately small report-based model. It separates the energy collection
request from a manually authored controls-record question and keeps both unresolved. No context register is needed.

## First, investigate the existing sources

Record the question, intended recipient, source identities/revisions and exact locations, what they support and
what evidence is missing. For a generated question, copy its complete finding ID and exact asset IDs from
`questions.json` (for example `E18@model`, not just catalog rule `E18`). For a manual question, use a labelled local
reference and the source's full identities. No asset model or generated ID is required for a document clarification.

For a generated question, retain the actual question catalog too, including any working copy supplied through
`--catalog`. Record its revision/content hash with the source/model references in the brief. The report's displayed
catalog filename helps locate it but cannot prove its contents or authority. If question rules change, regenerate
the screen rather than assuming the same finding ID still describes the same investigation.

Read the cited records and ask the document or engineering owner for the missing evidence. Record a qualified
answer, partial answer or unresolved question with the evidence and review date. If no recipient has agreed to
take it, keep the handoff marked **needs owner**. An assembled draft can still be useful while that remains open.
The [Covestro intake](../loop-audit/covestro/README.md) shows such a question with its missing records and owner
explicitly unknown. It supplies no completed investigation or site assignment.

A source investigation can conclude with an explanation of what the cited revision says. It does not establish
the current installed state, choose the governing document or authorize equipment work. Mark the trial fields
**not run / benefit not measured** when no trial occurred. A trial baseline and an operator participant are not
prerequisites for this desk-based first packet; actual access and work must still fit the organization's rules.

The plain brief and originals are enough to start. The optional [context register](../../docs/CONTEXT_REGISTER.md)
can retain answers and revision dependencies when a supported model/graph, question document and exact asset
references are available. Do not invent a model merely to store a source question.

## If the team chooses a measured pilot

Name the sponsor, intended user, evidence owner and applicable operational participants. The pilot should answer
one decision under a defined comparison. A supported decision to stop is a useful outcome too.

1. **Pick the decision.** For example, decide whether assembling a reviewed asset pack for one piece of equipment
   is less work than the current manual approach, or whether a pump merits a detailed drive study. Name the
   person who will use the result, the boundary and the authority needed for any next step.
2. **Choose one question and evidence pack.** Use an exact finding/asset ID from `questions.json`; manually authored
   questions also work. Keep the original documents and their revisions. The [question-engine bridge](../context-register/bayer/README.md)
   shows why a historical operating narrative can be useful while leaving the question only partly answered.
3. **Set the comparison before the trial.** Name the metric, units, baseline window, operating conditions and
   source. The site chooses a success threshold, resource limit and stop conditions. For drawing work, reuse the
   existing [timed-review protocol](../../docs/REVIEW_EFFORT_PROTOCOL.md). An assumed time saving is not a baseline.
4. **Collect and review.** Reuse the screen's `data_requests` when present, or the manual question's collection
   plan. Assign the people doing the walkdown, trend export and interpretation. Retain answers, ownership,
   competing evidence and review dates in the brief or a compatible context register. Recording a request does
   not complete it or assign site authority.
5. **Record the result and next owner.** Compare the observation with the baseline under comparable conditions,
   retain unsuccessful attempts and manual fallback, then record continue, change scope, stop or insufficient
   evidence. Name who receives the packet and when it will be reviewed again.

Do not mark a pilot complete while its baseline, trial observation or responsible decision-maker is missing.
Record **insufficient evidence** and the collection action that remains. A source-backed answer alone is not an
approved pilot or a measured benefit. A person at the site decides which documents govern, whether an operational
change is permitted, and what site acceptance is required.

Keep the brief, original sources and any source manifest, context history, reviewed model and observations
together. A second engineer should be able to reconstruct the decision from that packet. On a later source
revision, refresh the context register where used, or review the brief against the new source, and revisit
dependent conclusions. Transfer the packet's IDs, evidence, unfinished states and history through a reviewed
adapter when another team or system takes over.

When review identifies a model error, the existing [local correction route](../../docs/REVIEW_LOOP.md) applies an
engineer-filled `OPS_` sheet to a supported working model, retains old values and then regenerates outputs. Preview
with `--dry-run`, preserve the base and inspect the resulting diff; valid rows can persist even if other rows
refuse. A context answer alone does not edit the generator model. For ongoing organizational use, follow the
[context lifecycle](../../docs/CONTEXT_LIFECYCLE.md): stage the correction for the central authority, then generate
from its released snapshot. The organizational snapshot adapter and automated document update service remain
an integration target.

## After the first packet

The source investigation or pilot should leave one useful engineering result and an understandable record of how
the team reached it.
It also makes the next organizational need concrete: someone else must be able to find the evidence, understand
the decision and know who maintains it when the documents or equipment change.

When several people or projects need that context, take the packet into a shared company system. Look for a place
that retains source revisions and relationships, open questions, attributed decisions, ownership and history
under the company's access and review rules. A folder of generated documents leaves those responsibilities to
individuals. Keep the existing operational systems responsible for executing work and returning its results.

Use the toolkit's specialist tools as needed for new drafts, checks and evidence collection. The company system
should hold the maintained context and released snapshots from which those tools work. Returning a generated
finding is a new proposal for review. The [lifecycle guide](../../docs/CONTEXT_LIFECYCLE.md) describes that intended
handoff; an actual adapter and round trip still need validation. There is no ready hosted connector in this repo.

This workflow has software examples and AI reader review; no engineer's adoption or operational benefit has been
measured with it. Use that first site pilot to learn whether the package helps, including a result that it does not.
