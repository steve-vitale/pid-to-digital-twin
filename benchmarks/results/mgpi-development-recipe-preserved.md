# Task results: mgpi-source-development

Task: `description-facts`. No original-text unfamiliar-description accuracy trial, heldout score or universal model comparison. Initial input adaptation fails its bounded-source review; expanded evidence resolves placement without a model algorithm change.

Only rows with the same cohort are directly comparable. See JSON for exact cases, failures, fingerprints and configurations.

| Model / version | Method / interface | Family / split / evidence | Cohort | Cases | Replicates | Metric | Mean F1 | Min–max | SD |
|---|---|---|---|---|---|---|---|---|---|
| Codex authoring session; exact model identifier unavailable / unknown | initial source adaptation and model / ongoing maintainer coding-agent session | csb-mgpi / development / Separate agent original-source key; curated source adaptation; no human validation | 9445bf8457fb | 1 | 1 | units | 1.0000 | 1.0000–1.0000 | unavailable |
| Codex authoring session; exact model identifier unavailable / unknown | initial source adaptation and model / ongoing maintainer coding-agent session | csb-mgpi / development / Separate agent original-source key; curated source adaptation; no human validation | 9445bf8457fb | 1 | 1 | streams | 1.0000 | 1.0000–1.0000 | unavailable |
| Codex authoring session; exact model identifier unavailable / unknown | initial source adaptation and model / ongoing maintainer coding-agent session | csb-mgpi / development / Separate agent original-source key; curated source adaptation; no human validation | 9445bf8457fb | 1 | 1 | instruments | 0.8571 | 0.8571–0.8571 | unavailable |
| planted-control / 1 | planted unscored false automatic shutdown / deterministic authored control | csb-mgpi / development / Separate agent original-source key; curated source adaptation; no human validation | 3f3a61919172 | 1 | 1 | units | 1.0000 | 1.0000–1.0000 | unavailable |
| planted-control / 1 | planted unscored false automatic shutdown / deterministic authored control | csb-mgpi / development / Separate agent original-source key; curated source adaptation; no human validation | 3f3a61919172 | 1 | 1 | streams | 1.0000 | 1.0000–1.0000 | unavailable |
| planted-control / 1 | planted unscored false automatic shutdown / deterministic authored control | csb-mgpi / development / Separate agent original-source key; curated source adaptation; no human validation | 3f3a61919172 | 1 | 1 | instruments | 1.0000 | 1.0000–1.0000 | unavailable |
| planted-control / 1 | planted wrong chemical endpoint / deterministic authored control | csb-mgpi / development / Separate agent original-source key; curated source adaptation; no human validation | 3f3a61919172 | 1 | 1 | units | 1.0000 | 1.0000–1.0000 | unavailable |
| planted-control / 1 | planted wrong chemical endpoint / deterministic authored control | csb-mgpi / development / Separate agent original-source key; curated source adaptation; no human validation | 3f3a61919172 | 1 | 1 | streams | 0.9333 | 0.9333–0.9333 | unavailable |
| planted-control / 1 | planted wrong chemical endpoint / deterministic authored control | csb-mgpi / development / Separate agent original-source key; curated source adaptation; no human validation | 3f3a61919172 | 1 | 1 | instruments | 1.0000 | 1.0000–1.0000 | unavailable |
| Codex authoring session; exact model identifier unavailable / unknown | expanded original-source scope and reviewed model / ongoing maintainer coding-agent session | csb-mgpi / development / Separate agent original-source key; curated source adaptation; no human validation | 3f3a61919172 | 1 | 1 | units | 1.0000 | 1.0000–1.0000 | unavailable |
| Codex authoring session; exact model identifier unavailable / unknown | expanded original-source scope and reviewed model / ongoing maintainer coding-agent session | csb-mgpi / development / Separate agent original-source key; curated source adaptation; no human validation | 3f3a61919172 | 1 | 1 | streams | 1.0000 | 1.0000–1.0000 | unavailable |
| Codex authoring session; exact model identifier unavailable / unknown | expanded original-source scope and reviewed model / ongoing maintainer coding-agent session | csb-mgpi / development / Separate agent original-source key; curated source adaptation; no human validation | 3f3a61919172 | 1 | 1 | instruments | 1.0000 | 1.0000–1.0000 | unavailable |
| planted-control / 1 | planted empty output / deterministic authored control | csb-mgpi / development / Separate agent original-source key; curated source adaptation; no human validation | 3f3a61919172 | 1 | 1 | units | 0.0000 | 0.0000–0.0000 | unavailable |
| planted-control / 1 | planted empty output / deterministic authored control | csb-mgpi / development / Separate agent original-source key; curated source adaptation; no human validation | 3f3a61919172 | 1 | 1 | streams | 0.0000 | 0.0000–0.0000 | unavailable |
| planted-control / 1 | planted empty output / deterministic authored control | csb-mgpi / development / Separate agent original-source key; curated source adaptation; no human validation | 3f3a61919172 | 1 | 1 | instruments | 0.0000 | 0.0000–0.0000 | unavailable |

