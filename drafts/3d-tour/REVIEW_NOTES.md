# 3D tour draft: content review notes (2026-10-13)

These notes check the text that rides on the 3D tour stills: the unit purpose cards, the public-incident
citations and the labels' legibility. They also set out how the tour gets into the main branch. The 3D work itself
lives on a separate local branch that has not been published (its tip is commit `8a0aff5`). Nothing here was
reviewed by an operator or a process-safety engineer. The fixes are in [3d-content-fixes.patch](3d-content-fixes.patch)
plus two scrubbed replacement files in [replace/](replace/) (see section 4), to be applied when the tour is merged. The stills in this folder are **from before the fixes**.

## 1. Purpose cards

**Source of truth:** `data/te_unit_purposes.json` in the main repository, from the TE topology check. It has one
sentence per unit, each citing `teprob.f` lines, and `scripts/test_te_topology.py` checks every citation. The patch
copies those sentences verbatim into the tour's cards, with their citations. The tour's own short "function" lines
are rewritten to agree with the same code.

An independent check came first. Before that file existed, the cards were read against a second code base: the
revised C model `temexd_mod.c` (Bathelt, Ricker and Jelali) from N. L. Ricker's TE archive, plus open papers that
restate Downs and Vogel (arXiv 2208.08879, Appendix A; arXiv 2110.01759). That check found the same purge error
(see the compressor and separator rows below). The two code bases agree. The Downs and Vogel paper itself is
paywalled and was not read.

| Unit | Draft card said | The code shows | Difference |
|---|---|---|---|
| U-100 feed | fresh A, D, E feeds "join the recycle gas" so the reactor gets one feed | a vapour header mixes feeds 1–3, the **stripper overhead (stream 5)** and the recycle, giving reactor feed stream 6 (`teprob.f` 767) | stripper overhead missing |
| R-101 reactor | gas feeds react to liquid G and H; heat is given off; products leave as vapour | A, C, D, E react to G and H **with F as a by-product** (521–527); cooling water removes heat, and the transfer depends on agitator speed (670–672); products leave as vapour with unreacted gas | by-product F and agitation missing; otherwise right |
| E-101 condenser | cools the vapour "so that **most** of the products condense" | cooling-water duty on the reactor effluent (675); **no separate condenser vessel**: the duty is counted in the separator's energy balance | "most" not supported by any source; removed |
| V-101 separator | gas goes back as recycle, liquid to the stripper | vapour goes to the compressor **or out through the purge**; liquid to the stripper (764–765); purge flow is driven by separator pressure (585) | purge missing |
| K-101 compressor | recycles vapour; "**part of it is purged**" there | the compressor lifts separator vapour to header pressure (589), and its recycle valve reduces the net flow (598); the purge is **not** at the compressor | **wrong**: the purge leaves from the separator |
| C-101 stripper | strips "remaining reactants" with the A and C feed; G and H leave the base | stream 4 strips **most lighter components (A to F)** out of the separator liquid (622–627, 637, 643); overhead goes to the header (stream 5); steam heats it (678) | narrower and more precise |
| topology note | "five major unit operations" | supported (arXiv 2208.08879, Appendix A; ADCHEM 2015 draft in Ricker's archive) | none |

**Topology consequence:** the main repository moves the purge stream S9, with FI-110, FV-206 and AI-129, from K-101
to V-101. The 3D scene builds its pipes from that model, so the purge pipe, the purge instruments and the LOTO
mockup's point 5 ("Purge: battery-limit block valve") all move to the separator when the tour is rebuilt.

**Card size:** the sourced sentences are longer. Card height grows from 5–7 lines to 7–10 (the stripper card is 10).
The scene contract tests still pass with the fixes applied (76/76, including the new font and hygiene checks), and so do the render-verifier unit tests (27/27). Each
stop's narration stays within 70 words. But nothing has been re-rendered, so whether the taller cards collide with
labels is unchecked until the Blender render and `verify_3d_render.py` run again.

## 2. Public-incident citations

Each citation's date, location, casualty count and quoted recommendation was read against the agency page (csb.gov
and dol.gov). Kuraray, PEMEX Deer Park and Cuisine Solutions were read twice.

