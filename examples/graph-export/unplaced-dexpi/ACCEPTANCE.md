# Acceptance for this bounded repair

Declared on 2026-10-29 before this packet's expected graphs and check results were saved.
The source files and the diagnostic counts below had already been examined while diagnosing the defect.
These are development examples from a seen corpus, not held-out evidence.

1. A clean clone, Python 3.10+ and the standard library reproduce the committed graphs exactly from the
   committed deterministic reader models. No model call, account, network or original XML is required for
   this check. Graph validation must pass, and readable statements must retain the known asset roles.
2. In I04V01-VER.EX01, `FT-04` remains an instrument and `FV-04` remains a final element. The controller's
   explicit reader references produce `FT-04 -> FIC-04 -> FV-04` controls edges. Their source, unverified
   status and unresolved placement remain visible. No equipment ownership or physical signal-direction
   confirmation is invented.
3. In I01V01-SAG.EX01, `XMP_6` remains an instrument with unknown variable and no sensor location.
   No measurement-to-equipment edge is invented, despite equipment being present elsewhere in the file.
4. Mutation controls refuse missing, ambiguous, malformed and wrong-role controller references before graph
   output is written. An explicitly unknown unplaced role stays generic; the legacy no-role operated-valve
   fallback still works. Synthetic controls are labelled as such and do not count as source observations.
5. Optional original verification requires the pinned bytes and exact XML IDs/classes/associations, then
   regenerates each whole model with `dexpi_reader.Reader`. Missing or changed originals fail clearly;
   committed derived models are not substitutes for this source check.
6. A separate optional diagnostic traverses the same 220 cached DEXPI 1.2/1.3 XML files: 214 readable models
   and the same six independently confirmed duplicate-ID refusals. Before the repair, 87 declared unplaced
   roles were downgraded and 44 explicit controller references lacked controls edges. After the repair,
   neither loss may remain and no new graph refusal may appear. This tests retention of the reader's
   interpretation, not the correctness of every interpretation or a gain in drawing extraction accuracy.

The packet changes no matrix acceptance criterion. No human approval, plant truth, private source or
operational deployment is implied.
