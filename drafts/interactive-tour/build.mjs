// Interactive isometric process tour of the Tennessee Eastman (TE) seed model: a proof of concept.
//
//   python scripts/export_interactive_tour.py          # out/interactive_tour/tour_data.json (needs the replays)
//   node drafts/interactive-tour/build.mjs [--light] [--audit]
//
// Writes out/interactive_tour/te-tour.html (or te-tour-light.html) and out/interactive_tour/scene.json (what was
// drawn, for drafts/interactive-tour/verify.mjs). With --audit it runs the anatomy kit's geometry audit
// (kit/audit.mjs: clearances, mounts, support, depth order...) and writes drafts/interactive-tour/audit/geometry.json.
//
// Topology (which units, streams, utilities and tags exist, and what connects to what) comes only from the data
// file. Positions on the floor are the 2D seed layout's; every size, height, nozzle, pipe route and internal part is a
// placeholder chosen to make each machine recognisable, and the page says so. Drawing technique adapted from the
// MIT-licensed "anatomy" skill (kit/ is vendored from it unchanged; see kit/LICENSE and NOTICE.md).
// Written with AI assistance; not reviewed by an operator.
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import * as k from "./kit/iso-kit.mjs";
import * as G from "./kit/lathe.mjs";
import { tubePieces, tubeSvg } from "./kit/tube.mjs";
import * as A from "./kit/audit.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..", "..");
const OUT = join(ROOT, "out", "interactive_tour");
const THEME = process.argv.includes("--light") ? "light" : "dark";
const AUDIT = process.argv.includes("--audit");
const DATA = JSON.parse(readFileSync(join(OUT, "tour_data.json"), "utf8"));
const DEG = Math.PI / 180;

// ------------------------------------------------------------------ world: 1 unit = 0.1 m (placeholder sizes)
const PLAN_SCALE = 0.3; // world units per 2D seed-layout pixel (the Blender tour uses 0.03 m per pixel too)
const AZIMUTH = 50;
const ELEVATION = 30;
const W = 1200;
let H = 700;
const RP = 1.3; // process pipe radius
const RU = 1.0; // utility pipe radius
const FLANGE = 1.75; // flange radius / pipe radius

const unitById = Object.fromEntries(DATA.units.map((u) => [u.id, u]));
const plan = (id) => [unitById[id].plan[0] * PLAN_SCALE, unitById[id].plan[1] * PLAN_SCALE];

// Placeholder machine per symbol kind. Heights in world units. The kind comes from the display layout (data).
const SHAPES = {
  reactor: { type: "vessel", R: 13, zb: 12, zt: 58, window: [16, 54], agitator: true },
  separator: { type: "vessel", R: 10, zb: 10, zt: 40, window: [13, 37], demister: true },
  stripper: { type: "vessel", R: 7, zb: 12, zt: 122, window: [20, 112], trays: true },
  feed: { type: "header", r: 3.4, L: 50, zc: 16 },
  condenser: { type: "exchanger", r: 5, L: 40, zc: 52 },
  compressor: { type: "compressor", zc: 15 },
};
const GROUND = { x: -48, y: 14, w: 425, d: 136, r: 3 };
const GAS = new Set(["gas_feed", "recycle", "purge", "reactor_effluent"]);

const P = (() => {
  // fitted to what is drawn: each machine's envelope (from SHAPES) and the ground slab
  const pts = [];
  const box = (x0, x1, y0, y1, z1) => { for (const x of [x0, x1]) for (const y of [y0, y1]) for (const z of [0, z1]) pts.push([x, y, z]); };
  for (const u of DATA.units) {
    const [x, y] = plan(u.id);
    const sp = SHAPES[u.kind];
    if (sp.type === "vessel") box(x - sp.R - 3, x + sp.R + 3, y - sp.R - 3, y + sp.R + 3, sp.zt + sp.R / 2 + (sp.agitator ? 22 : 6));
    else if (sp.type === "header") box(x - 6, x + 6, y - sp.L / 2 - 4, y + sp.L / 2 + 4, sp.zc + 14);
    else if (sp.type === "exchanger") box(x - sp.L / 2 - 12, x + sp.L / 2 + 4, y - 7, y + 7, sp.zc + 14);
    else box(x - 12, x + 12, y - 26, y + 14, sp.zc + 22);
  }
  box(GROUND.x, GROUND.x + GROUND.w, GROUND.y, GROUND.y + GROUND.d, 0);
  const fit = k.fitProjection(pts, W, H, { pad: 14, azimuth: AZIMUTH, elevation: ELEVATION });
  // crop the frame to the content so the figure fills its card at every width
  const ys = pts.map((p) => k.iso(p, fit)[1]);
  const top = Math.min(...ys) - 14;
  const bottom = Math.max(...ys) + 14;
  H = Math.ceil(bottom - top);
  return { ...fit, origin: [fit.origin[0], fit.origin[1] - top] };
})();
const V = G.viewOf(P);
const KS = G.scaleOf(P);
const at = (p) => k.iso(p, P);
const segmentDistance2 = (q, a, b) => {
  const t = Math.max(0, Math.min(1, ((q[0] - a[0]) * (b[0] - a[0]) + (q[1] - a[1]) * (b[1] - a[1])) / ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2 || 1)));
  return Math.hypot(q[0] - a[0] - t * (b[0] - a[0]), q[1] - a[1] - t * (b[1] - a[1]));
};
const S = (paths, style) => k.solidSvg(paths, style);
const Ln = (d, style) => k.lineSvg(d, style);
const Dots = (points, style) => k.dotsSvg(points, style);
const poly = (pts, closed = false) => k.pathOf(pts.map(at), closed);
const VIEW_ANGLE = Math.atan2(k.towardViewer(P)[1], k.towardViewer(P)[0]);

const R = A.recorder(P);
const { nameFor } = R;
const record = R.solid;
function put(unit, ref, svg, { bias = 0, shapes = [], name, route, chunk, layer } = {}) {
  R.put({ piece: unit || "plant", at: ref, bias, svg, shapes, name: name ?? nameFor(`${unit}.item`), route, chunk, unit, layer });
}

// Volumes for the router: simple shapes that cover each machine, so a candidate route can be rejected before drawing.
const VOLUMES = [];
const OBST = []; // placed nozzles, manways, valves and markers: {c, r, tag?}
const usedAngles = {}; // nozzle and fitting angles taken on each vessel shell
const vcyl = (owner, x, y, r, z0, z1) => VOLUMES.push({ owner, kind: "vcyl", x, y, r, z0, z1 });
const hcyl = (owner, x0, x1, y, z, r) => VOLUMES.push({ owner, kind: "hcyl", x0, x1, y, z, r });
const vbox = (owner, min, max) => VOLUMES.push({ owner, kind: "box", min, max });
function volumeDistance(v, p) {
  if (v.kind === "vcyl") {
    const dr = Math.hypot(p[0] - v.x, p[1] - v.y) - v.r;
    const dz = Math.max(v.z0 - p[2], p[2] - v.z1, 0);
    return dr > 0 ? Math.hypot(dr, dz) : dz > 0 ? dz : Math.max(dr, Math.max(v.z0 - p[2], p[2] - v.z1));
  }
  if (v.kind === "hcyl") {
    const dr = Math.hypot(p[1] - v.y, p[2] - v.z) - v.r;
    const dx = Math.max(v.x0 - p[0], p[0] - v.x1, 0);
    return dr > 0 ? Math.hypot(dr, dx) : dx > 0 ? dx : dr;
  }
  const d = [0, 1, 2].map((i) => Math.max(v.min[i] - p[i], p[i] - v.max[i]));
  const outside = Math.hypot(...d.map((x) => Math.max(0, x)));
  return outside > 0 ? outside : Math.max(...d);
}

// ------------------------------------------------------------------ kit helpers (patterns from the anatomy examples)
function turned(unit, F, profile, style = {}, { extra = "", inner = "", bias = 0, name, owner, smooth, steps, rims } = {}) {
  const opts = { ...(smooth ? { smooth } : {}), ...(steps ? { steps } : {}), ...(rims ? { rims } : {}) };
  const paths = G.solidOf(profile, F, P, opts);
  const mid = (profile[0][0] + profile[profile.length - 1][0]) / 2;
  const id = nameFor(name ?? `${unit}.turned`);
  const shape = record(A.solid(F, profile, { name: id, owner: owner ?? unit, ...(smooth && smooth.radius ? { radius: smooth.radius } : {}) }));
  put(unit, G.add3(F.o, G.mul3(F.a, mid)), S(paths, { tone: "hi", ...style, inner }) + extra, { bias, name: id, shapes: [shape] });
  return shape;
}
function discAt(unit, F, s0, s1, r, style = {}, { extra = "", bias = 0, name, owner, inner = "" } = {}) {
  const id = nameFor(name ?? `${unit}.disc`);
  const shape = record(A.disc(F, s0, s1, r, { name: id, owner: owner ?? unit }));
  put(unit, G.add3(F.o, G.mul3(F.a, (s0 + s1) / 2)), S(G.disc(s0, s1, r, F, P), { tone: "hi", ...style, inner }) + extra, { bias, name: id, shapes: [shape] });
  return shape;
}
function boxAt(unit, min, max, style = {}, { extra = "", bias = 0, name, owner, bevel = 0.4, ground = false } = {}) {
  const plan = { x: min[0], y: min[1], w: max[0] - min[0], d: max[1] - min[1], r: 0.6 };
  const id = nameFor(name ?? `${unit}.box`);
  const shape = record(A.box(min, max, { name: id, owner: owner ?? unit, ...(ground ? { ground: true } : {}) }));
  put(unit, [(min[0] + max[0]) / 2, (min[1] + max[1]) / 2, (min[2] + max[2]) / 2], S(k.slabOf(plan, min[2], max[2] - min[2], P, 2, bevel), { tone: "mid", ...style }) + extra, { bias, name: id, shapes: [shape] });
  vbox(owner ?? unit, min, max);
  return shape;
}
function ballAt(unit, centre, r, { tone = "hi", bias = 0, name, owner, cls = "", extra = "" } = {}) {
  const id = nameFor(name ?? `${unit}.ball`);
  const shape = record(A.ball(centre, r, { name: id, owner: owner ?? unit }));
  const body = S(G.sphereOf(centre, r, P, { steps: 32 }), { tone });
  put(unit, centre, cls ? `<g class="${cls}">${body}${extra}</g>` : body + extra, { bias, name: id, shapes: [shape] });
  return shape;
}
// A seated pad on a curved host (anatomy raptor padOn): the nozzle neck meets the shell along the true curve.
function padOn(unit, hosts, point, outward, a, h, { name, tone = "hi", bias = 0.1, owner } = {}) {
  const list = [hosts].flat();
  const inside = (p) => list.some((shape) => A.sdf(shape, p) < 0);
  const axis = G.unit3(outward);
  const F = G.frameAlong(point, axis);
  const start = (angle) => {
    let lo = -2.5 * a;
    let hi = h;
    if (!inside(G.pointOf(F, lo, a, angle))) return 0;
    for (let step = 0; step < 40; step++) {
      const mid = (lo + hi) / 2;
      if (inside(G.pointOf(F, mid, a, angle))) lo = mid;
      else hi = mid;
    }
    return hi;
  };
  const low = Math.min(...Array.from({ length: 48 }, (_, index) => start((index / 48) * Math.PI * 2)));
  const id = nameFor(name ?? `${unit}.pad`);
  put(unit, G.add3(point, G.mul3(axis, h / 2)), S(G.saddleOf(F, a, start, h, P), { tone }), { bias, name: id, shapes: [record(A.disc(F, low - 0.05, h, a, { name: id, owner: owner ?? unit, seated: true, cut: list }))] });
  return G.add3(point, G.mul3(axis, h));
}
// A nozzle: seated neck plus a flange; returns the flange face, where a pipe starts, and its axis.
function nozzle(unit, hosts, point, outward, r, { name, length = 2.6 } = {}) {
  const axis = G.unit3(outward);
  const neckEnd = padOn(unit, hosts, point, axis, r + 0.35, length, { name: `${name}.neck` });
  const F = G.frameAlong(neckEnd, axis);
  const thick = 0.8;
  const faces = Math.abs(G.dot3(F.a, V)) > 0.15 ? Dots(G.dotsOf(F, G.dot3(F.a, V) > 0 ? thick : 0, r * FLANGE * 0.78, 6, P, { all: true }), { size: 0.4, tone: "mid" }) : "";
  discAt(unit, F, 0, thick, r * FLANGE, { tone: "hi" }, { name: `${name}.flange`, extra: faces, bias: 0.15 });
  OBST.push({ c: neckEnd, r: r * FLANGE + 0.8 });
  return { p: G.add3(neckEnd, G.mul3(axis, thick)), axis, unit, name };
}

// ------------------------------------------------------------------ ground
const back = [];
back.push(`<path class="iso-halo" d="${k.haloOf(GROUND, -3, 3, P)}"/>`);
back.push(S(k.slabOf(GROUND, -3, 3, P, 6, 1.2), { tone: "lo" }));
record(A.box([GROUND.x, GROUND.y, -3], [GROUND.x + GROUND.w, GROUND.y + GROUND.d, 0], { name: "stand.ground", ground: true }));
{
  const lines = [];
  for (let x = GROUND.x + 15; x < GROUND.x + GROUND.w - 4; x += 20) lines.push(k.lineOnTop([x, GROUND.y + 0.5], [x, GROUND.y + GROUND.d - 0.5], 0, P));
  for (let y = GROUND.y + 10; y < GROUND.y + GROUND.d - 4; y += 20) lines.push(k.lineOnTop([GROUND.x + 0.5, y], [GROUND.x + GROUND.w - 0.5, y], 0, P));
  back.push(Ln(lines.join(""), { tone: "faint" }));
}

// ------------------------------------------------------------------ equipment builders
const UNIT_GEOM = {}; // per unit: ports, markers, label anchor, focus box, window clip
const WINDOW_LEVELS = {};
const clips = [];

function windowPath(F, R, z0, z1, phiC, half) {
  const pts = [];
  const n = 18;
  for (let i = 0; i <= n; i++) pts.push(G.pointOf(F, z0, R, phiC - half + (2 * half * i) / n));
  for (let i = 0; i <= n; i++) pts.push(G.pointOf(F, z1, R, phiC + half - (2 * half * i) / n));
  return pts;
}

