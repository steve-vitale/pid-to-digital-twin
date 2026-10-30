# Point mapping: bundle/plant_model.json ← open100_sheet0_demo.csv

Status: valid plan

I/O source: open100_sheet0_demo.csv; 3108 bytes; SHA-256 `8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857`.
Locators are 1-based physical CSV lines, including quoted newlines. Retain the original file.
Address assignment does not verify OPC syntax, connectivity, signal identity, units or scaling.

Mapped: 25 · On the drawing, not in the I/O list: 10 · In the I/O list, not on the drawing: 2 · Ambiguous: 0

## Mapped

| Asset | Drawing tag | I/O tag | Point | Matched by | Source lines |
|---|---|---|---|---|---|
| S0-IN004 | TE 14084A | TE-14084A | TE_14084A | normalized tag | 2-2 |
| S0-IN005 | TE 14084B | TE-14084B | TE_14084B | normalized tag | 3-3 |
| S0-IN011 | TE 14089A | TE 14089A | TE_14089A | exact | 4-4 |
| S0-IN012 | TE 14089B | TE 14089B | TE_14089B | exact | 5-5 |
| S0-IN022 | TE 14090A | TE-14090A | TE_14090A | normalized tag | 6-6 |
| S0-IN023 | TE 14090B | TE-14090B | TE_14090B | normalized tag | 7-7 |
| S0-IN025 | TE 14091A | te_14091a | TE_14091A | normalized tag | 8-8 |
| S0-IN026 | TE 14091B | te_14091b | TE_14091B | normalized tag | 9-9 |
| S0-IN029 | TE 14092A | TE-14092A | TE_14092A | normalized tag | 10-10 |
| S0-IN030 | TE 14092B | TE-14092B | TE_14092B | normalized tag | 11-11 |
| S0-IN033 | TE 14093A | TE-14093A | TE_14093A | normalized tag | 12-12 |
| S0-IN032 | TE 14093B | TE-14093B | TE_14093B | normalized tag | 13-13 |
| S0-IN007 | PT 14085 | PT-14085 | PT_14085 | normalized tag | 14-14 |
| S0-IN008 | PT 14086 | PT-14086 | PT_14086 | normalized tag | 15-15 |
| S0-IN009 | PT 14087 | PT-14087 | PT_14087 | normalized tag | 16-16 |
| S0-IN010 | PT 14088 | PT-14088 | PT_14088 | normalized tag | 17-17 |
| S0-IN006 | RE 1402 | RE-1402 | RE_1402 | normalized tag | 18-18 |
| S0-IN021 | RE 1403 | RE-1403 | RE_1403 | normalized tag | 19-19 |
| S0-IN001 | TCV 1401 | TCV-1401 | TCV_1401_POS | normalized tag | 20-20 |
| S0-IN013 | TCV 1402 | TCV-1402 | TCV_1402_POS | normalized tag | 21-21 |
| S0-IN024 | TCV 1403 | TCV-1403 | TCV_1403_POS | normalized tag | 22-22 |
| S0-IN031 | TCV 1406 | TCV-1406 | TCV_1406_POS | normalized tag | 23-23 |
| S0-IN035 | TCV 1408 | TCV-1408 | TCV_1408_POS | normalized tag | 24-24 |
| S0-IN036 | TCV 1409 | TCV-1409 | TCV_1409_POS | normalized tag | 25-25 |
| S0-IN002 | FT 1401 | FT-1401 | FT_1401 | normalized tag | 26-26 |

## In the I/O list but not matched to a model item (reconcile both sources)

| Source lines | Tag | Point | Description |
|---|---|---|---|
| 27-27 | PT-14094 | PT_14094 | synthetic demo point (not on the drawing: a later addition in this made-up story) |
| 28-28 | TE-14095A | TE_14095A | synthetic demo point (not on the drawing: a later addition in this made-up story) |

## Ambiguous / blocked (valve callouts need signal review; other duplicates can be pinned)

| Source lines | Tag | Matching assets |
|---|---|---|

## On the drawing but not in the I/O list (10)

Model instruments not matched by this I/O input. Reconcile missing rows, local gauges and stale identities; omitted older mappings may remain in partial mode. Listed in the JSON report; count by sheet:

sheet 0: 10

Mode: partial; sheets: ['0']
Status: valid plan


## Complete mapping changes (before → after)

