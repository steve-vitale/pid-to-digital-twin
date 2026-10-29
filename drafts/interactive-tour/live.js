// Live layer of the interactive tour. Inlined by build.mjs after `const TOUR = {...}` and model.mjs (classify,
// statesAt, alarmsAt, firstAlarm, flowShare, energized, minutesAfterFault, fmt). Every number written to the page
// is read from TOUR.data (the export of the repository's data files) through those functions.
const D = TOUR.data;
const L = TOUR.live;
const stage = document.querySelector("[data-stage]");
const svgs = [...stage.querySelectorAll("svg")];
const plant = stage.querySelector('svg[data-layer="plant"]');
const labelsBox = stage.querySelector("[data-labels]");
const readout = document.querySelector("[data-readout]");
const hint = document.querySelector("[data-hint]");
const card = document.querySelector("[data-card]");
const scrub = document.querySelector("[data-scrub]");
const timeText = document.querySelector("[data-time]");
const alarmBox = document.querySelector("[data-alarms]");
const energyBox = document.querySelector("[data-energy]");
const playButton = document.querySelector("[data-play]");
const figure = document.querySelector(".tour-figure");
const still = matchMedia("(prefers-reduced-motion: reduce)");
const tagOf = Object.fromEntries(D.tags.map((t) => [t.tag, t]));
const unitOf = Object.fromEntries(D.units.map((u) => [u.id, u]));
const streamOf = Object.fromEntries(D.streams.map((s) => [s.id, s]));
const utilityOf = Object.fromEntries(D.utilities.map((u) => [u.id, u]));
const esc = (t) => String(t ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const NS = "http://www.w3.org/2000/svg";

const S = { mode: "flow", focus: null, run: "normal", sample: 0, playing: false, isolated: new Set(), view: L.viewBox.slice(), target: null };

// ------------------------------------------------------------------ flow pulses
const flowPaths = {};
for (const path of plant.querySelectorAll("[data-flow-line]")) {
  (flowPaths[path.dataset.flowLine] ??= []).push({ el: path, run: Number(path.dataset.run) });
}
const phase = Object.fromEntries(L.lines.map((l) => [l.id, 0]));
const BASE_SPEED = 46; // viewBox units per second at the normal-band mean flow
function lineShare(line) {
  if (S.mode === "loto") return 1;
  if (line.kind === "utility") return 1;
  return flowShare(D, S.run, S.sample, streamOf[line.id]).share;
}
function lineOn(line) {
  if (S.mode !== "loto") return true;
  const e = energy();
  return line.kind === "utility" ? e.utilities[line.id] : e.streams[line.id];
}
let energyCache = null;
function energy() {
  if (!energyCache) energyCache = energized(D, [...S.isolated]);
  return energyCache;
}
function paintFlow() {
  for (const line of L.lines) {
    for (const p of flowPaths[line.id] ?? []) p.el.style.strokeDashoffset = (p.run - phase[line.id]).toFixed(1);
  }
}

// ------------------------------------------------------------------ replay states
const markers = Object.fromEntries([...plant.querySelectorAll(".tour-marker")].map((g) => [g.querySelector("[data-ring]").dataset.ring, g]));
function states() {
  return statesAt(D, S.run, S.sample);
}
function paintStates() {
  const st = states();
  for (const [tag, g] of Object.entries(markers)) g.dataset.state = st[tag]?.state ?? "unknown";
  // liquid in each cut-away window: the level tag's recorded value as a share of the drawn window (placeholder)
  for (const [uid, tag] of Object.entries(L.levelTag)) {
    const holder = plant.querySelector(`[data-liquid="${uid}"]`);
    const w = L.windows[uid];
    if (!holder || !w) continue;
    const v = st[tag]?.value;
    const share = typeof v === "number" ? Math.max(0, Math.min(100, v)) / 100 : 0;
    const z = w.z0 + share * (w.z1 - w.z0);
    const ring = (zz) => Array.from({ length: 49 }, (_, i) => isoPt([w.x + w.R * Math.cos((i / 48) * Math.PI * 2), w.y + w.R * Math.sin((i / 48) * Math.PI * 2), zz]));
    const top = ring(z);
    const bottom = ring(w.z0 - 2);
    const hull = convexHull([...top, ...bottom]);
    holder.innerHTML = `<path class="tour-liquid" d="${pathD(hull, true)}"/><path class="tour-liquid-top" d="${pathD(top, true)}"/>`;
    holder.dataset.level = typeof v === "number" ? v.toFixed(1) : "";
    // the level glass shows the same recorded level over its own span
    const gl = L.glass && L.glass[uid];
    const gh = gl && plant.querySelector(`[data-glass="${uid}"]`);
    if (gh) {
      const zg = gl.z0 + share * (gl.z1 - gl.z0);
      const ringG = (zz) => Array.from({ length: 17 }, (_, i) => isoPt([gl.x + gl.r * Math.cos((i / 16) * Math.PI * 2), gl.y + gl.r * Math.sin((i / 16) * Math.PI * 2), zz]));
      gh.innerHTML = `<path class="tour-liquid tour-glass-liquid" d="${pathD(convexHull([...ringG(zg), ...ringG(gl.z0)]), true)}"/>`;
    }
  }
  const alarms = alarmsAt(D, S.run, S.sample);
  const n = alarms.length;
  const m = minutesAfterFault(D, S.sample);
  const when = S.run === "fault6" ? (m < 0 ? `${-m} min before the fault starts` : `+${m} min after the fault starts`) : "normal operation";
  const hours = Math.floor((S.sample * D.replay.minutes_per_sample) / 60);
  const mins = (S.sample * D.replay.minutes_per_sample) % 60;
  timeText.textContent = `Sample ${S.sample} of ${D.replay.runs[S.run].samples - 1} · ${hours} h ${String(mins).padStart(2, "0")} min into the record · ${when}`;
  readout.textContent = S.mode === "loto" ? `LOTO mockup · ${S.isolated.size} of ${D.loto.points.length} isolated` : `sample ${S.sample} · ${n ? `${n} alarm${n > 1 ? "s" : ""}` : "no alarm"}`;
  alarmBox.innerHTML = n
    ? alarms.map((a) => {
        const t = tagOf[a.tag];
        const op = t.alarms.operating_high;
        const sd = t.alarms.shutdown_high;
        const lim = op !== null && a.value > op ? `high alarm ${fmt(op)} ${t.uom}` : `shutdown limit ${fmt(sd)} ${t.uom}`;
        return `<p data-alarm-tag="${esc(a.tag)}"><strong>${esc(a.tag)}</strong> ${esc(t.label)}: ${esc(fmt(a.value))} ${esc(t.uom)}, above its ${esc(lim)} (published setpoint).</p>`;
      }).join("")
    : `<p class="tour-quiet">No tag above a published alarm setpoint at this sample.</p>`;
}

// ------------------------------------------------------------------ geometry helpers (same camera as the build)
function isoPt([x, y, z]) {
  const P = L.P;
  const a = ((P.azimuth ?? 45) * Math.PI) / 180;
  const e = ((P.elevation ?? 30) * Math.PI) / 180;
  const kk = P.scale * Math.sqrt(1.6);
  return [P.origin[0] + (x * Math.sin(a) - y * Math.cos(a)) * kk, P.origin[1] + ((x * Math.cos(a) + y * Math.sin(a)) * Math.sin(e) - z * Math.cos(e)) * kk];
}
const pathD = (pts, closed) => pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join("") + (closed ? "Z" : "");
function convexHull(points) {
  const pts = points.slice().sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const cross = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const lower = [];
  for (const p of pts) { while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], p) <= 0) lower.pop(); lower.push(p); }
  const upper = [];
  for (const p of pts.reverse()) { while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], p) <= 0) upper.pop(); upper.push(p); }
  return lower.slice(0, -1).concat(upper.slice(0, -1));
}