function vessel(u) {
  const spec = SHAPES[u.kind];
  const [x, y] = plan(u.id);
  const { R: Rv, zb, zt } = spec;
  const h = Rv / 2;
  const F = G.frameOf([x, y, 0], [0, 0, 1], [1, 0, 0], [0, 1, 0]);
  const g = (UNIT_GEOM[u.id] = { ports: {}, markers: [], hosts: {}, F, R: Rv, zb, zt, x, y, kind: u.kind });
  // plinth, skirt with an access opening, shell, top head
  discAt(u.id, F, 0, 2, Rv + 3, { tone: "mid" }, { name: `${u.id}.plinth`, extra: Dots(G.dotsOf(F, 2, Rv + 1.6, 12, P, { fade: [0.04, 0.42] }), { size: 0.45, tone: "lo" }) });
  const skirt = discAt(u.id, F, 2, zb, Rv, { tone: "mid" }, { name: `${u.id}.skirt`, inner: Ln(G.arcOf(F, zb - 0.6, Rv, P), { tone: "faint" }) });
  vcyl(u.id, x, y, Rv + 3, 0, zb);
  const shell = record(A.disc(F, zb, zt, Rv, { name: `${u.id}.shell`, owner: u.id }));
  g.hosts.shell = shell;
  // cutaway window, facing the viewer
  const half = 50 * DEG;
  const [w0, w1] = spec.window;
  const win = windowPath(F, Rv, w0, w1, VIEW_ANGLE, half);
  const clipId = `win-${u.id}`;
  clips.push(`<clipPath id="${clipId}"><path d="${poly(win, true)}"/></clipPath>`);
  WINDOW_LEVELS[u.id] = { x, y, R: Rv - 0.7, z0: w0, z1: spec.trays ? zb + 13 : w1, clip: clipId, span: spec.trays ? "sump below the bottom tray" : "the cut-away window" };
  const inside = [];
  inside.push(`<path class="tour-cavity" d="${poly(win, true)}"/>`);
  for (let z = w0 + 4; z < w1; z += Math.max(6, (w1 - w0) / 6)) inside.push(Ln(G.arcOf(F, z, Rv - 0.7, P, { inward: true }), { tone: "faint" }));
  inside.push(internals(u, F, spec, g));
  inside.push(`<g data-liquid="${u.id}"></g>`);
  const cut = [];
  for (const side of [-1, 1]) {
    const phi = VIEW_ANGLE + side * half;
    cut.push(poly([G.pointOf(F, w0, Rv - 0.7, phi), G.pointOf(F, w1, Rv - 0.7, phi)]));
  }
  const windowSvg = `<g clip-path="url(#${clipId})">${inside.join("")}</g>` + Ln(cut.join(""), { tone: "mid" }) + `<path class="iso-line tour-cut" data-tone="hi" d="${poly(win, true)}"/>`;
  const seams = Ln([zb + 0.3, zt - 0.3].map((z) => G.arcOf(F, z, Rv, P)).join(""), { tone: "faint" });
  put(u.id, [x, y, (zb + zt) / 2], S(G.disc(zb, zt, Rv, F, P), { tone: "hi", inner: seams }) + windowSvg, { name: `${u.id}.shell`, shapes: [shell] });
  // top head: 2:1 ellipsoidal, analytic profile so the shading is smooth
  const rTop = (s) => Rv * Math.sqrt(Math.max(0, 1 - ((s - zt) / h) ** 2));
  const sTop = (s) => {
    const t = Math.min(0.999, (s - zt) / h);
    return (-Rv * t) / (h * Math.sqrt(1 - t * t));
  };
  const head = turned(u.id, F, [[zt, Rv], [zt + h * 0.985, rTop(zt + h * 0.985)]], { tone: "hi" }, { name: `${u.id}.head`, smooth: { slope: sTop, radius: rTop } });
  g.hosts.head = head;
  vcyl(u.id, x, y, Rv, zb, zt + h);
  g.top = zt + h;
  // Callout leaders terminate on the shell, not in the empty space above a neighbouring machine.
  g.label = [x, y, zt - 4];
  g.focus = [[x - Rv - 8, y - Rv - 8, 0], [x + Rv + 8, y + Rv + 8, zt + h + (spec.agitator ? 22 : 4)]];
  if (spec.agitator) agitator(u, F, g);
  vesselDetails(u, F, g, spec);
}

function internals(u, F, spec, g) {
  const out = [];
  const { R: Rv, zb, zt } = spec;
  const [x, y] = [g.x, g.y];
  if (spec.agitator) {
    // cooling coil (helix), agitator shaft and two impellers
    const helix = [];
    for (let t = 0; t <= 1; t += 1 / 260) {
      const a = t * Math.PI * 2 * 8;
      helix.push([x + Rv * 0.8 * Math.cos(a), y + Rv * 0.8 * Math.sin(a), zb + 5 + t * (zt - zb - 14)]);
    }
    const pieces = tubePieces(helix, 0.55, P, { maxLength: 6, caps: false });
    const shaftDepth = G.dot3([x, y, 0], V);
    const backCoil = pieces.filter((p) => G.dot3(p.mid, V) < shaftDepth).map((p) => tubeSvg(p, { tone: "mid" }));
    const frontCoil = pieces.filter((p) => G.dot3(p.mid, V) >= shaftDepth).map((p) => tubeSvg(p, { tone: "mid" }));
    out.push(`<g class="tour-coil">${backCoil.join("")}</g>`);
    out.push(S(G.disc(zb + 4, zt + Rv / 2, 0.7, F, P), { tone: "hi", crease: "none" }));
    for (const z of [zb + 8, zb + 24]) {
      out.push(S(G.disc(z - 0.4, z + 0.4, Rv * 0.4, F, P), { tone: "hi" }));
      const blades = [];
      for (let i = 0; i < 6; i++) {
        const a = VIEW_ANGLE + (i * Math.PI) / 3 + 0.3;
        blades.push(poly([G.pointOf(F, z - 1.6, Rv * 0.26, a), G.pointOf(F, z + 1.6, Rv * 0.26, a), G.pointOf(F, z + 1.6, Rv * 0.42, a), G.pointOf(F, z - 1.6, Rv * 0.42, a)], true));
      }
      out.push(`<path class="tour-blade" d="${blades.join("")}"/>`);
      out.push(S(G.disc(z - 1.2, z + 1.2, 1.5, F, P), { tone: "hi" }));
    }
    out.push(`<g class="tour-coil">${frontCoil.join("")}</g>`);
  }
  if (spec.demister) {
    const zd = zt - 5;
    out.push(S(G.disc(zd - 1, zd + 1, Rv - 0.8, F, P), { tone: "mid", inner: Ln(Array.from({ length: 9 }, (_, i) => poly([G.pointOf(F, zd + 1, Rv - 0.9, VIEW_ANGLE - 1.2 + i * 0.3), G.pointOf(F, zd - 1, Rv - 0.9, VIEW_ANGLE - 1.2 + i * 0.3)])).join(""), { tone: "faint" }) }));
    // inlet deflector plate under the inlet
    out.push(S(G.disc(zt - 9, zt - 8.4, Rv * 0.35, G.frameAlong([x, y, 0], [0, 0, 1]), P), { tone: "mid" }));
  }
  if (spec.trays) {
    for (let z = zb + 14, i = 0; z < zt - 6; z += 7.5, i++) {
      out.push(S(G.disc(z - 0.35, z + 0.35, Rv - 0.75, F, P), { tone: "mid", crease: "none" }));
      // downcomer: a chord plate hanging from alternate sides of each tray
      const side = i % 2 ? 1 : -1;
      const a0 = VIEW_ANGLE + side * 1.1;
      out.push(`<path class="tour-blade" d="${poly([G.pointOf(F, z, Rv - 0.8, a0 - 0.5), G.pointOf(F, z, Rv - 0.8, a0 + 0.5), G.pointOf(F, z - 4.5, Rv - 0.8, a0 + 0.5), G.pointOf(F, z - 4.5, Rv - 0.8, a0 - 0.5)], true)}"/>`);
    }
    // steam sparger ring near the base
    const ring = [];
    for (let t = 0; t <= 1.0001; t += 1 / 60) ring.push([g.x + (Rv - 2.2) * Math.cos(t * Math.PI * 2), g.y + (Rv - 2.2) * Math.sin(t * Math.PI * 2), zb + 6]);
    out.push(tubePieces(ring, 0.45, P, { maxLength: 80, closed: true, caps: false }).map((p) => tubeSvg(p, { tone: "mid" })).join(""));
  }
  return out.join("");
}

// Parts a real vessel has: a manway with its blind flange; on the tall stripper two platforms with handrails and a
// ladder; on the separator a level glass on a bridle, whose liquid follows the level tag. All placeholder.
const GLASS = {};
function vesselDetails(u, F, g, spec) {
  const Rv = g.R;
  const manZ = g.zb + Math.min(9, (g.zt - g.zb) * 0.22);
  const manA = VIEW_ANGLE - 74 * DEG;
  const dir = [Math.cos(manA), Math.sin(manA), 0];
  const neck = padOn(u.id, g.hosts.shell, G.pointOf(F, manZ, Rv, manA), dir, 2.6, 2.2, { name: `${u.id}.manway.neck` });
  const MF = G.frameAlong(neck, dir);
  const facing = G.dot3(MF.a, V) > 0.12;
  discAt(u.id, MF, 0, 0.8, 4, { tone: "hi" }, { name: `${u.id}.manway.flange` });
  discAt(u.id, MF, 0.8, 1.4, 4, { tone: "hi" }, { name: `${u.id}.manway.blind`, extra: facing ? Dots(G.dotsOf(MF, 1.4, 3.3, 10, P, { all: true }), { size: 0.4, tone: "mid" }) + Ln(G.circleOf(MF, 1.4, 1.2, P, 20), { tone: "faint" }) : "" });
  (usedAngles[u.id] ??= []).push({ a: manA, z: manZ }, { a: manA, z: manZ + 4 }, { a: manA, z: manZ - 4 });
  OBST.push({ c: G.add3(neck, G.mul3(dir, 0.7)), r: 4.6 });
  VOLUMES.push({ owner: u.id, kind: "vcyl", x: neck[0], y: neck[1], r: 4.4, z0: manZ - 4.4, z1: manZ + 4.4 });
  if (spec.trays) {
    // platforms: twelve deck and rail sectors each, so every piece sorts in depth against the column it wraps
    const ladderA = VIEW_ANGLE - 128 * DEG;
    const arc = (r, from, to) => Array.from({ length: 5 }, (_, j) => { const a = from + ((to - from) * j) / 4; return [g.x + r * Math.cos(a), g.y + r * Math.sin(a)]; });
    for (const zp of [64, g.zt - 7]) {
      const n = 12;
      for (let i = 0; i < n; i++) {
        const a0 = (i / n) * Math.PI * 2;
        const a1 = ((i + 1) / n) * Math.PI * 2;
        const mid = (a0 + a1) / 2;
        const deck = [...arc(Rv, a0, a1), ...arc(Rv + 6, a1, a0)];
        const id = nameFor(`${u.id}.platform`);
        put(u.id, [g.x + (Rv + 3) * Math.cos(mid), g.y + (Rv + 3) * Math.sin(mid), zp + 0.4], S(k.extrude(deck, zp, 0.8, P, { convex: false }), { tone: "mid" }), { name: id, shapes: [record(A.extruded(deck, zp, 0.8, { name: id, owner: u.id }))] });
        const rail = [...arc(Rv + 5.4, a0, a1), ...arc(Rv + 5.9, a1, a0)];
        const rid = nameFor(`${u.id}.handrail`);
        put(u.id, [g.x + (Rv + 5.6) * Math.cos(mid), g.y + (Rv + 5.6) * Math.sin(mid), zp + 4.15], S(k.extrude(rail, zp + 3.9, 0.5, P, { convex: false }), { tone: "mid", crease: "none" }), { name: rid, shapes: [record(A.extruded(rail, zp + 3.9, 0.5, { name: rid, owner: u.id }))] });
        const pp = [g.x + (Rv + 5.65) * Math.cos(a0), g.y + (Rv + 5.65) * Math.sin(a0)];
        const PF = G.frameOf([pp[0], pp[1], 0], [0, 0, 1], [1, 0, 0], [0, 1, 0]);
        const pid = nameFor(`${u.id}.railpost`);
        put(u.id, [pp[0], pp[1], zp + 2.35], S(G.disc(zp + 0.8, zp + 3.9, 0.22, PF, P), { tone: "mid", crease: "none" }), { name: pid, shapes: [record(A.disc(PF, zp + 0.8, zp + 3.9, 0.22, { name: pid, owner: u.id }))] });
      }
      VOLUMES.push({ owner: u.id, kind: "vcyl", x: g.x, y: g.y, r: Rv + 6.2, z0: zp - 0.5, z1: zp + 4.6 });
    }
    // ladder: two rails from the ground to the top platform, outside the decks, rungs every 3 units
    const lr = Rv + 7.2;
    const side = [-Math.sin(ladderA), Math.cos(ladderA)];
    const top = g.zt - 7 + 4.4;
    const rails = [-1.4, 1.4].map((o) => [g.x + lr * Math.cos(ladderA) + o * side[0], g.y + lr * Math.sin(ladderA) + o * side[1]]);
    const rungs = [];
    const rungShapes = [];
    for (let z = 3; z < top - 1; z += 3) {
      rungs.push(poly([[rails[0][0], rails[0][1], z], [rails[1][0], rails[1][1], z]]));
      rungShapes.push(A.tube([[rails[0][0], rails[0][1], z], [rails[1][0], rails[1][1], z]], 0.12, { name: `${u.id}.ladder.rung` }));
    }
    rails.forEach(([rx, ry], i) => {
      const RF = G.frameOf([rx, ry, 0], [0, 0, 1], [1, 0, 0], [0, 1, 0]);
      const id = nameFor(`${u.id}.ladder`);
      put(u.id, [rx, ry, top / 2], S(G.disc(0, top, 0.3, RF, P), { tone: "mid", crease: "none" }) + (i ? Ln(rungs.join(""), { tone: "mid" }) : ""), { name: id, shapes: [record(A.disc(RF, 0, top, 0.3, { name: id, owner: u.id })), ...(i ? rungShapes : [])] });
    });
    VOLUMES.push({ owner: u.id, kind: "vcyl", x: g.x + lr * Math.cos(ladderA), y: g.y + lr * Math.sin(ladderA), r: 2.4, z0: 0, z1: top });
    for (let z = 0; z <= top; z += 4) (usedAngles[u.id] ??= []).push({ a: ladderA, z });
  }
  if (spec.demister) {
    // level glass on a bridle: two small nozzles off the shell and a vertical glass between them
    const ga = VIEW_ANGLE + 68 * DEG;
    const z0 = g.zb + 3;
    const z1 = g.zt - 4;
    const gr = Rv + 3.2;
    const gx = g.x + gr * Math.cos(ga);
    const gy = g.y + gr * Math.sin(ga);
    const dirG = [Math.cos(ga), Math.sin(ga), 0];
    for (const z of [z0, z1]) padOn(u.id, g.hosts.shell, G.pointOf(F, z, Rv, ga), dirG, 0.55, 3.2 - 0.9 + 0.05, { name: `${u.id}.bridle` });
    const GF = G.frameOf([gx, gy, 0], [0, 0, 1], [1, 0, 0], [0, 1, 0]);
    discAt(u.id, GF, z0 - 2, z0 - 0.8, 1.25, { tone: "hi" }, { name: `${u.id}.glass.cap` });
    discAt(u.id, GF, z1 + 0.8, z1 + 2, 1.25, { tone: "hi" }, { name: `${u.id}.glass.cap` });
    const id = nameFor(`${u.id}.glass`);
    put(u.id, [gx, gy, (z0 + z1) / 2], `<g class="tour-glass">${S(G.disc(z0 - 0.8, z1 + 0.8, 0.9, GF, P), { tone: "hi", crease: "none" })}<g data-glass="${u.id}"></g></g>`, { name: id, shapes: [record(A.disc(GF, z0 - 0.8, z1 + 0.8, 0.9, { name: id, owner: u.id }))] });
    GLASS[u.id] = { x: gx, y: gy, r: 0.75, z0, z1 };
    (usedAngles[u.id] ??= []).push(...[z0, (z0 + z1) / 2, z1].map((z) => ({ a: ga, z })));
    OBST.push({ c: [gx, gy, (z0 + z1) / 2], r: (z1 - z0) / 2 + 1 });
    VOLUMES.push({ owner: u.id, kind: "vcyl", x: gx, y: gy, r: 1.3, z0: z0 - 2, z1: z1 + 2 });
  }
}

