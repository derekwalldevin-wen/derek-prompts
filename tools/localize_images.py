#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""localize_images.py — 备选管线：把 pbs.twimg.com 的图本地化（下载原图 -> webp -> manifest）。

为什么需要它
------------
X/Twitter 的 CDN（pbs.twimg.com）在本机网络被墙（DNS 污染 + TLS RST），直连拿不到。
本脚本走**公共图片代理**（由代理服务器出网去抓），绕开本地封锁，无需 VPN。
主项目实际用的是 GitHub Actions 方案；这份脚本是可重跑、可续传的本地备选管线，
输出到 site/img_local/，不会碰 site/img/ 与 data/*.json。

本机实测的两个坑（已内置处理）
------------------------------
1. curl.exe（Windows/Schannel）连这些代理会被重置(curl:35)，Python urllib(OpenSSL) 正常。
2. 本机链路会把 >200KB 的下载中途掐断（IncompleteRead / WinError 10054），
   所以内置 Range 分段续传，一张图分几次拉完。

产物（--out 默认 <site>/img_local）
-----------------------------------
  _raw/<id>-<n>.jpg     原始图（校验通过即跳过，可续传/重跑）
  <id>-<n>.webp         最长边 <=900 的 webp（quality 82）
  manifest.json         [{id,n,url,file,w,h,bytes,src_bytes,via,ok,error}]
  failed.json           只含失败项，便于 --retry-failed
  file 字段是相对 site 根的路径，例如 img_local/2117795655389433978-1.webp

用法
----
  python tools/localize_images.py                    # 全量（默认代理链 + 续传，单线程约 15-20 分钟/151 张）
  python tools/localize_images.py --limit 3          # 小样本验证
  python tools/localize_images.py --retry-failed     # 只重跑失败项
  python tools/localize_images.py --force            # 全部重下
  # Derek 开了代理/VPN 后想拿原始字节（最干净）：
  python tools/localize_images.py --mode direct --proxy http://127.0.0.1:7890

数据来源
--------
默认优先读 data/media-manifest.json（含 id/n/原始 URL，data/prompts.json 回填成
img/*.webp 之后仍然可用）；没有该文件时退回读 data/prompts.json 里的 http URL。

⚠️ 已知死图：2105130671031427095 的 n=1（https://pbs.twimg.com/media/HTbtKwFbAAo7d5.jpg）
   源站 404，22 种 name/format 变体 + archive 快照均无，属已删除，脚本会记为 fail。
"""

import argparse
import io
import json
import os
import random
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from PIL import Image

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
IMG_MAGIC = (b"\xff\xd8", b"\x89PNG", b"RIFF", b"GIF8", b"BM")

_print_lock = threading.Lock()


def log(msg):
    with _print_lock:
        print(msg, flush=True)


# --------------------------------------------------------------------------- #
# 传输层
# --------------------------------------------------------------------------- #
def make_ctx(insecure=False):
    if insecure:
        c = ssl.create_default_context()
        c.check_hostname = False
        c.verify_mode = ssl.CERT_NONE
        return c
    return ssl.create_default_context()


class Truncated(Exception):
    """下载中途被掐断。partial = 已经拿到的字节，status = 本次响应码。"""

    def __init__(self, partial, msg="", status=None):
        super().__init__(msg)
        self.partial = partial
        self.status = status


def http_get(url, timeout=25, ctx=None, proxy=None, extra_headers=None):
    """返回 (status, content_type, bytes)。截断时抛 Truncated(partial)。

    故意不吃系统代理（ProxyHandler({})），行为可预期。
    """
    headers = {
        "User-Agent": UA,
        "Referer": "https://x.com/",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "close",
    }
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers)
    if proxy:
        r = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy}),
            urllib.request.HTTPSHandler(context=ctx or make_ctx()),
        ).open(req, timeout=timeout)
    else:
        # 坑（本机实测）：绝对不要用 build_opener(ProxyHandler({}))。带上空
        # ProxyHandler 后，这些图片代理域的连接会在 0.5s 内被 RST (WinError
        # 10054)，而裸 urlopen 完全正常。故无代理时走裸 urlopen。
        r = urllib.request.urlopen(req, timeout=timeout,
                                   context=ctx or make_ctx())
    with r:
        code = r.status
        ct = r.headers.get("Content-Type") or ""
        buf = bytearray()
        try:
            # 增量读：本机链路会在 ~200KB 处 RST，必须留下已读到的部分
            while True:
                chunk = r.read(65536)
                if not chunk:
                    break
                buf += chunk
        except Exception as e:  # IncompleteRead / ConnectionReset / 读超时
            part = getattr(e, "partial", b"") or b""
            if part and not bytes(buf).startswith(part[:64]):
                buf = bytearray(part)
            else:
                buf += part
            raise Truncated(bytes(buf), f"{type(e).__name__}: {str(e)[:60]}", code)
        return code, ct, bytes(buf)


def http_get_resumable(url, timeout=25, ctx=None, proxy=None, chunks=10):
    """带 Range 续传的 GET：本机链路会把大文件中途掐断，分段接着拉。"""
    buf = b""
    last = None
    for _ in range(chunks):
        hdrs = {"Range": f"bytes={len(buf)}-"} if buf else None
        try:
            code, ct, data = http_get(url, timeout=timeout, ctx=ctx, proxy=proxy,
                                      extra_headers=hdrs)
            # 206 = 接着上次的位置；200 = 代理不支持 Range，这是整份
            buf = (buf + data) if (code == 206 and buf) else data
            return code, ct, buf
        except Truncated as e:
            new = (buf + e.partial) if (e.status == 206 and buf) else e.partial
            if len(new) <= len(buf):     # 没有新进展，别再空转
                buf = new
                last = e
                break
            buf = new
            last = e
        except Exception as e:            # noqa: BLE001
            last = e
            if not buf:
                raise                     # 一个字节都没拿到 -> 交给外层换代理
    if buf:
        raise Truncated(buf, f"resume exhausted: {str(last)[:60]}")
    raise last or RuntimeError("fetch failed")


# --------------------------------------------------------------------------- #
# URL -> 候选请求地址
# --------------------------------------------------------------------------- #
def target_urls(target, mode):
    """给一个 pbs.twimg.com URL，产出 (via, url) 候选，按优先级排列。"""
    if mode == "direct":
        return [("direct", target)]
    q = urllib.parse.quote(target, safe="")
    bare = target.split("://", 1)[-1]        # pbs.twimg.com/media/xxx.jpg
    return [
        ("images.weserv.nl", "https://images.weserv.nl/?url=" + q),
        ("i0.wp.com", "https://i0.wp.com/" + bare),
        # 降级：让代理端直接给 <=900px 小图（60~100KB，被掐断概率低）
        ("weserv-900", "https://images.weserv.nl/?url=" + q
         + "&w=900&h=900&fit=inside&we&output=jpg&q=88"),
        ("wsrv.nl", "https://wsrv.nl/?url=" + q),
    ]


def is_image_bytes(b):
    if not b or len(b) < 2048:
        return False
    if not any(b.startswith(m) for m in IMG_MAGIC):
        return False
    try:
        with Image.open(io.BytesIO(b)) as im:
            im.load()
            return im.size[0] >= 64 and im.size[1] >= 64
    except Exception:
        return False


def is_valid_image_file(path):
    try:
        if not os.path.exists(path) or os.path.getsize(path) < 2048:
            return False
        with Image.open(path) as im:
            im.load()
            return im.size[0] >= 64 and im.size[1] >= 64
    except Exception:
        return False


class Gone(Exception):
    """源站明确 404 —— URL 已失效，不用再试别的代理。"""


def fetch_one(target, mode="proxy", proxy=None, retries=2, base_sleep=1.0,
              insecure=False, ctx=None, timeout=15, cooldown=20.0):
    """返回 (bytes, via)。

    两轮"快失败"：一轮把所有候选代理快速试一遍（连接级失败立刻换下一个），
    第二轮之前冷却 cooldown 秒。本机实测：密集/并发请求会让整条链路 RST 这些域名，
    隔几秒自动恢复，所以"快速换路 + 冷却重试"比"同一条路死磕"有效得多。
    """
    cands = target_urls(target, mode)
    last = None
    for p in range(max(1, retries)):
        for via, url in cands:
            try:
                code, _ct, b = http_get_resumable(url, timeout=timeout, ctx=ctx,
                                                  proxy=proxy)
                if code in (200, 206) and is_image_bytes(b):
                    return b, via
                last = ValueError(f"not image: code={code} len={len(b)} via={via}")
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    raise Gone(f"404 via {via}（源图已不存在）")
                last = e
            except ssl.SSLError as e:
                last = e
                if not insecure:
                    insecure = True
                    ctx = make_ctx(True)
                    continue
            except Exception as e:   # noqa: BLE001
                last = e
            time.sleep(base_sleep + random.random() * 0.4)
        if p + 1 < retries:
            log(f"    .. 全部候选失败，冷却 {cooldown:.0f}s 后重试（{target.rsplit('/',1)[-1]}）")
            time.sleep(cooldown)
    raise last or RuntimeError("all proxies failed")


def load_targets(proj):
    """返回 ([{id,n,url}], 来源路径)，优先 media-manifest（回填后仍可用）。"""
    mf = os.path.join(proj, "data", "media-manifest.json")
    if os.path.exists(mf):
        with open(mf, "r", encoding="utf-8") as f:
            data = json.load(f)
        items = data if isinstance(data, list) else (data.get("items") or [])
        out = [{"id": str(r["id"]), "n": int(r["n"]), "url": r["url"]}
               for r in items
               if str(r.get("url", "")).startswith("http")]
        if out:
            return out, mf
    dp = os.path.join(proj, "data", "prompts.json")
    with open(dp, "r", encoding="utf-8") as f:
        data = json.load(f)
    entries = data if isinstance(data, list) else (data.get("prompts") or data.get("entries") or [])
    out = []
    for e in entries:
        eid = str(e.get("id") or "")
        urls = e.get("media_preview_urls") or e.get("images") or []
        for n, u in enumerate(urls, 1):
            if isinstance(u, str) and u.startswith("http"):
                out.append({"id": eid, "n": n, "url": u})
    return out, dp


def safe_name(s):
    return "".join(ch for ch in s if ch.isalnum() or ch in "-_")


def atomic_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def to_webp(raw_path, webp_path, max_edge, quality):
    with Image.open(raw_path) as im:
        im.load()
        src_w, src_h = im.size
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGB")
        scale = min(1.0, max_edge / max(src_w, src_h))
        if scale < 1.0:
            im = im.resize((max(1, round(src_w * scale)), max(1, round(src_h * scale))),
                           Image.LANCZOS)
        tmp = webp_path + ".tmp"
        im.save(tmp, "WEBP", quality=quality, method=6)
        os.replace(tmp, webp_path)
        return im.size


def process(item, args, ctx, site_root):
    stem = f"{safe_name(item['id'])}-{item['n']}"
    raw_dir = os.path.join(args.out, "_raw")
    raw_path = os.path.join(raw_dir, stem + ".jpg")
    webp_path = os.path.join(args.out, stem + ".webp")
    rec = {
        "id": item["id"], "n": item["n"], "url": item["url"],
        "file": os.path.relpath(webp_path, site_root).replace("\\", "/"),
        "raw": os.path.relpath(raw_path, site_root).replace("\\", "/"),
        "w": None, "h": None, "bytes": None,
        "src_bytes": None, "via": None, "ok": False, "error": "",
    }

    # 1) 下载（可续传）
    try:
        if not args.force and is_valid_image_file(raw_path):
            rec["via"] = "cached"
            rec["src_bytes"] = os.path.getsize(raw_path)
        else:
            b, via = fetch_one(item["url"], mode=args.mode, proxy=args.proxy,
                               retries=args.retries, base_sleep=args.retry_sleep,
                               insecure=args.insecure, ctx=ctx, timeout=args.timeout,
                               cooldown=args.cooldown)
            os.makedirs(raw_dir, exist_ok=True)
            tmp = raw_path + ".tmp"
            with open(tmp, "wb") as f:
                f.write(b)
            os.replace(tmp, raw_path)
            rec["via"] = via
            rec["src_bytes"] = len(b)
    except Gone as e:
        rec["error"] = str(e)
        return rec
    except Exception as e:      # noqa: BLE001
        rec["error"] = f"{type(e).__name__}: {str(e)[:200]}"
        return rec

    # 2) webp
    try:
        os.makedirs(args.out, exist_ok=True)
        w, h = to_webp(raw_path, webp_path, args.max_edge, args.quality)
        rec.update(w=w, h=h, bytes=os.path.getsize(webp_path), ok=True)
    except Exception as e:      # noqa: BLE001
        rec["error"] = f"convert: {type(e).__name__}: {str(e)[:160]}"
    return rec


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    proj = os.path.dirname(here)
    site_root = os.path.join(proj, "site")
    ap = argparse.ArgumentParser(
        description="pbs.twimg.com 图片本地化备选管线（代理链 -> 原图 -> webp -> manifest）")
    ap.add_argument("--out", default=os.path.join(site_root, "img_local"),
                    help="输出目录，默认 site/img_local（不要指到 site/img，那是主产物）")
    ap.add_argument("--mode", choices=["proxy", "direct"], default="proxy",
                    help="proxy=走公共图片代理链（默认，无 VPN 可用）；direct=直连原站（需代理/VPN）")
    ap.add_argument("--proxy", default=None, help="direct 模式下的 HTTP(S) 代理，如 http://127.0.0.1:7890")
    ap.add_argument("--workers", type=int, default=1,
                    help="默认 1：本机并发 >1 会触发链路 RST")
    ap.add_argument("--max-edge", type=int, default=900)
    ap.add_argument("--quality", type=int, default=82)
    ap.add_argument("--retries", type=int, default=3, help="轮数（每轮把所有候选试一遍）")
    ap.add_argument("--retry-sleep", type=float, default=1.0)
    ap.add_argument("--timeout", type=float, default=15.0)
    ap.add_argument("--pace", type=float, default=1.5, help="每张图之间的休眠(秒)，太小会触发 RST")
    ap.add_argument("--cooldown", type=float, default=20.0, help="一轮候选全灭后的冷却(秒)")
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 条（调试）")
    ap.add_argument("--only", default=None, help="只处理 id 含该子串的条目")
    ap.add_argument("--force", action="store_true", help="忽略已有 raw 全部重下")
    ap.add_argument("--retry-failed", action="store_true", help="只重跑 manifest 里失败的条目")
    ap.add_argument("--insecure", action="store_true", help="跳过 TLS 证书校验")
    args = ap.parse_args(argv)

    os.makedirs(args.out, exist_ok=True)
    manifest_path = os.path.join(args.out, "manifest.json")

    targets, src = load_targets(proj)
    if args.only:
        targets = [t for t in targets if args.only in t["id"]]
    if args.retry_failed and os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            prev = json.load(f).get("items", [])
        bad = {(r["id"], r["n"]) for r in prev if not r.get("ok")}
        targets = [t for t in targets if (t["id"], t["n"]) in bad]
    if args.limit:
        targets = targets[: args.limit]

    log(f"[localize] src={os.path.basename(src)} mode={args.mode} "
        f"workers={args.workers} targets={len(targets)}")
    log(f"[localize] out={args.out}")

    ctx = make_ctx(args.insecure)
    records = {}
    if os.path.exists(manifest_path) and not args.force:
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                for r in json.load(f).get("items", []):
                    records[(r["id"], r["n"])] = r
        except Exception:
            records = {}

    t0 = time.time()
    done = fails = 0
    lock = threading.Lock()

    def dump():
        items = [records[k] for k in sorted(records)]
        ok_n = sum(1 for x in items if x.get("ok"))
        atomic_json(manifest_path, {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "source": ("pbs.twimg.com via image-proxy chain" if args.mode == "proxy"
                       else "pbs.twimg.com direct"),
            "mode": args.mode, "total": len(items), "ok": ok_n,
            "failed": len(items) - ok_n, "items": items,
        })

    def work(it):
        nonlocal done, fails
        r = process(it, args, ctx, site_root)
        with lock:
            done += 1
            if not r["ok"]:
                fails += 1
            records[(r["id"], r["n"])] = r
            log(f'[{done:3d}/{len(targets)}] {"ok  " if r["ok"] else "FAIL"} '
                f'{r["id"]}-{r["n"]} {r["w"]}x{r["h"]} {r["bytes"]}B '
                f'via={r["via"]} {r["error"][:90]}')
            if done % 10 == 0 or done == len(targets):
                dump()
        time.sleep(args.pace * random.uniform(0.6, 1.6))
        return r

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futures = [ex.submit(work, t) for t in targets]
        for f in as_completed(futures):
            f.result()      # 异常已在 process 内兜住

    items = [records[k] for k in sorted(records)]
    ok_n = sum(1 for x in items if x.get("ok"))
    dump()
    bad = [x for x in items if not x.get("ok")]
    atomic_json(os.path.join(args.out, "failed.json"), {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "count": len(bad), "items": bad})

    log(f"\n[localize] done in {time.time()-t0:.0f}s — ok={ok_n}/{len(items)} "
        f"failed={len(items)-ok_n}")
    for r in bad:
        log(f"  FAIL {r['id']}-{r['n']} {r['url']} -> {r['error'][:120]}")
    log(f"[localize] manifest: {manifest_path}")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