## Coverage and failures

- mgpi-initial (csb-mgpi / development): 1 cases in this family/cohort; suite total 2; suite-wide unattempted: mgpi-v2; failed attempted answers: none.
  mgpi-v1 unexpected_facts: [["instruments", "LI_HYPO", "unit", "HYPO_BULK"]].
- mgpi-expanded-source (csb-mgpi / development): 1 cases in this family/cohort; suite total 2; suite-wide unattempted: mgpi-v1; failed attempted answers: none.
- mgpi-empty (csb-mgpi / development): 1 cases in this family/cohort; suite total 2; suite-wide unattempted: mgpi-v1; failed attempted answers: none.
  mgpi-v2 missing_facts: [["instruments", "LI_HYPO", "exists", true], ["instruments", "LI_HYPO", "unit", "HYPO_BULK"], ["instruments", "LI_HYPO", "uom", ""], ["instruments", "LI_HYPO", "variable", "level"], ["streams", "A1", "exists", true], ["streams", "A1", "from", "BL"], ["streams", "A1", "to", "ACID_DAY"], ["streams", "A2", "exists", true], ["streams", "A2", "from", "ACID_DAY"], ["streams", "A2", "to", "BL"], ["streams", "H1", "exists", true], ["streams", "H1", "from", "BL"], ["streams", "H1", "to", "HYPO_BULK"], ["streams", "H2", "exists", true], ["streams", "H2", "from", "HYPO_BULK"], ["streams", "H2", "to", "HYPO_DAY"], ["streams", "H3", "exists", true], ["streams", "H3", "from", "HYPO_DAY"], ["streams", "H3", "to", "HYPO_PROCESS"], ["units", "ACID_DAY", "exists", true], ["units", "ACID_DAY", "type", "tank"], ["units", "HYPO_BULK", "exists", true], ["units", "HYPO_BULK", "type", "tank"], ["units", "HYPO_DAY", "exists", true], ["units", "HYPO_DAY", "type", "tank"], ["units", "HYPO_PROCESS", "exists", true], ["units", "HYPO_PROCESS", "type", "vessel"]].
- mgpi-wrong-endpoint (csb-mgpi / development): 1 cases in this family/cohort; suite total 2; suite-wide unattempted: mgpi-v1; failed attempted answers: none.
  mgpi-v2 missing_facts: [["streams", "H3", "to", "HYPO_PROCESS"]].
  mgpi-v2 unexpected_facts: [["streams", "H3", "to", "ACID_DAY"]].
- mgpi-false-shutdown (csb-mgpi / development): 1 cases in this family/cohort; suite total 2; suite-wide unattempted: mgpi-v1; failed attempted answers: none.

## Limits

- Compare only the same cohort and scoring contract; model identity is contributor-declared, not provider-attested.
- Each replicate pools counts over its cases; summary reports mean/range/stdev over replicates, not a significance test or winner.
- Missing/failed attempted answers score empty; unattempted cases remain visible and create different comparison cohorts.
- Public keys and retrospective registration do not establish blindness. Synthetic controls and corrected/development results are separate.
- Description facts grade literal selected fields only: no prose names, source validity, dimensions, limits, layout quality or plant truth.