function agitator(u, F, g) {
  const z0 = g.top - 0.05;
  discAt(u.id, F, z0, z0 + 1.2, 4.2, { tone: "hi" }, { name: `${u.id}.agitator.flange`, extra: Dots(G.dotsOf(F, z0 + 1.2, 3.5, 8, P, { fade: [0.04, 0.42] }), { size: 0.4 }) });
  discAt(u.id, F, z0 + 1.2, z0 + 6, 3, { tone: "mid" }, { name: `${u.id}.agitator.gearbox` });
  const motor = discAt(u.id, F, z0 + 6, z0 + 17, 3.8, { tone: "hi" }, { name: `${u.id}.agitator.motor`, extra: k.fadedSvg(G.ribsOf(F, z0 + 7, z0 + 16, 3.8, 22, P, { fade: [0.1, 0.55] }), { tone: "lo" }) });
  discAt(u.id, F, z0 + 17, z0 + 18.6, 3.3, { tone: "mid" }, { name: `${u.id}.agitator.cowl` });
  vcyl(u.id, g.x, g.y, 4.4, z0, z0 + 19);
  g.motor = { at: [g.x, g.y, z0 + 11.5], shape: motor };
}

function header(u) {
  // A vapour header running along y, so each battery-limit feed comes straight in on its own side nozzle.
  const spec = SHAPES.feed;
  const [x, cy] = plan(u.id);
  const y0 = cy - spec.L / 2;
  const F = G.frameOf([x, y0, spec.zc], [0, 1, 0], [1, 0, 0], [0, 0, 1]);
  const g = (UNIT_GEOM[u.id] = { ports: {}, markers: [], hosts: {}, F, x, y: cy, y0, kind: u.kind, r: spec.r, L: spec.L, zc: spec.zc, used: [] });
  for (const s of [9, spec.L - 9]) {
    boxAt(u.id, [x - 2.6, y0 + s - 2, 0], [x + 2.6, y0 + s + 2, spec.zc - spec.r], { tone: "mid" }, { name: `${u.id}.support` });
  }
  const r = spec.r;
  const bore = windowPath(F, r, 5, spec.L - 5, Math.atan2(G.dot3(V, F.v), G.dot3(V, F.u)), 58 * DEG);
  clips.push(`<clipPath id="win-${u.id}"><path d="${poly(bore, true)}"/></clipPath>`);
  const boreSvg = `<g clip-path="url(#win-${u.id})" data-internal="header-bore"><path class="tour-cavity" d="${poly(bore, true)}"/>`
    + Ln([10, 20, 30, 40].map((s) => G.arcOf(F, s, r - .6, P, { inward: true })).join(""), { tone: "mid" })
    + Ln(poly([G.pointOf(F, 4, 0, 0), G.pointOf(F, spec.L - 4, 0, 0)]), { tone: "hi" }) + `</g><path class="iso-line tour-cut" data-tone="hi" d="${poly(bore, true)}"/>`;
  const shell = turned(u.id, F, [[0, r], [spec.L, r]], { tone: "hi" }, { name: `${u.id}.header`, extra: boreSvg });
  const capR = (s) => r * Math.sqrt(Math.max(0, 1 - (s / (r / 2)) ** 2));
  turned(u.id, F, [[spec.L, r], [spec.L + (r / 2) * 0.985, capR((r / 2) * 0.985)]], { tone: "hi" }, { name: `${u.id}.cap`, smooth: { radius: (s) => capR(s - spec.L), slope: (s) => { const t = Math.min(0.999, (s - spec.L) / (r / 2)); return (-r * t) / ((r / 2) * Math.sqrt(1 - t * t)); } } });
  turned(u.id, F, [[-(r / 2) * 0.985, capR((r / 2) * 0.985)], [0, r]], { tone: "hi" }, { name: `${u.id}.cap`, smooth: { radius: (s) => capR(-s), slope: (s) => { const t = Math.min(0.999, -s / (r / 2)); return (r * t) / ((r / 2) * Math.sqrt(1 - t * t)); } } });
  g.hosts.shell = shell;
  VOLUMES.push({ owner: u.id, kind: "box", min: [x - r, y0 - r, spec.zc - r], max: [x + r, y0 + spec.L + r, spec.zc + r] });
  g.label = [x, cy, spec.zc];
  g.focus = [[x - 14, y0 - 10, 0], [x + 14, y0 + spec.L + 10, spec.zc + 14]];
}

function exchanger(u) {
  const spec = SHAPES.condenser;
  const [cx, y] = plan(u.id);
  const x0 = cx - spec.L / 2;
  const r = spec.r;
  const F = G.frameOf([x0, y, spec.zc], [1, 0, 0], [0, 1, 0], [0, 0, 1]);
  const g = (UNIT_GEOM[u.id] = { ports: {}, markers: [], hosts: {}, F, x: cx, y, kind: u.kind, r, L: spec.L, zc: spec.zc });
  for (const s of [7, spec.L - 7]) {
    boxAt(u.id, [x0 + s - 1.6, y - 4, 0], [x0 + s + 1.6, y + 4, spec.zc - r], { tone: "mid" }, { name: `${u.id}.saddle` });
  }
  // shell with a cutaway window on its upper front quarter: tube bundle and segmental baffles inside
  const shell = record(A.disc(F, 0, spec.L, r, { name: `${u.id}.shell`, owner: u.id }));
  g.hosts.shell = shell;
  const half = 55 * DEG;
  const phiC = Math.atan2(G.dot3([0, 0, 1], F.v) * 0.6 + G.dot3(V, F.v), G.dot3(V, F.u) * 1); // face the viewer, tilted up
  const winPts = [];
  const s0 = 5;
  const s1 = spec.L - 5;
  for (let i = 0; i <= 16; i++) winPts.push(G.pointOf(F, s0 + ((s1 - s0) * i) / 16, r, phiC - half));
  for (let i = 0; i <= 16; i++) winPts.push(G.pointOf(F, s1, r, phiC - half + (2 * half * i) / 16));
  for (let i = 0; i <= 16; i++) winPts.push(G.pointOf(F, s1 - ((s1 - s0) * i) / 16, r, phiC + half));
  for (let i = 0; i <= 16; i++) winPts.push(G.pointOf(F, s0, r, phiC + half - (2 * half * i) / 16));
  clips.push(`<clipPath id="win-${u.id}"><path d="${poly(winPts, true)}"/></clipPath>`);
  const inside = [`<path class="tour-cavity" d="${poly(winPts, true)}"/>`];
  const tubes = [];
  for (const [rr, a] of [[1.4, 0], [1.4, 2.1], [1.4, 4.2], [2.9, 0.5], [2.9, 1.55], [2.9, 2.6], [2.9, 3.65], [2.9, 4.7], [2.9, 5.75], [0, 0]]) {
    tubes.push(poly([G.pointOf(F, s0 - 1, rr, a), G.pointOf(F, s1 + 1, rr, a)]));
  }
  inside.push(Ln(tubes.join(""), { tone: "mid" }));
  for (let s = s0 + 5; s < s1; s += 7) inside.push(Ln(G.arcOf(F, s, r - 0.5, P, { least: -1 }), { tone: "lo" }));
  const cut = poly([G.pointOf(F, s0, r - 0.5, phiC - half), G.pointOf(F, s1, r - 0.5, phiC - half)]) + poly([G.pointOf(F, s0, r - 0.5, phiC + half), G.pointOf(F, s1, r - 0.5, phiC + half)]);
  const windowSvg = `<g clip-path="url(#win-${u.id})">${inside.join("")}</g>` + Ln(cut, { tone: "mid" }) + `<path class="iso-line tour-cut" data-tone="hi" d="${poly(winPts, true)}"/>`;
  put(u.id, [cx, y, spec.zc], S(G.disc(0, spec.L, r, F, P), { tone: "hi" }) + windowSvg, { name: `${u.id}.shell`, shapes: [shell] });
  // body flanges and channel head (tube side, cooling water) at the low-x end, rear head at the other
  discAt(u.id, F, -0.8, 0, r + 1, { tone: "hi" }, { name: `${u.id}.flange`, extra: Dots(G.dotsOf(F, -0.8, r + 0.5, 14, P, { fade: [0.04, 0.42] }), { size: 0.4 }) });
  const channel = discAt(u.id, F, -6.8, -0.8, r, { tone: "hi" }, { name: `${u.id}.channel` });
  discAt(u.id, F, -7.6, -6.8, r + 1, { tone: "hi" }, { name: `${u.id}.channel.flange` });
  const capR = (s) => r * Math.sqrt(Math.max(0, 1 - (s / (r / 2)) ** 2));
  turned(u.id, F, [[-7.6 - (r / 2) * 0.985, capR((r / 2) * 0.985)], [-7.6, r]], { tone: "hi" }, { name: `${u.id}.bonnet`, smooth: { radius: (s) => capR(-7.6 - s), slope: (s) => { const t = Math.min(0.999, (-7.6 - s) / (r / 2)); return (r * t) / ((r / 2) * Math.sqrt(1 - t * t)); } } });
  turned(u.id, F, [[spec.L, r], [spec.L + (r / 2) * 0.985, capR((r / 2) * 0.985)]], { tone: "hi" }, { name: `${u.id}.rearhead`, smooth: { radius: (s) => capR(s - spec.L), slope: (s) => { const t = Math.min(0.999, (s - spec.L) / (r / 2)); return (-r * t) / ((r / 2) * Math.sqrt(1 - t * t)); } } });
  g.hosts.channel = channel;
  hcyl(u.id, x0 - 10.5, x0 + spec.L + 3, y, spec.zc, r + 1);
  g.label = [cx, y, spec.zc + 12];
  g.focus = [[x0 - 14, y - 12, 0], [x0 + spec.L + 8, y + 12, spec.zc + 14]];
}

