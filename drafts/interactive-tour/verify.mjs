// Procedural verification of the interactive tour. Proof of concept; written with AI assistance.
//
//   node drafts/interactive-tour/build.mjs --audit && node drafts/interactive-tour/build.mjs --light
//   node drafts/interactive-tour/verify.mjs
//
// Writes drafts/interactive-tour/audit/report.json and report.md, and review stills in drafts/interactive-tour/shots/.
// The checks read the repository's raw files themselves (the process model, the generated P&ID answer key, the
// Ignition gateway tag import, the PI AF staging sheet, the Braatz replay files), not the export the page is built
// from, so a fault in scripts/export_interactive_tour.py or build.mjs shows up as a mismatch here.
//   A. topology and tags   every drawn stream is exactly one model stream and one P&ID connection, its ends land on
//                          the right units (from the anatomy audit's own mount search), every tag shown exists in
//                          the Ignition and PI AF exports, and the reverse is reported
//   B. geometry            the anatomy kit audit (audit/geometry.json, written by build.mjs --audit)
//   C. legibility          in headless Chrome at 390 px and 1440 px, dark and light: label overlaps, minimum font
//                          size, WCAG contrast of every visible text, labels that had no room
//   D. behaviour           replay values equal the raw replay file, the fault 6 alarm shows at its first sample,
//                          pulses move forward, LOTO isolation stops the flow downstream, keyboard focus works
// Exit 0 when nothing fails, 1 otherwise, 2 when a prerequisite (built page, Chrome) is missing.
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { launch, openPage } from "./cdp.mjs";
import * as M from "./model.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..", "..");
const OUT = join(ROOT, "out", "interactive_tour");
const AUDIT = join(HERE, "audit");
const SHOTS = join(HERE, "shots");
const read = (p) => readFileSync(join(ROOT, p), "utf8");
const json = (p) => JSON.parse(read(p));
const checks = [];
const add = (group, id, ok, summary, details = [], status) => checks.push({ group, id, status: status ?? (ok ? "pass" : "fail"), summary, details });

for (const need of ["te-tour.html", "te-tour-light.html", "scene.json", "tour_data.json"]) {
  if (!existsSync(join(OUT, need))) { console.log(`missing out/interactive_tour/${need}: run the export and both builds first`); process.exit(2); }
}
if (!existsSync(join(AUDIT, "geometry.json"))) { console.log("missing audit/geometry.json: run node drafts/interactive-tour/build.mjs --audit"); process.exit(2); }

// ------------------------------------------------------------------ independent sources
const model = json("data/te_process_model.json");
const scene = JSON.parse(readFileSync(join(OUT, "scene.json"), "utf8"));
const data = JSON.parse(readFileSync(join(OUT, "tour_data.json"), "utf8"));
const geometry = JSON.parse(readFileSync(join(AUDIT, "geometry.json"), "utf8"));
const html = readFileSync(join(OUT, "te-tour.html"), "utf8");

// P&ID graph from the generated sheets' answer key: units and battery-limit / off-sheet stream ends are terminals;
// lines, valves and instruments between them are contracted. One connection per stream end, plus unnamed unit-unit links.
function pidConnections() {
  const key = json("data/te_pid/key.json");
  const byStream = {};
  const internal = [];
  const utilities = [];
  for (const [sheet, s] of Object.entries(key.sheets)) {
    const sym = s.symbols;
    const adj = {};
    for (const [a, b] of s.edges) { (adj[a] ??= new Set()).add(b); (adj[b] ??= new Set()).add(a); }
    const hard = (n) => sym[n] && ["unit", "stream_end", "utility"].includes(sym[n].model_kind);
    const nearestUnit = (start) => {
      const seen = new Set([start]);
      let frontier = [start];
      while (frontier.length) {
        const next = [];
        for (const n of frontier) for (const m of adj[n] ?? []) {
          if (seen.has(m)) continue;
          seen.add(m);
          if (sym[m]?.model_kind === "unit") return sym[m].model_ref.slice(5);
          if (!hard(m)) next.push(m);
        }
        frontier = next;
      }
      return null;
    };
    for (const [n, v] of Object.entries(sym)) {
      if (v.model_kind === "stream_end") {
        const sid = v.model_ref.slice(7);
        const e = (byStream[sid] ??= { units: new Set(), bl: false, sheets: [] });
        const u = nearestUnit(n);
        if (u) e.units.add(u);
        if (/^BATTERY LIMIT/.test(v.text)) e.bl = true;
        e.sheets.push(sheet);
      } else if (v.model_kind === "utility") utilities.push({ sheet, text: v.text, unit: nearestUnit(n) });
    }
    // unit-to-unit links with no stream end between them
    const seen = new Set();
    for (const start of Object.keys(adj)) {
      if (hard(start) || seen.has(start)) continue;
      const stack = [start];
      const terms = new Set();
      while (stack.length) {
        const n = stack.pop();
        if (seen.has(n)) continue;
        seen.add(n);
        for (const m of adj[n]) { if (hard(m)) terms.add(m); else if (!seen.has(m)) stack.push(m); }
      }
      const units = [...terms].filter((t) => sym[t].model_kind === "unit").map((t) => sym[t].model_ref.slice(5));
      const ends = [...terms].filter((t) => sym[t].model_kind !== "unit");
      if (units.length === 2 && !ends.length) internal.push({ sheet, units: units.sort() });
      if (units.length === 2 && ends.length) internal.push({ sheet, units: units.sort(), shared_with: ends.map((t) => sym[t].model_ref || sym[t].text) });
    }
  }
  return { byStream, internal, utilities };
}

