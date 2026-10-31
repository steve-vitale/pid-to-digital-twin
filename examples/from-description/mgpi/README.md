# MGPI transfer paths: a source-adapted development case

This case takes selected facts from the CSB's [MGPI investigation, report 2017-01-I-KS](https://www.csb.gov/file.aspx?DocumentId=6047)
through an authored model, a separate source-key review and a two-sheet draft bundle. It is another public-report
case within the CSB collection, not a held-out model trial or a new estimate of unfamiliar-description accuracy.
The input is a project-authored adaptation, not the original report's prose. A maintainer saw Figure 3 during
source scouting; no blindness is claimed. No original report figures are redistributed.

## Why retain the first failed source review?

The initial adaptation placed `LI_HYPO` on the hypochlorite bulk tank. A separate coding agent, working from the
bounded original narrative without the candidate, froze a key that could support the indicator's existence but
could not resolve bulk versus day tank. The initial model followed the supplied adaptation; the error was in
the adaptation's source support, not an LLM misreading of that input.

The next sentence in the original paragraph explicitly identifies the bulk tank. V2 expands the source boundary
and adds that one placement fact. It retains V1 unchanged. **The source/key changes; this is not an algorithm gain.**

| Artifact | Role |
|---|---|
| [source-initial.txt](source-initial.txt), [model-initial.json](model-initial.json) | Preserved initial development artifacts; bulk placement is unsupported within V1's restricted original-source scope. Do not treat them as accepted designs. |
| [V1 inventory](v1/source_inventory.json), [V1 fact key](v1/facts.json) | Separate agent's original-narrative interpretation, frozen before candidate inspection; no human engineering sign-off. |
| [V2 inventory](v2/source_inventory.json), [V2 fact key](v2/facts.json) | Explicitly enlarged original-source scope and key, with the added locator and exact difference recorded. |
| [source.txt](source.txt), [expanded-source model](model-expanded-source.json), [answer.json](answer.json) | Current source-adapted development draft; layout is authored separately from the initial model freeze. All tags are project aliases. |
| [HYP draft](result/pid/HYP.png), [ACID draft](result/pid/ACID.png), [graph](result/graph.json), [review](result/REVIEW.md) | Actual built outputs. Geometry and size/spec fields are proposed; platform files are staging. No plant-system acceptance is established. |
| [Protocol](protocol.json), [registered results](../../../benchmarks/results/mgpi-development-source-preserved.md) | Exposure, source revisions, selected scoring scope and planted controls. Recorded model identity/settings are incomplete, so these are development artifacts rather than provider model comparisons. |

`BL` denotes a scope boundary. The two chemistry paths do not share a physical junction, and the unspecified acid
destination must not be equated with `HYPO_PROCESS`. The graph uses the existing single `BL` boundary node; do not
interpret traversal through that node as physical connectivity between chemicals. Separate draft sheets make the
scope distinction visible, but neither sheet is an unloading procedure, isolation plan or drawing of record.

## Run the current draft offline

From the repository root, after installing the existing drawing dependencies, choose new output folders:

```sh
python scripts/description_workflow.py prepare --source examples/from-description/mgpi/source.txt --out out/mgpi-packet
python scripts/description_workflow.py check --packet out/mgpi-packet --answer examples/from-description/mgpi/answer.json
python scripts/description_workflow.py build --packet out/mgpi-packet --answer examples/from-description/mgpi/answer.json --out out/mgpi-result
python scripts/benchmark.py --suite benchmarks/mgpi-development.json --out out/mgpi-development-review
```

The first three commands check and build the supplied answer; they call no model API. The last re-scores saved
artifacts, including failures and controls. Inspect the actual sheets and original evidence, rather than treating
the generated drawing key as independent truth. [The approved-assistant guide](../README.md) explains authoring
for another description. The reported capacities/concentrations and notification-only alarm claim travel as
source-backed draft attributes, but the fact scorer does not grade those attributes.

## What the score can miss

| Development artifact/control | Literal selected-field result | Source-review meaning |
|---|---|---|
| Initial draft against V1 | 26 matched facts, one unexpected placement | Initial adaptation asserted more than the selected primary record supported. |
| Expanded-source draft against V2 | 27 matched facts | Additional source evidence resolves placement; it does not validate the entire design. |
| Empty output | All selected facts missing | Positive/empty behavior remains observable. |
| Wrong chemical endpoint | One missing and one unexpected stream endpoint | The selected-field scorer detects this planted error. |
| False automatic shutdown | Same literal field score as the expanded-source draft | **The scorer misses this false claim** because alarm action is outside its field subset. The original source inventory contradicts it. |

No general success rate or model ranking follows from these rows. The [false-shutdown control](controls/false-shutdown.json)
is a deliberately wrong artifact, not an alternative design. Source review must catch its invented automatic
unloading shutdown. Structure checks, quotation matching and selected-field scores cannot do that work alone.

The [question-engine screen](result/questions/screen.md) currently produces zero findings on this sparse model.
That is a coverage limit, not a clean bill of health. A useful manual source question is: **does the recorded
level alarm stop unloading, or only notify operators?** The selected historical record supports notification
only. Installed-state evidence, present-day protections, numerical settings, complete controls, responsible
owners and accepted decisions are outside this example. Carry the question, source revision, qualification and
next owner through a private [first-question brief](../../first-pilot/pilot-brief.md) into the company's maintained
information and decision system. The [worked draft](first-question.md) shows the qualified answer, missing
installed-state evidence and unassigned recipient. No company handoff has occurred here.

The separate [fixed-claim label exercise](../../../benchmarks/results/source-support-development.md) includes the
false automatic-shutdown claim and historical/current distinctions. Its twelve supplied claims across MGPI and
NIST use explicit project paraphrases and a separately frozen agent-authored key. Results are synthetic scorer
controls, not model trials, raw-report comprehension or a useful-question benchmark. The fact scorer and
question-engine catalog remain unchanged.

## Check the original source

The original 48-page PDF is not committed. Optionally download the checksum-pinned source into ignored
`data/external/csb-mgpi/`:

```sh
python examples/from-description/mgpi/fetch_source.py
```

The receipt records the original URL and raw SHA-256; an existing file or download with different bytes is
refused. Review printed pages 7–8 §2.3 and page 23 §5.2, using the exact scope in each inventory. The inventories
are agent-authored derived interpretations; they are not CSB answer keys or human approval. Source freezes,
the unsupported initial claim and the post-review source expansion remain visible for future contributors.
The `FREEZE.json` files preserve the original key-creation receipts; their private excerpt/helper proof names
do not name files distributed here. Use the public inventories, locators and pinned original to review the facts.
Use [CONTRIBUTING.md](../../../CONTRIBUTING.md) to add other source families and model attempts without relabeling
this development evidence as held out.