function compressor(u) {
  // Shaft along y: the suction eye faces +y, toward the separator it draws from; the motor sits behind.
  const [x, y] = plan(u.id);
  const zc = SHAPES.compressor.zc;
  const g = (UNIT_GEOM[u.id] = { ports: {}, markers: [], hosts: {}, x, y, kind: u.kind, zc });
  const yc = y + 8; // casing centre
  boxAt(u.id, [x - 7, yc - 32, 0], [x + 7, yc + 8, 2.5], { tone: "mid" }, { name: `${u.id}.baseplate`, extra: Dots([[x - 5, yc + 6], [x + 5, yc + 6], [x - 5, yc - 30], [x + 5, yc - 30]].map(([a0, b0]) => at([a0, b0, 2.5])), { size: 0.45 }) });
  const F = G.frameOf([x, yc, zc], [0, -1, 0], [1, 0, 0], [0, 0, 1]);
  boxAt(u.id, [x - 3, yc - 3, 2.5], [x + 3, yc + 3, zc - 9.95], { tone: "mid" }, { name: `${u.id}.pedestal` });
  const bulge = (s0) => 8.6 + 1.4 * Math.sqrt(Math.max(0, 1 - (s0 / 3.2) ** 2));
  const bulgeSlope = (s0) => {
    const t = Math.max(-0.995, Math.min(0.995, s0 / 3.2));
    return (-1.4 * t) / (3.2 * Math.sqrt(1 - t * t));
  };
  const casingProfile = [[-3.2, 0], [-3.2, 8.6], ...Array.from({ length: 13 }, (_, i) => { const s0 = -3.2 + (6.4 * i) / 12; return [s0, bulge(s0), i && i < 12 ? 1 : 0]; }), [3.2, 8.6], [3.2, 0]];
  const casing = record(A.body(F, casingProfile, { name: `${u.id}.casing`, owner: u.id }));
  const faceDots = Dots(G.dotsOf(F, -3.2, 7.4, 12, P, { fade: [0.04, 0.42] }), { size: 0.4 });
  // Illustrative radial impeller behind a front-cover opening; the benchmark does not specify compressor internals.
  const opening = G.circleOf(F, -3.24, 6.6, P, 48);
  clips.push(`<clipPath id="win-${u.id}"><path d="${opening}"/></clipPath>`);
  const vanes = Array.from({ length: 9 }, (_, i) => {
    const a = i * Math.PI * 2 / 9;
    return poly([G.pointOf(F, -3.3, 1.5, a), G.pointOf(F, -3.3, 3.8, a + .35), G.pointOf(F, -3.3, 5.8, a + .55)]);
  }).join("");
  const wheel = `<g clip-path="url(#win-${u.id})" data-internal="compressor-impeller"><path class="tour-cavity" d="${opening}"/>`
    + Ln(G.circleOf(F, -3.3, 5.8, P, 48) + vanes, { tone: "hi" })
    + S(G.disc(-3.5, -3.3, 1.5, F, P), { tone: "hi" }) + `</g><path class="iso-line tour-cut" data-tone="hi" d="${opening}"/>`;
  put(u.id, F.o, S(G.lathe(casingProfile, F, P, { steps: 64, smooth: { slope: bulgeSlope, rows: 4 } }), { tone: "hi" }) + faceDots + wheel, { name: `${u.id}.casing`, shapes: [casing] });
  g.hosts.casing = casing;
  discAt(u.id, F, 3.2, 7, 3, { tone: "mid" }, { name: `${u.id}.bearing` });
  discAt(u.id, F, 7, 11, 1.1, { tone: "hi" }, { name: `${u.id}.shaft` });
  discAt(u.id, F, 11, 12.2, 3.4, { tone: "mid" }, { name: `${u.id}.coupling` });
  boxAt(u.id, [x - 5.5, yc - 30, 2.5], [x + 5.5, yc - 13.5, zc - 7], { tone: "mid" }, { name: `${u.id}.motorfeet` });
  const motor = discAt(u.id, F, 12.2, 28, 7, { tone: "hi" }, { name: `${u.id}.motor`, extra: k.fadedSvg(G.ribsOf(F, 13.5, 27, 7, 30, P, { fade: [0.1, 0.55] }), { tone: "lo" }) });
  discAt(u.id, F, 28, 30.5, 6.4, { tone: "mid" }, { name: `${u.id}.cowl`, extra: Ln(G.circleOf(F, 30.5, 4.6, P, 32), { tone: "faint" }) });
  boxAt(u.id, [x - 3, yc - 23, zc + 6.9], [x + 3, yc - 17, zc + 10], { tone: "mid" }, { name: `${u.id}.terminalbox` });
  VOLUMES.push({ owner: u.id, kind: "box", min: [x - 10.2, yc - 31, 0], max: [x + 10.2, yc + 3.6, zc + 10.2] });
  g.motor = { at: [x, yc - 20, zc + 10], shape: motor };
  g.F = F;
  g.label = [x, yc, zc + 5];
  g.focus = [[x - 14, yc - 34, 0], [x + 14, yc + 12, zc + 22]];
}

for (const u of DATA.units) {
  const t = SHAPES[u.kind]?.type;
  if (t === "vessel") vessel(u);
  else if (t === "header") header(u);
  else if (t === "exchanger") exchanger(u);
  else if (t === "compressor") compressor(u);
  else throw new Error(`no placeholder machine for kind ${u.kind} (${u.id}); add one rather than guessing`);
}

// ------------------------------------------------------------------ ports: where each stream meets its unit
// Placeholder conventions, by unit kind and the stream's service (both from the data):
//   vertical vessels: vapour out through the top head, liquid out low on the side, inlets on the side
//   header: inlets on top, the outlet through its end cap; exchanger: in on top, out underneath
//   compressor: suction into the casing eye (axial), discharge up from the volute.
const angleToward = (g, to) => Math.atan2(to[1] - g.y, to[0] - g.x);

function freeAngle(uid, z, want) {
  const half = 50 * DEG + 16 * DEG;
  const list = (usedAngles[uid] ??= []);
  const clash = (a) => {
    const d = (b) => Math.abs(((a - b + Math.PI * 3) % (Math.PI * 2)) - Math.PI);
    return d(VIEW_ANGLE) < half || list.some((o) => Math.abs(o.z - z) < 6 && d(o.a) < 30 * DEG);
  };
  for (let step = 0; step < 120; step++) {
    for (const sign of [1, -1]) {
      const a = want + sign * step * 3 * DEG;
      if (!clash(a)) { list.push({ a, z }); return a; }
    }
  }
  return want;
}
const BL_POSTS = {};
function otherEnd(stream, end) {
  const id = end === "from" ? stream.to : stream.from;
  if (id === "BL") return BL_POSTS[stream.id].xy;
  const g = UNIT_GEOM[id];
  return [g.x, g.y];
}
// Battery-limit tie-in posts: away from the plant centre on the far side of their unit.
{
  const cx = DATA.units.reduce((s, u) => s + plan(u.id)[0], 0) / DATA.units.length;
  const cy = DATA.units.reduce((s, u) => s + plan(u.id)[1], 0) / DATA.units.length;
  const count = {};
  for (const s of DATA.streams) {
    if (s.from !== "BL" && s.to !== "BL") continue;
    const uid = s.from === "BL" ? s.to : s.from;
    const g = UNIT_GEOM[uid];
    let dx = g.x - cx;
    let dy = (g.y - cy) * 0.35;
    const n = Math.hypot(dx, dy) || 1;
    dx /= n;
    dy /= n;
    const kidx = (count[uid] = (count[uid] ?? -1) + 1);
    const reach = g.kind === "feed" ? 52 : 60;
    const side = (kidx - 1) * 17;
    BL_POSTS[s.id] = { xy: [g.x + dx * reach - dy * side, Math.max(GROUND.y + 8, Math.min(GROUND.y + GROUND.d - 8, g.y + dy * reach + dx * side))], stream: s.id, unit: uid };
  }
}

const PORTS = {}; // key `${stream}:${end}` -> {p, axis, unit}
function portFor(stream, end) {
  const uid = stream[end];
  const g = UNIT_GEOM[uid];
  const out = end === "from";
  const other = otherEnd(stream, end);
  const gas = GAS.has(stream.service);
  const name = `${uid}.nozzle.${stream.id}`;
  if (g.kind === "feed") {
    // a station along the header nearest the other end, kept 8 apart from the stations already used
    const face = out ? "right" : (end === "to" ? stream.from : stream.to) === "BL" ? "left" : "top";
    const take = (want) => {
      const clamp = (v) => Math.max(6, Math.min(g.L - 6, v));
      const used = g.used.filter((o) => o.face === face || (face === "top" && o.face !== "top"));
      for (let step = 0; step < 120; step++) {
        for (const sign of [1, -1]) {
          const s = clamp(want + sign * step);
          if (used.every((o) => Math.abs(o.s - s) >= (o.face === face ? 8 : 5))) { g.used.push({ s, face }); return s; }
        }
      }
      throw new Error(`no free station on ${uid}`);
    };
    const s = take(other[1] - g.y0);
    if (face === "right") return nozzle(uid, g.hosts.shell, G.pointOf(g.F, s, g.r, 0), [1, 0, 0], RP, { name });
    if (face === "left") return nozzle(uid, g.hosts.shell, G.pointOf(g.F, s, g.r, Math.PI), [-1, 0, 0], RP, { name });
    return nozzle(uid, g.hosts.shell, G.pointOf(g.F, s, g.r, Math.PI / 2), [0, 0, 1], RP, { name });
  }
  if (g.kind === "condenser") {
    if (out) return nozzle(uid, g.hosts.shell, G.pointOf(g.F, g.L - 14, g.r, -Math.PI / 2), [0, 0, -1], RP, { name });
    return nozzle(uid, g.hosts.shell, G.pointOf(g.F, 11, g.r, Math.PI / 2), [0, 0, 1], RP, { name });
  }
  if (g.kind === "compressor") {
    if (!out) {
      // suction: a straight eye pipe on the casing face, axial
      return nozzle(uid, g.hosts.casing, G.pointOf(g.F, -3.2, 0, 0), G.mul3(g.F.a, -1), RP, { name, length: 3 });
    }
    return nozzle(uid, g.hosts.casing, G.pointOf(g.F, 0, 9.98, Math.PI / 2), [0, 0, 1], RP, { name, length: 2 });
  }
  // vertical vessels
  const want = angleToward(g, other);
  if (out && gas) {
    const used = (g.topUsed = (g.topUsed ?? 0) + 1) - 1;
    const rho = g.R * 0.55;
    const a = want + (used ? 70 * DEG : 0) * (used % 2 ? 1 : -1);
    const zTop = g.zt + (g.R / 2) * Math.sqrt(1 - (rho / g.R) ** 2);
    return nozzle(uid, g.hosts.head, [g.x + rho * Math.cos(a), g.y + rho * Math.sin(a), zTop - 0.6], [0, 0, 1], RP, { name, length: 2.4 });
  }
  let z;
  if (out) z = g.zb + 3.5;
  else if (g.kind === "reactor") z = g.zb + 6;
  else if (g.kind === "stripper") z = gas ? g.zb + 14 : g.zt - 14;
  else z = g.zt - 8;
  const a = freeAngle(uid, z, want);
  return nozzle(uid, g.hosts.shell, G.pointOf(g.F, z, g.R, a), [Math.cos(a), Math.sin(a), 0], RP, { name });
}

// Battery-limit and utility posts: a plinth, a riser and a flange the line lands on from above; feed and product
// posts carry a hand-wheel block valve (the LOTO mockup's inferred isolation point).
function post(id, unit, xy, r, { block = false, label }) {
  const [x, y] = xy;
  const F = G.frameOf([x, y, 0], [0, 0, 1], [1, 0, 0], [0, 1, 0]);
  boxAt(id, [x - 3.5, y - 3.5, 0], [x + 3.5, y + 3.5, 2], { tone: "mid" }, { name: `${id}.plinth`, owner: id });
  discAt(id, F, 2, 8, r + 0.3, { tone: "mid" }, { name: `${id}.riser`, owner: id });
  let top = 8;
  const out = { id, unit };
  if (block) {
    boxAt(id, [x - 2.2, y - 2.2, 8], [x + 2.2, y + 2.2, 11.5], { tone: "hi" }, { name: `${id}.valve`, owner: id });
    const stem = G.frameAlong([x, y, 9.75], [0, 1, 0]);
    discAt(id, stem, 2.2, 4.4, 0.5, { tone: "mid" }, { name: `${id}.stem`, owner: id });
    discAt(id, stem, 4.4, 4.9, 2.4, { tone: "hi" }, { name: `${id}.handwheel`, owner: id, extra: Ln(G.circleOf(stem, 4.9, 1.4, P, 24), { tone: "faint" }) });
    out.lock = G.pointOf(stem, 5.6, 0, 0);
    top = 11.5;
  }
  discAt(id, F, top, top + 0.8, r * FLANGE, { tone: "hi" }, { name: `${id}.flange`, owner: id });
  vbox(id, [x - 3.6, y - 3.6, 0], [x + 3.6, y + 3.6, top + 0.8]);
  out.port = { p: [x, y, top + 0.8], axis: [0, 0, 1], unit: id };
  out.label = label;
  return out;
}
const POSTS = {};
for (const s of DATA.streams) if (BL_POSTS[s.id]) POSTS[`BL-${s.id}`] = post(`BL-${s.id}`, BL_POSTS[s.id].unit, BL_POSTS[s.id].xy, RP, { block: true, label: `Battery limit: ${s.name}` });
for (const s of DATA.streams) {
  PORTS[`${s.id}:from`] = s.from === "BL" ? POSTS[`BL-${s.id}`].port : portFor(s, "from");
  PORTS[`${s.id}:to`] = s.to === "BL" ? POSTS[`BL-${s.id}`].port : portFor(s, "to");
}

// Utility stubs (inferred in the data from a valve's own description): a nozzle on the unit, out to a post.
const UTIL = {};
for (const u of DATA.utilities) {
  const g = UNIT_GEOM[u.unit];
  const pairIndex = DATA.utilities.filter((x) => x.tag === u.tag).findIndex((x) => x.id === u.id);
  let port;
  let postXY;
  const name = `${u.unit}.nozzle.${u.id}`;
  if (g.kind === "condenser") {
    // tube side (cooling water) on the front of the channel head: supply low, return high, both toward the viewer,
    // each with its post straight out in front, so every line is one bend
    const supply = u.role === "supply";
    const a = supply ? -0.5 : Math.PI / 2;
    const pt = G.pointOf(g.F, supply ? -5.0 : -2.6, g.r, a);
    port = nozzle(u.unit, g.hosts.channel, pt, supply ? [0, 1, 0] : [0, 0, 1], RU, { name });
    postXY = supply ? [pt[0], g.y + 38] : [pt[0] - 20, g.y + 26];
  } else {
    const z = u.role === "supply" ? g.zb + 7 : u.role === "return" ? g.zt - 6 : g.zb + 8;
    const want = 125 * DEG + (pairIndex ? 14 * DEG : 0);
    const a = freeAngle(u.unit, z, want);
    port = nozzle(u.unit, g.hosts.shell, G.pointOf(g.F, z, g.R, a), [Math.cos(a), Math.sin(a), 0], RU, { name });
    const reach = g.R + 36 + pairIndex * 9;
    postXY = [g.x + reach * Math.cos(a), g.y + reach * Math.sin(a)];
  }
  const p = post(`UT-${u.id}`, u.unit, postXY, RU, { block: false, label: `${u.service.replace(/_/g, " ")} (inferred)` });
  POSTS[`UT-${u.id}`] = p;
  UTIL[u.id] = { from: u.role === "return" ? port : p.port, to: u.role === "return" ? p.port : port, data: u };
}