// ------------------------------------------------------------------ focus, dimming and the camera (viewBox)
const items = [...plant.querySelectorAll(".it")];
const linesOfUnit = (uid) => new Set(L.lines.filter((l) => l.from === uid || l.to === uid || l.unit === uid || (l.from || "").includes(uid) || (l.to || "").includes(uid)).map((l) => l.id));
function paintFocus() {
  const keep = S.focus ? linesOfUnit(S.focus) : null;
  for (const it of items) {
    const route = it.dataset.route;
    const dim = S.focus && !(it.dataset.unit === S.focus || (route && keep.has(route)) || (it.dataset.unit || "").endsWith(S.focus));
    it.classList.toggle("tour-dim", Boolean(dim));
  }
  const on = energy();
  for (const it of items) {
    const route = it.dataset.route;
    if (!route) continue;
    const line = L.lines.find((l) => l.id === route);
    it.classList.toggle("tour-off", Boolean(line) && !lineOn(line));
  }
  void on;
  for (const b of document.querySelectorAll("[data-unit-button]")) b.setAttribute("aria-pressed", String((b.dataset.unitButton || null) === S.focus));
  hint.textContent = S.focus ? "Arrow keys · Esc" : "Select a unit";
  S.target = S.focus ? fitView(L.units[S.focus].box) : L.viewBox.slice();
  if (still.matches) S.view = S.target.slice();
}
function fitView([x, y, w, h]) {
  const [X0, Y0, W] = L.viewBox;
  const rect = stage.getBoundingClientRect();
  const aspect = rect.width / rect.height;
  const H = Math.max(L.viewBox[3], W / aspect);
  const margin = 1.35;
  let vw = Math.max(w * margin, 360);
  let vh = Math.max(h * margin, 210);
  if (vw / vh > aspect) vh = vw / aspect;
  else vw = vh * aspect;
  vw = Math.min(W, vw);
  vh = Math.min(H, vh);
  const yMid = Y0 + L.viewBox[3] / 2;
  const cx = Math.max(X0 + vw / 2, Math.min(X0 + W - vw / 2, x + w / 2));
  const cy = Math.max(yMid - H / 2 + vh / 2, Math.min(yMid + H / 2 - vh / 2, y + h / 2));
  return [cx - vw / 2, cy - vh / 2, vw, vh];
}
function applyView() {
  const v = S.view.map((n) => n.toFixed(2)).join(" ");
  for (const s of svgs) s.setAttribute("viewBox", v);
}

