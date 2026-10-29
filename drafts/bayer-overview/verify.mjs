// Verification of the residue treater overview page. Proof of concept.
//
//   python scripts/build_bayer_overview.py && node drafts/bayer-overview/verify.mjs
//
// Reads data/bayer_rt/replay.csv itself (not the data embedded in the page), so a fault in the page generator or in
// the page's own code shows up as a mismatch. In headless Chrome at 390 and 1440 px, light and dark:
//   every replay row   the four values, three interlock conditions and four limit states shown equal the CSV row
//   the end            the failure note shows at the last row only, and nowhere earlier
//   the walk-through   each report event's Show button sets the screen to the CSV row nearest the event (computed
//                      here), and the agree/disagree marks under it equal the checks' own results, read here from
//                      out/bayer_rt/fig11_check.json and replay_states.json through data/bayer_rt/walkthrough_steps.json
//   layout             no horizontal page scroll; every visible text at least 12 px; no console errors
// Writes drafts/bayer-overview/verification.md and review stills in drafts/bayer-overview/shots/.
// Exit 0 when nothing fails, 1 otherwise, 2 when Chrome or the built page is missing.
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { launch, openPage } from "../interactive-tour/cdp.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..", "..");
const PAGE = join(HERE, "index.html");
const SHOTS = join(HERE, "shots");
if (!existsSync(PAGE)) { console.error("build the page first: python scripts/build_bayer_overview.py"); process.exit(2); }

const lines = readFileSync(join(ROOT, "data", "bayer_rt", "replay.csv"), "utf8").split(/\r?\n/).filter((l) => l && !l.startsWith("#"));
const head = lines[0].split(",");
const csv = lines.slice(1).map((l) => Object.fromEntries(l.split(",").map((v, i) => [head[i], v])));
const TAGS = ["TT-104", "PT-101", "LT-102", "FT-103"];
const readJson = (...p) => JSON.parse(readFileSync(join(ROOT, ...p), "utf8"));
const STEPS = readJson("data", "bayer_rt", "walkthrough_steps.json").steps;
const FIG11 = Object.fromEntries(readJson("out", "bayer_rt", "fig11_check.json").checks.map((c) => [c.name, c.ok]));
const KOK = Object.fromEntries(readJson("out", "bayer_rt", "replay_states.json").checks.map((c) => [c.id, c.ok]));
const sec = (t) => { const [h, m, s = 0] = t.split(":").map(Number); return h * 3600 + m * 60 + s; };
const ILS = head.filter((h) => /^IL-\d$/.test(h));
const LIMS = head.filter((h) => !h.startsWith("IL-") && !TAGS.some((t) => h.startsWith(t)) && h !== "time");

const results = [];
const record = (id, ok, detail) => { results.push({ id, ok, detail }); console.log(`${ok ? "pass" : "FAIL"}  ${id}: ${detail}`); };