// ------------------------------------------------------------------ routing (placeholder: orthogonal legs)
const ROUTED = [];
const WHY = [];
function clearOf(points, r, ends, skipOwners) {
  const samples = G.resample(points, 1);
  const total = samples.length;
  for (let i = 0; i < total; i++) {
    const p = samples[i];
    const nearStart = i < 7;
    const nearEnd = i > total - 8;
    for (const v of VOLUMES) {
      if ((nearStart && skipOwners[0].includes(v.owner)) || (nearEnd && skipOwners[1].includes(v.owner))) continue;
      if (volumeDistance(v, p) < r + 2) { WHY.push(`vol ${v.owner} ${v.kind} at ${p.map((c) => c.toFixed(1))}`); return false; }
    }
    if (p[2] < r + 1.5) { WHY.push("ground"); return false; }
    for (const other of ROUTED) {
      const need = r + other.r + 2.4;
      for (const q of other.samples) {
        if (Math.abs(q[0] - p[0]) < need && Math.abs(q[1] - p[1]) < need && Math.abs(q[2] - p[2]) < need && G.len3(G.sub3(p, q)) < need) { WHY.push(`pipe ${other.id} at ${p.map((c) => c.toFixed(1))}`); return false; }
      }
    }
  }
  return true;
}
// A candidate whose projection bends tighter than the tube's own half-width on screen (a bend seen edge-on) would
// pinch or fold; the anatomy audit fails those, so the router never picks one.
// Screen boxes of every machine, so a bend can be kept off another machine's outline (crossings belong on straights).
function screenBox(v) {
  const c = v.kind === "vcyl" ? [[v.x - v.r, v.y - v.r, v.z0], [v.x + v.r, v.y + v.r, v.z1]] : v.kind === "hcyl" ? [[v.x0, v.y - v.r, v.z - v.r], [v.x1, v.y + v.r, v.z + v.r]] : [v.min, v.max];
  const pts = [];
  for (const x of [c[0][0], c[1][0]]) for (const y of [c[0][1], c[1][1]]) for (const z of [c[0][2], c[1][2]]) pts.push(at([x, y, z]));
  return [Math.min(...pts.map((p) => p[0])), Math.min(...pts.map((p) => p[1])), Math.max(...pts.map((p) => p[0])), Math.max(...pts.map((p) => p[1]))];
}
// Bends and ends of a candidate kept off other lines on screen, and its straights kept off other lines' bends and
// ends (the audit's crowding check: a corner landing on another line reads as a joint).
function screenCrowd(simple, line, r) {
  let n = 0;
  const mine = simple.map(at);
  const pts = G.resample(line, 2).map(at);
  for (const o of ROUTED) {
    const need = (r + o.r) * KS + 5;
    for (const c of mine) if (o.screen.some((q) => Math.hypot(q[0] - c[0], q[1] - c[1]) < need)) n++;
    for (const c of o.corners) if (pts.some((q) => Math.hypot(q[0] - c[0], q[1] - c[1]) < need)) n++;
  }
  return n;
}
function bendsOverOthers(simple, owners) {
  let n = 0;
  const mine = new Set([...owners[0], ...owners[1]]);
  for (const p of simple.slice(1, -1)) {
    const q = at(p);
    for (const v of VOLUMES) {
      if (mine.has(v.owner) || v.owner.startsWith("BL-") || v.owner.startsWith("UT-")) continue;
      const b = (v.box ??= screenBox(v));
      if (q[0] > b[0] - 8 && q[0] < b[2] + 8 && q[1] > b[1] - 8 && q[1] < b[3] + 8) { n++; break; }
    }
  }
  return n;
}
// How many of a line's valve and stem markers would find no horizontal straight stretch (0 = room for all).
function roomFor(line, r, need) {
  const runs = straights(line, 4).filter(([, , d]) => Math.abs(G.dot3(d, V)) < 0.62).map(([a0, b0]) => b0 - a0 - 16).filter((l) => l > 0).sort((p, q) => q - p);
  let missing = 0;
  if (need.valve) { if (runs.length && runs[0] >= r * 5) runs[0] -= r * 5 + 16; else missing++; }
  for (let i = 0; i < need.markers; i++) {
    const k2 = runs.findIndex((l) => l >= 0);
    if (k2 < 0) missing++; else runs[k2] -= 8;
  }
  return missing;
}
function pinches(line, r) {
  const pts = G.resample(line, 0.6).map(at);
  const half = r * KS * 1.4;
  for (let i = 2; i < pts.length - 2; i++) {
    const a = pts[i - 2], b = pts[i], c = pts[i + 2];
    const ab = Math.hypot(b[0] - a[0], b[1] - a[1]), bc = Math.hypot(c[0] - b[0], c[1] - b[1]), ca = Math.hypot(a[0] - c[0], a[1] - c[1]);
    const area = Math.abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) / 2;
    if (area < 1e-6) continue;
    const radius = (ab * bc * ca) / (4 * area);
    if (radius < half) return true;
    const d1 = [b[0] - a[0], b[1] - a[1]], d2 = [c[0] - b[0], c[1] - b[1]];
    const cos = (d1[0] * d2[0] + d1[1] * d2[1]) / ((ab * bc) || 1);
    if (cos < -0.5) return true;
  }
  return false;
}
const LANES = [10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 62, 66, 70, 74, 78, 82, 86, 90, 95, 105, 115, 128, 136];
// A deliberate overhead corridor for the long recycle return. Only its connections are source-backed.
const RACK = { status: "inferred placeholder structure, not a plant layout", x: [45, 195], y: [26, 60], z: 74, frames: [], rails: [] };
function bendsOverRack(points) {
  return points.slice(1, -1).some((p) => RACK.y.some((y) => segmentDistance2(at(p), at([RACK.x[0], y, RACK.z - RP - 1.5]), at([RACK.x[1], y, RACK.z - RP - 1.5])) < (RP + .8) * KS + 6));
}
function route(id, a, b, r, owners, need) {
  const stub = (port, len) => G.add3(port.p, G.mul3(port.axis, len));
  let best = null;
  if (id === "S8b") {
    const shoulder = G.add3(a.p, [0, 0, 12]);
    const riser = G.add3(shoulder, [-24, 0, 0]);
    const simple = [a.p, shoulder, riser, [riser[0], riser[1], RACK.z], [b.p[0], a.p[1], RACK.z], [b.p[0], b.p[1], RACK.z], b.p];
    const line = G.fillet(simple, Math.max(r * 5.6, 6), 14, { P, tube: r });
    if (!pinches(line, r) && clearOf(line, r, [a, b], owners)) best = { simple, line, score: -1 };
    else throw new Error(`recycle corridor obstructed: ${WHY.slice(-4).join("; ")}`);
  }
  const escapes = (port, toward) => {
    if (Math.abs(port.axis[2]) < 0.5) return [null];
    const dx = toward[0] - port.p[0];
    const dy = toward[1] - port.p[1];
    const out = [null];
    for (const d of [10, 18, 26]) {
      out.push([Math.sign(dx || 1) * d, 0, 0]);
      out.push([0, Math.sign(dy || 1) * d, 0]);
    }
    return out;
  };
  for (const lenA of best ? [] : [6, 11, 17, 24]) {
    for (const lenB of [6, 11, 17, 24]) {
      const pa0 = stub(a, lenA);
      const pb0 = stub(b, lenB);
      for (const ea of escapes(a, b.p)) for (const eb of escapes(b, a.p)) {
      const pa = ea ? G.add3(pa0, ea) : pa0;
      const pb = eb ? G.add3(pb0, eb) : pb0;
      for (const z of [...LANES, pa[2], pb[2]]) {
        for (const order of ["xy", "yx", "direct"]) {
          const pts = [a.p, pa0];
          if (ea) pts.push(pa);
          const climbA = [pa[0], pa[1], z];
          const climbB = [pb[0], pb[1], z];
          pts.push(climbA);
          if (order !== "direct") pts.push(order === "xy" ? [pb[0], pa[1], z] : [pa[0], pb[1], z]);
          pts.push(climbB);
          if (eb) pts.push(pb);
          pts.push(pb0, b.p);
          const clean = [pts[0]];
          for (const p of pts.slice(1)) if (G.len3(G.sub3(p, clean[clean.length - 1])) > 0.5) clean.push(p);
          // drop collinear middles
          const simple = clean.filter((p, i) => {
            if (i === 0 || i === clean.length - 1) return true;
            const d1 = G.unit3(G.sub3(p, clean[i - 1]));
            const d2 = G.unit3(G.sub3(clean[i + 1], p));
            return G.dot3(d1, d2) < 0.999;
          });
          if (bendsOverRack(simple)) continue; // a projected bend must not read as a joint on a rack beam
          // no hooks: two vertical legs within three legs of each other may not run in opposite directions
          const vert = simple.slice(1).map((p, i) => { const d = p[2] - simple[i][2]; const h = Math.hypot(p[0] - simple[i][0], p[1] - simple[i][1]); return Math.abs(d) > h ? Math.sign(d) : 0; });
          if (id === "S8") {
            const directions = vert.filter(Boolean);
            if (simple.length > 6 || directions.length > 2 || directions.filter((d, i) => i && d !== directions[i - 1]).length > 1) continue;
          }
          const hook = vert.some((v, i) => v && vert.slice(i + 1, i + 4).some((w, j) => w === -v && Math.hypot(simple[i + 1 + j][0] - simple[i + 1][0], simple[i + 1 + j][1] - simple[i + 1][1]) < 16));
          if (hook) continue;
          // no leg may reverse straight back on the previous one
          if (simple.some((p, i) => i > 0 && i < simple.length - 1 && G.dot3(G.unit3(G.sub3(p, simple[i - 1])), G.unit3(G.sub3(simple[i + 1], p))) < -0.5)) continue;
          const line = G.fillet(simple, Math.max(r * 5.6, 6), 14, { P, tube: r });
          const length = G.pathLength(line);
          const crowded = bendsOverOthers(simple, owners) + 2.5 * screenCrowd(simple, line, r);
          const room = need ? roomFor(line, r, need) : 0;
          const high = simple.slice(1).reduce((sum, q, i) => { const p0 = simple[i]; const flat = Math.abs(q[2] - p0[2]) < 0.01; return sum + (flat ? Math.hypot(q[0] - p0[0], q[1] - p0[1]) * Math.max(0, q[2] - 62) * 0.06 : 0); }, 0); // long runs low, on supports, not over the plant
          const score = high + crowded * 150 + room * 400 + length + simple.length * 6 + Math.abs(z - (a.p[2] + b.p[2]) / 2) * 0.3 + (order === "direct" ? 25 : 0);
          if (best && score >= best.score) continue;
          if (pinches(line, r)) { WHY.push("pinch"); continue; }
          if (!clearOf(line, r, [a, b], owners)) continue;
          best = { line, score, simple };
        }
      }
      }
    }
  }
  if (!best) {
    const tally = {};
    for (const w of WHY) { const key = w.split(" at ")[0]; tally[key] = (tally[key] ?? 0) + 1; }
    WHY.length = 0;
    return { failed: true, tally, from: a.p, to: b.p };
  }
  WHY.length = 0;
  ROUTED.push({ id, r, samples: G.resample(best.line, 1), screen: G.resample(best.line, 2).map(at), corners: best.simple.map(at) });
  if (process.env.ROUTE_SHOW === id) console.log(id, JSON.stringify(best.simple.map((p) => p.map((c) => +c.toFixed(1)))), best.score.toFixed(0));
  return best;
}
// Route every line; when one cannot find a clear path because an earlier line is in the way, route it before that
// line and start again (rip-up and retry). A line blocked by equipment alone is a layout error and stops the build.
const JOBS = [];
function planRoutes() {
  let order = JOBS.map((j) => j.id);
  const byId = Object.fromEntries(JOBS.map((j) => [j.id, j]));
  for (let attempt = 0; attempt < 60; attempt++) {
    ROUTED.length = 0;
    const plans = {};
    let failure = null;
    for (const id of order) {
      const j = byId[id];
      const best = route(id, j.a, j.b, j.r, j.owners, j.need);
      if (best.failed) { failure = { id, ...best }; break; }
      plans[id] = best;
    }
    if (!failure) return plans;
    const pipes = Object.entries(failure.tally).filter(([key]) => key.startsWith("pipe ")).sort((p, q) => q[1] - p[1]);
    if (!pipes.length) throw new Error(`no clear route for ${failure.id} from ${failure.from.map((c) => c.toFixed(1))} to ${failure.to.map((c) => c.toFixed(1))}: ${JSON.stringify(failure.tally)}`);
    const blocker = pipes[0][0].slice(5);
    order = order.filter((x) => x !== failure.id);
    order.splice(Math.max(0, order.indexOf(blocker)), 0, failure.id);
  }
  throw new Error("routing did not converge");
}

// ------------------------------------------------------------------ pipes, valves, flow layers
const FLOW = []; // per drawn line: id, service, chunks
const VALVES = [];
function valveOn(owner, unit, line, along, r, tag) {
  const centre = G.pointAlong(line, along);
  const tangent = G.tangentAlong(line, along);
  const F = G.frameAlong(centre, tangent);
  const crown = r * 2.0;
  const bulge = (x) => r * 1.45 + (crown - r * 1.45) * Math.sqrt(Math.max(0, 1 - (x / (r * 1.6)) ** 2));
  const bulgeSlope = (x) => {
    if (Math.abs(x) >= r * 1.6 - 1e-9) return 0;
    const t = Math.max(-0.995, Math.min(0.995, x / (r * 1.6)));
    return (-(crown - r * 1.45) * t) / (r * 1.6 * Math.sqrt(1 - t * t));
  };
  const meridian = [[-r * 2.4, 0], [-r * 2.4, r * 1.45], ...Array.from({ length: 17 }, (_, index) => { const x = r * 1.6 * Math.sin(((index - 8) / 8) * (Math.PI / 2)); return [x, bulge(x), index && index < 16 ? 1 : 0]; }), [r * 2.4, r * 1.45], [r * 2.4, 0]];
  const id = `${owner}.valve.${tag}`;
  put(unit, centre, `<g data-valve="${tag}">${S(G.lathe(meridian, F, P, { steps: 36, smooth: { slope: bulgeSlope, rows: 3 } }), { tone: "hi" })}</g>`, { name: id, shapes: [record(A.body(F, meridian, { name: id, owner }))] });
  const up = [0, 0, 1];
  const NF = G.frameAlong(centre, up);
  const s0 = crown - 0.25;
  const s1 = crown + 1.6;
  put(unit, G.add3(centre, [0, 0, (s0 + s1) / 2]), S(G.disc(s0, s1, r * 0.45, NF, P), { tone: "mid" }), { bias: 0.2, name: `${id}.neck`, shapes: [record(A.disc(NF, s0, s1, r * 0.45, { name: `${id}.neck`, owner }))] });
  // diaphragm actuator: a shallow dome on a flat case
  const dome = [[s1, 0], [s1, r * 2.1], [s1 + 1.0, r * 2.1], [s1 + 1.0, r * 1.8], [s1 + 2.2, r * 0.9, 1], [s1 + 2.6, 0, 1]];
  put(unit, G.add3(centre, [0, 0, s1 + 1.3]), `<g data-valve="${tag}">${S(G.lathe(dome, NF, P, { steps: 40 }), { tone: "hi" })}</g>`, { bias: 0.3, name: `${id}.actuator`, shapes: [record(A.body(NF, dome, { name: `${id}.actuator`, owner }))] });
  const side = G.unit3(G.cross3(tangent, [0, 0, 1]));
  const sides = [1, -1].map((sg) => G.add3(centre, G.mul3(side, sg * (crown + 1.6)))).sort((p, q) => G.dot3(q, V) - G.dot3(p, V));
  VALVES.push({ tag, owner, unit, at: G.add3(centre, [0, 0, s1 + 2.6]), centre, sides });
  OBST.push({ c: centre, r: crown + 1, tag }, { c: G.add3(centre, [0, 0, s1 + 1.3]), r: r * 2.2, tag });
  // the pipe runs 0.15 into each end face, so the joint is a clean overlap rather than a coplanar contact
  return [along - r * 2.4, along + r * 2.4];
}