// ------------------------------------------------------------------ labels: unit names, key tags, alarms, LOTO points
let leaderSvg = null;
function toScreen([x, y]) {
  const m = plant.getScreenCTM();
  const host = labelsBox.getBoundingClientRect();
  return [m.a * x + m.c * y + m.e - host.left, m.b * x + m.d * y + m.f - host.top];
}
function wanted() {
  const narrow = plant.getBoundingClientRect().width < 620;
  const out = [];
  const st = states();
  const focus = S.focus;
  if (S.mode === "loto") {
    for (const p of L.loto) {
      if (focus && !lotoNear(p.id, focus)) continue;
      const point = D.loto.points.find((x) => x.id === p.id);
      out.push({ id: `loto:${p.id}`, kind: "loto", at: p.at, text: narrow && !focus ? `${p.n}` : `${p.n} ${point.text.split(":")[0]}`, isolated: S.isolated.has(p.id), priority: 2 });
    }
  }
  for (const id of D.tour_order) {
    if (focus && id !== focus) continue;
    const u = unitOf[id];
    const short = u.kind === "separator" ? "Separator" : u.kind === "compressor" ? "Compressor" : "";
    out.push({ id: `unit:${id}`, kind: "unit", unit: id, at: L.units[id].label, text: narrow && !focus ? `${id}${short ? ` ${short}` : ""}` : `${id} ${u.name}`, focus: id === focus, priority: 3 });
  }
  if (S.mode === "flow") {
    const show = new Set();
    if (focus) for (const t of unitOf[focus].key_tags.slice(0, narrow ? 3 : 4)) show.add(t);
    for (const t of D.tags) if (st[t.tag].state === "alarm") show.add(t.tag);
    for (const tag of show) {
      const t = tagOf[tag];
      const m = L.markers.find((x) => x.tag === tag);
      if (!m) continue;
      const s = st[tag];
      const value = s.value !== null && s.value !== undefined ? `${fmt(s.value)} ${t.uom}` : "not connected";
      const op = t.alarms.operating_high;
      const text = `${tag} ${value}${op !== null && !narrow ? ` · high alarm ${fmt(op)}` : ""}`;
      out.push({ id: `tag:${tag}`, kind: "tag", tag, at: m.at, text, state: s.state, priority: s.state === "alarm" ? 4 : 1 });
    }
  }
  return out.sort((a, b) => b.priority - a.priority);
}
function lotoNear(pointId, uid) {
  const p = D.loto.points.find((x) => x.id === pointId);
  if (p.target.unit) return p.target.unit === uid;
  if (p.target.stream) { const s = streamOf[p.target.stream]; return s.from === uid || s.to === uid; }
  return utilityOf[p.target.utility]?.unit === uid;
}
// Occupancy of drawn geometry on screen, at a third of the pixel size, for label placement and its audit. Parts that
// are dimmed in a focused view do not count: a label may sit over a faded unit.
function occupancy(host) {
  const f = 3;
  const cw = Math.max(1, Math.ceil(host.width / f)), ch = Math.max(1, Math.ceil(host.height / f));
  const canvas = document.createElement("canvas");
  canvas.width = cw; canvas.height = ch;
  const ctx = canvas.getContext("2d");
  const m = plant.getScreenCTM();
  ctx.setTransform(m.a / f, m.b / f, m.c / f, m.d / f, (m.e - host.left) / f, (m.f - host.top) / f);
  const keep = S.focus ? linesOfUnit(S.focus) : null;
  const shown = (unit) => !S.focus || unit === S.focus;
  ctx.fillStyle = "#000"; ctx.strokeStyle = "#000"; ctx.lineCap = "round"; ctx.lineJoin = "round";
  for (const b of L.occ.bodies) {
    if (!shown(b.unit) || b.hull.length < 3) continue;
    ctx.beginPath(); b.hull.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y))); ctx.closePath(); ctx.fill();
  }
  for (const l of L.occ.lines) {
    if (keep && !keep.has(l.id)) continue;
    ctx.lineWidth = l.w + 2;
    ctx.beginPath(); l.pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y))); ctx.stroke();
  }
  const data = ctx.getImageData(0, 0, cw, ch).data;
  const sum = new Uint32Array((cw + 1) * (ch + 1));
  for (let y = 0; y < ch; y++) {
    let row = 0;
    for (let x = 0; x < cw; x++) { row += data[(y * cw + x) * 4 + 3] > 40 ? 1 : 0; sum[(y + 1) * (cw + 1) + x + 1] = sum[y * (cw + 1) + x + 1] + row; }
  }
  const cover = (r) => {
    const x0 = Math.max(0, Math.floor(r.x / f)), y0 = Math.max(0, Math.floor(r.y / f));
    const x1 = Math.min(cw, Math.ceil((r.x + r.w) / f)), y1 = Math.min(ch, Math.ceil((r.y + r.h) / f));
    if (x1 <= x0 || y1 <= y0) return 0;
    const n = sum[y1 * (cw + 1) + x1] - sum[y0 * (cw + 1) + x1] - sum[y1 * (cw + 1) + x0] + sum[y0 * (cw + 1) + x0];
    return n / ((x1 - x0) * (y1 - y0));
  };
  return { cover };
}
const pills = new Map();
function layoutLabels() {
  const want = wanted();
  const host = labelsBox.getBoundingClientRect();
  if (!leaderSvg) {
    leaderSvg = document.createElementNS(NS, "svg");
    leaderSvg.setAttribute("class", "tour-leaders");
    leaderSvg.setAttribute("aria-hidden", "true");
    labelsBox.appendChild(leaderSvg);
  }
  const ids = new Set(want.map((w) => w.id));
  for (const [id, el] of pills) if (!ids.has(id)) { el.remove(); pills.delete(id); }
  const placed = [];
  const occ = occupancy(host);
  const anchors = want.map((w) => toScreen(w.at));
  let leaders = "";
  want.forEach((w, index) => {
    let el = pills.get(w.id);
    if (!el) {
      el = document.createElement("span");
      el.className = "tour-pill";
      el.dataset.kind = w.kind;
      el.dataset.label = w.id;
      el.addEventListener("click", () => {
        if (w.kind === "unit") focusUnit(w.unit);
        else if (w.kind === "tag") focusUnit(tagOf[w.tag].unit);
        else if (w.kind === "loto") toggleLoto(w.id.slice(5));
      });
      labelsBox.appendChild(el);
      pills.set(w.id, el);
    }
    if (el.textContent !== w.text) el.textContent = w.text;
    el.toggleAttribute("data-focus", Boolean(w.focus));
    el.toggleAttribute("data-isolated", Boolean(w.isolated));
    if (w.state) el.dataset.state = w.state; else delete el.dataset.state;
    el.hidden = false; // a pill hidden by an earlier pass measures 0 x 0
    const bw = el.offsetWidth;
    const bh = el.offsetHeight;
    const [ax, ay] = anchors[index];
    // candidates on rings around the anchor (a leader line joins far ones); the clearest of drawn geometry wins
    let spot = null;
    let best = Infinity;
    const dists = Array.from({ length: 18 }, (_, i) => 6 + i * 12);
    for (const d of dists) {
      for (let k = 0; k < 24; k++) {
        const ang = -Math.PI / 2 + (k * Math.PI) / 12;
        const ux = Math.cos(ang), uy = Math.sin(ang);
        const r = { x: ax + ux * (d + bw / 2) - bw / 2, y: ay + uy * (d + bh / 2) - bh / 2, w: bw, h: bh };
        const inside = r.x >= 2 && r.y >= 2 && r.x + r.w <= host.width - 2 && r.y + r.h <= host.height - 2;
        if (!inside) continue;
        const free = placed.every((q) => r.x + r.w + 4 <= q.x || q.x + q.w + 4 <= r.x || r.y + r.h + 3 <= q.y || q.y + q.h + 3 <= r.y);
        if (!free) continue;
        const coversAnchor = anchors.some(([px, py], j) => j !== index && px > r.x - 3 && px < r.x + r.w + 3 && py > r.y - 3 && py < r.y + r.h + 3);
        if (coversAnchor) continue;
        const cost = occ.cover(r) * 900 + d + (w.kind === "unit" && uy > 0.3 ? 14 : 0);
        if (cost < best) { best = cost; spot = r; }
      }
      if (spot && occ.cover(spot) === 0) break;
    }
    // a unit name that finds no clear ring position goes to a free corner of the figure, with a leader
    if (w.kind === "unit" && (!spot || occ.cover(spot) > 0.05)) {
      for (const r of [{ x: 6, y: 6, w: bw, h: bh }, { x: host.width - bw - 6, y: 6, w: bw, h: bh }, { x: 6, y: host.height - bh - 6, w: bw, h: bh }, { x: host.width - bw - 6, y: host.height - bh - 6, w: bw, h: bh }]) {
        const free = placed.every((q) => r.x + r.w + 4 <= q.x || q.x + q.w + 4 <= r.x || r.y + r.h + 3 <= q.y || q.y + q.h + 3 <= r.y);
        if (free && occ.cover(r) < (spot ? occ.cover(spot) : 1)) { spot = r; break; }
      }
    }
    // a tag label that can only sit on top of the drawing is left off (its value stays on the card and the ring)
    if (spot && w.kind === "tag" && w.state !== "alarm" && occ.cover(spot) > 0.1) spot = null;
    if (!spot) { el.hidden = true; el.dataset.placed = "no"; return; }
    el.hidden = false;
    el.dataset.placed = "yes";
    el.style.transform = `translate(${spot.x.toFixed(1)}px, ${spot.y.toFixed(1)}px)`;
    placed.push(spot);
    const ex = Math.max(spot.x, Math.min(spot.x + spot.w, ax));
    const ey = Math.max(spot.y, Math.min(spot.y + spot.h, ay));
    if (w.kind === "unit" || Math.hypot(ex - ax, ey - ay) > 5) leaders += `<g${w.kind === "unit" ? ` data-leader-unit="${w.unit}"` : ""}><line x1="${ax.toFixed(1)}" y1="${ay.toFixed(1)}" x2="${ex.toFixed(1)}" y2="${ey.toFixed(1)}"/>${w.kind === "unit" ? `<circle cx="${ax.toFixed(1)}" cy="${ay.toFixed(1)}" r="2.5"/>` : ""}</g>`;
  });
  leaderSvg.innerHTML = leaders;
}