| Citation | Result | Agency page |
|---|---|---|
| TPC Group Port Neches (Nov 27, 2019) | **confirmed** | csb.gov/tpc-port-neches-explosions-and-fire/ |
| PEMEX Deer Park (Oct 10, 2024) | **confirmed**: workers removing an isolation blind from H2S piping; 2 died, 13 injured | csb.gov/pemex-deer-park-chemical-release-/ |
| LyondellBasell La Porte (2021) | **confirmed** | csb.gov/lyondellbasell-la-porte-fatal-chemical-release-/ |
| CSB remote-isolation safety study | **confirmed**; published July 25, 2024 (the year was missing) | csb.gov/csb-safety-study-remote-isolation-of-process-equipment/ |
| Kuraray Pasadena (May 19, 2018) | **confirmed**: "An explosion … injured 21 workers"; the lower-design-pressure recommendation (2018-03-I-TX-6) and the safe-location relief recommendation (2018-03-I-TX-1) match | csb.gov/kuraray-pasadena-release-and-fire/ |
| Bayer CropScience (2008) | **corrected**: "liquid-phase residue treater" and "restart before its controls were ready" are not on the cited page. Narrowed to "a runaway reaction destroyed a waste-treatment vessel; two workers died" | csb.gov/bayer-cropscience-pesticide-waste-tank-explosion/ |
| PolyCarbon Industries | **corrected**: Newburyport, Massachusetts, May 4, 2023 (place and date added) | dol.gov/newsroom/releases/osha/osha20231116 |
| Arkema Crosby (2017) | **confirmed** | csb.gov/arkema-inc-chemical-plant-fire-/ |
| Tesoro Anacortes (Apr 2, 2010) | **corrected**: it happened during a maintenance operation to switch a stream between two parallel banks of exchangers, **not "during a restart"**; HTHA; 7 died | csb.gov/tesoro-anacortes-refinery-fatal-explosion-and-fire-/ |
| Williams Olefins Geismar (2013) | **corrected**: the URL returned 404; the live page is csb.gov/williams-olefins-plant-explosion-and-fire-/; 2 died, 167 injured | (both the condenser and stripper entries) |
| Cuisine Solutions (Jul 31, 2024) | **corrected**: Loudoun County, Virginia; 40 evaluated at hospitals; a completed investigation (final report Sept 25, 2025). The recommendation names horizontal surge vessels with little vapor space and vapor-liquid disengagement; "knockout drums" was not in it and was removed | csb.gov/cuisine-solutions-ammonia-release-/ |
| BP-Husky Toledo, Oregon OH | **completed**: September 20, 2022, 2 died (the year was missing) | csb.gov/bp---husky-oregon-chemical-release-and-fire-/ |
| BP Texas City (2005) | **confirmed**: 15 died | csb.gov/bp-america-refinery-explosion/ |
| 6 EPA RMP records | **link replaced**: `epa.gov/rmp?facility=<id>` returns the RMP landing page and ignores the id. Now linked to EPA's RMP Public Data Sharing search (cdxapps.epa.gov/olem-rmp-pds/) with the accident and facility ids. Record contents were **not** re-checked against EPA data | — |

The design doc gets a "Source check" section recording all of this, and the citation file gets a `source_check`
block, so the corrections stay visible.

## 3. Legibility: OCR read-back

Tesseract is not installed and no portable copy was found. The check used `rapidocr` with `onnxruntime` (pip, ONNX
models, no torch, about 300 MB with OpenCV, in a separate virtual environment). The script is
[ocr_readback.py](ocr_readback.py), the ground truth (57 drawn labels, text and pixel box, taken from the renderer's
own label report) is [label_truth.json](label_truth.json), and the full result is [ocr_readback.json](ocr_readback.json).

