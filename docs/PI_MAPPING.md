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

## Generated PI files (sheet schema v2) and native handoff

**Not import-tested.** None of these files has been published to a licensed PI AF server. Every file says so, and
so does `reconciliation.json`. Each export writes four files under `pi/`, plus `reconciliation.json` for an extracted
twin:

| File | What it holds |
|---|---|
| `pi_builder_af.csv` | The PI Builder sheet: element templates first, then elements, then attributes, with the headers the vendor sheets show (`Selected(x)`, `Parent`, `Name`, `ObjectType`, `Description`, `Template`, `AttributeType`, `AttributeDefaultUOM`, `AttributeDataReference`, `AttributeConfigString`) |
| `custom_uoms.csv` | Every unit the sheet uses that has no vendor-published AF abbreviation in the sources read, with a definition (class, whether the class is new, name, abbreviation, reference unit, factor, offset, how many attributes use it, and a note). None of these units is assumed to exist |
| `attribute_descriptions.csv` | Attribute descriptions (`<parent>\|<name>`, description). No vendor sheet shows the attribute description header, so they are kept out of the sheet |
| `IMPORT_STEPS.txt` | The publish order, generated with this export's counts |

What changed from the v1 staging sheet:
- **`AttributeType`** replaces `AttributeValueType`, which appears in no vendor source. The separate "UNVALIDATED
  candidate" file is gone; a regenerated twin folder deletes its old copy.
- **Units.**
  - `degC` is written as the vendor abbreviation `°C`. `%`, `kW` and `m3/h` already matched.
  - `kg/h`, `kPa g`, `kscmh` and `mol%` are defined in `custom_uoms.csv`:
    - `kg/h` (Mass Flow Rate, 1/3600 of kg/s) is exact, and may already exist at a site.
    - `mol%` (Ratio) is equal to percent.
    - `kPa g` and `kscmh` each get their own new class with no conversion. A gauge-to-absolute conversion needs
      the local atmospheric pressure, and standard volume is not actual volume.
  - A site with its own convention maps these to its own units instead.
