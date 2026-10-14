// Minimal headless Chrome session over the DevTools protocol, no dependencies. Adapted from the anatomy skill's
// scripts/drive.mjs and scripts/chrome-port.mjs (MIT, Copyright (c) 2026 Ryan; see kit/LICENSE and NOTICE.md).
// Finds a Chrome or Chromium binary from CHROME_PATH, the usual install folders or a Playwright browser cache.
import { spawn } from "node:child_process";
import { existsSync, mkdtempSync, readdirSync, rmSync } from "node:fs";
import { homedir, tmpdir } from "node:os";
import { join } from "node:path";

export function chromePath() {
  const candidates = [process.env.CHROME_PATH, "/opt/pw-browsers/chromium/chrome-linux/chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
    "/usr/bin/google-chrome", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe", "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"].filter(Boolean);
  const caches = [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers", join(homedir(), ".cache", "ms-playwright"),
    process.env.LOCALAPPDATA && join(process.env.LOCALAPPDATA, "ms-playwright"), join(homedir(), "Library", "Caches", "ms-playwright")].filter(Boolean);
  for (const cache of caches) {
    if (!existsSync(cache)) continue;
    for (const dir of readdirSync(cache).filter((d) => /^chromium-\d+$/.test(d)).sort().reverse()) {
      for (const sub of ["chrome-win64/chrome.exe", "chrome-win/chrome.exe", "chrome-linux64/chrome", "chrome-linux/chrome", "chrome-mac/Chromium.app/Contents/MacOS/Chromium"]) candidates.push(join(cache, dir, sub));
    }
  }
  return candidates.find((p) => existsSync(p));
}

function chromePort(chrome) {
  return new Promise((done, fail) => {
    let text = "";
    const timer = setTimeout(() => fail(new Error("Chrome did not start")), 20000);
    chrome.stderr.on("data", (chunk) => {
      text += chunk;
      const match = text.match(/DevTools listening on ws:\/\/[^:]+:(\d+)\//);
      if (match) { clearTimeout(timer); done(Number(match[1])); }
    });
    chrome.on("exit", (code) => { clearTimeout(timer); fail(new Error(`Chrome exited before startup: ${code}`)); });
  });
}

export async function launch() {
  const binary = chromePath();
  if (!binary) throw Object.assign(new Error("No Chrome or Chromium found; set CHROME_PATH"), { code: "NO_CHROME" });
  const profile = mkdtempSync(join(tmpdir(), "te-tour-"));
  const chrome = spawn(binary, ["--headless=new", ...(process.platform === "linux" ? ["--no-sandbox"] : []), "--remote-debugging-port=0", `--user-data-dir=${profile}`,
    "--no-first-run", "--no-default-browser-check", "--hide-scrollbars", "--allow-file-access-from-files", "--force-color-profile=srgb", "about:blank"]);
  const port = await chromePort(chrome);
  const close = () => {
    chrome.kill("SIGKILL");
    try { rmSync(profile, { recursive: true, force: true }); } catch {}
  };
  return { port, close, binary };
}

export async function openPage(port, { width, height, scale = 1, reduced = false }) {
  const page = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: "PUT" })).json();
  const socket = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0;
  const pending = new Map();
  const problems = [];
  socket.onmessage = (message) => {
    const data = JSON.parse(message.data);
    if (data.id && pending.has(data.id)) { pending.get(data.id)(data); pending.delete(data.id); }
    else if (data.method === "Runtime.consoleAPICalled" && (data.params.type === "error" || data.params.type === "warning")) problems.push(`console.${data.params.type}: ${data.params.args.map((a) => a.value ?? a.description ?? "").join(" ").slice(0, 400)}`);
    else if (data.method === "Runtime.exceptionThrown") problems.push(`exception: ${data.params.exceptionDetails.exception?.description ?? data.params.exceptionDetails.text}`.slice(0, 600));
  };
  await new Promise((done) => (socket.onopen = done));
  const send = (method, params = {}) => new Promise((done) => { const call = ++id; pending.set(call, done); socket.send(JSON.stringify({ id: call, method, params })); });
  const evaluate = async (expression) => {
    const reply = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
    if (reply.error) throw new Error(reply.error.message);
    const ex = reply.result?.exceptionDetails;
    if (ex) throw new Error(ex.exception?.description ?? ex.text);
    return reply.result?.result?.value;
  };
  await send("Runtime.enable");
  await send("Page.enable");
  if (reduced) await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-motion", value: "reduce" }] });
  await send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: scale, mobile: width < 600 });
  const sleep = (ms) => new Promise((done) => setTimeout(done, ms));
  const goto = async (url) => {
    const nav = await send("Page.navigate", { url });
    if (nav.result?.errorText) throw new Error(nav.result.errorText);
    for (let i = 0; i < 100; i++) { if (await evaluate("document.readyState === 'complete' && Boolean(window.__tour)").catch(() => false)) break; await sleep(100); }
    await evaluate("document.fonts ? document.fonts.ready.then(() => true) : true");
    await sleep(400);
  };
  const shot = async (selector, scaleShot = 1, format = "png", maxHeight = Infinity) => {
    const box = await evaluate(`(()=>{const el=document.querySelector(${JSON.stringify(selector)});const r=el.getBoundingClientRect();return {x:r.left+scrollX,y:r.top+scrollY,w:r.width,h:r.height}})()`);
    const res = await send("Page.captureScreenshot", { format, ...(format === "jpeg" ? { quality: 78 } : {}), clip: { x: box.x, y: box.y, width: box.w, height: Math.min(box.h, maxHeight), scale: scaleShot }, captureBeyondViewport: true });
    return Buffer.from(res.result.data, "base64");
  };
  const click = async (selector) => {
    const box = await evaluate(`(()=>{const el=document.querySelector(${JSON.stringify(selector)});el.scrollIntoView({block:"center"});const r=el.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2}})()`);
    await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: box.x, y: box.y });
    await send("Input.dispatchMouseEvent", { type: "mousePressed", x: box.x, y: box.y, button: "left", clickCount: 1 });
    await send("Input.dispatchMouseEvent", { type: "mouseReleased", x: box.x, y: box.y, button: "left", clickCount: 1 });
  };
  const key = async (k, code = k) => {
    await send("Input.dispatchKeyEvent", { type: "keyDown", key: k, code, windowsVirtualKeyCode: { ArrowRight: 39, ArrowLeft: 37, Escape: 27, Tab: 9, Enter: 13, " ": 32 }[k] ?? 0 });
    await send("Input.dispatchKeyEvent", { type: "keyUp", key: k, code });
  };
  const close = () => socket.close();
  return { send, evaluate, goto, shot, click, key, sleep, problems, close };
}