let browser;
try { browser = await launch(); } catch (e) { console.error(String(e.message)); process.exit(2); }
mkdirSync(SHOTS, { recursive: true });
try {
  for (const [w, h] of [[1440, 1000], [390, 844]]) {
    for (const theme of ["light", "dark"]) {
      const page = await openPage(browser.port, { width: w, height: h });
      await page.send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: theme }] });
      await page.goto(pathToFileURL(PAGE).href);
      const state = `${w}px ${theme}`;
      if (w === 1440 && theme === "light") {
        let bad = [], early = [];
        for (let i = 0; i < csv.length; i++) {
          const s = await page.evaluate(`(window.__tour.setTime(${i}), window.__tour.state())`);
          const r = csv[i];
          const want = { t: r.time, values: Object.fromEntries(TAGS.map((t) => [t, r[t] === "" ? "" : String(Number(r[t]))])),
            interlocks: Object.fromEntries(ILS.map((k) => [k, r[k]])), limits: Object.fromEntries(LIMS.map((k) => [k, r[k]])) };
          const got = { t: s.t, values: Object.fromEntries(TAGS.map((t) => [t, s.values[t] === "" ? "" : String(Number(s.values[t]))])),
            interlocks: s.interlocks, limits: s.limits };
          if (JSON.stringify(got) !== JSON.stringify(want)) bad.push(`${r.time}: page ${JSON.stringify(got)} vs csv ${JSON.stringify(want)}`);
          if (s.endShown !== (i === csv.length - 1)) early.push(r.time);
        }
        record("rows_match_replay_csv", bad.length === 0, bad.length ? `${bad.length} rows differ; first ${bad[0].slice(0, 300)}` : `all ${csv.length} rows: values, ${ILS.length} interlocks, ${LIMS.length} limits`);
        const walkBad = [];
        for (let k = 0; k < STEPS.length; k++) {
          const st = STEPS[k];
          let want = 0;
          csv.forEach((r, i) => { if (Math.abs(sec(r.time) - sec(st.event)) < Math.abs(sec(csv[want].time) - sec(st.event))) want = i; });
          const s = await page.evaluate(`(window.__tour.showStep(${k}), window.__tour.state())`);
          if (s.t !== csv[want].time || s.step !== k) walkBad.push(`${st.event}: screen ${s.t} step ${s.step}, want ${csv[want].time} step ${k}`);
          const marks = await page.evaluate(`window.__tour.stepChecks(${k})`);
          const truth = [...st.fig11.map((n) => FIG11[n]), ...st.replay.map((id) => KOK[id])];
          if (JSON.stringify(marks) !== JSON.stringify(truth)) walkBad.push(`${st.event}: marks ${JSON.stringify(marks)} vs checks ${JSON.stringify(truth)}`);
        }
        await page.evaluate("window.__tour.setTime(0)");
        const seq = [];
        for (let k = 0; k <= STEPS.length; k++) seq.push((await page.evaluate("(window.__tour.nextStep(), window.__tour.state())")).step);
        if (JSON.stringify(seq) !== JSON.stringify([...STEPS.keys(), STEPS.length - 1])) walkBad.push(`Next event from the start visits ${JSON.stringify(seq)}`);
        const nChecks = STEPS.reduce((n, st) => n + st.fig11.length + st.replay.length, 0);
        record("walkthrough_steps_match", walkBad.length === 0, walkBad.length ? walkBad.slice(0, 3).join("; ") : `${STEPS.length} events: each Show sets the nearest CSV row; ${nChecks} agree/disagree marks equal the checks' own results`);
        record("failure_note_only_at_the_end", early.length === 0, early.length ? `shown at ${early.slice(0, 5).join(", ")}` : `shown at ${csv[csv.length - 1].time} only`);
      }
      for (const [name, i] of [["start", 0], ["flow-lost", csv.findIndex((r) => r.time >= "22:23:00")], ["end", csv.length - 1]]) {
        await page.evaluate(`window.__tour.setTime(${i})`);
        await page.sleep(150);
        const overflow = await page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth");
        const small = await page.evaluate(`[...document.querySelectorAll("body *")].filter(e=>e.childNodes.length&&[...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim())&&e.getClientRects().length&&!(e.closest("svg"))).map(e=>parseFloat(getComputedStyle(e).fontSize)).filter(s=>s<12).length`);
        if (name === "end" && w === 1440) {
          const tiny = await page.evaluate(`Math.min(...[...document.querySelectorAll("#mimic text")].map(t=>t.getBoundingClientRect().height).filter(h=>h>0))`);
          record(`mimic_text_size_${theme}`, tiny >= 11, `smallest mimic text ${tiny.toFixed(1)} px tall (at 390 px the "Values now" card carries the values)`);
        }
        if (name === "end") {
          record(`no_horizontal_scroll_${w}_${theme}`, overflow <= 0, `${overflow} px wider than the viewport`);
          record(`min_html_font_${w}_${theme}`, small === 0, `${small} text elements under 12 px`);
        }
        if ((theme === "light" && w === 1440) || name === "end") {
          writeFileSync(join(SHOTS, `${name}-${w}-${theme}.png`), await page.shot("body", w === 1440 ? 0.6 : 1));
        }
      }
      record(`console_clean_${state.replace(" ", "_")}`, page.problems.length === 0, page.problems.length ? page.problems.slice(0, 3).join(" | ") : "no errors or warnings");
      page.close();
    }
  }
} finally { browser.close(); }

const failed = results.filter((r) => !r.ok).length;
writeFileSync(join(HERE, "verification.md"), ["# Residue treater overview: verification", "",
  "Written by `node drafts/bayer-overview/verify.mjs`, which reads `data/bayer_rt/replay.csv` itself rather than the data embedded in the page.", "",
  `Result: ${results.length - failed} pass, ${failed} fail, of ${results.length} checks.`, "",
  "| Check | Result | Detail |", "|---|---|---|",
  ...results.map((r) => `| ${r.id} | ${r.ok ? "pass" : "FAIL"} | ${String(r.detail).replace(/\|/g, "/")} |`), ""].join("\n"));
console.log(`${results.length - failed} pass, ${failed} fail`);
process.exit(failed ? 1 : 0);