// Straight horizontal stretches of the drawn (filleted) line, as [from, to] arc lengths.
function straights(line, minLength) {
  const out = [];
  let walked = 0, start = null, dir = null;
  for (let i = 0; i < line.length - 1; i++) {
    const seg = G.sub3(line[i + 1], line[i]);
    const len = G.len3(seg);
    const d = G.unit3(seg);
    const flat = Math.abs(d[2]) < 0.02;
    if (flat && dir && G.dot3(d, dir) > 0.9999) { /* continues */ }
    else {
      if (start !== null && walked - start >= minLength) out.push([start, walked, dir]);
      start = flat ? walked : null;
      dir = flat ? d : null;
    }
    walked += len;
  }
  if (start !== null && walked - start >= minLength) out.push([start, walked, dir]);
  return out;
}
function chevrons(line, total, service, gaps) {
  const out = [];
  for (let s = 14; s < total - 10; s += 30) {
    if (gaps.some(([a, b]) => s > a - 4 && s < b + 4)) continue;
    const p = G.pointAlong(line, s);
    const t = G.tangentAlong(line, s);
    const a0 = at(G.sub3(p, G.mul3(t, 1.2)));
    const tip = at(G.add3(p, G.mul3(t, 1.2)));
    const dir = [tip[0] - a0[0], tip[1] - a0[1]];
    const n = Math.hypot(...dir) || 1;
    const ux = dir[0] / n;
    const uy = dir[1] / n;
    const size = 0.9 * KS;
    const c = at(p);
    const head = [c[0] + ux * size, c[1] + uy * size];
    const l = [c[0] - ux * size - uy * size, c[1] - uy * size + ux * size];
    const rr = [c[0] - ux * size + uy * size, c[1] - uy * size - ux * size];
    out.push({ s, d: `M${l[0].toFixed(1)} ${l[1].toFixed(1)}L${head[0].toFixed(1)} ${head[1].toFixed(1)}L${rr[0].toFixed(1)} ${rr[1].toFixed(1)}`, dir: [ux, uy], at: c });
  }
  return out;
}

function drawLine(id, kind, service, unit, ports, r, { valve } = {}) {
  const best = PLANS[id];
  const line = best.line;
  const total = G.pathLength(line);
  const gaps = [];
  if (valve) {
    // the middle of the horizontal straight stretch nearest the valve's own unit end
    // not on a leg pointing at the viewer: the pipe either side would then overlap itself on screen
    const all = straights(line, r * 6 + 4).map(([a0, b0, d]) => [a0 + 2, b0 - 2, d]);
    const side = all.filter(([, , d]) => Math.abs(G.dot3(d, V)) < 0.62);
    const runs = side.length ? side : all;
    runs.sort((p, q) => (valve.end === "from" ? p[0] - q[0] : q[1] - p[1]));
    const zoneClear = (along) => { const c = G.pointAlong(line, along); return [0, 4, 8, 12].every((h) => OBST.every((o) => G.len3(G.sub3(o.c, G.add3(c, [0, 0, h]))) > o.r + 5) && ROUTED.every((o) => o.id === id || o.samples.every((q) => G.len3(G.sub3(q, G.add3(c, [0, 0, h]))) > o.r + 4.5))); };
    let spot = null;
    for (const [a0, b0] of runs) {
      const mid = (a0 + b0) / 2;
      for (let d = 0; d <= (b0 - a0) / 2 - r * 2.4 - 9 && spot === null; d += 1) for (const sg of [1, -1]) if (spot === null && zoneClear(mid + sg * d)) spot = mid + sg * d;
      if (spot !== null) break;
    }
    if (spot === null) {
      // best effort: the spot whose valve and marker zone stays furthest from every other line, valve and marker
      let bestScore = -Infinity;
      const margin = (along) => { const c = G.pointAlong(line, along); let m = Infinity; for (const h of [0, 4, 8, 12]) { const q = G.add3(c, [0, 0, h]); for (const o of OBST) m = Math.min(m, G.len3(G.sub3(o.c, q)) - o.r); for (const o of ROUTED) if (o.id !== id) for (const w of o.samples) m = Math.min(m, G.len3(G.sub3(w, q)) - o.r); } return m; };
      for (const [a0, b0] of runs) for (let c = a0 + r * 2.4 + 2; c <= b0 - r * 2.4 - 2; c += 1) { const m = margin(c); if (m > bestScore) { bestScore = m; spot = c; } }
      if (spot === null && runs[0]) spot = (runs[0][0] + runs[0][1]) / 2;
    }
    if (spot !== null) gaps.push(valveOn(id, valve.unit, line, spot, r, valve.tag));
  }
  STRAIGHTS[id] = straights(line, 4).map(([a0, b0]) => [a0 + 8, b0 - 8]).filter(([a0, b0]) => b0 > a0)
    .flatMap(([a0, b0]) => { const cut = []; let from = a0; for (const [g0, g1] of [...gaps].sort((p, q) => p[0] - q[0])) { if (g1 < from || g0 > b0) continue; if (g0 - 10 > from) cut.push([from, g0 - 10]); from = Math.max(from, g1 + 10); } if (b0 > from) cut.push([from, b0]); return cut; });
  const breaks = gaps.flatMap(([g0, g1]) => [g0 - 1.5, g1 + 1.5]).filter((b) => b > 0.5 && b < total - 0.5);
  const pieces = tubePieces(line, r, P, { maxLength: 8, spacing: 2, gaps, breaks, caps: true });
  // Only the supporting crossbeams intentionally touch the recycle pipe; columns and rails keep full clearance checks.
  R.route(id, line, r, { owner: id, gaps, ends: [true, true], rims: [r, r], piece: unit, touch: [`${id}.support*`, ...(id === "S8b" ? [(name) => name.startsWith("rack.") && name.endsWith(".crossbeam")] : [])] });
  const marks = chevrons(line, total, service, gaps);
  // per chunk: the tube, then its flow pulse and chevrons, so pulses sit in the tube's own depth slot
  let screenRun = 0;
  const chunks = [];
  pieces.forEach((part, index) => {
    const pts = part.points.map(at);
    const d = k.pathOf(pts);
    const len = pts.reduce((sum, p, i) => (i ? sum + Math.hypot(p[0] - pts[i - 1][0], p[1] - pts[i - 1][1]) : 0), 0);
    const from = part.from ?? 0;
    const to = part.to ?? total;
    const mine = marks.filter((m) => m.s >= from && m.s < to);
    const svg = `<g data-line="${id}" data-service="${service}">${tubeSvg(part, { tone: "hi" })}<path class="tour-flow" data-flow-line="${id}" data-run="${screenRun.toFixed(1)}" d="${d}"/>${mine.map((m) => `<path class="tour-chev" data-chev="${id}" data-dir="${m.dir.map((v) => v.toFixed(3)).join(",")}" d="${m.d}"/>`).join("")}</g>`;
    chunks.push({ index, start: pts[0], end: pts[pts.length - 1], run: screenRun, len });
    screenRun += len;
    put(unit, part.mid, svg, { name: `${id}:${index}`, route: id, chunk: index, shapes: [A.tube(part.points, part.radii)] });
  });
  FLOW.push({ id, kind, service, unit, from: ports[0].unit, to: ports[1].unit, start: at(ports[0].p), end: at(ports[1].p), startWorld: ports[0].p, endWorld: ports[1].p, length: screenRun, chunks: chunks.length, chevrons: marks.length, line });
  return { line, total };
}

const LINES = {};
const STRAIGHTS = {};
const ownersOf = (id) => (id === "BL" ? [] : [id]);
const finalOnStream = (sid) => DATA.tags.find((t) => t.kind === "final_element" && t.stream === sid && t.connected);
for (const s of DATA.streams) {
  const owners = [s.from === "BL" ? [`BL-${s.id}`] : ownersOf(s.from), s.to === "BL" ? [`BL-${s.id}`] : ownersOf(s.to)];
  const markersOn = DATA.tags.filter((t) => t.attach[0] === "stream" && t.attach[1] === s.id && !(t.kind === "final_element" && t.connected)).length;
  JOBS.push({ id: s.id, a: PORTS[`${s.id}:from`], b: PORTS[`${s.id}:to`], r: RP, owners, need: { valve: Boolean(finalOnStream(s.id)), markers: markersOn } });
}
for (const [uid, u] of Object.entries(UTIL)) {
  const owners = u.data.role === "return" ? [[u.data.unit], [`UT-${uid}`]] : [[`UT-${uid}`], [u.data.unit]];
  const ft = DATA.tags.find((t) => t.tag === u.data.tag);
  JOBS.push({ id: uid, a: u.from, b: u.to, r: RU, owners, need: { valve: u.data.role !== "return" && Boolean(ft && ft.connected), markers: 0 } });
}
// short lines first: their ends are fixed by the nozzles, and the long runs then route around them
JOBS.sort((p, q) => (p.id === "S8b" ? -1 : q.id === "S8b" ? 1 : G.len3(G.sub3(p.a.p, p.b.p)) - G.len3(G.sub3(q.a.p, q.b.p))));
const PLANS = planRoutes();
for (const s of DATA.streams) {
  const fe = finalOnStream(s.id);
  const valve = fe ? { tag: fe.tag, unit: fe.unit, end: fe.unit === s.from ? "from" : "to" } : null;
  LINES[s.id] = drawLine(s.id, "stream", s.service, s.from === "BL" ? s.to : s.from, [PORTS[`${s.id}:from`], PORTS[`${s.id}:to`]], RP, { valve });
}
for (const [uid, u] of Object.entries(UTIL)) {
  const tag = DATA.tags.find((t) => t.tag === u.data.tag);
  const valve = u.data.role !== "return" && tag && tag.connected ? { tag: u.data.tag, unit: u.data.unit, end: "from" } : null;
  LINES[uid] = drawLine(uid, "utility", u.data.service, u.data.unit, [u.from, u.to], RU, { valve });
}

