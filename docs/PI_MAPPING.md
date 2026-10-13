# PI point mapping from reviewer-supplied references: offline staging, not a native import

The extracted-twin exporter now accepts a separate `pi_point` record. The OPC
`data_point` mapper remains Ignition-only; it cannot establish a PI mapping.
Nothing infers an archive, real point name, value type, or units from drawing text.
Unmapped attributes retain their existing placeholder references. Reviewed valve
callouts remain metadata-only with no data reference; explicit IDs cannot bypass
that restriction.

## Local workflow

Prepare a CSV with exactly these columns (order is flexible):

```csv
asset_id,archive,point,value_type,uom,reviewed_by,review_note
I-1,SYNTHETIC-ARCHIVE,TEST.PV,Double,bar,Synthetic reviewer,Synthetic contract test only
```

This row is synthetic, not a plant address. Use the exact instrument asset ID from
your own model and evidence from a qualified reviewer. `reviewed_by` identifies
who supplied the attestation; `review_note` records their evidence/reference and
scope, including type and UOM review. Both must be nonempty. These strings are
attestations, not authenticated approval or independent PI verification.

`archive` means the PI Data Archive server name, not the AF server. `value_type`
is the requested AF attribute type, not a PI point's native point-type spelling.
The deliberately narrow local allowlist is `Double`, `Single`, `Int32`, `Int16`,
and `String`; it is not a complete enumeration of AF types. `uom` is the requested
AF UOM name. Empty `uom` explicitly means no UOM, not an inferred unit. Compatibility
with actual point types, installed AF UOM definitions, conversions and live values
remains a native verification gate. Digital states/arrays and advanced config
strings are not supported by this bounded mapper.

```sh
python scripts/map_pi_points.py /path/plant_model.json /path/reviewed_pi.csv --dry-run
python scripts/map_pi_points.py /path/plant_model.json /path/reviewed_pi.csv
python scripts/generate.py /path/plant_model.json
```

Dry-run writes nothing and prints the full JSON before/after mapping snapshots,
change list, unresolved IDs and validation errors. Apply prints the same plan and
replaces the local model only after all rows validate. It does not regenerate
exports automatically. Save the JSON report if you need an audit record. Default
partial updates preserve unrelated PI mappings. `--replace-all` removes omitted
PI mappings and restores export placeholders; an empty CSV with a valid header
therefore clears all PI mappings. OPC mappings and source/provenance fields are
unchanged. This CLI supports extracted-twin models only, not the separate TE seed.

The whole mapping transaction fails on unknown IDs, duplicate targets, duplicate
headers/JSON keys, extra/missing fields, rejected instruments, reviewed valve
callouts, unknown types, unknown-marker text, missing review evidence, controls,
formula-like text or unsupported config delimiters/macros. Unsupported/manual
`pi_point` state is also rejected during generation before any export writes.
Simple literal references are supported; complex point names requiring delimiter
escaping must remain pending until their native syntax has been reviewed. Multiple
assets may explicitly reference the same point; that choice is retained for review.

## Generated reconciliation and native handoff

`pi/pi_builder_af.csv` remains the repository's **PI Builder-style staging format**.
`pi/pi_builder_UNVALIDATED_candidate_v1.csv` is a separate, versioned candidate
that corrects only the vendor-observed header mismatch: `AttributeValueType` →
`AttributeType`. Its row data is identical to the legacy staging CSV. This is an
**UNVALIDATED candidate, not native-import-ready**; no other schema correction is
invented. Verify the remaining Parent/Name/ObjectType/Template/data-reference
headers, element/attribute row identities, parent paths and installed-version
conventions against a retrieved native workbook before any import.

`pi/reconciliation.json` lists the candidate schema/version, remaining contract
checks, vendor source/pages, asset IDs, exported attribute paths/names, mapping
attestations, config strings, types/UOMs, unresolved placeholders, counts and the
native verification checklist. The status explicitly says native PI Builder
import has **not been tested**. No PI point creation, PI connection, account access,
read-back or import is performed by these scripts.

CSV quoting preserves commas/quotes; spreadsheet formula-like free-text labels are
prefixed with an apostrophe. Mapping fields reject formula-like text rather than
silently changing the address. Review any escaped labels before native import.
Ordinary unmapped legacy CSV rows remain unchanged.

Before an authorized native import, obtain a sample workbook/export from the
installed PI Builder version and reconcile every column and row convention. In
particular, the legacy staging CSV preserves `AttributeValueType`; the separate
candidate uses the vendor-observed `AttributeType`. Neither is proof that a direct
import is valid.
Exclude unresolved placeholders. Use an authorized isolated AF database and
reconcile imported counts, paths, references, types, UOMs and every mapped
attribute's read-back value, timestamp and quality. Save native error/read-back
evidence. Real plant data verification and operational approval remain separate.

## Primary-source basis and limits

The vendor's [Asset Framework: Beyond the Basics workbook](https://osicdn.blob.core.windows.net/learningcontent/Online%20Course%20Workbooks/Asset%20Framework_Beyond%20the%20Basics_Workbook.pdf)
shows the `\\server\point` configuration structure using substitutions (page 34),
and recommends retrieving existing structures as syntax examples when using PI
Builder (pages 85–86). Page 92 uses `AttributeType` and `AttributeDefaultUOM`.
The mapper uses only literal archive/point components in that reference shape,
and disallows substitutions and extra config parameters. This source supports
reference construction and the reconciliation workflow, not an end-to-end import
claim or verification of the supplied type/UOM on a live system.

## Offline tests

```sh
python scripts/test_pi_mapping.py
```

Tests use synthetic models/points and cover transactional rejection, full diffs,
partial/replacement behavior, OPC separation, callout blocking, placeholders,
CSV safety, dry-run nonmutation, apply, and fail-before-write export guards.