| Measure (orientation classifier off; all labels are horizontal) | Result |
|---|---|
| Labels read back exactly, after folding case and spacing | 40 / 57 |
| Mean character accuracy | 0.974 |
| Tag and unit IDs read exactly, each label cropped | 41 / 42 |
| Tag and unit IDs read exactly, whole frame at once | 35 / 42 |
| With the engine's default 180° orientation classifier on | 38 / 57 exact, 39 / 42 IDs cropped: `TI-109` came back upside down as `601-11` twice, an engine artefact |

**The one real legibility finding: in this typeface 1, I and l look alike, and tag IDs are made of them.** Every
ID the whole-frame read missed is one of these: `Pl-107` (twice, plus once in the fault caption), `Tl-121`,
`Tl-109`, `E-10I`, `V-10I`. LOTO tag 1 came back as `I` and tag 11 as `II`. A person reads the stills easily at
100 % (crops checked by eye), but an operator copying a tag from a screen is exactly the case that matters.
**Fix, in the patch (not yet rendered):** every Blender text object now uses **Atkinson Hyperlegible Regular**
(Braille Institute, SIL Open Font License 1.1; bundled as `assets/fonts/AtkinsonHyperlegible-Regular.ttf` with
`OFL.txt`; NOTICE.md entry added). It was designed so that 1, I and l differ, and it covers every character the
labels use (checked against its character map, including `°` and `·`). The generated Blender script loads it from
the repository, not from a machine path. Two new contract checks:
- the script references the bundled font and its OFL text;
- 1, I and l rasterize as clearly different shapes (each pair differs in at least 25 % of its ink).

A flat test render (each unit, tag and LOTO label in the new font at the stills' 25 px size, read by the same
OCR) read **36 of 36** tag and unit IDs correctly. That is not a like-for-like comparison with the stills (no
scene, no perspective), and the lone LOTO numerals were inconclusive: the detector skipped six of the 11 short
numbers entirely rather than misreading them. The real test is the OCR check on the re-rendered stills at merge.

The other misses are the engine, not the image: duplicated fragments (`Feed d System` on four stills,
`placeholder g r geometry` on all five badges, `Separator` doubled). They pull the exact-match count down and are
reported as they came out. OCR is a proxy for legibility, not proof. A person still has to look (review kit,
`docs/review-kit/CHECKLIST_3D_STILLS.md`).

## 4. Getting the tour into main without its history

The tour branch must **not** be merged or pushed. Its history and some current files name the private system
it took its incident corpus from, and it is based on an old commit (it shares history with main only up to the
TE source check), so its versions of every shared file are stale. Plan:

1. **Wait for the main-branch work it depends on:** the TE topology correction (purge at V-101, sourced
   `data/te_unit_purposes.json`) and this branch.
