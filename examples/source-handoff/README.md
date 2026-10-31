# Explicit local Native/source handoff

This optional prototype exports one explicitly selected source-bearing model into
`native.model.json`, the complete policy-filtered `source.evidence.json`, and
`handoff.manifest.json`. The result is a draft for review. The native projection
preserves every field except the top-level packet. Existing embedded models remain
supported. No graph, context, MCP or Copilot consumer acquires source support here.

Run the small public training example offline from a clean checkout with Python 3.10+:

```text
python -B scripts/source_handoff.py export --root . --embedded-model examples/source-handoff/fixture/embedded.model.json --out handoff-example-v1 --owned-scope "Training / process" --responsible-role "Process engineering"
python -B scripts/source_handoff.py inspect --root . --native handoff-example-v1/native.model.json --evidence handoff-example-v1/source.evidence.json --manifest handoff-example-v1/handoff.manifest.json --format text
python -B scripts/test_source_handoff.py
```

The committed [converted model](worked/native.model.json), [captured evidence](worked/source.evidence.json)
and [manifest](worked/handoff.manifest.json) use the same training scope and role shown above. They can be
inspected before running a command; the labels are supplied training data, not company approval. Each role has
a distinct job: the model feeds existing Native tools, the evidence preserves captured structured occurrences,
and the manifest binds their bytes and declarations. The brief identifies the selection and its limits.

Use a NEW output directory for another version. Any existing role file, including an
identical file, refuses export. An existing directory containing unrelated files is
allowed and those files are preserved. All inputs and outputs must resolve under the
explicit approved root. The embedded input can have another parent; the three
inspected role files must share one package parent. The tests use the platform's
temporary directory, honoring caller `TEMP`/`TMP` selection. Git is required for
the checkout/relocation tests; no accounts, downloads or model calls are needed.

For your own drawing, first use the explicit source capture route, for example:

```text
python -B scripts/dexpi_reader.py --xml APPROVED_ROOT/drawing.xml --out APPROVED_ROOT/captured --sheet-id revision1 --capture-source
python -B scripts/source_handoff.py export --root APPROVED_ROOT --embedded-model APPROVED_ROOT/captured/revision1.model.json --out APPROVED_ROOT/handoff-v1 --owned-scope "Site / process" --responsible-role "Process engineering"
```

The reader's default remains Native-only; the handoff utility refuses a Native-only
model rather than finding a source or capturing evidence itself. The tool does not
open originals, URLs, schema references, siblings or historical code files during
inspection. All three receiving files are explicitly selected.

Each selected file and generated artifact has an inclusive 32MiB limit. Acquisition
requests at most 64KiB, continues positive short reads, and distinguishes EOF from
the byte beyond the cap. The entire encoded success brief has an inclusive 2MiB
limit, including escaping, Unicode and the final LF. A complete sidecar may fit
its file limit while a larger brief refuses. These are protocol limits, not memory,
latency or plant-capacity claims.

Export validates all artifact bytes and the entire brief before creating the
directory. It then writes Native, evidence and manifest in order, rechecking
selected input bytes and identities. A later failure can leave an INCOMPLETE prefix
or partial current role. There is no rollback, atomic trio, race-free transaction,
concurrency control or publication state. A manifest's presence is not success;
run explicit inspect and use the company's review/release process.

Preserve complete trio bytes through the approved company transfer route. Git's
raw-file attributes protect the committed seed; apply the company's approved
byte-preservation policy to its own packages. CRLF conversion changes raw hashes.
Inspect accepts legal alternative JSON formatting only when actual raw bindings,
packet/native semantics and package identity are consistent. Reattachment places
the packet last; arbitrary original whitespace, escape spelling and top-level
packet position are not reconstructed.

Send only the verified brief and attachments permitted by company policy and the
client. A brief is a summary, not access to the complete packet. The company-managed
receiving system owns ongoing identity, access, review and decisions; this inspectable
toolkit supplies portable inputs and an on-ramp to that system. Keep unchanged
original XML/images and the review note in existing company systems. Record the
selected package/source revision, Native/evidence/manifest hashes, supplied material,
omissions, unresolved decisions and the next responsible role. No approved transfer
route means the work stays local.

Historical input/exporter/validator hashes are declared history, distinct from the
current receiving code hashes. Scope, role and opaque company reference are quoted
data, not authenticated ownership, equipment identity, merge authority or company
approval. `not_compared`, `unverified`, `not_reverified`, `not_evaluated` and
`not_provided` preserve the limits of the local check. No latest/revocation or
installed-plant truth is inferred. No operator review or timed usability is claimed.

## Public fixture credit and limits

The unchanged 6,144-byte CRLF XML is DEXPI example `I01V01-VER.EX01.xml` from
the DEXPI initiative and its contributing members, in the
[DEXPI TrainingTestCases repository](https://gitlab.com/dexpi/TrainingTestCases),
commit `a23d61e2e089eb2ca464cd552f9ae580a2785963`, under
[Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/).
Its exact upstream path, original digest and license record are in
[PROVENANCE.json](fixture/PROVENANCE.json). The embedded JSON is this project's
Native conversion plus the complete existing policy-filtered source packet, an
adaptation retaining that source credit and license. The fixture data is not
MIT-only. Credit and expected identities remain separate from the hash-bound model.

This is a fictional public training example, not plant/customer data, engineering
approval or evidence of accuracy on held-out company drawings. Complete evidence
means the entire captured policy-filtered packet, not every original XML byte or
text/geometry payload. Review of this seed and named-field exclusions do not provide
general PII detection or blanket clearance for arbitrary company input. See the
explicit one-XML redistribution exception in [NOTICE.md](../../NOTICE.md).
