// Browser contract for the PIDTwin Perspective project, run against a gateway you are authorized to test.
// Read-only: it opens pages and clicks navigation only; it never writes a tag or changes configuration.
//
//   node browser_contract.js contract CONTRACT.json OUT.json
//       Every route loaded directly and reloaded; every click target clicked at its exported position and checked
//       to land on the right route and view title with no "null" value text; browser Back after each click; a
//       Back/Forward chain; repeated rapid clicks.
//   node browser_contract.js capture CONTRACT.json OUTDIR LABEL desktop|narrow ROUTE...
//       Screenshots of each route (scrolling the view; at most MAXSHOTS per route) plus text counts.
//   node browser_contract.js count OUT.json SAMPLES INTERVAL_MS
//       Samples /alarms: the header's "Process alarms: N" plus the data-source box against the alarm table's own
//       "N ACTIVE" count. Ported from the scratch sampler used in the 2026-10-13 run (journal entry 47); it counts
//       one diagnostic alarm when the box reads DATA SOURCE LOST, so with both sources lost it under-counts.
//
// Environment: PIDTWIN_BASE (default http://localhost:8088/data/perspective/client/PIDTwin),
// PLAYWRIGHT_MODULE (default "playwright"; a path to an installed package also works).
// Needs Node and Playwright with Chromium; neither is a dependency of the Python checks.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('fs');
const path = require('path');

const BASE = (process.env.PIDTWIN_BASE || 'http://localhost:8088/data/perspective/client/PIDTwin').replace(/\/$/, '');
const VIEWPORTS = { desktop: { width: 1600, height: 930 }, narrow: { width: 390, height: 844 } };
const url = r => BASE + (r === '/' ? '' : r);
const routeOf = u => { const r = u.split('?')[0].replace(BASE, ''); return r === '' ? '/' : r; };
const squash = s => s.replace(/\s+/g, ' ');

async function settle(page, title, ms = 12000) {
  // Loaded = the view's own title is on screen and no value renders as the literal text "null". Only the view is
  // read: Perspective's own page chrome (a project-info panel that says "by null" at narrow widths) is not ours.
  const want = squash(title);
  const t0 = Date.now();
  let body = '';
  while (Date.now() - t0 < ms) {
    body = squash(await page.innerText('.ia_container--root').catch(() => ''));
    if (body.includes(want) && !/\bnull\b/.test(body)) return { ok: true, ms: Date.now() - t0 };
    await page.waitForTimeout(400);
  }
  return { ok: false, ms, sample: body.slice(0, 300) };
}

async function clickAt(page, nav) {
  // Fixed-mode coordinate views: exported positions are CSS pixels at 1600 px width; scroll the view, then click.
  const top = await page.evaluate(y => {
    const root = document.querySelector('.ia_container--root');
    root.scrollTop = Math.max(0, y - 300);
    return root.scrollTop;
  }, nav.y);
  await page.waitForTimeout(150);
  await page.mouse.click(nav.x + nav.w / 2, nav.y + nav.h / 2 - top);
}

async function contract(contractPath, outPath) {
  const C = JSON.parse(fs.readFileSync(contractPath, 'utf8')).routes;
  const browser = await chromium.launch();
  const page = await (await browser.newContext({ viewport: VIEWPORTS.desktop })).newPage();
  const errors = [];
  page.on('console', m => { if (m.type() === 'error') errors.push(`${routeOf(page.url())}: ${m.text().slice(0, 200)}`); });
  page.on('pageerror', e => errors.push('pageerror ' + String(e).slice(0, 200)));
  const res = { base: BASE, browser: browser.version(), direct: [], clicks: [], backforward: [], repeated: [], errors };
  const open = async r => { await page.goto(url(r), { waitUntil: 'load' }); return settle(page, C[r].title); };
  for (const r of Object.keys(C)) {
    const first = await open(r);
    await page.reload({ waitUntil: 'load' });
    const again = await settle(page, C[r].title);
    res.direct.push({ route: r, load: first.ok, reload: again.ok, landed: routeOf(page.url()), ms: [first.ms, again.ms] });
  }
  for (const r of Object.keys(C)) {
    await open(r);
    for (const nav of C[r].navs) {
      await clickAt(page, nav);
      const t0 = Date.now();
      while (nav.target !== r && routeOf(page.url()) === r && Date.now() - t0 < 6000) await page.waitForTimeout(150);
      const landed = routeOf(page.url());
      const shown = await settle(page, C[nav.target].title, 8000);
      let back = null;
      if (landed !== r) {
        await page.goBack();
        back = (await settle(page, C[r].title, 8000)).ok && routeOf(page.url()) === r;
      }
      res.clicks.push({ from: r, name: nav.name, target: nav.target, landed, ok: landed === nav.target && shown.ok, back });
      if (routeOf(page.url()) !== r) await open(r);
    }
  }
  await open('/');
  for (const t of ['/unit/R-101', '/unit/C-101', '/alarms', '/drawings']) {
    await clickAt(page, C[routeOf(page.url())].navs.find(n => n.target === t));
    await settle(page, C[t].title, 8000);
  }
  for (const [dir, want] of [['back', '/alarms'], ['back', '/unit/C-101'], ['back', '/unit/R-101'], ['back', '/'],
                             ['forward', '/unit/R-101'], ['forward', '/unit/C-101']]) {
    await (dir === 'back' ? page.goBack() : page.goForward());
    const s = await settle(page, C[want].title, 8000);
    res.backforward.push({ dir, want, got: routeOf(page.url()), ok: s.ok && routeOf(page.url()) === want });
  }
  await open('/');
  const tab = C['/'].navs.find(n => n.target === '/unit/V-101');
  for (let i = 0; i < 4; i++) { await clickAt(page, tab); await page.waitForTimeout(120); }
  const s = await settle(page, C['/unit/V-101'].title, 8000);
  res.repeated.push({ clicks: 4, target: '/unit/V-101', got: routeOf(page.url()), ok: s.ok && routeOf(page.url()) === '/unit/V-101' });
  res.summary = {
    direct_load_and_reload: `${res.direct.filter(d => d.load && d.reload && d.landed === d.route).length}/${res.direct.length}`,
    clicks: `${res.clicks.filter(c => c.ok).length}/${res.clicks.length}`,
    back_after_click: `${res.clicks.filter(c => c.back !== false).length}/${res.clicks.length}`,
    back_forward_chain: `${res.backforward.filter(x => x.ok).length}/${res.backforward.length}`,
    repeated_clicks: res.repeated.every(x => x.ok) ? 'pass' : 'FAIL',
    console_errors: errors.length,
  };
  fs.writeFileSync(outPath, JSON.stringify(res, null, 1));
  console.log(JSON.stringify(res.summary));
  await browser.close();
}

