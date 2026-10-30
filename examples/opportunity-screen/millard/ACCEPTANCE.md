# Scope fixed before the committed screen

This is a development example of the existing E30 question on a small, source-authored refrigeration model.
The original bulletin was read before choosing the subset; a private feasibility run already produced one finding.
This is not a held-out drawing test, extraction benchmark, full facility model or new independent source family.
The CSB is also the source agency for the existing Bayer example.

- Use the unchanged question engine and catalog, selecting only E30.
- Represent one authored aggregate of the reported evaporator group and one reported hot-gas main valve.
  Both identifiers are local labels. Do not invent plant tags, instruments, streams or historian mappings.
- Expect `E30@EVAP-GROUP`, with exactly `EVAP-GROUP` and `HG-MAIN` as its asset references and three unanswered
  collection requests. Absence means absent from this deliberately incomplete model, not absent from the plant.
- Reproduce both committed screen files with the actual CLI. Removing the hot-gas item from a labelled copy
  should leave no E30 finding; that control tests software triggering, not source completeness.
- Check the original report bytes against `source.json`; changed or missing bytes must refuse offline.
  Any download is explicit. Never replace a changed local original to make the check pass.
- Independently compare both model records and the first-question brief against the original pages and Figure 5.
  A source reader must distinguish pump-out duration from defrost frequency and historical evidence from current
  configuration. No model or catalog tuning is authorized by a failed example check.

The generated screen is an energy investigation prompt. It does not analyze restart logic, pressure transients,
control adequacy, safe sequencing or equipment acceptance. The plain brief carries the separate source question
to a qualified company recipient; it supplies no operating instructions, approval or assigned owner.
