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
   Expect no errors. The TE sheet should have one warning (create or map the units in `custom_uoms.csv`). The twin
   sheet should have two warnings: no units, and placeholder rows held back from publishing. Anything else is a
   finding.
2. Open `out/pi/attribute_descriptions.csv` and `out/pi/pi_builder_af.csv` in a spreadsheet. For 10 attributes,
   check that the description (`<tag>: <text>`) matches the same tag in `out/ops_review_sheet.csv`. The unit in the
   sheet should be the same unit, written the AF way (`°C` for `degC`).
3. Check that each attribute sits under the unit the screens show it on (`Parent` column against the Ignition
   unit screen), for the same 10 rows.
4. Read `out/pi/IMPORT_STEPS.txt` and `out/pi/custom_uoms.csv`, and say in plain words what a PI administrator
   would have to do before an import. If you cannot, the documentation is unclear: that is a finding.

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
