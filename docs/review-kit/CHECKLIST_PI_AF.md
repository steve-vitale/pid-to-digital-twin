# Checklist: PI AF export

**Files:** `out/pi/pi_builder_af.csv` (Tennessee Eastman), `out/twin/r2-tiles-trace/codex/pi/pi_builder_af.csv`
(extracted twin). **What is and is not verified:** `docs/PI_MAPPING.md`, section "What is verified, what is not".

These files have never been imported into a PI system. Nothing in this checklist changes that; it only finds
problems earlier.

## Track A: anyone

1. Run the offline check and keep its output:
   ```sh
   python scripts/check_pi_export.py out/pi/pi_builder_af.csv
   python scripts/check_pi_export.py out/twin/r2-tiles-trace/codex/pi/pi_builder_af.csv
   ```
   Expect no errors and the warnings listed in `docs/PI_MAPPING.md`. Anything else is a finding.
2. Open `out/pi/pi_builder_af.csv` in a spreadsheet. For 10 attribute rows, check that the `Description`
   (`<tag>: <text>`) matches the same tag in `out/ops_review_sheet.csv`: same tag, same unit of measure.
3. Check that each attribute sits under the unit the screens show it on (`Parent` column against the Ignition
   unit screen), for the same 10 rows.
4. Read the warnings and say, in plain words, what a PI administrator would have to do before an import
   (custom units, templates, the `°C` spelling). If you cannot, the documentation is unclear: that is a finding.

## Track B: operations or controls reviewer (ideally someone who administers PI)

1. **Units of measure:** how does your site write gauge pressure (`kPa g`), thousand standard m³/h (`kscmh`),
   mole percent (`mol%`) and degrees Celsius in AF? Is there a standard UOM list?
2. **Hierarchy:** would your site put these attributes under unit elements like this, or under equipment
   templates? Would it use templates at all?
3. **Point naming:** `TE.<tag>.PV` is a placeholder. What does a real point name look like at your site, and who
   owns the mapping?
4. Would you run the "Steps a plant with PI would run to confirm" in `docs/PI_MAPPING.md` as written? What is
   missing or wrong?

Record answers in the notes file. Mapping real points is a separate, attested step (`scripts/map_pi_points.py`)
and is not part of the review day.
