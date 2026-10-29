# Point mapping: bundle/plant_model.json ← open100_sheet0_demo.csv

Status: valid plan

Mapped: 25 · On the drawing, not in the I/O list: 10 · In the I/O list, not on the drawing: 2 · Ambiguous: 0

## Mapped

| Asset | Drawing tag | I/O tag | Point | Matched by |
|---|---|---|---|---|
| S0-IN004 | TE 14084A | TE-14084A | TE_14084A | normalized tag |
| S0-IN005 | TE 14084B | TE-14084B | TE_14084B | normalized tag |
| S0-IN011 | TE 14089A | TE 14089A | TE_14089A | exact |
| S0-IN012 | TE 14089B | TE 14089B | TE_14089B | exact |
| S0-IN022 | TE 14090A | TE-14090A | TE_14090A | normalized tag |
| S0-IN023 | TE 14090B | TE-14090B | TE_14090B | normalized tag |
| S0-IN025 | TE 14091A | te_14091a | TE_14091A | normalized tag |
| S0-IN026 | TE 14091B | te_14091b | TE_14091B | normalized tag |
| S0-IN029 | TE 14092A | TE-14092A | TE_14092A | normalized tag |
| S0-IN030 | TE 14092B | TE-14092B | TE_14092B | normalized tag |
| S0-IN033 | TE 14093A | TE-14093A | TE_14093A | normalized tag |
| S0-IN032 | TE 14093B | TE-14093B | TE_14093B | normalized tag |
| S0-IN007 | PT 14085 | PT-14085 | PT_14085 | normalized tag |
| S0-IN008 | PT 14086 | PT-14086 | PT_14086 | normalized tag |
| S0-IN009 | PT 14087 | PT-14087 | PT_14087 | normalized tag |
| S0-IN010 | PT 14088 | PT-14088 | PT_14088 | normalized tag |
| S0-IN006 | RE 1402 | RE-1402 | RE_1402 | normalized tag |
| S0-IN021 | RE 1403 | RE-1403 | RE_1403 | normalized tag |
| S0-IN001 | TCV 1401 | TCV-1401 | TCV_1401_POS | normalized tag |
| S0-IN013 | TCV 1402 | TCV-1402 | TCV_1402_POS | normalized tag |
| S0-IN024 | TCV 1403 | TCV-1403 | TCV_1403_POS | normalized tag |
| S0-IN031 | TCV 1406 | TCV-1406 | TCV_1406_POS | normalized tag |
| S0-IN035 | TCV 1408 | TCV-1408 | TCV_1408_POS | normalized tag |
| S0-IN036 | TCV 1409 | TCV-1409 | TCV_1409_POS | normalized tag |
| S0-IN002 | FT 1401 | FT-1401 | FT_1401 | normalized tag |

## In the I/O list but not on the drawing (is the drawing out of date?)

| Row | Tag | Point | Description |
|---|---|---|---|
| 27 | PT-14094 | PT_14094 | synthetic demo point (not on the drawing: a later addition in this made-up story) |
| 28 | TE-14095A | TE_14095A | synthetic demo point (not on the drawing: a later addition in this made-up story) |

## Ambiguous / blocked (valve callouts need signal review; other duplicates can be pinned)

| Row | Tag | Matching assets |
|---|---|---|

## On the drawing but not in the I/O list (10)

Spare or demolished instruments, local gauges with no signal, or missing I/O rows. Listed in the JSON report; the count by sheet:

sheet 0: 10

Mode: partial; sheets: ['0']
Status: valid plan


## Complete mapping changes (before → after)

- S0-IN001 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TCV_1401_POS", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 20"}
- S0-IN002 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "FT_1401", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 26"}
- S0-IN004 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14084A", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 2"}
- S0-IN005 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14084B", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 3"}
- S0-IN006 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "RE_1402", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 18"}
- S0-IN007 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "PT_14085", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 14"}
- S0-IN008 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "PT_14086", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 15"}
- S0-IN009 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "PT_14087", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 16"}
- S0-IN010 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "PT_14088", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 17"}
- S0-IN011 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14089A", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 4"}
- S0-IN012 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14089B", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 5"}
- S0-IN013 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TCV_1402_POS", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 21"}
- S0-IN021 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "RE_1403", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 19"}
- S0-IN022 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14090A", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 6"}
- S0-IN023 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14090B", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 7"}
- S0-IN024 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TCV_1403_POS", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 22"}
- S0-IN025 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14091A", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 8"}
- S0-IN026 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14091B", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 9"}
- S0-IN029 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14092A", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 10"}
- S0-IN030 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14092B", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 11"}
- S0-IN031 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TCV_1406_POS", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 23"}
- S0-IN032 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14093B", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 13"}
- S0-IN033 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14093A", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 12"}
- S0-IN035 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TCV_1408_POS", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 24"}
- S0-IN036 (added): null → {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TCV_1409_POS", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 25"}

## All mappings before

{}

## All mappings after

{"S0-IN001": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TCV_1401_POS", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 20"}, "S0-IN002": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "FT_1401", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 26"}, "S0-IN004": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14084A", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 2"}, "S0-IN005": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14084B", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 3"}, "S0-IN006": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "RE_1402", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 18"}, "S0-IN007": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "PT_14085", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 14"}, "S0-IN008": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "PT_14086", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 15"}, "S0-IN009": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "PT_14087", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 16"}, "S0-IN010": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "PT_14088", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 17"}, "S0-IN011": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14089A", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 4"}, "S0-IN012": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14089B", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 5"}, "S0-IN013": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TCV_1402_POS", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 21"}, "S0-IN021": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "RE_1403", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 19"}, "S0-IN022": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14090A", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 6"}, "S0-IN023": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14090B", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 7"}, "S0-IN024": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TCV_1403_POS", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 22"}, "S0-IN025": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14091A", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 8"}, "S0-IN026": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14091B", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 9"}, "S0-IN029": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14092A", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 10"}, "S0-IN030": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14092B", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 11"}, "S0-IN031": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TCV_1406_POS", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 23"}, "S0-IN032": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14093B", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 13"}, "S0-IN033": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TE_14093A", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 12"}, "S0-IN035": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TCV_1408_POS", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 24"}, "S0-IN036": {"base_path": "nsu=urn:pid-digital-twin:open100-demo;s=PLANT", "point": "TCV_1409_POS", "server": "OPEN100-Demo", "source": "open100_sheet0_demo.csv row 25"}}
