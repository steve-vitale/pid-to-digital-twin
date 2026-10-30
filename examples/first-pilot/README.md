# Choose one useful engineering pilot

The question engine finds technically relevant things to investigate. It does not choose the company's priority,
authorize a trial or demonstrate value. Start with one operational problem, one intended user and one decision
the pilot will inform. A supported decision to stop can be a useful outcome.

Copy [pilot-brief.md](pilot-brief.md) into the team's working documents and fill it with the sponsor, operator
and evidence owner. It is an editable decision record, not another application or an automatically validated plan.
Missing information stays unknown. The blank template contains no actual approval, threshold or achieved result.

1. **Pick the decision.** For example, decide whether assembling a reviewed asset pack for one piece of equipment
   is less work than the current manual approach, or whether a pump merits a detailed drive study. Name the
   person who will use the result, the boundary and the authority needed for any next step.
2. **Choose one question and evidence pack.** Use an exact finding/asset ID from `questions.json`; manually authored
   questions also work. Keep the original documents and their revisions. The [question-engine bridge](../context-register/bayer/README.md)
   shows why a historical operating narrative can be useful while leaving the question only partly answered.
3. **Set the comparison before the trial.** Name the metric, units, baseline window, operating conditions and
   source. The site chooses a success threshold, resource limit and stop conditions. For drawing work, reuse the
   existing [timed-review protocol](../../docs/REVIEW_EFFORT_PROTOCOL.md). An assumed time saving is not a baseline.
4. **Collect and review.** Reuse the screen's `data_requests` for where and how to collect evidence. Assign the
   people doing the walkdown, trend export and interpretation. Use the [context register](../../docs/CONTEXT_REGISTER.md)
   to retain answers, ownership, competing evidence and review dates. It does not automatically complete each
   collection request or assign site authority.
5. **Record the result and next owner.** Compare the observation with the baseline under comparable conditions,
   retain unsuccessful attempts and manual fallback, then record continue, change scope, stop or insufficient
   evidence. Name who receives the packet and when it will be reviewed again.

Do not mark a pilot complete while its baseline, trial observation or responsible decision-maker is missing.
Record **insufficient evidence** and the collection action that remains. A source-backed answer alone is not an
approved pilot or a measured benefit. A person at the site decides which documents govern, whether an operational
change is permitted, and what site acceptance is required.

Keep the brief, source manifest, context history, reviewed model and observations together. A second engineer
should be able to reconstruct the decision from that packet. On a later source revision, refresh the context
register and revisit dependent conclusions. Transfer its stable IDs, evidence, unfinished states and history
through a reviewed adapter when another team or system takes over.

This workflow has software examples and AI reader review; no engineer's adoption or operational benefit has been
measured with it. Use that first site pilot to learn whether the package helps, including a result that it does not.
