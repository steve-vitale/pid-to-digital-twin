# A small context register you can run offline

All documents, equipment, people, dates and decisions in this example are invented training fixtures under the
repository's MIT license. They are not from MIT as an institution or from a real plant. The two pressure values
are a planted disagreement. The accepted service answer demonstrates the software and is not a person's sign-off.
Every plant-truth field stays unknown.

From the repository root:

```sh
python -S scripts/context_register.py prepare --model examples/context-register/illustrative/model.json --questions examples/context-register/illustrative/questions.json --sources examples/context-register/illustrative/sources.json --out my-context/prepared
python -S scripts/context_register.py apply --model examples/context-register/illustrative/model.json --questions examples/context-register/illustrative/questions.json --sources examples/context-register/illustrative/sources.json --answers examples/context-register/illustrative/filled_answers.csv --out my-context/current
```

`my-context/prepared/answers.csv` is the blank sheet you would fill. `evidence_choices.csv` gives the source,
locator and fingerprint to copy into an answer. The second command uses the supplied filled training sheet so
you can see the whole result immediately. Open `my-context/current/context.md`.

The result keeps all four questions visible:

| Question | Result | What remains |
|---|---|---|
| P-101 pressure limit | Disputed: 50 kPa and 60 kPa from separate documents | Select the governing evidence and record a decision |
| P-102 service | Accepted source interpretation, water | Fictional owner/reviewer/date; plant truth unknown |
| P-101 normal range | Needs data | Collect and review a trend |
| P-101 identity walkdown | Unanswered | A person must check the equipment |

Four historical decision snapshots and one fictional ownership assignment are retained. Three questions still
need an owner. The [expected files](expected/context.md) are committed and reproduced by the example test.

To retain decisions when you rerun, pass the current register explicitly:

```sh
python -S scripts/context_register.py apply --model examples/context-register/illustrative/model.json --questions examples/context-register/illustrative/questions.json --sources examples/context-register/illustrative/sources.json --register my-context/current/context.json --out my-context/current
```

For a source revision, use copies of the training files. Update the document's declared revision and expected
SHA-256 deliberately, then refresh using the preserved register. The old evidence-bound answer sheet must not be
used to approve the new source. Prepare a new sheet and review the changed evidence. Unrelated answers persist.
The test exercises this with disposable copies; it does not alter these committed files.

Full maintenance and handoff instructions: [CONTEXT_REGISTER.md](../../../docs/CONTEXT_REGISTER.md).
