#!/usr/bin/env node
/**
 * End-to-end check of the gallery against the DESIGN-SPEC acceptance list.
 *   node tools/e2e.mjs [--url http://127.0.0.1:8765/]
 * Exits non-zero when a check fails.
 */
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const args = process.argv.slice(2);
const iUrl = args.indexOf("--url");
const URL_ = iUrl > -1 ? args[iUrl + 1] : "http://127.0.0.1:8765/";
const PORT = 9800 + Math.floor(Math.random() * 300);
const profile = mkdtempSync(join(tmpdir(), "e2e-prof-"));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const chrome = spawn(CHROME, [
  "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
  "--no-first-run", `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`,
  "--window-size=1440,1000", "about:blank",
], { stdio: "ignore" });

async function waitVersion() {
  for (let k = 0; k < 100; k++) {
    try {
      const r = await fetch(`http://127.0.0.1:${PORT}/json/version`);
      if (r.ok) return await r.json();
    } catch {}
    await sleep(120);
  }
  throw new Error("chrome failed to start");
}

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

const v = await waitVersion();
const ws = new WebSocket(v.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.addEventListener("open", res); ws.addEventListener("error", rej); });
const cdp = new CDP(ws);
const { targetId } = await cdp.send("Target.createTarget", { url: "about:blank" }, null);
const { sessionId } = await cdp.send("Target.attachToTarget", { targetId, flatten: true }, null);
cdp.sessionId = sessionId;
await cdp.send("Page.enable");
await cdp.send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
await cdp.send("Page.navigate", { url: URL_ });

// 等页面真正渲染完（线上 https 首屏可能要 2–4s），而不是死等固定毫秒
for (let i = 0; i < 60; i++) {
  await sleep(400);
  try {
    const ok = await cdp.send("Runtime.evaluate", {
      expression: `!!(window.DEREK_PROMPTS && document.getElementById('stat-total') && document.querySelectorAll('.card').length > 0)`,
      returnByValue: true,
    });
    if (ok.result.value) break;
  } catch {}
}

async function js(expression, awaitPromise = false) {
  const r = await cdp.send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise });
  if (r.exceptionDetails) throw new Error("JS error: " + JSON.stringify(r.exceptionDetails).slice(0, 400));
  return r.result.value;
}

const results = [];
const check = (name, ok, detail = "") => { results.push({ name, ok, detail }); };

// 1. dataset
const stats = await js(`JSON.stringify({total:+document.getElementById('stat-total').textContent,
  img:+document.getElementById('stat-img').textContent, vid:+document.getElementById('stat-vid').textContent,
  cards:document.querySelectorAll('.card').length, data:window.DEREK_PROMPTS.length})`).then(JSON.parse);
check("数据 42 条 / 图像 39 / 视频 3", stats.total === 42 && stats.img === 39 && stats.vid === 3, JSON.stringify(stats));
check("卡片渲染数量 = 42", stats.cards === 42, "cards=" + stats.cards);

// 2. category filters
const clickCat = (label) => js(`(() => { const b=[...document.querySelectorAll('#cats button')].find(x=>x.textContent.trim().startsWith('${label}')); b&&b.click(); return document.querySelectorAll('.card').length; })()`);
check("分类 视频 → 3 张", (await clickCat("视频")) === 3);
check("分类 图像 → 39 张", (await clickCat("图像")) === 39);
const cats = await js(`(() => { const bad=[...document.querySelectorAll('.card .cat')].filter(e=>e.textContent.trim()!=='图像').length; return bad; })()`);
check("图像筛选后卡片分类全部为图像", cats === 0, "mismatch=" + cats);
await clickCat("全部");

// 3. model chips
const modelRes = await js(`(() => {
  const chips=[...document.querySelectorAll('#models .chip')];
  const target=chips.find(c=>c.dataset.v==='MiniMax');
  if(!target) return {err:'no chip'};
  target.click();
  return {count:document.querySelectorAll('.card').length, chips:chips.map(c=>c.dataset.v)};
})()`);
check("模型 chips 含 MiniMax", Array.isArray(modelRes.chips) && modelRes.chips.includes("MiniMax"), JSON.stringify(modelRes.chips || []));
check("MiniMax 筛选 → 3 张", modelRes.count === 3, "count=" + modelRes.count);
await js(`[...document.querySelectorAll('#models .chip')].find(c=>c.dataset.v==='全部').click()`);

// 4. model chips are not fragmented ("GPT Image" intact)
const chips = await js(`JSON.stringify([...document.querySelectorAll('#models .chip')].map(c=>c.dataset.v))`).then(JSON.parse);
check("模型 chips 未被错误拆分（含 'GPT Image'）", chips.includes("GPT Image"), JSON.stringify(chips));

