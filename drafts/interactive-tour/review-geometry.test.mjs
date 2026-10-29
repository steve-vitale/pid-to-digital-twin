// Mechanical guards for the operator-review drawing defects. Run after both builds.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { iso } from "./kit/iso-kit.mjs";

const root = new URL("../../", import.meta.url);
const data = JSON.parse(readFileSync(new URL("out/interactive_tour/tour_data.json", root)));
const read = (name) => readFileSync(new URL(`out/interactive_tour/${name}`, root), "utf8");
for (const theme of ["dark", "light"]) {
  const scene = JSON.parse(read(theme === "dark" ? "scene.json" : "scene-light.json"));
  const html = read(theme === "dark" ? "te-tour.html" : "te-tour-light.html");
  test(`${theme}: all six machines have visible cutaway windows, including bore and impeller`, () => {
    for (const u of data.units) assert.match(html, new RegExp(`id="win-${u.id}"`), u.id);
    assert.match(html, /data-internal="header-bore"/);
    assert.match(html, /data-internal="compressor-impeller"/);
  });
  test(`${theme}: separator and compressor callouts terminate on their own bodies`, () => {
    for (const [id, dz, dy] of [["V-101", 36, 0], ["K-101", 20, 8]]) {
      const u = data.units.find((u) => u.id === id);
      const expected = iso([u.plan[0] * .3, u.plan[1] * .3 + dy, dz], scene.projection);
      assert.ok(Math.hypot(...scene.units[id].label.map((v, i) => v - expected[i])) < .01, id);
    }
    assert.match(html, /data-leader-unit/);
  });
  test(`${theme}: an overhead corridor has paired columns, crossbeams and longitudinal rails`, () => {
    assert.ok(scene.rack?.frames.length >= 3, "at least three portal frames");
    assert.equal(scene.rack.status, "inferred placeholder structure, not a plant layout");
    for (const f of scene.rack.frames) {
      assert.equal(f.columns.length, 2);
      assert.ok(f.columns[1][1] - f.columns[0][1] >= 12, "open corridor between columns");
      assert.ok(f.crossbeam[2] >= 45, "overhead crossbeam");
    }
    assert.equal(scene.rack.rails.length, 2);
  });
  test(`${theme}: separator-to-compressor suction has one crest and no S-shaped vertical excursion`, () => {
    const points = scene.routes?.S8;
    assert.ok(points?.length, "actual router control points are exported");
    const signs = points.slice(1).map((p, i) => Math.sign(p[2] - points[i][2])).filter(Boolean);
    assert.ok(signs.length <= 2, `one rise and one drop, not staggered drops: ${signs}`);
    const changes = signs.filter((s, i) => i && s !== signs[i - 1]);
    assert.ok(changes.length <= 1, `vertical reversals: ${signs}`);
    assert.ok(points.length <= 6, "direct single-crest transfer, not a serpentine detour");
  });
}
