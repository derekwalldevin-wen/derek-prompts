#!/usr/bin/env node
/**
 * 验证「老内核降级」：在没有 dialog.showModal 的浏览器里（旧版微信 X5 / iOS<15.4），
 * 点卡片仍能打开详情、点 × 能关闭。
 *
 *   node tools/check-fallback.mjs [--url http://127.0.0.1:8765/]
 */
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const args = process.argv.slice(2);
const i = args.indexOf("--url");
const URL_ = i > -1 ? args[i + 1] : "http://127.0.0.1:8765/";
const PORT = 9500 + Math.floor(Math.random() * 300);
const profile = mkdtempSync(join(tmpdir(), "fb-prof-"));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const chrome = spawn(CHROME, [
  "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
  `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`, "--window-size=1440,1000", "about:blank",
], { stdio: "ignore" });

class CDP {
  constructor(ws) {
    this.ws = ws; this.id = 0; this.pending = new Map(); this.sessionId = null;
    ws.addEventListener("message", (ev) => {
      const m = JSON.parse(ev.data);
      if (m.id && this.pending.has(m.id)) {
        const { resolve, reject } = this.pending.get(m.id);
        this.pending.delete(m.id);
        m.error ? reject(new Error(JSON.stringify(m.error))) : resolve(m.result);
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

async function version() {
  for (let k = 0; k < 100; k++) {
    try {
      const r = await fetch(`http://127.0.0.1:${PORT}/json/version`);
      if (r.ok) return await r.json();
    } catch {}
    await sleep(120);
  }
  throw new Error("chrome failed to start");
}

const v = await version();
const ws = new WebSocket(v.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.addEventListener("open", res); ws.addEventListener("error", rej); });
const cdp = new CDP(ws);
const { targetId } = await cdp.send("Target.createTarget", { url: "about:blank" }, null);
const { sessionId } = await cdp.send("Target.attachToTarget", { targetId, flatten: true }, null);
cdp.sessionId = sessionId;
await cdp.send("Page.enable");
await cdp.send("Runtime.enable");
// 关键：在页面脚本执行前，把 dialog 的现代 API 摘掉，模拟旧内核
await cdp.send("Page.addScriptToEvaluateOnNewDocument", {
  source: `try{ delete HTMLDialogElement.prototype.showModal; delete HTMLDialogElement.prototype.close; }catch(e){}`,
});
await cdp.send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
await cdp.send("Page.navigate", { url: URL_ });

async function js(expression, awaitPromise = false) {
  const r = await cdp.send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise });
  if (r.exceptionDetails) throw new Error("JS error: " + JSON.stringify(r.exceptionDetails).slice(0, 300));
  return r.result.value;
}

for (let k = 0; k < 60; k++) {
  await sleep(400);
  if (await js(`!!(window.DEREK_PROMPTS && document.querySelectorAll('.card').length)`)) break;
}

const result = await js(`(async () => {
  const d = document.getElementById('dlg');
  const nativeGone = typeof HTMLDialogElement.prototype.showModal !== 'function';
  document.querySelector('.card').click();
  await new Promise(r => setTimeout(r, 300));
  const opened = d.hasAttribute('open') && d.classList.contains('fallback');
  const hasTitle = !!document.getElementById('dlg-title');
  const bodyLocked = document.body.classList.contains('dlg-open');
  d.querySelector('.dlg-close').click();
  await new Promise(r => setTimeout(r, 300));
  const closed = !d.hasAttribute('open') && !document.body.classList.contains('dlg-open');
  return { nativeGone, opened, hasTitle, bodyLocked, closed };
})()`, true);

const ok = result.nativeGone && result.opened && result.hasTitle && result.bodyLocked && result.closed;
console.log(`${ok ? "PASS" : "FAIL"}  老内核降级：无 dialog API 也能打开 / 关闭详情  — ${JSON.stringify(result)}`);
ws.close(); chrome.kill();
try { rmSync(profile, { recursive: true, force: true }); } catch {}
process.exit(ok ? 0 : 1);
