# Carry a known source answer into the next investigation

This source-scoped catalog demonstrates an authored investigation that the default pattern catalog misses.
It uses the existing MGPI development model and CSB report. It does not add a generic alarm rule or claim that
two generated questions prove usefulness. The default catalog still produces zero findings for this model.

Run offline from the repository root:

```sh
python scripts/question_engine.py --model examples/from-description/mgpi/model-expanded-source.json --catalog examples/opportunity-screen/source-investigation/catalog.json --out out/mgpi-source-investigation
python scripts/graph_export.py examples/from-description/mgpi/model-expanded-source.json --questions out/mgpi-source-investigation/questions.json --out out/mgpi-source-investigation/graph.json
```

The first command reproduces the `questions.json` and `screen.md` here. The second retains the questions,
historical answers, source attribution and requests in a portable graph. See the
[context guide](../../../docs/CONTEXT_REGISTER.md) to retain supplied answers, a reviewer, source revisions and
unresolved requests. This example supplies no current answer, owner or acceptance.

**What is already answered:** CSB's [2017 report](https://www.csb.gov/file.aspx?DocumentId=6047), printed p.23 §5.2,
describes a high-level signal that notified operators without automatic unloading shutdown. It also distinguishes
emergency/remote actions affecting downstream bulk-to-day flow from incoming unloading-to-bulk flow. Those are
different endpoints. Historical questions can close on that bounded answer; do not ask someone to rediscover it.

**What is conditional:** a receiving engineer must first identify whether the example applies to an actual
company asset/process and period. Only then request current approved configuration and endpoint-specific action
evidence. An indication, ordinary feedback loop, notification, automatic protective action and remote command
are distinct functions. Their presence or absence cannot be inferred from one another or from missing model data.

The exact `HYPO_BULK` selector is a documented project alias, not a reported plant tag or transferable classifier.
Use this as a recipe: choose a permitted source and a bounded question, retain its known answer with locators,
state what remains unknown, name the receiving decision and evidence, then ask an engineer to assess the packet.
Do not broaden the selector and call that source reasoning. Unrelated models and a renamed/nonmatching alias
stay quiet in the regression controls; this is expected scoping, not generalization performance.

The independently prepared source rubric informed the historical/function/endpoint distinctions before this
candidate was authored. Final source review is separate from reproducing CLI output. No engineer trial,
current installation review, safety assessment, model call or benefit measurement has occurred. Broader default
question coverage and usefulness remain open until additional source families and prospective engineer cases
support them. The [manual brief](../../from-description/mgpi/first-question.md) retains the original handoff.
