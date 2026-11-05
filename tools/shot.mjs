#!/usr/bin/env node
/**
 * Dependency-free screenshot helper (Chrome DevTools Protocol via Node's built-in WebSocket).
 *
 *   node tools/shot.mjs --url http://127.0.0.1:8765/ --out shot.png --width 1440 --full
 *   node tools/shot.mjs --url http://127.0.0.1:8765/ --out dark.png --theme dark --full
 */
import { spawn } from "node:child_process";
import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const args = process.argv.slice(2);
const opt = (name, def = null) => {
  const i = args.indexOf("--" + name);
  if (i === -1) return def;
  const v = args[i + 1];
  return v && !v.startsWith("--") ? v : true;
};
const URL_ = opt("url", "http://127.0.0.1:8765/");
const OUT = opt("out", "shot.png");
const WIDTH = Number(opt("width", 1440));
const HEIGHT = Number(opt("height", 900));
const FULL = !!opt("full", false);
const THEME = opt("theme", null);
const WAIT = Number(opt("wait", 1200));
const PORT = 9333 + Math.floor(Math.random() * 400);
const profile = mkdtempSync(join(tmpdir(), "shot-prof-"));

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const chrome = spawn(CHROME, [
  "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
  "--no-first-run", "--no-default-browser-check", "--disable-extensions",
  `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`,
  `--window-size=${WIDTH},${HEIGHT}`,
  "about:blank",
], { stdio: ["ignore", "pipe", "pipe"] });

let stderr = "";
chrome.stderr.on("data", (d) => { stderr += d.toString(); });

async function waitVersion() {
  for (let i = 0; i < 80; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${PORT}/json/version`);
      if (r.ok) return await r.json();
    } catch {}
    await sleep(150);
  }
  throw new Error("chrome did not start: " + stderr.slice(0, 500));
}

class CDP {
  constructor(ws) {
    this.ws = ws; this.id = 0; this.pending = new Map(); this.sessionId = null;
    ws.addEventListener("message", (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.id && this.pending.has(msg.id)) {
        const { resolve, reject } = this.pending.get(msg.id);
        this.pending.delete(msg.id);
        msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result);
      }
    });
  }
  send(method, params = {}, sessionId = this.sessionId) {
    const id = ++this.id;
    const payload = { id, method, params };
    if (sessionId) payload.sessionId = sessionId;
    this.ws.send(JSON.stringify(payload));
    return new Promise((resolve, reject) => this.pending.set(id, { resolve, reject }));
  }
}

const version = await waitVersion();
const ws = new WebSocket(version.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.addEventListener("open", res); ws.addEventListener("error", rej); });
const cdp = new CDP(ws);

const { targetId } = await cdp.send("Target.createTarget", { url: "about:blank" }, null);
const { sessionId } = await cdp.send("Target.attachToTarget", { targetId, flatten: true }, null);
cdp.sessionId = sessionId;

await cdp.send("Page.enable");
await cdp.send("Runtime.enable");
await cdp.send("Emulation.setDeviceMetricsOverride", {
  width: WIDTH, height: HEIGHT, deviceScaleFactor: 1, mobile: WIDTH < 640,
});
await cdp.send("Page.navigate", { url: URL_ });
await sleep(WAIT);

if (THEME) {
  await cdp.send("Runtime.evaluate", {
    expression: `localStorage.setItem('derek-theme','${THEME}');document.documentElement.dataset.theme='${THEME}';`,
  });
}

// trigger lazy images: walk the page down, then back up
await cdp.send("Runtime.evaluate", {
  expression: `(async () => {
    const step = innerHeight * 0.8;
    for (let y = 0; y < document.body.scrollHeight; y += step) {
      scrollTo(0, y); await new Promise(r => setTimeout(r, 60));
    }
    scrollTo(0, ${Number(opt("scroll", 0))});
    await document.fonts.ready;
    const imgs = [...document.images];
    await Promise.race([
      Promise.all(imgs.map(i => i.complete ? 0 : new Promise(r => { i.onload = i.onerror = r; setTimeout(r, 8000); }))),
      new Promise(r => setTimeout(r, 12000)),
    ]);
    return { imgs: imgs.length, broken: imgs.filter(i => i.complete && i.naturalWidth === 0).length };
  })()`,
  awaitPromise: true,
});

const metrics = await cdp.send("Runtime.evaluate", {
  expression: `JSON.stringify({h: document.documentElement.scrollHeight, w: document.documentElement.scrollWidth})`,
  returnByValue: true,
});
const size = JSON.parse(metrics.result.value);
const shotParams = { format: "png", captureBeyondViewport: FULL };
if (FULL) shotParams.clip = { x: 0, y: 0, width: WIDTH, height: Math.min(size.h, 20000), scale: 1 };
const shot = await cdp.send("Page.captureScreenshot", shotParams);
writeFileSync(OUT, Buffer.from(shot.data, "base64"));
console.log(JSON.stringify({ out: OUT, pageHeight: size.h, pageWidth: size.w }));

ws.close();
chrome.kill();
try { rmSync(profile, { recursive: true, force: true }); } catch {}
process.exit(0);