async function capture(contractPath, outDir, label, vpName, routes) {
  const C = JSON.parse(fs.readFileSync(contractPath, 'utf8')).routes;
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: VIEWPORTS[vpName], deviceScaleFactor: vpName === 'narrow' ? 2 : 1 });
  const out = [];
  fs.mkdirSync(outDir, { recursive: true });
  for (const r of routes) {
    const page = await ctx.newPage();
    await page.goto(url(r), { waitUntil: 'load' });
    const loaded = await settle(page, C[r].title, Number(process.env.WAIT || 12000));
    await page.waitForTimeout(Number(process.env.EXTRA_WAIT || 2500));  // let trends and fills finish drawing
    const geo = await page.evaluate(() => { const e = document.querySelector('.ia_container--root');
      return { sh: e.scrollHeight, ch: e.clientHeight, sw: e.scrollWidth, cw: e.clientWidth }; });
    const name = r === '/' ? 'overview' : r.slice(1).replace(/\//g, '-');
    const files = [];
    const rows = Math.max(1, Math.ceil(geo.sh / geo.ch));
    for (let i = 0; i < rows && files.length < Number(process.env.MAXSHOTS || 2); i++) {
      await page.evaluate(i => { const e = document.querySelector('.ia_container--root'); e.scrollTop = i * e.clientHeight; }, i);
      await page.waitForTimeout(600);
      const file = `${label}-${vpName}-${name}${i ? '-' + i : ''}.png`;
      await page.screenshot({ path: path.join(outDir, file) });
      files.push(file);
    }
    const text = await page.innerText('.ia_container--root');
    const count = re => (text.match(re) || []).length;
    out.push({ route: r, loaded: loaded.ok, geo, files, null_text: count(/\bnull\b/g), unknown: count(/UNKNOWN/g), not_connected: count(/not connected/gi),
               alarm_active_text: count(/ALARM ACTIVE/g), outside_band_text: count(/Outside normal band/g),
               header: (text.match(/(Process alarms|Outside band|Data source): [^\n]*|DATA SOURCE LOST/g) || []).join(' | '),
               // The alarm table's own "N ACTIVE" count, and alarm names as it prints them, to compare with the header.
               table_active: (text.match(/(\d+)\s+ACTIVE/) || [null, null])[1],
               alarm_names: Object.fromEntries(['PressureHigh', 'PressureShutdown', 'TemperatureShutdown', 'DataSourceLost',
                 'Data source lost'].map(n => [n, count(new RegExp(n, 'g'))])) });
    console.log(JSON.stringify(out.at(-1)));
    await page.close();
  }
  fs.writeFileSync(path.join(outDir, `capture-${label}-${vpName}.json`), JSON.stringify(out, null, 1));
  await browser.close();
}

async function count(outPath, samples, gap) {
  const browser = await chromium.launch();
  const page = await (await browser.newContext({ viewport: VIEWPORTS.desktop })).newPage();
  await page.goto(url('/alarms'), { waitUntil: 'load' });
  await page.waitForTimeout(8000);
  const rows = [];
  for (let i = 0; i < Number(samples); i++) {
    const t = await page.innerText('.ia_container--root', { timeout: 10000 }).catch(() => '');
    const p = Number((t.match(/Process alarms: (\d+)/) || [])[1]);
    const d = /DATA SOURCE LOST/.test(t) ? 1 : 0;
    const a = Number((t.match(/(\d+)\s+ACTIVE/) || [])[1]);
    rows.push({ utc: new Date().toISOString(), header_process: p, header_diag_lost: d, table_active: a, match: p + d === a });
    console.log(JSON.stringify(rows.at(-1)));
    await page.waitForTimeout(Number(gap));
  }
  fs.writeFileSync(outPath, JSON.stringify(rows, null, 1));
  console.log(`header matches table ${rows.filter(r => r.match).length}/${rows.length}`);
  await browser.close();
}

const [mode, ...args] = process.argv.slice(2);
(mode === 'contract' ? contract(args[0], args[1]) : mode === 'capture' ? capture(args[0], args[1], args[2], args[3], args.slice(4))
  : mode === 'count' ? count(args[0], args[1] || 30, args[2] || 3000)
  : Promise.reject(new Error('usage: contract CONTRACT OUT | capture CONTRACT OUTDIR LABEL desktop|narrow ROUTE... | count OUT [N] [MS]')))
  .catch(e => { console.error(e); process.exit(1); });