// ------------------------------------------------------------------ LOTO pins drawn in the figure
const lotoLayer = plant.querySelector(".tour-loto-layer");
function paintLoto() {
  energyCache = null;
  if (S.mode !== "loto") { lotoLayer.innerHTML = ""; return; }
  lotoLayer.innerHTML = L.loto.map((p) => {
    const [x, y] = p.at;
    const iso = S.isolated.has(p.id);
    return `<g class="tour-loto-pin" data-pin="${esc(p.id)}"${iso ? " data-isolated" : ""}><circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="7"/><path d="M${(x - 2.6).toFixed(1)} ${(y - 0.5).toFixed(1)}v-1.6a2.6 2.6 0 0 1 5.2 0v1.6M${(x - 3.4).toFixed(1)} ${(y - 0.4).toFixed(1)}h6.8v4.4h-6.8z"/></g>`;
  }).join("");
  const e = energy();
  for (const b of document.querySelectorAll("[data-loto]")) b.setAttribute("aria-pressed", String(S.isolated.has(b.dataset.loto)));
  const yes = e.sources.filter((s) => s.isolated);
  const no = e.sources.filter((s) => !s.isolated);
  energyBox.innerHTML = `<p><strong>Isolated (${yes.length}):</strong></p><ul>${yes.map((s) => `<li>${s.n}. ${esc(s.text)}: ${esc(s.energy)}; carries ${esc(s.carries)}</li>`).join("") || "<li>none</li>"}</ul>`
    + `<p><strong>Not isolated (${no.length}):</strong></p><ul>${no.map((s) => `<li class="on">${s.n}. ${esc(s.text)}: ${esc(s.energy)}; carries ${esc(s.carries)}</li>`).join("") || "<li>none</li>"}</ul>`
    + `<p data-stopped><strong>Lines with flow stopped (${e.stopped.length} of ${D.streams.length} streams):</strong> ${esc(e.stopped.join(", ") || "none")}</p>`
    + `<p data-flowing><strong>Still flowing:</strong> ${esc(e.flowing.join(", ") || "none")}</p>`
    + `<p><strong>Not modelled:</strong> ${esc(e.not_modelled)}. A real isolation is verified at the point (try-start, zero pressure and temperature) under the site's procedure.</p>`;
}
function toggleLoto(id) {
  if (S.isolated.has(id)) S.isolated.delete(id); else S.isolated.add(id);
  paintAll();
}

