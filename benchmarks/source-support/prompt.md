# Judge the supplied claims against the bounded evidence packet

Use only the selected `*.input.json` packet. Do not open scoring keys, reference answers, controls or results.
This is an exposed development exercise using project-authored paraphrases. It does not test comprehension of
the original PDF, deployed plant conditions or unfamiliar documents.

Preserve each item's exact `id`. Judge within its `claim_time_scope`; explain relevant scope in `reason`.
Return one judgment:

- `supported`: the admitted evidence supports the whole claim within that scope.
- `contradicted`: the admitted evidence directly conflicts with the claim.
- `insufficient-evidence`: the bounded evidence cannot settle the claim. Silence does not establish absence;
  historical or published records do not establish current installed state or deployed revision.

Return JSON only:

```json
{"schema":"source-support-answer-1","decisions":[{"id":"EXACT_ITEM_ID","judgment":"insufficient-evidence","evidence_ids":["ADMITTED_EVIDENCE_ID"],"reason":"Explain the scope and evidence for this particular judgment."}]}
```

Use one or more evidence IDs from that item's `admitted_evidence_ids`. Keep distinct sources distinct, including
multiple sources behind one evidence entry. Explain timestamp, endpoint, quality and revision distinctions when
relevant. Do not invent missing measurements, safeguards, owners or operating instructions.

The scorer checks IDs and labels against a fixed key. It requires a nonempty reason and admitted citation IDs,
but cannot determine whether either is persuasive or correct. A person must review those. Missing decisions
remain in the accuracy denominator; a readable/scored `ok` status does not mean complete or reviewed.