// ------------------------------------------------------------------ instrument markers
const MARKERS = [];
// The first candidate position clear of every other drawn line (a marker must not sit on a pipe it does not belong to).
function clearSpot(candidates, rad, own, ownTag) {
  for (const c of candidates) {
    if (OBST.some((o) => o.tag !== ownTag && G.len3(G.sub3(o.c, c)) < o.r + rad + 1)) continue;
    const ok = ROUTED.every((o) => o.id === own || o.samples.every((q) => G.len3(G.sub3(q, c)) > rad + o.r + 1.6 && Math.hypot(q[0] - c[0], q[1] - c[1]) > o.r + 1.2));
    if (ok) return c;
  }
  return candidates[0];
}
const SHELL_Z = { pressure: 0.85, temperature: 0.5, level: 0.25, composition: 0.6, flow: 0.4, power: 0.9 };
const perLine = {};
const MARKER_AT = {};
for (const t of DATA.tags) {
  let centre;
  let basis;
  const valve = VALVES.find((v) => v.tag === t.tag);
  const g = UNIT_GEOM[t.unit];
  let valveStem = 0;
  let onStraight = true;
  let sideStem = null;
  if (valve) {
    const lifts = [0, 3, 6, 9];
    const spots = [...lifts.map((h) => G.add3(valve.at, [0, 0, 1.6 + h])), ...valve.sides];
    centre = clearSpot(spots, 1.6, valve.owner, t.tag);
    valveStem = lifts[spots.indexOf(centre)] ?? 0;
    basis = "at its valve symbol on the line (placeholder position)";
  } else if (t.attach[0] === "stream" && LINES[t.attach[1]]) {
    const { line, total } = LINES[t.attach[1]];
    const s = DATA.streams.find((x) => x.id === t.attach[1]);
    const fromOwner = s.from === t.unit;
    const count = (perLine[t.attach[1]] = (perLine[t.attach[1]] ?? 0) + 1);
    const want = fromOwner ? total * (0.3 + 0.16 * (count - 1)) : total * (0.7 - 0.16 * (count - 1));
    // nearest point on a horizontal straight stretch (clear of valves and bends) so the stem stands upright
    let along = want;
    let bestD = Infinity;
    const lineId = t.attach[1];
    const clearAt = (c) => ROUTED.every((o) => o.id === lineId || o.samples.every((q) => G.len3(G.sub3(q, c)) > o.r + 1.6 + 1.6));
    for (const [a0, b0] of STRAIGHTS[lineId] ?? []) {
      for (let c = a0; c <= b0; c += 1) {
        const taken = (MARKER_AT[lineId] ?? []).some((o) => Math.abs(o - c) < 8);
        if (taken || Math.abs(c - want) >= bestD) continue;
        const top = G.add3(G.pointAlong(line, c), [0, 0, RP + 5.4]);
        if (!clearAt(top) || !clearAt(G.add3(top, [0, 0, -3])) || [0, 2.7, 5.4].some((h) => OBST.some((o) => G.len3(G.sub3(o.c, G.add3(top, [0, 0, -h]))) < o.r + 3.2))) continue;
        bestD = Math.abs(c - want);
        along = c;
      }
    }
    (MARKER_AT[t.attach[1]] ??= []).push(along);
    onStraight = bestD < Infinity;
    const p = G.pointAlong(line, along);
    if (onStraight) centre = G.add3(p, [0, 0, RP + 5.4]);
    else {
      // no clear straight: the clear spot nearest the wanted one, with a stem out to the side
      const sideAt = (c) => {
        const tan = G.tangentAlong(line, c);
        let sd = G.unit3(G.cross3(tan, [0, 0, 1]));
        if (G.len3(G.cross3(tan, [0, 0, 1])) < 0.2) sd = G.unit3(G.cross3(tan, [1, 0, 0]));
        if (G.dot3(sd, V) < 0) sd = G.mul3(sd, -1);
        return { sd, ball: G.add3(G.pointAlong(line, c), G.mul3(sd, RP + 5.4)) };
      };
      let bestC = null;
      for (let c = 8; c <= total - 8; c += 1) {
        if ((MARKER_AT[lineId] ?? []).some((o) => o !== along && Math.abs(o - c) < 8)) continue;
        const { sd, ball } = sideAt(c);
        const pts = [ball, G.add3(G.pointAlong(line, c), G.mul3(sd, RP + 2.7))];
        if (!pts.every((q) => clearAt(q) && OBST.every((o) => G.len3(G.sub3(o.c, q)) > o.r + 3.2))) continue;
        if (bestC === null || Math.abs(c - want) < Math.abs(bestC - want)) bestC = c;
      }
      if (bestC !== null) { along = bestC; MARKER_AT[lineId][MARKER_AT[lineId].length - 1] = bestC; }
    }
    const p2 = G.pointAlong(line, along);
    if (!onStraight) {
      const tan = G.tangentAlong(line, along);
      let side = G.unit3(G.cross3(tan, [0, 0, 1]));
      if (G.len3(G.cross3(tan, [0, 0, 1])) < 0.2) side = G.unit3(G.cross3(tan, [1, 0, 0]));
      if (G.dot3(side, V) < 0) side = G.mul3(side, -1);
      centre = G.add3(p2, G.mul3(side, RP + 5.4));
      sideStem = { from: G.add3(p2, G.mul3(side, RP)), dir: side };
    }
    basis = `on stream ${t.attach[1]} (placeholder position along the line)`;
  } else if (t.tag === "SC-212" && g.motor) {
    centre = G.add3(g.motor.at, [Math.cos(VIEW_ANGLE) * 5.4, Math.sin(VIEW_ANGLE) * 5.4, 0]);
    basis = "on the agitator motor (no replay source)";
  } else if (t.unit && (g.kind === "reactor" || g.kind === "separator" || g.kind === "stripper")) {
    const n = (g.markerCount = (g.markerCount ?? 0) + 1);
    const z = g.zb + (g.zt - g.zb) * (SHELL_Z[t.variable] ?? 0.7) + (n % 2) * 2;
    let a = VIEW_ANGLE + (n % 2 ? 1 : -1) * (50 + 14 + Math.floor((n - 1) / 2) * 16) * DEG;
    centre = G.pointOf(g.F, z, g.R + 1.6, a);
    for (let k2 = 0; k2 < 14 && (OBST.some((o) => G.len3(G.sub3(o.c, centre)) < o.r + 2.2) || ROUTED.some((o) => o.samples.some((w) => G.len3(G.sub3(w, centre)) < o.r + 3.4))); k2++) {
      a += (n % 2 ? 1 : -1) * 12 * DEG;
      centre = G.pointOf(g.F, z, g.R + 1.6, a);
    }
    basis = "on the unit shell; height by measured variable (placeholder)";
  } else if (g.kind === "compressor") {
    centre = G.pointOf(g.F, 0, 10 + 1.6, 0.45);
    basis = "on the compressor casing (placeholder)";
  } else if (g.kind === "condenser") {
    centre = G.pointOf(g.F, g.L * 0.55, g.r + 1.6, Math.PI / 2 + 0.6);
    basis = "on the exchanger shell (placeholder)";
  } else {
    centre = G.pointOf(g.F, g.L * 0.5, g.r + 1.6, Math.PI / 2 + 0.5);
    basis = "on the header (placeholder)";
  }
  if (valveStem) discAt(t.unit, G.frameAlong(valve.at, [0, 0, 1]), -0.1, valveStem + 0.05, 0.35, { tone: "mid" }, { name: `tag.${t.tag}.stem`, owner: valve.owner });
  const stemFrom = valve ? null : t.attach[0] === "stream" && LINES[t.attach[1]] ? (sideStem ? sideStem.from : G.sub3(centre, [0, 0, 5.4])) : null;
  if (stemFrom) {
    const F = G.frameAlong(stemFrom, sideStem ? sideStem.dir : [0, 0, 1]);
    discAt(t.unit, F, -0.1, 3.8, 0.35, { tone: "mid" }, { name: `tag.${t.tag}.stem`, owner: t.attach[1] });
  }
  const ring = `<path class="tour-ring" data-ring="${t.tag}" d="${k.pathOf(Array.from({ length: 33 }, (_, i) => { const c = at(centre); const rr = 1.6 * KS + 2.5; return [c[0] + rr * Math.cos((i / 32) * Math.PI * 2), c[1] + rr * Math.sin((i / 32) * Math.PI * 2)]; }), true)}"/>`;
  ballAt(t.unit, centre, 1.6, { tone: "hi", name: `tag.${t.tag}`, owner: stemFrom ? t.attach[1] : t.unit, cls: "tour-marker", extra: ring, bias: 0.4 });
  MARKERS.push({ tag: t.tag, unit: t.unit, centre, screen: at(centre), basis });
  OBST.push({ c: centre, r: 1.6 });
}

// ------------------------------------------------------------------ pipe supports under elevated runs
// A T-post from the ground to the underside of every long horizontal run above 22 units, every ~36 units, where the
// post and its foot are clear of every machine, other line, valve and marker. Placeholder structure; it holds the
// pipe for the audit's support check. The long recycle line instead rests on a framed overhead corridor.
const SUPPORTS = [];
const rackTop = RACK.z - RP;
for (let x = RACK.x[0]; x <= RACK.x[1]; x += 5) {
  if (RACK.frames.some((f) => Math.abs(f.crossbeam[0] - x) < 35)) continue;
  const segments = RACK.y.map((y) => [at([x, y, 0]), at([x, y, rackTop])]);
  segments.push(RACK.y.map((y) => at([x, y, rackTop])));
  if (ROUTED.some((o) => o.corners.some((p) => segments.some(([a, b]) => segmentDistance2(p, a, b) < (o.r + .8) * KS + 5)))) continue;
  const columns = RACK.y.map((y) => [x, y, 0]);
  for (const [i, y] of RACK.y.entries()) {
    boxAt("rack", [x - 2, y - 2, 0], [x + 2, y + 2, .8], { tone: "lo" }, { name: `rack.${x}.foot${i}`, owner: "rack" });
    boxAt("rack", [x - .65, y - .65, .8], [x + .65, y + .65, rackTop - 1.5], { tone: "mid" }, { name: `rack.${x}.column${i}`, owner: "rack" });
  }
  boxAt("rack", [x - .8, RACK.y[0] - .65, rackTop - 1.5], [x + .8, RACK.y[1] + .65, rackTop], { tone: "mid" }, { name: `rack.${x}.crossbeam`, owner: "rack" });
  RACK.frames.push({ columns, crossbeam: [x, (RACK.y[0] + RACK.y[1]) / 2, rackTop] });
}
for (const [i, y] of RACK.y.entries()) {
  boxAt("rack", [RACK.x[0], y - .55, rackTop - 3], [RACK.x[1], y + .55, rackTop - 1.5], { tone: "mid" }, { name: `rack.rail${i}`, owner: "rack" });
  RACK.rails.push([[RACK.x[0], y, rackTop - 1.5], [RACK.x[1], y, rackTop - 1.5]]);
}
for (const f of FLOW) {
  if (f.id === "S8b") continue;
  const r = f.kind === "utility" ? RU : RP;
  for (const [a0, b0, dir] of straights(f.line, 30)) {
    const z = G.pointAlong(f.line, a0)[2];
    if (z < 22 || Math.min(Math.abs(dir[0]), Math.abs(dir[1])) > 0.02) continue; // axis-aligned runs only
    for (let s0 = a0 + 10; s0 <= b0 - 10; s0 += 36) {
      const p = G.pointAlong(f.line, s0);
      const top = p[2] - r;
      const ok = (q) => VOLUMES.every((v) => volumeDistance(v, q) > 3) && ROUTED.every((o) => o.id === f.id || o.samples.every((w) => G.len3(G.sub3(w, q)) > o.r + 2.4)) && OBST.every((o) => G.len3(G.sub3(o.c, q)) > o.r + 2.4);
      let clear = true;
      for (let zz = 1; zz < top - 0.5 && clear; zz += 1.5) clear = ok([p[0], p[1], zz]);
      // keep the post off other lines on screen too (a post drawn across a bend reads as a joint)
      const a2 = at([p[0], p[1], 0]), b2 = at([p[0], p[1], top]);
      if (clear) clear = ROUTED.every((o) => o.id === f.id || o.corners.every((w) => segmentDistance2(w, a2, b2) > (o.r + 1.5) * KS + 4));
      if (!clear) continue;
      const id = `${f.id}.support${SUPPORTS.length}`;
      const tan = G.tangentAlong(f.line, s0);
      const along = Math.abs(tan[0]) > Math.abs(tan[1]) ? "x" : "y";
      const w = 4.4;
      const plate = along === "x" ? [[p[0] - 0.9, p[1] - w / 2, top - 0.8], [p[0] + 0.9, p[1] + w / 2, top]] : [[p[0] - w / 2, p[1] - 0.9, top - 0.8], [p[0] + w / 2, p[1] + 0.9, top]];
      boxAt(f.unit, [p[0] - 1.6, p[1] - 1.6, 0], [p[0] + 1.6, p[1] + 1.6, 0.8], { tone: "lo" }, { name: `${id}.foot`, owner: id });
      discAt(f.unit, G.frameOf([p[0], p[1], 0], [0, 0, 1], [1, 0, 0], [0, 1, 0]), 0.8, top - 0.8, 0.55, { tone: "mid" }, { name: `${id}.post`, owner: id });
      boxAt(f.unit, plate[0], plate[1], { tone: "mid" }, { name: `${id}.shoe`, owner: id });
      SUPPORTS.push({ id, line: f.id, at: p });
      OBST.push({ c: [p[0], p[1], top / 2], r: 1.2 });
    }
  }
}

// ------------------------------------------------------------------ settle depth order, optional audit
A.settle(R, P);
R.items.sort((a, b) => a.key - b.key);
const groups = R.items.map((item) => `<g class="it" data-unit="${item.unit || item.piece}"${item.route ? ` data-route="${item.route}"` : ""} data-name="${item.name}">${item.svg}</g>`);

let geometry = null;
if (AUDIT) {
  const started = Date.now();
  // Explicit, reported excusal (kit "allow"): a valve body against the chunks of its own pipe, which meet it face to
  // end cap; the raycast reads that shared plane both ways by a few px². Listed in the report, not hidden by a key bias.
  const ALLOW = VALVES.map((v) => [`${v.owner}.valve.${v.tag}`, `${v.owner}:*`]);
  const result = A.audit(R, P, { crowd: [], allow: ALLOW });
  const mounts = A.mountsOf(R.tubes, R.solids);
  // Which unit each drawn line lands on, read from the audit's own mount search (the solid each end sits on).
  const unitOfShape = (name) => (name || "").split(".")[0];
  const landed = {};
  for (const tube of R.tubes) {
    const routeId = tube.name.split("#")[0].split(":")[0];
    const ends = mounts.get(tube) ?? [];
    ends.forEach((m, index) => {
      if (!tube.tips || !tube.tips[index]) return;
      const key = `${routeId}:${index ? "end" : "start"}`;
      landed[key] = { mount: m ? m.shape.name : null, unit: m ? unitOfShape(m.shape.owner || m.shape.name) : null, landed: Boolean(m && m.landed) };
    });
  }
  const count = (list) => (Array.isArray(list) ? list.length : 0);
  geometry = {
    tool: "anatomy kit/audit.mjs (vendored, commit e6600ff): audit(R, P)",
    items: R.items.length, tubes: R.tubes.length, solids: R.solids.length,
    failures: A.failures(result),
    counts: {
      clearance: count(result.clearance), terminals: count(result.terminals), loose_ends: result.loose.filter((e) => !e.free).length,
      folds: count(result.folds), crowding: count(result.crowding), self_overlap: count(result.self), wobble: count(result.wobble),
      stand_in_shapes: count(result.cover), unsupported_solids: result.supports.loose.length, hanging_tubes: (result.supports.hanging ?? []).length,
      sunk_pairs: result.supports.sunk.length, depth_order: result.depth.problems.length, items_without_shape: result.depth.missing.length,
    },
    landed,
    allowed: {
      rule: "a valve body against chunks of its own pipe, which meet it face to end cap", patterns: ALLOW,
      excused_depth_pairs: (() => {
        const raw = A.depthOrder(R.settled.items, P, { overlaps: R.settled.overlaps, solved: R.settled.solved, allow: [] });
        return raw.problems.filter((d) => !result.depth.problems.some((x) => x.front === d.front && x.back === d.back))
          .map((d) => ({ front: d.front, back: d.back, px2: +d.area.toFixed(2), other_way_px2: +(d.against ?? 0).toFixed(2) }));
      })(),
    },
    report: A.report(result).split("\n"),
  };
}

// ------------------------------------------------------------------ frame: crop the viewBox to what was drawn
const VB = (() => {
  const ys = [];
  for (const f of FLOW) for (const p of f.line) ys.push(at(p)[1]);
  for (const g of Object.values(UNIT_GEOM)) ys.push(at(g.label)[1] - 30);
  for (const x of [GROUND.x, GROUND.x + GROUND.w]) for (const y of [GROUND.y, GROUND.y + GROUND.d]) ys.push(at([x, y, -3])[1]);
  const top = Math.min(...ys) - 12;
  const bottom = Math.max(...ys) + 12;
  return [0, Math.floor(top), W, Math.ceil(bottom - top)];
})();

