# Opportunity screen: MGPI transfer paths - source-adapted development draft

Model: `examples/from-description/mgpi/model-expanded-source.json`. Questions: `examples/opportunity-screen/source-investigation/catalog.json`.

**How to read this.** This is a screen, not an audit. Each finding is a question the drawing or model
raises, with the evidence found, what to collect (and exactly where), and how the collected data settles it. Nothing
here says the plant wastes energy, and no savings are computed: the "what the source says" lines are the cited
sources' general figures for plants in general, quoted as written, never an estimate for this plant. Data requests
are in one of three states: **on drawing** (the value is on the drawing or model and is quoted as evidence),
**blank on drawing** (the drawing prints a field for it but leaves it empty, so fill that field), and **not on
drawing** (collect it from the place named). Systems listed under "Left out" were not screened.

| Family | Findings |
|---|---|
| Source investigation: historical answer and receiving applicability | 2 |

## Source investigation: historical answer and receiving applicability

### MGPI-NOTIFY: If this historical example applies to a receiving installation, what current approved evidence distinguishes high-level indication/notification from automatic action on incoming unloading?

**About:** HYPO_BULK  

**Evidence on the drawing / model**

- equipment HYPO_BULK reads "HYPO_BULK Sodium hypochlorite bulk tank" (`units[HYPO_BULK]`)

**Data to collect**

- Receiving scope, applicability and engineering owner [not on drawing]. Where: site records: company-approved scope and designated controls/document owner. How: First decide whether this historical question applies to an identified receiving asset/process and period. No receiving company, owner, due date or current configuration is supplied here; if not applicable, record that reason rather than inventing a collection task.
- Current signal function and incoming-transfer action path [not on drawing]. Where: site records: approved current control narrative, logic/cause-and-effect revision and signal mapping. How: Retain revision/locator and distinguish indication, ordinary feedback, operator notification, automatic protective action and remote commanded action. Identify the affected unloading-to-bulk final element or endpoint; do not infer an installed trip or its absence from a level indicator or a missing model record.

**How it is decided:** Historical reading is already answered: the report describes high-level notification, without automatic incoming-transfer shutdown (p.23 section5.2). Close that bounded historical question with its citation. Only an explicitly applicable current-installation question needs receiving records and owner review; record unknowns or not-applicable rather than prescribing equipment or settings.

**What the source says (MGPI):** No operational benefit or measured usefulness is established. The source supports a distinction between notification and endpoint-specific action.

**Limits:** Known historical answer to retain: the sodium hypochlorite bulk-tank high-level signal notified operators and was not configured to shut the transfer automatically (p.23 section5.2). The report records alarm activation at7:59AM and says awareness/evacuation was likely about the same time; do not turn likely into exact timing. This source does not establish every ordinary-control use, present-day configuration, required safeguards or operating safety. HYPO_BULK and LI_HYPO are project aliases.

### MGPI-ENDPOINT: If this example applies to a receiving installation, which current approved remote/emergency action actually affects unloading-to-bulk transfer, separately from bulk-to-day-tank or downstream processes?

**About:** HYPO_BULK  

**Evidence on the drawing / model**

- equipment HYPO_BULK reads "HYPO_BULK Sodium hypochlorite bulk tank" (`units[HYPO_BULK]`)

**Data to collect**

- Endpoint-specific current action and applicability [not on drawing]. Where: site records: approved P&ID/line tracing and remote-command or emergency-stop functional description. How: A receiving engineering owner must identify applicability, process segment, actual final element and current revision. Distinguish incoming unloading-to-bulk from bulk-to-day/downstream transfer; action on one segment does not establish action on another.
- Evidence for any asserted current capability [not on drawing]. Where: site records: applicable approved functional-test/acceptance record or other owner-approved action-path evidence. How: Retain declared test scope, revision/date, result and unresolved discrepancies. No present-day test, acceptance or operational action is supplied here; no new test or live action is instructed.

**How it is decided:** The bounded report-era answer is already sufficient: downstream emergency/remote action existed, but incoming unloading lacked remote shutdown (p.23 section5.2; transfer segments pp.7-8 section2.3). Retain that answer. A separately accepted current-installation claim needs endpoint-specific receiving evidence and a reviewer, not inference from the drawing or the historical source.

**What the source says (MGPI):** No operational benefit or measured usefulness is established. The source supports a distinction between notification and endpoint-specific action.

**Limits:** Known historical answer to retain: two emergency-stop buttons and control-system remote actions affected downstream equipment; one could stop bulk-to-day flow but not unloading-to-bulk flow. The report says even activation would not mitigate the reaction because unloading lacked remote shutdown (p.23 section5.2). The manually activated unloading-area deluge addressed cloud suppression, not automatic unloading isolation. No current action capability/absence, named owner or engineering prescription follows.

## Sources cited above

- MGPI: CSB, Key Lessons from the MGPI Processing Inc. Toxic Chemical Release, 2017-01-I-KS, December 2017. https://www.csb.gov/file.aspx?DocumentId=6047 (license: Publicly available CSB report; this catalog paraphrases bounded facts and links the original.)