2. **New branch from current main.** Copy **only the tour's own new files** at `8a0aff5` (`git archive 8a0aff5
   -- <paths> | tar -x`): `scripts/build_3d_scene.py`, `blender_tour_template.py`, `orientation_tour.py`,
   `label_layout.py`, `hazard_citations.py`, `verify_3d_render.py`, `test_build_3d_scene.py`,
   `test_verify_3d_render.py`, `data/hazard_citations_prototype.json`, `data/te_unit_purposes.json` (see step 4),
   `docs/3D_TOUR_PLAN.md`, `docs/HAZARD_CITATIONS_DESIGN.md`. **Do not copy:** any shared file (they are stale),
   the generated outputs (`docs/3d_tour/*`, `docs/screenshots/3d/**`; they are rebuilt in step 6), or the branch's
   resume/handoff note.
3. **Apply the fixes:** `git apply drafts/3d-tour/3d-content-fixes.patch`, then copy `drafts/3d-tour/replace/scripts/*`
   over the two tour scripts. Checked against an export of `8a0aff5`: the patch applies, and the 3D tests pass
   (contract 76/76, render verifier 27/27).
4. **Resolve the file-name collision.** Main's `data/te_unit_purposes.json` (keyed by unit, with citations) and the
   tour's file of the same name (keyed by equipment kind, with function/highlight/inferred fields) are different
   files. Keep main's as the only source of purpose text. Rename the tour's file to e.g. `data/te_tour_cards.json`,
   remove its `purpose` fields, and make `orientation_tour.py` read the purpose by unit ID from main's file. A
   test should check that every tour stop's purpose equals main's sentence.
5. **Scrub: a hard pre-merge step. Do not merge until it passes.** The tour's `hazard_citations.py` hard-coded a
   path to the private corpus repository, that repository's internal file layout, a directory named after a
   person, and a real site's name as a deny-list term. The test file spelled out the private product's name in
   order to assert its absence. Both files are replaced wholesale by the scrubbed versions in
   [replace/scripts/](replace/scripts/). They are full files rather than patch hunks, so that the patch never
   quotes the removed strings. In them:
   - the corpus layout and the deny terms come only from an untracked local JSON (`--corpus-config`) and the
     `HAZARD_DENY_TERMS` environment variable; nothing private is in the repository;
   - `test_build_3d_scene.py` has a **public-hygiene check** over every file the tour adds. It uses generic
     rules, so no sensitive string is written in the test:
     - absolute user or drive paths;
     - hard-coded deny-lists;
     - e-mail addresses;
     - file or directory path literals that point outside this repository;
     - Markdown links to missing documents (this catches the resume-note links once they are in main);
     - any `HAZARD_DENY_TERMS` term, when the variable is set.

     A positive control plants one example of each rule, built at run time, and requires every one to be
     caught. Run against the original files, the check flags the drive paths in two scripts and a doc, the
     hard-coded deny-list, and all four outside-repository paths. With the deny terms set locally, it also
     catches the person's name, the site, the repository name and the product name. On the scrubbed files
     it reports nothing.
   - The patch also removes the resume-note link and the machine-specific Blender path from `docs/3D_TOUR_PLAN.md`,
     and the `C:/path` example from `build_3d_scene.py`.

   Before committing the merge, run `HAZARD_DENY_TERMS=<the private terms> python scripts/test_build_3d_scene.py`
   locally (never write the terms into a file in the repository), and confirm the hygiene check passes. Also confirm
   that `git grep -i` for each term over the staged tree and the commit message returns nothing. Separately reword
   the citation file's `excluded` sentence ("partner or customer material"), and drop or keep the opaque private
   corpus commit hash.
6. **Port the shared-file hunks by hand onto main's current versions** (main's NOTICE.md already credits the label
   font, which the patch adds under `assets/fonts/`): `.gitignore` (`out/3d/`), `README.md`
   (two rows), `docs/MODELS.md` (four rows; the purpose-card row now says the text comes from the verified TE file),
   `scripts/run_tests.py` (two tests, citation and label-box source files), `docs/JOURNAL.md` (three entries,
   **renumbered** after main's latest entry: the branch numbers them 37–39, which main has already used).
7. **Rebuild everything generated:** run `build_3d_scene.py` with Blender (stills, label boxes, GLB, narration
   script, SRT), then `verify_3d_render.py` (`verification.md`, whose tag map moves FI-110, FV-206 and AI-129 to
   V-101), then `drafts/3d-tour/ocr_readback.py` against the new stills. Check that the purge pipe and LOTO point
   5 now sit at the separator.
8. **Tests:** `python scripts/run_tests.py` (full), plus the two 3D test files.
9. **One commit, parent = current main**, message in the journal's voice and free of the private name. Check
   `git log --oneline -2` shows one new commit on top of main. Then retire `drafts/3d-tour/` (move these notes to
   `docs/3d_tour/`). Delete the old local branch only after the clean commit is published.

## 5. What is still not done

- No operator, process-safety engineer or second model has reviewed the cards, citations or LOTO points.
- The stills are not re-rendered; the taller cards, the moved purge and the font change are untested visually.
- EPA RMP record contents were not re-checked against EPA data.
- The aptness of each incident to its equipment kind is a judgement, not a check: see the Track B questions in
  `docs/review-kit/CHECKLIST_3D_STILLS.md`.