// ------------------------------------------------------------------ purpose card
function citationText(c) {
  if (c.source === "teprob") return `teprob.f line ${c.line}: <code>${esc(c.code)}</code>: ${esc(c.shows)}`;
  return `revised TE code: ${esc(c.text)}`;
}
function paintCard() {
  const st = states();
  if (!S.focus) {
    card.innerHTML = `<h2>Overview</h2><div class="tour-card-a"><p>${esc(D.title)}: six units in flow order, from the feed header through the reactor, condenser and separator to the recycle compressor and the product stripper. Select a unit, use the buttons above, or focus the figure and press the arrow keys.</p>`
      + `<p class="tour-cite">Flow order: ${esc(D.tour_order.join(" → "))} (${esc(D.tour_order_basis)}).</p>`
      + `</div><div class="tour-card-b"><h3>Placeholder versus data</h3><p>From the data: units, streams and their direction, tags, which unit or line each tag belongs to, purpose sentences with their citations, normal bands, published alarm setpoints and every replay value. Placeholder: shapes, sizes, heights, nozzle positions, pipe routes, marker positions along a line and the parts drawn inside each cut-away.</p></div>`;
    return;
  }
  const u = unitOf[S.focus];
  const tags = D.tags.filter((t) => t.unit === u.id);
  const rows = tags.map((t) => {
    const s = st[t.tag];
    const v = s.value !== null && s.value !== undefined ? `${fmt(s.value)} ${t.uom}` : "not connected";
    const band = t.band ? `${fmt(t.band.lo)} to ${fmt(t.band.hi)}` : "none";
    const lim = [t.alarms.operating_high !== null ? `high alarm ${fmt(t.alarms.operating_high)}` : "", t.alarms.shutdown_high !== null ? `shutdown ${fmt(t.alarms.shutdown_high)}` : ""].filter(Boolean).join(", ") || "none published";
    return `<tr data-tag-row="${esc(t.tag)}"><td>${esc(t.tag)}${u.key_tags.includes(t.tag) ? " ★" : ""}<br><span class="tour-paths">${esc(t.label)}</span></td><td data-state="${s.state}">${esc(v)}</td><td>${esc(band)}<br><span class="tour-paths">${esc(lim)}</span></td></tr>`
      + `<tr><td colspan="3" class="tour-paths">Ignition ${esc(t.ignition_path || "not in the export")} · PI AF ${esc(t.pi_path || "not in the export")}${t.disputed ? " · owner disputed in the layout" : ""}</td></tr>`;
  }).join("");
  const h = u.hazard;
  card.innerHTML = `<h2>${esc(u.id)} ${esc(u.name)}</h2><div class="tour-card-a">`
    + `<h3>Why it exists</h3><p data-purpose>${esc(u.purpose)}</p>`
    + `<p class="tour-cite">Source: ${u.citations.map(citationText).join("; ")}.</p>`
    + `<p><strong>Essential function:</strong> ${esc(u.function)} <span class="tour-cite">(the tour's short paraphrase of the same code)</span></p>`
    + (u.flow_text ? `<p class="tour-cite">${esc(u.flow_text)}</p>` : "")
    + (u.inferred.length ? `<p class="tour-cite">Inferred, not in the model's stream list: ${esc(u.inferred.join("; "))}.</p>` : "")
    + `</div><div class="tour-card-b"><h3>Instruments (★ watch first)</h3><table><thead><tr><th>Tag</th><th>Now</th><th>Normal band · limits</th></tr></thead><tbody>${rows}</tbody></table>`
    + `<p class="tour-cite">Normal bands are display aids from the recorded normal run, not limits. Only published setpoints make an alarm.</p>`
    + (h ? `<h3>Why this matters (public record)</h3><p>${esc(h.caption)}</p><p class="tour-cite">${esc(h.agency)}${h.year ? `, ${h.year}` : ""}: <a href="${esc(h.url)}" rel="noopener">${esc(h.title)}</a>. Prototype keyword match: a mechanism analogy, not a hazard analysis.</p>` : "") + `</div>`;
}

