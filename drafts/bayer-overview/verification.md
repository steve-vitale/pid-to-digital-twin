# Residue treater overview: verification

Written by `node drafts/bayer-overview/verify.mjs`, which reads `data/bayer_rt/replay.csv` itself rather than the data embedded in the page.

Result: 16 pass, 0 fail, of 16 checks.

| Check | Result | Detail |
|---|---|---|
| rows_match_replay_csv | pass | all 519 rows: values, 3 interlocks, 4 limits |
| failure_note_only_at_the_end | pass | shown at 22:32:31 only |
| mimic_text_size_light | pass | smallest mimic text 12.0 px tall (at 390 px the "Values now" card carries the values) |
| no_horizontal_scroll_1440_light | pass | 0 px wider than the viewport |
| min_html_font_1440_light | pass | 0 text elements under 12 px |
| console_clean_1440px_light | pass | no errors or warnings |
| mimic_text_size_dark | pass | smallest mimic text 12.0 px tall (at 390 px the "Values now" card carries the values) |
| no_horizontal_scroll_1440_dark | pass | 0 px wider than the viewport |
| min_html_font_1440_dark | pass | 0 text elements under 12 px |
| console_clean_1440px_dark | pass | no errors or warnings |
| no_horizontal_scroll_390_light | pass | 0 px wider than the viewport |
| min_html_font_390_light | pass | 0 text elements under 12 px |
| console_clean_390px_light | pass | no errors or warnings |
| no_horizontal_scroll_390_dark | pass | 0 px wider than the viewport |
| min_html_font_390_dark | pass | 0 text elements under 12 px |
| console_clean_390px_dark | pass | no errors or warnings |