- **Element templates.** The six TE templates (`FeedHeader`, `Reactor`, …) are `ElementTemplate` rows with an
  empty `Parent`, at the top of the sheet (the convention on the vendor's p92 sheet). An empty AF database no longer
  depends on templates that don't exist.
- **Descriptions.** `Description` is written for element and template rows. It is listed as an Element and
  ElementTemplate column in the vendor's column dialogs, and is a sheet header on the PIPoint sheet. It is left empty on
  attribute rows.
- **Placeholders.** An attribute whose PI point reference is a placeholder (the extracted twin's, which also have no
  units) has an empty `Selected(x)`, so PI Builder won't publish it. `reconciliation.json` lists each attribute's
  `selected` flag and status. Rows with a reviewed `pi_point` mapping are selected.

`reconciliation.json` (extracted twins) records the sheet schema, what changed from v1, the remaining contract
checks, asset IDs, attribute paths, mapping attestations, config strings, types and units, the placeholder status of
each row, element, template and attribute counts, and the native verification checklist. No PI point creation, PI
connection, account access, read-back or import is performed by these scripts.

CSV quoting preserves commas and quotes; spreadsheet formula-like free-text labels are prefixed with an apostrophe.
Mapping fields reject formula-like text rather than silently changing the address.

Before an authorized native import, still compare the header row and row conventions with a sheet retrieved from the
installed PI Builder version (step 2 below). Both "documented" and "matches the vendor workbooks" mean only that.

## Primary-source basis and limits

The vendor's [Asset Framework: Beyond the Basics workbook](https://osicdn.blob.core.windows.net/learningcontent/Online%20Course%20Workbooks/Asset%20Framework_Beyond%20the%20Basics_Workbook.pdf)
shows the `\\server\point` configuration structure using substitutions (page 34),
and recommends retrieving existing structures as syntax examples when using PI
Builder (pages 85–86). Page 92 uses `AttributeType` and `AttributeDefaultUOM`.
The mapper uses only literal archive/point components in that reference shape,
and disallows substitutions and extra config parameters. This source supports
reference construction and the reconciliation workflow, not an end-to-end import
claim or verification of the supplied type/UOM on a live system.

## What is verified, what is not (2026-10-13)

The PI AF files have **never been imported into a licensed PI system**. Nothing below changes that.

| Claim | Status | Evidence |
|---|---|---|
| Sheet headers `Selected(x)`, `Parent`, `Name`, `ObjectType`, `Template`, `AttributeType`, `AttributeDefaultUOM`, `AttributeDataReference`, `AttributeConfigString` | **Seen in vendor workbooks** | Beyond the Basics workbook pp87, 92; TechCon 2016 PI Builder lab p26 (sheet screenshots, read by OCR and checked by eye) |
| `Description` on element and template rows | **Listed as an Element / ElementTemplate column**, and a sheet header on the PIPoint sheet | TechCon pp25, 31; Beyond p89 |
| Attribute description header (`AttributeDescription` by the prefix rule) | **Unconfirmed**, so not written: descriptions go to `attribute_descriptions.csv` | TechCon p26 lists the property only |
| `AttributeValueType` (v1 sheet) | **Not a documented column**; replaced by `AttributeType` in v2 | The dialog calls the property Type and the sheets show `AttributeType` |
| `ObjectType` values `Element` / `Attribute`; an attribute row's `Parent` is its element's full path | **Seen in a vendor sheet** | TechCon p26 |
| Attribute type `Double` (all TE rows), `String` | **Seen in vendor sheets and a vendor AF export** | Beyond p87; AVEVA AF SDK sample export |
| Attribute type `Int16` | **Seen in a vendor sheet** | Beyond p92 screenshot |
| Attribute type `Int32` (mapper allowlist) | **Not seen** in the sources read | — |
| `\\%Server%\TE.<tag>.PV` | **Form documented**: `%Server%` is the default Data Archive, not the AF server | Building PI System Assets workbook, printed pp209–210 |
| TE default UOMs `%`, `kW`, `m3/h` | **Exact abbreviations in a vendor AF export** | AVEVA AF SDK sample (Ratio, Power, Volume Flow Rate) |
| `degC` | **Spelling differed**; v2 writes the vendor abbreviation `°C` | same sample |
| `kg/h`, `kPa g`, `kscmh`, `mol%` | **Not in the vendor sample**, which holds only 33 of the default classes, so that alone doesn't prove they are missing. v2 never assumes them: they are defined in `custom_uoms.csv` for the site to create or map | same sample |
| Element templates `FeedHeader`, `Reactor`, … | v1 referenced them without defining them; **v2 defines them** as ElementTemplate rows ahead of the elements | Beyond p92 (ElementTemplate rows) |
| Extracted-twin export | All PI references are placeholders and no attribute has a UOM. v2 leaves every placeholder row **unselected**, so it is not published (the workbook says "Always assign a unit of measurement!") | Assets workbook printed p29 |
| Import, point resolution, read-back, value quality | **Not verified** | needs a PI system |

`scripts/check_pi_export.py` turns that table into a check: `python scripts/check_pi_export.py out/pi/pi_builder_af.csv`
prints every finding with its evidence, and fails only on internal inconsistencies (duplicate rows, an attribute with
no element in the file, an element row with attribute fields, a PI Point reference without a config string, an
undocumented `ObjectType`). The evidence is in [`data/pi_builder_reference.json`](../data/pi_builder_reference.json),
with source, page and access date per entry; its UOM list comes from AVEVA's Apache-2.0
`AF-SDK-Getting-Started-Guide` sample export (see `NOTICE.md`). This repo has **no AF XML export**. If one is added:
the AF XML schema (`OSIsoft.AF.xsd`) is not on a vendor download page, but copies are redistributed in third-party
repositories. It types attribute `Type`, `DefaultUOM` and `ConfigString` as plain strings, so passing XML schema
validation would not check types or UOMs either. It does allow an import file to define its own UOMs.

### How to get a PI system to test on (checked 2026-10-13; nothing was signed up for)

| Route | Terms as published | Source |
|---|---|---|
| PI Developers Club (personal development PI System, plus a 45-day free trial) | **Retired January 1, 2026.** Existing subscriptions run to term, with no renewals; the trial site was removed | [AVEVA community announcement](https://community.aveva.com/pi-square-community/f/annoucement-board/100597/product-news-pi-developers-club-end-of-life); [trial thread](https://community.aveva.com/pi-square-community/f/forum/96161/pi-developers-club-free-trial) |
| AVEVA Partner Ecosystem Program | Development packages ("unlimited development PI Servers") for organizations that sign the partner member agreement | same announcement |
| AVEVA Flex subscription, test credits | For Flex customers: "test credits, a cost-effective way of provisioning a non-production environment". Paid; no public price found | same announcement |
| AVEVA Academic Program | "Free academic licenses for research and educational purposes", for institutions, by email request. The page does not say PI Server is included | [aveva.com/en/academia](https://www.aveva.com/en/academia/) |
| Public vendor material (free) | Course workbooks with PI Builder sheets, and AVEVA's Apache-2.0 AF SDK samples with full AF exports. Enough for the offline check above, not for an import | sources in `data/pi_builder_reference.json` |

So there is no longer a free individual route to a licensed PI Server. Realistically, the native import happens at a
plant that already runs PI, or through a partner or academic arrangement.

### Steps a plant with PI would run to confirm

All of it in a separately authorized, isolated AF database, never production:

1. `python scripts/check_pi_export.py <your export>/pi/pi_builder_af.csv` (it reads `custom_uoms.csv` beside
   it). Keep the output, and follow `IMPORT_STEPS.txt` for the order.
2. In PI Builder, connect to the test database. **Elements > Find Elements** on any existing element with attributes,
   with the Parent, Name, ObjectType, Description, Template and Attribute Type/DefaultUOM/DataReference/ConfigString
   columns. Compare that header row and its row conventions with `pi_builder_af.csv`, column by column. Record the PI
   Builder and AF versions.
3. **Library > Units of Measure > Find UOM Classes**, all classes. For every UOM the check flagged, find the site's
   name or abbreviation, or decide to add a custom UOM (`kscmh`), and decide how gauge pressure (`kPa g`) is
   represented. `custom_uoms.csv` gives a definition for each unit that may be missing.
4. Publish the `ElementTemplate` rows first (select only them), or blank the `Template` column.
5. Map real points with `scripts/map_pi_points.py` (reviewer-attested CSV), regenerate, re-run step 1. Leave out
   every placeholder row.
6. Select the rows and **Publish** with Edit Mode **Create Only**. Save the "Publish Selected Objects" result list.
7. In PI System Explorer: compare element and attribute counts and paths with `reconciliation.json`; check each
   mapped attribute resolves to its point (no configuration error), with the expected type and UOM.
8. Back in PI Builder, retrieve the attributes with **Show Values in Columns** and record value, timestamp and
   quality for each mapped attribute. Reject bad or stale values.
9. **File > Export to File** (Include All Referenced Objects) from PSE, and keep the XML with the logs as the
   evidence of what was imported.
10. Report every difference back (a GitHub issue is fine). The import, its read-back and any operational use stay
    the plant's decision.

## Offline tests

```sh
python scripts/test_pi_mapping.py
python scripts/test_check_pi_export.py
```

`test_check_pi_export.py` checks that every evidence entry names a listed source, that the committed TE and twin
exports give exactly the findings in the table above, and that each error class fires on a planted fault.

Tests use synthetic models/points and cover transactional rejection, full diffs,
partial/replacement behavior, OPC separation, callout blocking, placeholders,
CSV safety, dry-run nonmutation, apply, and fail-before-write export guards.