// ------------------------------------------------------------------ controls
function focusUnit(uid) {
  S.focus = uid || null;
  paintAll();
}
function paintAll() {
  energyCache = null;
  figure.dataset.mode = S.mode;
  for (const el of document.querySelectorAll("[data-flow-only]")) el.hidden = S.mode !== "flow";
  for (const el of document.querySelectorAll("[data-loto-only]")) el.hidden = S.mode !== "loto";
  for (const b of document.querySelectorAll("[data-mode-button]")) b.setAttribute("aria-pressed", String(b.dataset.modeButton === S.mode));
  paintLoto();
  paintStates();
  paintFocus();
  paintCard();
  applyView();
  layoutLabels();
  kick();
}
for (const b of document.querySelectorAll("[data-unit-button]")) b.addEventListener("click", () => focusUnit(b.dataset.unitButton || null));
for (const b of document.querySelectorAll("[data-mode-button]")) b.addEventListener("click", () => { S.mode = b.dataset.modeButton; paintAll(); });
for (const b of document.querySelectorAll("[data-loto]")) b.addEventListener("click", () => toggleLoto(b.dataset.loto));
document.querySelector("[data-loto-all]").addEventListener("click", () => { for (const p of D.loto.points) S.isolated.add(p.id); paintAll(); });
document.querySelector("[data-loto-none]").addEventListener("click", () => { S.isolated.clear(); paintAll(); });
for (const r of document.querySelectorAll('input[name="run"]')) r.addEventListener("change", () => { if (r.checked) { S.run = r.value; paintAll(); } });
scrub.addEventListener("input", () => { S.sample = Number(scrub.value); paintAll(); });
playButton.addEventListener("click", () => { S.playing = !S.playing; playButton.textContent = S.playing ? "Pause" : "Play"; playButton.setAttribute("aria-label", S.playing ? "Pause the replay" : "Play the replay"); kick(); });
document.querySelector("[data-jump-alarm]").addEventListener("click", () => {
  const first = firstAlarm(D, "fault6");
  if (!first) return;
  S.run = "fault6";
  document.querySelector('input[name="run"][value="fault6"]').checked = true;
  S.sample = first.sample;
  scrub.value = String(first.sample);
  S.focus = tagOf[first.tags[0]].unit;
  paintAll();
});
plant.addEventListener("click", (event) => {
  const it = event.target.closest(".it");
  if (!it) return;
  const uid = it.dataset.unit;
  if (unitOf[uid]) focusUnit(uid);
});
stage.addEventListener("keydown", (event) => {
  const order = D.tour_order;
  const here = S.focus ? order.indexOf(S.focus) : -1;
  let next;
  if (event.key === "ArrowRight" || event.key === "ArrowDown") next = order[Math.min(order.length - 1, here + 1)];
  else if (event.key === "ArrowLeft" || event.key === "ArrowUp") next = here <= 0 ? null : order[here - 1];
  else if (event.key === "Home") next = order[0];
  else if (event.key === "End") next = order[order.length - 1];
  else if (event.key === "Escape") next = null;
  else if (event.key === " ") { event.preventDefault(); playButton.click(); return; }
  else return;
  event.preventDefault();
  focusUnit(next);
});

