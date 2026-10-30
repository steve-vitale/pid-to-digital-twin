# Start with one engineering question, then decide whether to pilot

Copy [pilot-brief.md](pilot-brief.md) into your team's approved working documents. Start with one question and
the sources needed to answer it. You can do this manually or with company-approved Copilot, without Python,
a model, a graph or a custom agent. Use the [connectivity guide](../../docs/INTERNAL_CONNECTIVITY.md) for permitted
source access. Keep company documents outside this public repository.

The immediate result is a short, reviewable finding: what the selected records support, what remains unknown
and who should take the next step. A desk-based investigation need not become a trial or an equipment change.

## First, investigate the existing sources

1. **Ask one bounded question.** Name the equipment or record, the question and intended recipient. For example,
   ask which deployed configuration explains an archived signal. Do not begin by trying to model the whole plant.
2. **Select the evidence.** Retain document identities, revisions, original locations and exact pages/sections.
   Mark unknown metadata and revision conflicts. A retrieved citation still needs checking against the original.
3. **Write a qualified answer.** Separate reported facts, interpretations, conflicting records and missing evidence.
   A partial answer or unresolved question is useful; it does not establish current installed state or choose
   which document governs.
4. **Hand off the next action.** Name the needed reviewer/evidence owner and ask for the missing record or review.
   Until someone accepts it, mark the packet **needs owner**. Record the review date and any agreed next step.

Use the brief's source-investigation sections. Mark trial fields **not run / benefit not measured** if no trial
occurred. The template does not validate its completion, authenticate an approval or establish a site's authority.

| Worked example | What to look for |
|---|---|
| [Covestro source question](../loop-audit/covestro/first-question.md) | A qualified partial explanation and missing controls records; owner and installed behavior unresolved. |
| [NIST configuration question](../context-register/nist-smstestbed/first-question.md) | A published identifier-meaning change and the missing deployment/mapping evidence. |
| [Millard generated question](../opportunity-screen/millard/first-question.md) | A model-based collection request kept separate from a manually authored controls question. |

If using the question engine, retain the complete finding ID, asset IDs and exact catalog revision/content hash
with the source/model references. A rule ID or catalog filename alone is insufficient. If rules change, regenerate
the screen. A manual document question needs a labelled local reference, not an invented model or finding ID.

## If the team chooses a measured pilot

Extend the same brief rather than starting a separate evidence trail:

1. Name the decision-maker, intended user, evidence owner and any operational participants required for the work.
2. Set the comparison before the trial: metric, units, baseline, operating conditions, source and site-selected
   success/stop criteria. The [timed-review protocol](../../docs/REVIEW_EFFORT_PROTOCOL.md) covers drawing review.
3. Collect and check observations under comparable conditions. A question's collection requests are a plan,
   not completed measurements. Retain unsuccessful attempts and manual fallback.
4. Record continue, change scope, stop or insufficient evidence, with reasons, next owner and review date.

Missing baseline, observations or responsible decision-maker means **insufficient evidence**. No pilot benefit
has been measured by these software examples. Applicable site access, engineering, quality and change processes
still govern actual work.

## After the first packet

Keep the brief, original sources and revisions together so another engineer can reconstruct the reasoning.
Review dependent conclusions when evidence changes. The optional [local context register](../../docs/CONTEXT_REGISTER.md)
can retain supplied answers and dependencies for supported models/questions; it is not required for a plain brief.
Use the separate [model-review route](../../docs/REVIEW_LOOP.md) to correct a working model—answers do not edit it.

For continuing team use, the company system owns maintained records, access, accepted decisions and responsibility.
The [lifecycle](../../docs/CONTEXT_LIFECYCLE.md) describes the intended handoff and return path; checked company
adapters and automatic document updates remain integration work. The [MCP starter](../internal-mcp/README.md)
retrieves one local snapshot; company authentication, Copilot deployment and live process connectors are separate.

Return to the [documentation map](../../docs/README.md) for the next task and [project status](../../docs/STATUS.md)
for the implementation gaps. No company handoff or operational benefit is established by a supplied example.