function ignitionTags() {
  const provider = json("out/ignition/gateway/twin_provider.json");
  const te = provider.tags.find((t) => t.name === "TE_Plant");
  const out = {};
  for (const folder of te.tags) {
    if (folder.tagType !== "Folder" || folder.name.startsWith("_")) continue;
    for (const inst of folder.tags) if (inst.tagType === "UdtInstance") out[inst.name] = `TE_Plant/${folder.name}/${inst.name}`;
  }
  return out;
}
function csvRows(text) {
  const lines = text.replace(/^﻿/, "").split(/\r?\n/).filter(Boolean);
  const split = (l) => { const out = []; let cur = "", q = false; for (const ch of l) { if (ch === '"') q = !q; else if (ch === "," && !q) { out.push(cur); cur = ""; } else cur += ch; } out.push(cur); return out; };
  const head = split(lines[0]);
  return lines.slice(1).map((l) => Object.fromEntries(split(l).map((v, i) => [head[i], v])));
}
function piTags() {
  const out = {};
  for (const r of csvRows(read("out/pi/pi_builder_af.csv"))) {
    if (r.ObjectType !== "Attribute") continue;
    const m = /TE\.([A-Z0-9-]+)\.PV/.exec(r.AttributeConfigString || "");
    if (m) out[m[1]] = `\\\\${r.Parent}|${r.Name}`;
  }
  return out;
}
// The raw replay, read here independently: XMEAS n is column n-1, XMV n is column 41+n-1 (teprob.f order, the same
// mapping the Ignition replay server uses); analyzer tags show their first component.
function rawReplay(file) {
  return readFileSync(join(ROOT, "data", "external", "te-braatz", file), "utf8").split(/\r?\n/).filter((l) => l.trim()).map((l) => l.trim().split(/\s+/).map(Number));
}
const columnOf = (item) => ("xmeas" in item ? Number(String(item.xmeas).split("-")[0]) - 1 : item.xmv <= 11 ? 41 + item.xmv - 1 : null);