- S0-IN001 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TCV_1401_POS", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 20", "source_lines": [20, 20], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}
- S0-IN002 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "FT_1401", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 26", "source_lines": [26, 26], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}
- S0-IN004 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14084A", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 2", "source_lines": [2, 2], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}
- S0-IN005 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14084B", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 3", "source_lines": [3, 3], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}
- S0-IN006 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "RE_1402", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 18", "source_lines": [18, 18], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}
- S0-IN007 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "PT_14085", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 14", "source_lines": [14, 14], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}
- S0-IN008 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "PT_14086", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 15", "source_lines": [15, 15], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}
- S0-IN009 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "PT_14087", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 16", "source_lines": [16, 16], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}
- S0-IN010 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "PT_14088", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 17", "source_lines": [17, 17], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}
- S0-IN011 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14089A", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 4", "source_lines": [4, 4], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}
- S0-IN012 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14089B", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 5", "source_lines": [5, 5], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}
- S0-IN013 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TCV_1402_POS", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 21", "source_lines": [21, 21], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}
- S0-IN021 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "RE_1403", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 19", "source_lines": [19, 19], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}
- S0-IN022 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14090A", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 6", "source_lines": [6, 6], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}
- S0-IN023 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14090B", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 7", "source_lines": [7, 7], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}
- S0-IN024 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TCV_1403_POS", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 22", "source_lines": [22, 22], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}
- S0-IN025 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14091A", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 8", "source_lines": [8, 8], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}
- S0-IN026 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14091B", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 9", "source_lines": [9, 9], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}
- S0-IN029 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14092A", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 10", "source_lines": [10, 10], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}
- S0-IN030 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14092B", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 11", "source_lines": [11, 11], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}
- S0-IN031 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TCV_1406_POS", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 23", "source_lines": [23, 23], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}
- S0-IN032 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14093B", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 13", "source_lines": [13, 13], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}
- S0-IN033 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14093A", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 12", "source_lines": [12, 12], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}
- S0-IN035 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TCV_1408_POS", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 24", "source_lines": [24, 24], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}
- S0-IN036 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TCV_1409_POS", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 25", "source_lines": [25, 25], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}

## All mappings before

{}

## All mappings after

{"S0-IN001": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TCV_1401_POS", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 20", "source_lines": [20, 20], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}, "S0-IN002": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "FT_1401", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 26", "source_lines": [26, 26], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}, "S0-IN004": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14084A", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 2", "source_lines": [2, 2], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}, "S0-IN005": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14084B", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 3", "source_lines": [3, 3], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}, "S0-IN006": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "RE_1402", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 18", "source_lines": [18, 18], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}, "S0-IN007": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "PT_14085", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 14", "source_lines": [14, 14], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}, "S0-IN008": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "PT_14086", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 15", "source_lines": [15, 15], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}, "S0-IN009": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "PT_14087", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 16", "source_lines": [16, 16], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}, "S0-IN010": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "PT_14088", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 17", "source_lines": [17, 17], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}, "S0-IN011": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14089A", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 4", "source_lines": [4, 4], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}, "S0-IN012": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14089B", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 5", "source_lines": [5, 5], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}, "S0-IN013": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TCV_1402_POS", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 21", "source_lines": [21, 21], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}, "S0-IN021": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "RE_1403", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 19", "source_lines": [19, 19], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}, "S0-IN022": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14090A", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 6", "source_lines": [6, 6], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}, "S0-IN023": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14090B", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 7", "source_lines": [7, 7], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}, "S0-IN024": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TCV_1403_POS", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 22", "source_lines": [22, 22], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}, "S0-IN025": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14091A", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 8", "source_lines": [8, 8], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}, "S0-IN026": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14091B", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 9", "source_lines": [9, 9], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}, "S0-IN029": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14092A", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 10", "source_lines": [10, 10], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}, "S0-IN030": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14092B", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 11", "source_lines": [11, 11], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}, "S0-IN031": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TCV_1406_POS", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 23", "source_lines": [23, 23], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}, "S0-IN032": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14093B", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 13", "source_lines": [13, 13], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}, "S0-IN033": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14093A", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 12", "source_lines": [12, 12], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}, "S0-IN035": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TCV_1408_POS", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 24", "source_lines": [24, 24], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}, "S0-IN036": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TCV_1409_POS", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv line 25", "source_lines": [25, 25], "source_sha256": "8cf3457547537d7113cc52f6c5ef44b70d668d08295afc7bca7cec95a6aec857"}}