// ------------------------------------------------------------------ frame loop (calm, stops offscreen, still under reduced motion)
let frame = 0;
let last = 0;
let visible = true;
let replayClock = 0;
function tick(now) {
  const dt = last ? Math.min((now - last) / 1000, 1 / 20) : 1 / 60;
  last = now;
  let moving = false;
  if (!still.matches) {
    for (const line of L.lines) phase[line.id] += BASE_SPEED * (lineOn(line) ? lineShare(line) : 0) * dt;
    paintFlow();
    moving = true;
  }
  if (S.target) {
    const f = still.matches ? 1 : 1 - Math.exp(-dt / 0.22);
    let settled = true;
    S.view = S.view.map((v, i) => {
      const nv = v + (S.target[i] - v) * f;
      if (Math.abs(S.target[i] - nv) > 0.05) settled = false;
      return settled && Math.abs(S.target[i] - nv) < 0.05 ? S.target[i] : nv;
    });
    applyView();
    layoutLabels();
    if (settled) { S.view = S.target.slice(); applyView(); layoutLabels(); S.target = null; }
    else moving = true;
  }
  if (S.playing && S.mode === "flow") {
    replayClock += dt;
    if (replayClock > 0.12) {
      replayClock = 0;
      S.sample = (S.sample + 1) % D.replay.runs[S.run].samples;
      scrub.value = String(S.sample);
      paintStates();
      layoutLabels();
      paintCard();
    }
    moving = true;
  }
  frame = visible && moving ? requestAnimationFrame(tick) : 0;
}
function kick() {
  if (!frame && visible) { last = 0; frame = requestAnimationFrame(tick); }
}
new IntersectionObserver((entries) => { visible = entries[entries.length - 1].isIntersecting; if (visible) kick(); }, { rootMargin: "80px 0px" }).observe(stage);
addEventListener("resize", () => layoutLabels());
still.addEventListener?.("change", () => paintAll());

// Test hook for drafts/interactive-tour/verify.mjs (read-only state plus the same setters the controls use).
window.__tour = {
  state: () => ({ mode: S.mode, focus: S.focus, run: S.run, sample: S.sample, isolated: [...S.isolated], phase: { ...phase } }),
  energy: () => energized(D, [...S.isolated]),
  firstAlarm: (run) => firstAlarm(D, run),
  // share of each visible label's box that lies over drawn, undimmed geometry (for verify.mjs)
  labelCover: () => { const host = labelsBox.getBoundingClientRect(); const occ = occupancy(host); return [...pills.values()].filter((p) => !p.hidden).map((p) => { const r = p.getBoundingClientRect(); return { id: p.dataset.label, cover: +occ.cover({ x: r.left - host.left, y: r.top - host.top, w: r.width, h: r.height }).toFixed(3) }; }); },
};
paintAll();
document.fonts?.ready.then(() => layoutLabels());