// 5. search
const searchRes = await js(`(() => {
  const q=document.getElementById('q'); q.value='机甲';
  q.dispatchEvent(new Event('input',{bubbles:true}));
  return new Promise(r=>setTimeout(()=>r({count:document.querySelectorAll('.card').length, label:document.getElementById('count').textContent}),200));
})()`, true);
check("搜索「机甲」有结果且收窄", searchRes.count > 0 && searchRes.count < 42, JSON.stringify(searchRes));
const emptyRes = await js(`(() => {
  const q=document.getElementById('q'); q.value='zzzzzz';
  q.dispatchEvent(new Event('input',{bubbles:true}));
  return new Promise(r=>setTimeout(()=>r({cards:document.querySelectorAll('.card').length, empty:!!document.querySelector('.empty')}),200));
})()`, true);
check("无结果时显示空状态", emptyRes.cards === 0 && emptyRes.empty, JSON.stringify(emptyRes));
await js(`document.getElementById('clear').click()`);

// 6. images are local + all load
const imgStats = await js(`(async () => {
  const step=innerHeight*0.85;
  for(let y=0;y<document.body.scrollHeight;y+=step){scrollTo(0,y);await new Promise(r=>setTimeout(r,50));}
  scrollTo(0,0);
  await Promise.race([Promise.all([...document.images].map(i=>i.complete?0:new Promise(r=>{i.onload=i.onerror=r;setTimeout(r,6000)}))), new Promise(r=>setTimeout(r,9000))]);
  const imgs=[...document.images];
  return {total:imgs.length, broken:imgs.filter(i=>i.complete&&i.naturalWidth===0).length,
          remote:imgs.filter(i=>/^https?:/.test(i.getAttribute('src')||'')).length,
          lazy:imgs.filter(i=>i.loading==='lazy').length};
})()`, true);
check("卡片图片全部本地相对路径", imgStats.remote === 0, "remote=" + imgStats.remote);
check("图片全部可解码（无破图）", imgStats.broken === 0, JSON.stringify(imgStats));

// 7. dialog
const dlg = await js(`(() => {
  const card=document.querySelector('.card'); card.click();
  const d=document.getElementById('dlg');
  return {open:d.open, title:document.getElementById('dlg-title').textContent,
          pre:(d.querySelector('pre')||{}).textContent||'',
          xlink:(d.querySelector('a[href^="https://x.com"]')||{}).href||'',
          hash:location.hash, copyButtons:d.querySelectorAll('.copy').length};
})()`);
check("点击卡片打开详情", dlg.open === true);
check("详情有完整 prompt 文本", dlg.pre.length > 50, "len=" + dlg.pre.length);
check("详情有 X 原帖链接", /^https:\/\/x\.com\//.test(dlg.xlink), dlg.xlink);
check("详情 URL 带 hash 可分享", dlg.hash.length > 1, dlg.hash);

const copyRes = await js(`(async () => {
  const btn=document.querySelector('#dlg .copy'); btn.click();
  await new Promise(r=>setTimeout(r,300));
  return {label:btn.textContent, cls:btn.className};
})()`, true);
check("复制提示词有成功反馈", /已复制/.test(copyRes.label), JSON.stringify(copyRes));

const nav = await js(`(async () => {
  const before=document.getElementById('dlg-title').textContent;
  document.querySelector('#dlg [data-move="1"]').click();
  await new Promise(r=>setTimeout(r,150));
  return {before, after:document.getElementById('dlg-title').textContent};
})()`, true);
check("详情可切换下一条", nav.before !== nav.after, JSON.stringify(nav));
await js(`document.getElementById('dlg').close()`);
await sleep(200); // <dialog> 的 close 事件是异步派发的
const closed = await js(`JSON.stringify({open:document.getElementById('dlg').open, id:document.getElementById('dlg').dataset.id, hash:location.hash})`).then(JSON.parse);
check("关闭详情后状态复位", closed.open === false && closed.id === "" && closed.hash === "", JSON.stringify(closed));

// 8. no external network dependency (fonts / css / js must be same-origin)
const remote = await js(`JSON.stringify([...document.querySelectorAll('link[rel~="stylesheet"][href],link[rel~="preload"][href],link[rel~="icon"][href],script[src]')]
  .map(e=>e.getAttribute('href')||e.getAttribute('src')).filter(u=>/^https?:/.test(u)))`).then(JSON.parse);
check("无外部依赖（字体/CSS/JS 全本地）", remote.length === 0, JSON.stringify(remote));

// 9. theme toggle
const theme = await js(`(() => { document.getElementById('theme').click();
  const a=document.documentElement.dataset.theme; document.getElementById('theme').click();
  return {dark:a, light:document.documentElement.dataset.theme}; })()`);
check("深浅色切换生效", theme.dark === "dark" && theme.light === "light", JSON.stringify(theme));

ws.close(); chrome.kill();
try { rmSync(profile, { recursive: true, force: true }); } catch {}

const failed = results.filter((r) => !r.ok);
for (const r of results) console.log(`${r.ok ? "PASS" : "FAIL"}  ${r.name}${r.detail ? "  — " + r.detail : ""}`);
console.log(`\n${results.length - failed.length}/${results.length} passed`);
process.exit(failed.length ? 1 : 0);