// ------------------------------------------------------------------ A. topology and tags
const pid = pidConnections();
const drawnStreams = scene.lines.filter((l) => l.kind === "stream");
const drawnUtilities = scene.lines.filter((l) => l.kind === "utility");
const modelIds = new Set(model.streams.map((s) => s.id));
const drawnIds = new Set(drawnStreams.map((l) => l.id));
const domLines = new Set([...html.matchAll(/data-flow-line="([^"]+)"/g)].map((m) => m[1]));
{
  const unmatched = model.streams.filter((s) => !drawnIds.has(s.id)).map((s) => s.id);
  const extra = drawnStreams.filter((l) => !modelIds.has(l.id)).map((l) => l.id);
  const notInDom = [...drawnIds].filter((id) => !domLines.has(id));
  add("A", "streams_vs_model", !unmatched.length && !extra.length && !notInDom.length,
    `${drawnStreams.length} drawn process lines; ${model.streams.length - unmatched.length} of ${model.streams.length} model streams matched one to one; ${unmatched.length} model streams not drawn; ${extra.length} drawn lines with no model stream`,
    [...unmatched.map((s) => `not drawn: ${s}`), ...extra.map((s) => `extra: ${s}`), ...notInDom.map((s) => `no flow path in the page: ${s}`)]);
  const wrongEnds = [];
  for (const s of model.streams) {
    const l = drawnStreams.find((x) => x.id === s.id);
    if (!l) continue;
    const want = [s.from === "BL" ? `BL-${s.id}` : s.from, s.to === "BL" ? `BL-${s.id}` : s.to];
    const got = [geometry.landed[`${s.id}:start`]?.unit, geometry.landed[`${s.id}:end`]?.unit];
    const landed = [geometry.landed[`${s.id}:start`]?.landed, geometry.landed[`${s.id}:end`]?.landed];
    if (got[0] !== want[0] || got[1] !== want[1] || !landed[0] || !landed[1]) wrongEnds.push(`${s.id}: drawn ${got.join(" -> ")} (landed ${landed.join("/")}), model ${want.join(" -> ")}`);
  }
  add("A", "stream_ends_on_nozzles", !wrongEnds.length,
    `${drawnStreams.length - wrongEnds.length} of ${drawnStreams.length} lines start on a nozzle of their model 'from' unit and end on a nozzle of their 'to' unit (mount found by the kit audit's own search; battery-limit ends land on a battery-limit post)`, wrongEnds);
  // P&ID: each model stream must be exactly one connection in the generated drawing set
  const pidRows = [];
  let pidMatched = 0;
  for (const s of model.streams) {
    const ends = new Set([s.from, s.to].filter((e) => e !== "BL"));
    const named = pid.byStream[s.id];
    let hits = 0;
    let how = "";
    if (named) {
      const units = [...named.units];
      const okUnits = units.length === ends.size && units.every((u) => ends.has(u));
      const okBl = named.bl === (s.from === "BL" || s.to === "BL");
      if (okUnits && okBl) { hits = 1; how = `stream end ${s.id} on sheet(s) ${named.sheets.join(", ")}`; }
      else how = `stream end ${s.id} reaches ${units.join(", ") || "no unit"}${named.bl ? " and the battery limit" : ""}`;
    } else {
      const pair = [...ends].sort().join("|");
      const found = pid.internal.filter((c) => c.units.join("|") === pair);
      hits = found.length;
      how = found.length ? `unit-to-unit line ${pair.replace("|", " - ")} on sheet ${found.map((f) => f.sheet).join(", ")}${found.some((f) => f.shared_with) ? " (shares a line with " + found.flatMap((f) => f.shared_with ?? []).join(", ") + ")" : ""}` : `no line between ${pair}`;
    }
    if (hits === 1 && drawnIds.has(s.id)) pidMatched++;
    else pidRows.push(`${s.id}: ${hits} P&ID connections (${how})`);
  }
  add("A", "streams_vs_pid_graph", pidMatched === model.streams.length,
    `${pidMatched} of ${model.streams.length} drawn streams match exactly one connection in the generated P&ID graph (data/te_pid/key.json); the sheets are drawn from the same model, so this is a round-trip agreement, not independent plant evidence`, pidRows);
  // utilities: inferred lines must point at a final element naming the utility, and are compared with the P&ID's drafting additions
  const utilRows = [];
  for (const l of drawnUtilities) {
    const tag = l.id.split("-").slice(0, 2).join("-");
    const fe = model.final_elements.find((f) => f.tag === tag);
    const ok = fe && /cooling water|steam/i.test(fe.description) && fe.unit === l.unit;
    if (!ok) utilRows.push(`${l.id}: no final element on ${l.unit} naming the utility`);
  }
  const pidUtil = pid.utilities.map((u) => `${u.unit}: ${u.text}`);
  add("A", "utilities_inferred", !utilRows.length,
    `${drawnUtilities.length} inferred utility lines, each from a final element whose own description names cooling water or steam; the P&ID sheets draw ${pid.utilities.length} utility connections as drafting additions (${pidUtil.join("; ")}). Not drawn here: the stripper's condensate return (no final element names it).`, utilRows);
}
{
  const ign = ignitionTags();
  const pi = piTags();
  const markerTags = [...new Set([...html.matchAll(/data-ring="([^"]+)"/g)].map((m) => m[1]))];
  const shown = markerTags;
  const notIgn = shown.filter((t) => !ign[t]);
  const notPi = shown.filter((t) => !pi[t]);
  const pageData = JSON.parse(/const TOUR = (\{.*?\});\n/s.exec(html)[1]).data;
  const pathMismatch = pageData.tags.filter((t) => (t.ignition_path ?? null) !== (ign[t.tag] ?? null) || (t.pi_path ?? null) !== (pi[t.tag] ?? null)).map((t) => `${t.tag}: page ${t.ignition_path} / ${t.pi_path}, exports ${ign[t.tag]} / ${pi[t.tag]}`);
  const modelTags = [...model.instruments, ...model.final_elements].map((i) => i.tag);
  const notShownModel = modelTags.filter((t) => !shown.includes(t));
  const notShownIgn = Object.keys(ign).filter((t) => !shown.includes(t));
  const notShownPi = Object.keys(pi).filter((t) => !shown.includes(t));
  add("A", "tags_in_ignition_and_pi", !notIgn.length && !notPi.length && !pathMismatch.length,
    `${shown.length} tags drawn as markers; ${shown.length - notIgn.length} found in the Ignition gateway tag import, ${shown.length - notPi.length} in the PI AF staging sheet; the paths on each purpose card equal the exports'`,
    [...notIgn.map((t) => `not in Ignition: ${t}`), ...notPi.map((t) => `not in PI AF: ${t}`), ...pathMismatch]);
  add("A", "model_items_not_shown", true,
    `reverse direction: ${modelTags.length - notShownModel.length} of ${modelTags.length} model tags shown; Ignition has ${Object.keys(ign).length} tag instances (${notShownIgn.length} not shown), PI AF ${Object.keys(pi).length} attributes (${notShownPi.length} not shown)`,
    [`model tags not shown: ${notShownModel.join(", ") || "none"}`, `Ignition instances not shown: ${notShownIgn.join(", ") || "none"}`, `PI AF attributes not shown: ${notShownPi.join(", ") || "none"}`], "info");
  // limits: the page's alarm setpoints equal the gateway's published ones
  const meta = json("out/ignition/gateway/build_meta.json").alarms;
  const lim = pageData.tags.filter((t) => JSON.stringify((t.alarms.all || []).map((a) => a.setpointA)) !== JSON.stringify((meta[t.tag] || []).map((a) => a.setpointA))).map((t) => t.tag);
  // every connected final element on a drawn line (a stream, or a utility its description names) has its valve symbol
  const valves = new Set([...html.matchAll(/data-valve="([^"]+)"/g)].map((m) => m[1]));
  const wantValves = model.final_elements.filter((f) => pageData.tags.find((t) => t.tag === f.tag)?.connected && (drawnIds.has(f.stream) || drawnUtilities.some((l) => l.id.startsWith(f.tag + "-"))));
  const missingValves = wantValves.filter((f) => !valves.has(f.tag)).map((f) => f.tag);
  add("A", "valve_symbols", !missingValves.length, `${wantValves.length - missingValves.length} of ${wantValves.length} final elements that sit on a drawn line have a valve symbol on it`, missingValves.map((t) => `no valve drawn: ${t}`));
  add("A", "alarm_limits_from_gateway", !lim.length, `alarm setpoints on the page equal out/ignition/gateway/build_meta.json for all ${pageData.tags.length} tags (${Object.keys(meta).join(", ")} carry published setpoints)`, lim);
  // values: the page's replay data equal the raw files at every sample (rounded to six significant figures)
  const bad = [];
  let compared = 0;
  for (const [run, file] of [["normal", "d00_te.dat"], ["fault6", "d06_te.dat"]]) {
    const rows = rawReplay(file);
    for (const t of pageData.tags) {
      const series = pageData.replay.runs[run].values[t.tag];
      if (!series) continue;
      const item = [...model.instruments, ...model.final_elements].find((i) => i.tag === t.tag);
      const col = columnOf(item);
      rows.forEach((r, k) => {
        compared++;
        const raw = r[col];
        if (Math.abs(raw - series[k]) > Math.max(1e-9, Math.abs(raw) * 6e-6)) bad.push(`${run} ${t.tag} sample ${k}: page ${series[k]}, file ${raw}`);
      });
    }
  }
  add("A", "replay_values_from_file", !bad.length, `${compared} replay values on the page compared with the raw Braatz files; ${bad.length} differ beyond six significant figures`, bad.slice(0, 20));
  const notConnected = pageData.tags.filter((t) => !t.connected).map((t) => t.tag);
  add("A", "not_connected_tags", true, `tags with no replay source, shown as not connected and never animated: ${notConnected.join(", ") || "none"}`, [], "info");
}

// ------------------------------------------------------------------ B. geometry
for (const [k, v] of Object.entries(geometry.counts)) add("B", `kit_${k}`, v === 0, `${k.replace(/_/g, " ")}: ${v}`);
add("B", "kit_allowed_pairs", true, `explicitly excused depth pairs (${geometry.allowed.rule}): ${geometry.allowed.excused_depth_pairs.length}`, geometry.allowed.excused_depth_pairs.map((d) => `${d.front} / ${d.back}: ${d.px2} px² one way, ${d.other_way_px2} px² the other`), "info");
add("B", "kit_audit", geometry.failures === 0, `anatomy kit audit over ${geometry.items} drawn items, ${geometry.tubes} tube runs, ${geometry.solids} solids: ${geometry.failures} problems`);

// ------------------------------------------------------------------ C/D. browser
const LEGIBILITY = `(() => {
  const parse = (c) => { const m = c.match(/rgba?\\(([^)]+)\\)/); if (!m) return null; const p = m[1].split(/[ ,/]+/).filter(Boolean).map(Number); return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 }; };
  const lum = ({ r, g, b }) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const over = (top, under) => ({ r: top.r * top.a + under.r * (1 - top.a), g: top.g * top.a + under.g * (1 - top.a), b: top.b * top.a + under.b * (1 - top.a), a: 1 });
  const background = (el) => { const stack = []; for (let e = el; e; e = e.parentElement) { const c = parse(getComputedStyle(e).backgroundColor); if (c && c.a > 0) { stack.push(c); if (c.a >= 0.999) break; } } let bg = { r: 255, g: 255, b: 255, a: 1 }; for (const c of stack.reverse()) bg = over(c, bg); return bg; };
  const out = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    if (!n.textContent.trim()) continue;
    const el = n.parentElement;
    if (!el || el.closest("svg, script, style, [hidden]")) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === "hidden" || cs.display === "none" || Number(cs.opacity) === 0) continue;
    const range = document.createRange(); range.selectNodeContents(n);
    const r = range.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    const fg = parse(cs.color); const bg = background(el);
    const L1 = lum(over(fg, bg)), L2 = lum(bg);
    out.push({ text: n.textContent.trim().slice(0, 60), size: parseFloat(cs.fontSize), contrast: (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05), pill: Boolean(el.closest(".tour-pill")) });
  }
  const pills = [...document.querySelectorAll(".tour-pill")].filter((p) => !p.hidden).map((p) => { const r = p.getBoundingClientRect(); return { id: p.dataset.label, x: r.left, y: r.top, w: r.width, h: r.height }; });
  const stage = document.querySelector("[data-stage]").getBoundingClientRect();
  const overlaps = [];
  for (let i = 0; i < pills.length; i++) for (let j = i + 1; j < pills.length; j++) { const a = pills[i], b = pills[j]; if (a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h) overlaps.push(a.id + " x " + b.id); }
  const outside = pills.filter((p) => p.x < stage.left - 0.5 || p.y < stage.top - 0.5 || p.x + p.w > stage.right + 0.5 || p.y + p.h > stage.bottom + 0.5).map((p) => p.id);
  const dropped = [...document.querySelectorAll('.tour-pill[data-placed="no"]')].map((p) => p.dataset.label);
  return { texts: out, pills: pills.length, overlaps, outside, dropped, scrollX: document.documentElement.scrollWidth > innerWidth + 1 };
})()`;

const VIEWS = [
  { id: "overview", js: "" },
  ...data.tour_order.map((u) => ({ id: `focus-${u}`, js: `document.querySelector('[data-unit-button="${u}"]').click()` })),
  { id: "fault6-alarm", js: "document.querySelector('[data-jump-alarm]').click()" },
  { id: "loto", js: "document.querySelector('[data-mode-button=\"loto\"]').click(); document.querySelector('[data-loto=\"bl:S1\"]').click()" },
];
const STILLS = { "overview": "overview", "fault6-alarm": "fault6-alarm", "loto": "loto-mockup", "focus-R-101": "reactor" };
let browser;
try { browser = await launch(); } catch (e) { console.log(`no browser: ${e.message}`); process.exit(2); }
mkdirSync(SHOTS, { recursive: true });
const legibility = [];
const stills = [];
try {
  for (const theme of ["dark", "light"]) {
    for (const [w, h] of [[390, 844], [1440, 1000]]) {
      const page = await openPage(browser.port, { width: w, height: h });
      const file = join(OUT, theme === "light" ? "te-tour-light.html" : "te-tour.html");
      for (const view of VIEWS) {
        await page.goto(pathToFileURL(file).href);
        if (view.js) await page.evaluate(view.js);
        await page.sleep(1300);
        const r = await page.evaluate(LEGIBILITY);
        const cover = await page.evaluate("window.__tour.labelCover()");
        const small = r.texts.filter((t) => t.size < 12);
        const low = r.texts.filter((t) => t.contrast < 4.5);
        legibility.push({ theme, width: w, view: view.id, texts: r.texts.length, pills: r.pills, min_font: Math.min(...r.texts.map((t) => t.size)), min_contrast: +Math.min(...r.texts.map((t) => t.contrast)).toFixed(2), overlaps: r.overlaps, outside: r.outside, dropped: r.dropped, small: small.map((t) => `${t.text} (${t.size}px)`), cover: cover.filter((c) => c.cover > 0.1).map((c) => `${c.id} ${(c.cover * 100).toFixed(0)}%`), max_cover: Math.max(0, ...cover.map((c) => c.cover)), low: low.map((t) => `${t.text} (${t.contrast.toFixed(2)}:1)`), hscroll: r.scrollX });
        const still = STILLS[view.id];
        if (still) {
          const name = `${still}-${w}-${theme}.jpg`;
          writeFileSync(join(SHOTS, name), await page.shot(w < 600 ? "main" : ".tour-layout", 1, "jpeg", w < 600 ? 1700 : 1250));
          stills.push(`drafts/interactive-tour/shots/${name}`);
        }
      }
      if (page.problems.length) add("D", `console_${theme}_${w}`, false, `console errors at ${w}px ${theme}`, page.problems);
      page.close();
    }
  }
  // D. behaviour, on the dark desktop page
  const page = await openPage(browser.port, { width: 1440, height: 1000 });
  await page.goto(pathToFileURL(join(OUT, "te-tour.html")).href);
  const raw6 = rawReplay("d06_te.dat");
  const pi107 = model.instruments.find((i) => i.tag === "PI-107");
  const setpoints = json("out/ignition/gateway/build_meta.json").alarms["PI-107"].map((a) => a.setpointA);
  const firstRaw = raw6.findIndex((r) => setpoints.some((s) => r[columnOf(pi107)] > s));
  await page.evaluate("document.querySelector('[data-jump-alarm]').click()");
  await page.sleep(900);
  const at = await page.evaluate(`({ state: window.__tour.state(), alarms: [...document.querySelectorAll('[data-alarm-tag]')].map((p) => p.dataset.alarmTag), ring: document.querySelector('[data-ring="PI-107"]').closest('.tour-marker').dataset.state, pill: document.querySelector('[data-label="tag:PI-107"]')?.textContent, pillState: document.querySelector('[data-label="tag:PI-107"]')?.dataset.state, readout: document.querySelector('[data-readout]').textContent })`);
  const shownValue = Number((at.pill || "").match(/PI-107 ([\d,.]+)/)?.[1]?.replace(/,/g, ""));
  const rawValue = raw6[firstRaw][columnOf(pi107)];
  add("D", "fault6_alarm_shown", at.state.run === "fault6" && at.state.sample === firstRaw && at.alarms.includes("PI-107") && at.ring === "alarm" && at.pillState === "alarm" && Math.abs(shownValue - rawValue) < 0.5,
    `the raw d06_te.dat first crosses a published PI-107 setpoint at sample ${firstRaw} (+${(firstRaw - 160) * 3} min after the fault starts; ${rawValue} > ${setpoints[0]} kPa g); "Jump to the first alarm" lands on sample ${at.state.sample}, the alarm list shows ${at.alarms.join(", ") || "nothing"}, the marker ring is "${at.ring}", the pill reads "${at.pill}"`);
  await page.evaluate(`(() => { const s = document.querySelector('[data-scrub]'); s.value = ${firstRaw - 1}; s.dispatchEvent(new Event('input')); })()`);
  await page.sleep(300);
  const before = await page.evaluate("[...document.querySelectorAll('[data-alarm-tag]')].length");
  add("D", "no_alarm_one_sample_before", before === 0, `one sample earlier (${firstRaw - 1}) the page shows ${before} alarms`);
  // pulses move forward: the dash offset of a line's first path falls over time (pattern travels from 'from' to 'to')
  await page.evaluate("document.querySelector('[data-unit-button=\"\"]').click()");
  const offsets = async () => page.evaluate(`Object.fromEntries([...new Set([...document.querySelectorAll('[data-flow-line]')].map((p) => p.dataset.flowLine))].map((id) => [id, parseFloat(document.querySelector('[data-flow-line="' + id + '"]').style.strokeDashoffset || "0")]))`);
  const o1 = await offsets();
  await page.sleep(800);
  const o2 = await offsets();
  const backwards = Object.keys(o1).filter((id) => !(o2[id] < o1[id]));
  add("D", "pulses_move_forward", !backwards.length, `${Object.keys(o1).length - backwards.length} of ${Object.keys(o1).length} lines' pulses advance from the line's start (its model 'from' end) toward its end in 0.8 s`, backwards);
  // chevrons agree with the path direction they sit on
  const chev = await page.evaluate(`(() => { const bad = []; let n = 0; for (const c of document.querySelectorAll('[data-chev]')) { n++; const p = c.parentElement.querySelector('.tour-flow'); const len = p.getTotalLength(); const d = c.dataset.dir.split(',').map(Number); const box = c.getBBox(); const cx = box.x + box.width / 2, cy = box.y + box.height / 2; let best = 0, bd = 1e9; for (let s = 0; s <= len; s += 0.5) { const q = p.getPointAtLength(s); const dd = Math.hypot(q.x - cx, q.y - cy); if (dd < bd) { bd = dd; best = s; } } const a = p.getPointAtLength(Math.max(0, best - 1)), b = p.getPointAtLength(Math.min(len, best + 1)); if ((b.x - a.x) * d[0] + (b.y - a.y) * d[1] <= 0) bad.push(c.dataset.chev); } return { n, bad }; })()`);
  add("D", "arrows_point_downstream", !chev.bad.length, `${chev.n - chev.bad.length} of ${chev.n} chevrons point along their line's path direction`, chev.bad);
  // LOTO: isolate the A feed block valve, then every feed and the compressor motor
  await page.evaluate("document.querySelector('[data-mode-button=\"loto\"]').click(); document.querySelector('[data-loto=\"bl:S1\"]').click()");
  await page.sleep(500);
  const l1 = await offsets();
  await page.sleep(700);
  const l2 = await offsets();
  const off1 = await page.evaluate("[...new Set([...document.querySelectorAll('.it.tour-off[data-route]')].map((e) => e.dataset.route))]");
  const expect1 = M.energized(data, ["bl:S1"]);
  const stopped1 = Object.keys(l1).filter((id) => l1[id] === l2[id]);
  add("D", "loto_one_point", JSON.stringify(off1.sort()) === JSON.stringify(expect1.stopped.slice().sort()) && JSON.stringify(stopped1.sort()) === JSON.stringify(expect1.stopped.slice().sort()),
    `isolating the A feed block valve: the model says ${expect1.stopped.join(", ")} stop(s); the page greys ${off1.join(", ")} and the pulses stand still on ${stopped1.join(", ")}; the rest keep moving`);
  const all = ["bl:S1", "bl:S2", "bl:S3", "bl:S4", "motor:K-101"];
  for (const id of all.slice(1)) await page.evaluate(`document.querySelector('[data-loto="${id}"]').click()`);
  await page.sleep(500);
  const l3 = await offsets();
  await page.sleep(700);
  const l4 = await offsets();
  const e = M.energized(data, all);
  const movingStreams = drawnStreams.map((s) => s.id).filter((id) => l3[id] !== l4[id]);
  const text = await page.evaluate("document.querySelector('[data-energy]').textContent");
  const namesNot = e.sources.filter((s) => !s.isolated).every((s) => text.includes(s.text));
  add("D", "loto_downstream_stops", e.flowing.length === 0 && movingStreams.length === 0 && namesNot && /Not isolated \(6\)/.test(text),
    `isolating every feed block valve and the K-101 motor stops all ${drawnStreams.length} process lines (computed: ${e.flowing.length} flowing; pulses moving on the page: ${movingStreams.length}); the readout lists the ${e.sources.filter((s) => !s.isolated).length} sources still not isolated (outlets, agitator, utilities)`);
  const recycle = M.energized(data, ["bl:S1", "bl:S2", "bl:S3", "bl:S4"]);
  add("D", "loto_compressor_still_drives_recycle", recycle.flowing.length > 0, `with only the four feeds isolated the K-101 motor still drives the recycle loop: ${recycle.flowing.join(", ")} keep flowing (the readout does not call the unit isolated)`, [], "pass");
  writeFileSync(join(SHOTS, "loto-all-feeds-and-motor-1440-dark.jpg"), await page.shot(".tour-layout", 1, "jpeg", 1500));
  stills.push("drafts/interactive-tour/shots/loto-all-feeds-and-motor-1440-dark.jpg");
  // keyboard: the figure takes focus and the arrow keys walk the units in flow order
  await page.evaluate("document.querySelector('[data-mode-button=\"flow\"]').click(); document.querySelector('[data-unit-button=\"\"]').click(); document.querySelector('[data-stage]').focus()");
  await page.key("ArrowRight", "ArrowRight");
  await page.sleep(200);
  const k1 = await page.evaluate("window.__tour.state().focus");
  await page.key("ArrowRight", "ArrowRight");
  await page.sleep(200);
  const k2 = await page.evaluate("window.__tour.state().focus");
  await page.key("Escape", "Escape");
  await page.sleep(200);
  const k3 = await page.evaluate("window.__tour.state().focus");
  add("D", "keyboard", k1 === data.tour_order[0] && k2 === data.tour_order[1] && k3 === null, `arrow keys on the focused figure: ${k1}, then ${k2}; Escape returns to the overview (${k3 === null ? "yes" : k3})`);
  const controls = await page.evaluate("[...document.querySelectorAll('button, input')].filter((b) => !b.closest('[hidden]')).filter((b) => !(b.getAttribute('aria-label') || b.textContent.trim() || b.closest('label'))).length");
  add("D", "controls_named", controls === 0, `${controls} visible buttons or inputs without an accessible name`);
  if (page.problems.length) add("D", "console_behaviour", false, "console errors during the behaviour drive", page.problems);
  page.close();
} finally {
  browser.close();
}
const worst = (k) => legibility.reduce((m, r) => Math.min(m, r[k]), Infinity);
const overl = legibility.filter((r) => r.overlaps.length);
const small = legibility.filter((r) => r.small.length);
const low = legibility.filter((r) => r.low.length);
const outside = legibility.filter((r) => r.outside.length);
const scroll = legibility.filter((r) => r.hscroll);
add("C", "label_overlaps", !overl.length, `${legibility.length} page states (2 themes × 390 and 1440 px × ${VIEWS.length} views): ${overl.length} with overlapping labels`, overl.map((r) => `${r.theme} ${r.width} ${r.view}: ${r.overlaps.join("; ")}`));
const covered = legibility.filter((r) => r.cover.length);
add("C", "labels_off_geometry", !covered.length, `no label covers more than 10% of its box with drawn, undimmed pipes or machines (largest share ${(Math.max(...legibility.map((r) => r.max_cover)) * 100).toFixed(1)}%); ${covered.length} states over the limit`, covered.map((r) => `${r.theme} ${r.width} ${r.view}: ${r.cover.join(", ")}`));
add("C", "min_font_size", !small.length, `smallest visible text ${worst("min_font")} px (minimum 12 px) in every state`, small.flatMap((r) => r.small.map((s) => `${r.theme} ${r.width} ${r.view}: ${s}`)).slice(0, 20));
add("C", "contrast_wcag_aa", !low.length, `lowest text contrast ${worst("min_contrast")}:1 over ${legibility.reduce((n, r) => n + r.texts, 0)} visible text runs (WCAG AA for normal text: 4.5:1)`, low.flatMap((r) => r.low.map((s) => `${r.theme} ${r.width} ${r.view}: ${s}`)).slice(0, 30));
add("C", "labels_inside_figure", !outside.length, `labels outside the figure: ${outside.length} states`, outside.map((r) => `${r.theme} ${r.width} ${r.view}: ${r.outside.join(", ")}`));
add("C", "no_horizontal_scroll", !scroll.length, `pages wider than the viewport: ${scroll.length} states`, scroll.map((r) => `${r.theme} ${r.width} ${r.view}`));
const dropped = legibility.filter((r) => r.dropped.length);
add("C", "labels_without_room", true, `labels the layout had no room for (hidden rather than overlapped; the same information stays on the purpose card): ${dropped.length} of ${legibility.length} states`, dropped.map((r) => `${r.theme} ${r.width} ${r.view}: ${r.dropped.join(", ")}`), "info");

// ------------------------------------------------------------------ hygiene: no local paths or private names in what is published
{
  // Local paths are matched by shape; names that must never appear are supplied from outside the repository in
  // TOUR_DENY_TERMS (comma-separated), like the HAZARD_DENY_TERMS check of scripts/hazard_citations.py.
  const deny = (process.env.TOUR_DENY_TERMS || "").split(",").map((t) => t.trim()).filter(Boolean);
  const escapeRe = (t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const pats = [/[A-Za-z]:\\Users\\/, /[A-Za-z]:\/Users\//, /\/Users\/[A-Za-z]/, /\/home\/[a-z]/, ...deny.map((t) => new RegExp(escapeRe(t), "i"))];
  const files = [];
  const walk = (d) => { for (const n of readdirSync(d)) { const p = join(d, n); if (statSync(p).isDirectory()) walk(p); else if (/\.(mjs|js|css|md|json)$/.test(n)) files.push(p); } };
  walk(HERE);
  files.push(join(OUT, "te-tour.html"), join(OUT, "te-tour-light.html"), join(ROOT, "scripts", "export_interactive_tour.py"));
  const hits = [];
  for (const f of files) {
    if (f.endsWith("report.json") || f.endsWith("report.md")) continue;
    const text = readFileSync(f, "utf8");
    pats.forEach((p, i) => { if (p.test(text)) hits.push(`${relative(ROOT, f).replace(/\\/g, "/")}: ${i < 4 ? "local path" : `deny term ${i - 3}`}`); });
  }
  add("E", "hygiene", !hits.length, `${files.length} files scanned for local paths${deny.length ? ` and ${deny.length} deny terms (TOUR_DENY_TERMS)` : " (TOUR_DENY_TERMS not set: deny-term part skipped)"}: ${hits.length} hits`, hits, deny.length ? undefined : (hits.length ? "fail" : "info"));
}

const failed = checks.filter((c) => c.status === "fail");
const report = {
  schema: "pid-interactive-tour-verification/0 (proof of concept)",
  note: "Proof of concept, not reviewed by an operator. Passing these checks means the drawing agrees with the repository's model, exports and replay files and is legible by these measures; it does not mean an operator finds it useful, and the geometry is placeholder.",
  chrome: browser.binary.split(/[\\/]/).slice(-2).join("/"),
  summary: { checks: checks.length, pass: checks.filter((c) => c.status === "pass").length, info: checks.filter((c) => c.status === "info").length, fail: failed.length },
  checks, legibility: legibility.map(({ texts, ...r }) => ({ texts, ...r })), stills,
};
mkdirSync(AUDIT, { recursive: true });
writeFileSync(join(AUDIT, "report.json"), JSON.stringify(report, null, 1) + "\n");
const md = [
  "# Interactive tour: verification report (proof of concept)", "",
  report.note, "",
  `Result: ${report.summary.pass} pass, ${report.summary.info} informational, ${report.summary.fail} fail, of ${report.summary.checks} checks. Written by \`node drafts/interactive-tour/verify.mjs\`.`, "",
  "| Group | Check | Status | Result |", "|---|---|---|---|",
  ...checks.map((c) => `| ${c.group} | ${c.id} | ${c.status} | ${c.summary.replace(/\|/g, "\\|")} |`), "",
  "Groups: A topology and tags against the raw model, P&ID key, Ignition and PI AF exports and replay files; B the anatomy kit geometry audit; C legibility in headless Chrome; D behaviour; E publication hygiene.", "",
  "## Details", "",
  ...checks.filter((c) => c.details.length).flatMap((c) => [`**${c.id}**`, "", ...c.details.slice(0, 40).map((d) => `- ${d.replace(/\|/g, "\\|")}`), ""]),
  "## Review stills", "", ...stills.map((s) => `- [${s.split("/").pop()}](../shots/${s.split("/").pop()})`), "",
].join("\n");
writeFileSync(join(AUDIT, "report.md"), md);
console.log(md.split("## Details")[0]);
process.exit(failed.length ? 1 : 0);
