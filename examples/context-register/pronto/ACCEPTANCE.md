# PRONTO context packet acceptance criteria

Declared 2026-10-29 before assembling or running the packet. This is linked-document coverage within the existing PRONTO source family, not independent evidence from a new plant.

1. Use at least three public primary documents already pinned by `fetch_corpus.py`. Record document ID, the Zenodo record version, raw-byte SHA-256, attribution, and exact page, worksheet/cell, or physical-record locators for every supplied fact.
2. Assemble roughly twenty source facts and answer/data-request examples. Join them by exact stable asset IDs. Keep unresolved alternate labels explicit without inventing aliases. A repeated tag is a join key, not proof of the current operational state of a plant.
3. Distinguish configured numerical limits from the source's enabled/disabled state. Include disabled-limit negative controls; a number in a disabled row must never become an enabled alarm assertion.
4. Preserve the known report schematic/controller-description disagreement concerning FIC301 as an unresolved issue with both locators. Do not choose a plant truth from conflicting sources.
5. Bind an answer to the exact evidence revisions on which it depends. Synthetic revision copies must make only dependent answers stale. Retain unrelated answers. Reject an unknown or ambiguous asset ID; a tag or alternate label must not be guessed as an alias.
6. Keep missing requested information explicit. No operator response, owner, sign-off, approval, current setpoint, or current alarm state may be inferred from a historical setting, event, or affiliation. Any example roles or decisions are illustrative AI-authored drafts with no human sign-off.
7. The shipped PRONTO packet runs offline without accounts or model calls after the explicit pinned public-source fetch. Original files remain in the ignored cache; the manifest binds these actual supporting files. Missing originals must fail clearly rather than substitute the derived key. The separate tiny illustrative fixture supplies a no-network CI route. Separate deterministic packet consistency from raw-source verification; report unavailable source checks as unavailable, not passed. This source requirement was clarified with the parent task before the packet was run.

The expected checks are exact bindings and source locators, stable joins, explicit disagreements, negative controls, and selective staleness under synthetic revisions. They do not establish extraction accuracy, engineer time saved, operational safety, or review by a person.
