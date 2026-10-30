# A normal label does not choose a baseline

Fixed development diagnostic on existing PRONTO records. Recent candidates are shorter; context, length and
noise history change together. No causal effect, prospective selection rule or operating approval is established.

| Case | Choice | Normal records | Common pre-fault flags | Detection delay (s) | Criterion met | K target met |
|---|---|---:|---|---:|---|---|
| day2-leakage | early | 361 | 155/181 | 3 | False | True |
| day2-leakage | recent | 180 | 0/181 | 20 | True | True |
| day3-leakage | early | 600 | 0/150 | 631 | True | True |
| day3-leakage | recent | 150 | 17/150 | 26 | False | False |
| day3-diverted | early | 600 | 0/300 | 1922 | True | True |
| day3-diverted | recent | 300 | 0/300 | 7290 | True | True |
| day4-slugging2 | early | 1981 | 0/1385 | 1144 | True | True |
| day4-slugging2 | recent | 1385 | 895/1385 | 0 | False | False |

Criterion: three consecutive any-tag flags at/after the labelled onset and at most 0.5% of common
pre-fault records flagged. K selection has its separate existing target. Both filters start at the common
score interval with no carried history. No extra burn-in is removed within that interval. Moving the start
changes warm-up and population relative to the original full-score controls; these paired counts cannot
replace matrix counts. No failure is discarded.
The JSON retains every band-tool result, warning, bad-sample count, source fingerprint and exact range.

## Separate original full-score controls

These use the earlier scoring starts and different denominators; they are not the paired comparison.

| Case | Pre-fault flags | Detection delay (s) |
|---|---|---:|
| day2-leakage | 347/361 | 0.0 |
| day3-leakage | 0/300 | 631.0 |
| day3-diverted | 0/600 | 1922.0 |
| day4-slugging2 | 492/2770 | 1144.0 |

## Normal-labelled source blocks

Medians describe the supplied columns, not verified setpoints or a resolved equipment identity.

| Day | Merged rows [start,end) | Records | AirIn median | WaterIn median |
|---|---|---:|---:|---:|
| 2 | [0, 361] | 361 | 119.456 | 0.0983408 |
| 2 | [9241, 9602] | 361 | 149.798 | 0.501404 |
| 3 | [0, 900] | 900 | 119.565 | 0.0956205 |
| 3 | [3781, 5401] | 1620 | 148.825 | 0.496978 |
| 3 | [7981, 9301] | 1320 | 118.937 | 0.101269 |
| 3 | [16621, 17101] | 480 | 148.427 | 0.493086 |
| 4 | [1559, 3540] | 1981 | 194.918 | 0.49154 |
| 4 | [4544, 7314] | 2770 | 100.881 | 1.00781 |
| 4 | [9594, 11700] | 2106 | 98.4679 | 2.0219 |

No blocks are pooled. The row-based drift filter would treat samples across gaps as adjacent.
No qualified contiguous multi-day normal baseline was established here; N056 remains open.

Source: A. Stief et al., PRONTO, Zenodo 1341583, CC BY 4.0.
https://zenodo.org/records/1341583 ; doi:10.1016/j.jprocont.2019.04.009.
This derived comparison preserves source labels and values; it adds fixed window selection and statistical summaries.
