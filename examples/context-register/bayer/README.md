# A generated question keeps its partial answer

This example runs the actual question engine, then retains a qualified response in the context register. It uses
the existing sourced Bayer model and the original public CSB report. It is a development example in an existing
source family, with no human owner, reviewer, sign-off or plant-truth verdict.

E18 asks whether heat rejected to cooling water could serve another heating duty. The engine finds one question,
`E18@model`, with six exact asset/stream references and three collection requests. The published narrative supplies
part of the operating-sequence context; it does not establish actual simultaneous duties or an opportunity.

First read the [generated screen](screen/screen.md), then the [retained context report](expected/context.md).
The latter keeps E18 **partial**, with its original temperature/duty, time-overlap and layout/fouling prompts,
decision rule and limits still visible. No saving is calculated and no engineering change is proposed.

From the repository root:

```sh
python scripts/question_engine.py --model data/bayer_rt/process_model.json --question E18 --out my-bayer-question/screen
```

If the source report is not already cached, this existing fetch command downloads it from csb.gov and verifies
its pinned SHA-256. It does not digitize or publish a figure:

```sh
python scripts/digitize_bayer_fig11.py fetch
```

Then run the context workflow against the current original bytes:

```sh
python -S scripts/context_register.py prepare --model data/bayer_rt/process_model.json --questions my-bayer-question/screen/questions.json --sources examples/context-register/bayer/sources.json --source-root data/external --out my-bayer-question/prepared
python -S scripts/context_register.py apply --model data/bayer_rt/process_model.json --questions my-bayer-question/screen/questions.json --sources examples/context-register/bayer/sources.json --source-root data/external --register examples/context-register/bayer/history/before-appearances.context.json --answers examples/context-register/bayer/proposed_answer.csv --out my-bayer-question/current
```

The supplied CSV is an AI-authored proposed interpretation of the temperature-control narrative on PDF page 37
(printed page 29). `source_key.json` records the exact locator, file identity, interpretation and remaining requests.
Neither the report PDF nor its figures are redistributed here. Historical model data and its existing caveats
are not revalidated or upgraded by attaching this answer.

The [prior register](history/before-appearances.context.json) retains the original proposal unchanged. The current
sheet is an explicitly labelled AI re-proposal against expanded item evidence; both decision snapshots remain.
The [old answer sheet](history/before-appearances.answers.csv) refuses against the revised evidence. This software
refresh adds no human review, plant-truth verdict or opportunity claim.

For your own unit, the owner must examine the operating sequence and representative measured duties together,
including their timing and operating states. Record further independently sourced answers without overwriting
this one. Keep unresolved requests visible, and make an explicit reviewed decision rather than treating a screen
as an opportunity or a historical sequence as proof of current operation. The register does not track completion
of each collection prompt automatically.

Use the [first-pilot brief](../../first-pilot/README.md) to choose one decision worth investigating. The
[maintenance guide](../../../docs/CONTEXT_REGISTER.md) explains ownership, revision refresh and portable handoff.