// ------------------------------------------------------------------ live data for the page
const unitGeom = Object.fromEntries(Object.entries(UNIT_GEOM).map(([id, g]) => {
  const corners = [];
  for (const x of [g.focus[0][0], g.focus[1][0]]) for (const y of [g.focus[0][1], g.focus[1][1]]) for (const z of [g.focus[0][2], g.focus[1][2]]) corners.push(at([x, y, z]));
  const xs = corners.map((c) => c[0]);
  const ys = corners.map((c) => c[1]);
  return [id, { label: at(g.label), box: [Math.min(...xs), Math.min(...ys), Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys)] }];
}));
const liquids = Object.fromEntries(Object.entries(WINDOW_LEVELS).map(([id, w]) => [id, w]));
const levelTag = { "R-101": "LT-108", "V-101": "LT-112", "C-101": "LT-115" };
const lotoPoints = DATA.loto.points.map((p) => {
  let where;
  if (p.kind === "bl") where = POSTS[`BL-${p.target.stream}`].lock;
  else if (p.kind === "motor" || p.kind === "agitator") where = G.add3(UNIT_GEOM[p.target.unit].motor.at, p.kind === "motor" ? [0, 0, 1.5] : [0, -4.4, 0]);
  else where = POSTS[`UT-${p.target.utility}`].port.p;
  return { id: p.id, n: p.n, at: at(where) };
});
const sceneOut = {
  schema: "pid-interactive-tour-scene/0", theme: THEME, viewBox: VB, projection: P,
  lines: FLOW.map(({ line, ...rest }) => rest),
  units: unitGeom, markers: MARKERS.map(({ centre, ...rest }) => rest), loto: lotoPoints,
  posts: Object.values(POSTS).map((p) => ({ id: p.id, unit: p.unit, at: at(p.port.p), label: p.label })),
  windows: liquids,
  rack: RACK, routes: Object.fromEntries(Object.entries(PLANS).map(([id, p]) => [id, p.simple])),
};
mkdirSync(OUT, { recursive: true });
writeFileSync(join(OUT, THEME === "light" ? "scene-light.json" : "scene.json"), JSON.stringify(sceneOut, null, 1));

// What is drawn, in viewBox coordinates, for the page's label placement (labels go where nothing is drawn): every
// line as a projected polyline with its screen width, every machine and post as the hull of its envelope.
const hull2 = (pts) => {
  const q = pts.slice().sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const cr = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const lo = [], hi = [];
  for (const p of q) { while (lo.length >= 2 && cr(lo[lo.length - 2], lo[lo.length - 1], p) <= 0) lo.pop(); lo.push(p); }
  for (const p of q.reverse()) { while (hi.length >= 2 && cr(hi[hi.length - 2], hi[hi.length - 1], p) <= 0) hi.pop(); hi.push(p); }
  return lo.slice(0, -1).concat(hi.slice(0, -1));
};
const round1 = (p) => [Math.round(p[0] * 10) / 10, Math.round(p[1] * 10) / 10];
const OCC = {
  lines: FLOW.map((f) => ({ id: f.id, w: +(2 * (f.kind === "utility" ? RU : RP) * KS).toFixed(1), pts: G.resample(f.line, 4).map((p) => round1(at(p))) })),
  bodies: VOLUMES.map((v) => {
    const pts = [];
    if (v.kind === "vcyl") for (let i = 0; i < 16; i++) for (const z of [v.z0, v.z1]) pts.push(at([v.x + v.r * Math.cos((i / 16) * Math.PI * 2), v.y + v.r * Math.sin((i / 16) * Math.PI * 2), z]));
    else if (v.kind === "hcyl") for (let i = 0; i < 16; i++) for (const x of [v.x0, v.x1]) pts.push(at([x, v.y + v.r * Math.cos((i / 16) * Math.PI * 2), v.z + v.r * Math.sin((i / 16) * Math.PI * 2)]));
    else for (const x of [v.min[0], v.max[0]]) for (const y of [v.min[1], v.max[1]]) for (const z of [v.min[2], v.max[2]]) pts.push(at([x, y, z]));
    const owner = v.owner.startsWith("BL-") ? (POSTS[v.owner]?.unit ?? v.owner) : v.owner.startsWith("UT-") ? (POSTS[v.owner]?.unit ?? v.owner) : v.owner;
    return { unit: owner, hull: hull2(pts).map(round1) };
  }),
};
const live = {
  viewBox: VB, P, units: unitGeom, markers: MARKERS.map((m) => ({ tag: m.tag, unit: m.unit, at: m.screen })),
  lines: FLOW.map((f) => ({ id: f.id, kind: f.kind, service: f.service, unit: f.unit, from: f.from, to: f.to, length: f.length })),
  windows: liquids, levelTag, loto: lotoPoints, glass: GLASS, occ: OCC,
  posts: Object.values(POSTS).map((p) => ({ id: p.id, unit: p.unit, at: at(p.port.p) })),
};

// ------------------------------------------------------------------ page
const esc = (t) => String(t ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const rgb = (c, theme) => {
  // service colours from the Blender flow legend; on paper they are darkened enough to read as lines
  const f = theme === "light" ? 0.78 : 1;
  return `rgb(${c.map((v) => Math.round(v * 255 * f)).join(",")})`;
};
const serviceCss = Object.entries(DATA.services).map(([s, v]) => `[data-service="${s}"]{--svc:${rgb(v.rgb, THEME)}}`).join("");
const font = readFileSync(join(ROOT, "assets", "fonts", "AtkinsonHyperlegible-Regular.ttf")).toString("base64");
const css = readFileSync(join(HERE, "tour.css"), "utf8");
const backSvg = `<svg xmlns="http://www.w3.org/2000/svg" class="iso-svg tour-svg" viewBox="${VB.join(" ")}" aria-hidden="true" data-layer="ground">${back.join("")}</svg>`;
const mainSvg = `<svg xmlns="http://www.w3.org/2000/svg" class="iso-svg tour-svg" viewBox="${VB.join(" ")}" role="img" aria-labelledby="fig-title fig-desc" data-layer="plant"><title id="fig-title">Isometric cutaway of the Tennessee Eastman process unit</title><desc id="fig-desc">Six process units drawn as cut-away machines: the feed header, the agitated reactor with its cooling coil, the product condenser, the vapour-liquid separator, the recycle compressor and the product stripper with its trays. Pipes are coloured by service with moving pulses in the flow direction. Geometry is a placeholder; connections come from the process model.</desc><defs>${clips.join("")}</defs><g class="tour-plant">${groups.join("")}</g><g class="tour-loto-layer" aria-hidden="true"></g></svg>`;

const units = DATA.tour_order.map((id) => unitById[id]);
const legend = Object.entries(DATA.services).map(([s, v]) => `<li data-service="${s}"><svg class="tour-swatch" viewBox="0 0 28 10" aria-hidden="true"><path d="M2 5h20M18 2l4 3-4 3"/></svg>${esc(v.label)}</li>`).join("");
const body = `
<a class="tour-skip" href="#tour-panel">Skip to the controls</a>
<header class="tour-head">
  <p class="tour-kicker">Draft proof of concept · not reviewed by an operator</p>
  <h1>Tennessee Eastman unit: an interactive process tour</h1>
  <p class="tour-badge">${esc(DATA.badge)}</p>
  <p class="tour-lede">A walk through a published benchmark process for new-operator orientation. Pick a unit to see why it exists, which instruments to watch and what the recorded replay shows. The connections, tags, purpose sentences, alarm limits and every number come from this repository's data files; shapes, sizes, heights and pipe routes are placeholders.</p>
  <p class="tour-theme"><a href="${THEME === "light" ? "te-tour.html" : "te-tour-light.html"}">${THEME === "light" ? "Dark theme" : "Light theme"}</a></p>
</header>
<div class="tour-layout">
<div class="tour-left">
<figure class="iso-figure tour-figure" data-mode="flow">
  <div class="iso-plate tour-plate">
    <div class="iso-plate-corners" aria-hidden="true"><span class="iso-plate-corner" data-corner="fig">Fig 1</span><span class="iso-plate-corner" data-corner="title">TE unit · cutaway</span><span class="iso-plate-corner" data-corner="hint" data-hint>Select a unit</span><span class="iso-plate-corner" data-corner="readout" data-readout>—</span></div>
    <div class="tour-stage" style="--vb-aspect:${(VB[2] / VB[3]).toFixed(4)}" tabindex="0" role="group" aria-roledescription="process figure" aria-label="Process figure. Arrow keys move between units in flow order, Escape returns to the overview." data-stage>
      ${backSvg}${mainSvg}
      <div class="tour-labels" data-labels></div>
    </div>
  </div>
</figure>
  <article class="tour-card" data-card aria-live="polite"></article>
  <aside class="iso-legend tour-legend" aria-label="Legend">
    <ul class="tour-services" aria-label="Line colours by service">${legend}</ul>
    <p class="tour-legend-note">Pulses move in the flow direction given by the model. Their speed follows the recorded flow where the stream has a flow tag (${esc(DATA.streams.filter((s) => s.flow_tag).map((s) => s.flow_tag).join(", "))}); other lines move at a constant, illustrative rate. Cooling water and steam are inferred from valve descriptions; they are not streams in the model.</p>
    <ul class="tour-states" aria-label="Instrument ring colours"><li data-state="normal">in normal band</li><li data-state="outside_band">outside normal band (display aid, not a limit)</li><li data-state="alarm">above a published alarm limit</li><li data-state="not_connected">not connected (no replay source)</li></ul>
  </aside>
</div>
<section class="tour-panel" id="tour-panel" aria-label="Tour controls">
  <div class="tour-modes" role="group" aria-label="Mode">
    <button type="button" data-mode-button="flow" aria-pressed="true">Process flow</button>
    <button type="button" data-mode-button="loto" aria-pressed="false">Lockout/tagout mockup</button>
  </div>
  <div class="tour-units" role="group" aria-label="Units in flow order">
    <button type="button" data-unit-button="" aria-pressed="true">Overview</button>
    ${units.map((u, i) => `<button type="button" data-unit-button="${u.id}" aria-pressed="false"><span class="tour-n">${i + 1}</span>${esc(u.id)} <span class="tour-uname">${esc(u.name)}</span></button>`).join("")}
  </div>
  <div class="tour-replay" data-flow-only>
    <div class="tour-runs" role="radiogroup" aria-label="Recorded replay">
      ${["normal", "fault6"].filter((id) => DATA.replay.runs[id]).map((id) => `<label><input type="radio" name="run" value="${id}"${id === "normal" ? " checked" : ""}> ${esc(id === "normal" ? "Normal operation" : "Fault 6: loss of A feed")}</label>`).join("")}
    </div>
    <div class="tour-scrub">
      <button type="button" data-play aria-label="Play the replay">Play</button>
      <input type="range" min="0" max="${DATA.replay.runs.normal.samples - 1}" step="1" value="0" data-scrub aria-label="Replay sample">
    </div>
    <p class="tour-time" data-time aria-live="off"></p>
    <p><button type="button" data-jump-alarm>Jump to the first alarm in fault 6</button></p>
    <div class="tour-alarms" data-alarms aria-live="polite"></div>
  </div>
  <div class="tour-loto" data-loto-only hidden>
    <p class="tour-warning"><strong>Design mockup, not a procedure.</strong> ${esc(DATA.loto.status.replace(/^DESIGN MOCKUP: i/, "I"))}. Nothing here may be used as a lockout/tagout procedure.</p>
    <p>Select inferred isolation points to see which energy sources remain and where flow stops, computed from the stream graph. The pulses here run at a constant rate; they are not the replay.</p>
    <div class="tour-points" role="group" aria-label="Inferred isolation points">
      ${DATA.loto.points.map((p) => `<button type="button" data-loto="${esc(p.id)}" aria-pressed="false"><span class="tour-n">${p.n}</span>${esc(p.text)} <span class="tour-inf">inferred</span></button>`).join("")}
    </div>
    <p><button type="button" data-loto-all>Isolate all</button> <button type="button" data-loto-none>Clear</button></p>
    <div class="tour-energy" data-energy aria-live="polite"></div>
  </div>
</section>
</div>
<footer class="tour-foot">
  <h2>What this is and is not</h2>
  <p>${esc(DATA.full_disclaimer.replace(/Claude/g, "an AI assistant"))}</p>
  <p>The tour's text around the numbers (the short function lines, captions and this page) was written with AI assistance from the data files; each purpose sentence comes from <code>data/te_unit_purposes.json</code>, which cites the simulator lines it restates. Nothing here has been reviewed by an operator. Hazard citations are a prototype keyword match against public incident records: mechanism analogies, not a hazard analysis.</p>
  <p>Data: Tennessee Eastman process after Downs and Vogel (1993); simulator code and recorded runs by the Large Scale Systems Research Laboratory (Professor Richard Braatz, Director), University of Illinois. This page embeds values from their test runs d00_te.dat and d06_te.dat. Copyright (c) 1998-2002 The Board of Trustees of the University of Illinois. All rights reserved. Redistributed under the permission notice in their TE_process archive readme; their names do not endorse this work. THE SOFTWARE IS PROVIDED &quot;AS IS&quot;, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE CONTRIBUTORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE. (Full notice: <code>drafts/interactive-tour/TE_DATA_NOTICE.txt</code>.) Drawing technique adapted from the MIT-licensed <a href="https://github.com/wheresryan22/anatomy">anatomy</a> skill by Ryan. Labels in Atkinson Hyperlegible (SIL Open Font License 1.1).</p>
</footer>`;

const modelSrc = readFileSync(join(HERE, "model.mjs"), "utf8").replace(/^export /gm, "");
const liveSrc = readFileSync(join(HERE, "live.js"), "utf8");
const pageData = { data: { ...DATA, sources: undefined }, live };
const script = `const TOUR = ${JSON.stringify(pageData)};\n${modelSrc}\n${liveSrc}`;
const page = k.pageHtml({ title: "TE unit: interactive process tour (draft)", theme: THEME, body: `<style>@font-face{font-family:"Atkinson Hyperlegible";src:url(data:font/ttf;base64,${font}) format("truetype");font-display:block}${css}${serviceCss}</style>${body}`, script, width: 1520 });
const name = THEME === "light" ? "te-tour-light.html" : "te-tour.html";
writeFileSync(join(OUT, name), page);
console.log(`wrote out/interactive_tour/${name} ${(page.length / 1024).toFixed(0)} KB · ${R.items.length} items · ${R.tubes.length} tube runs · ${R.solids.length} solids · ${FLOW.length} lines`);
if (geometry) {
  mkdirSync(join(HERE, "audit"), { recursive: true });
  writeFileSync(join(HERE, "audit", "geometry.json"), JSON.stringify(geometry, null, 1) + "\n");
  console.log(geometry.report.join("\n"));
  console.log(geometry.failures ? `geometry audit: ${geometry.failures} problem(s)` : "geometry audit passed");
}
