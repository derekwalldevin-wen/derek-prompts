#!/usr/bin/env python3
"""把一批新帖子合并进提示词库（供每日/每周同步用）。

    python tools/ingest_batch.py data/inbox/2026-11-05.json
    python tools/ingest_batch.py data/inbox/xxx.json --dry-run
    python tools/ingest_batch.py data/inbox/xxx.json --no-download   # 仅合并数据，图片稍后补

输入：一个 JSON 数组，每条字段与 data/prompts.json 一致（见 tools/grok-daily-prompt.md）：

    id, title, description, category(image|video), models[], date, x_url, prompt,
    media_preview_urls[], notes(可选)

流程：
  1. 按 id 去重（已存在则跳过，不覆盖旧数据）
  2. 下载 media_preview_urls → site/img/<id>-<n>.webp（最长边 ≤900，q82）
     · 先直连，失败走图片代理（images.weserv.nl / i*.wp.com），X CDN 在本机被墙时也能取
  3. 写回 data/prompts.json（新增条目 prompt_raw = prompt，不做任何改写）
  4. 重建 site/data/prompts.js 与 docs/，并跑一遍 verify.py
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "prompts.json"
IMG = ROOT / "site" / "img"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121 Safari/537.36"
PROXIES = [
    "https://images.weserv.nl/?url={u}",
    "https://i0.wp.com/{raw}",
    "https://i1.wp.com/{raw}",
    "https://i2.wp.com/{raw}",
]
REQUIRED = {"id", "title", "category", "x_url", "prompt"}


def fetch(url: str, timeout: int = 40) -> bytes | None:
    """直连 → 代理链，返回图片字节。"""
    candidates = [url]
    raw = re.sub(r"^https?://", "", url)
    for p in PROXIES:
        candidates.append(p.format(u=urllib.parse.quote(url, safe=""), raw=raw))
    for cand in candidates:
        for attempt in range(2):
            try:
                req = urllib.request.Request(cand, headers={"User-Agent": UA, "Accept": "image/*,*/*"})
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    data = r.read()
                if data[:2] == b"\xff\xd8" or data[:4] == b"RIFF" or data[:8] == b"\x89PNG\r\n\x1a\n":
                    return data
            except Exception:  # noqa: BLE001
                time.sleep(0.8 * (attempt + 1))
    return None


def write_entries_md(entries: list[dict]) -> None:
    """为新条目生成 entries/*.md（结构与历史条目一致，便于 Markdown 原文链接）。"""
    out = ROOT / "entries"
    out.mkdir(exist_ok=True)
    for e in entries:
        slug = re.sub(r'[\\/:*?"<>|\n\r\t]', "", e.get("title") or "untitled").strip()[:40]
        path = out / f"{e['id']}-{slug}.md"
        if path.exists():
            continue
        models = "\n".join(f"- {m}" for m in (e.get("models") or [])) or "- 通用图像模型"
        path.write_text(
            f"## {e.get('title','')}\n\n"
            f"### 概述\n\n{e.get('description','')}\n\n"
            f"### 来源\n\n[X 原帖]({e.get('x_url','')}) · {e.get('date','')}（Asia/Shanghai）\n\n"
            f"### 适配模型\n\n{models}\n\n"
            f"### 示例\n\n见 X 原帖媒体：{e.get('x_url','')}\n\n"
            f"### 提示词\n\n```\n{e.get('prompt','').strip()}\n```\n",
            encoding="utf-8",
        )
        print(f"  + entries/{path.name}")


def bump_expected(entries: list[dict]) -> None:
    (ROOT / "data" / "expected.json").write_text(
        json.dumps(
            {
                "total": len(entries),
                "image": sum(1 for e in entries if e.get("category") == "image"),
                "video": sum(1 for e in entries if e.get("category") == "video"),
                "note": "最新基线。verify.py 用「不少于」判断：删除条目会 FAIL，新增不会。",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def save_webp(data: bytes, dest: Path) -> tuple[int, int, int] | None:
    tmp = dest.with_suffix(".tmp")
    tmp.write_bytes(data)
    try:
        with Image.open(tmp) as im:
            im = im.convert("RGB")
            w, h = im.size
            scale = min(1.0, 900 / max(w, h))
            if scale < 1.0:
                im = im.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)
            im.save(dest, "WEBP", quality=82, method=6)
            return im.width, im.height, dest.stat().st_size
    except Exception as e:  # noqa: BLE001
        print(f"    ! 转码失败 {dest.name}: {e}")
        return None
    finally:
        tmp.unlink(missing_ok=True)


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        raise SystemExit(__doc__)
    src = Path(args[0])
    dry = "--dry-run" in sys.argv
    no_dl = "--no-download" in sys.argv

    batch = json.loads(src.read_text(encoding="utf-8"))
    if not isinstance(batch, list):
        raise SystemExit("批次文件必须是 JSON 数组")

    data = json.loads(DATA.read_text(encoding="utf-8"))
    have = {str(e["id"]) for e in data}
    fresh = []
    for e in batch:
        missing = REQUIRED - set(e)
        if missing:
            raise SystemExit(f"条目 {e.get('id')} 缺字段: {sorted(missing)}")
        if str(e["id"]) in have:
            print(f"  跳过（已存在）{e['id']} {e.get('title','')}")
            continue
        fresh.append(e)

    print(f"批次 {len(batch)} 条：新增 {len(fresh)}，已存在 {len(batch) - len(fresh)}")
    if not fresh:
        return
    if dry:
        for e in fresh:
            print(f"  + {e['id']} [{e.get('category')}] {e.get('title')}  图 {len(e.get('media_preview_urls') or [])} 张")
        print("[dry-run] 未写入")
        return

    IMG.mkdir(parents=True, exist_ok=True)
    for e in fresh:
        e["id"] = str(e["id"])
        e.setdefault("description", "")
        e.setdefault("models", [])
        e.setdefault("notes", "")
        e.setdefault("prompt_raw", e["prompt"])  # 新条目：原始即提示词
        media = []
        urls = e.get("media_preview_urls") or []
        for n, url in enumerate(urls, 1):
            if no_dl:
                break
            dest = IMG / f"{e['id']}-{n}.webp"
            if dest.exists():
                with Image.open(dest) as im:
                    media.append({"src": f"img/{dest.name}", "w": im.width, "h": im.height, "bytes": dest.stat().st_size})
                continue
            print(f"  下载 {e['id']}-{n}.webp …")
            data_bytes = fetch(url)
            if not data_bytes:
                print("    ! 下载失败（保留远程 URL 占位）")
                continue
            saved = save_webp(data_bytes, dest)
            if saved:
                media.append({"src": f"img/{dest.name}", "w": saved[0], "h": saved[1], "bytes": saved[2]})
        if media:
            e["media"] = media
            e["media_preview_urls"] = [m["src"] for m in media]
    data.extend(fresh)

    if dry:
        return
    DATA.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"data/prompts.json: {len(data)} 条")

    write_entries_md(fresh)
    bump_expected(data)

    import subprocess

    for cmd, cwd in ((["python", "build.py"], ROOT / "site"), (["python", "verify.py"], ROOT / "site")):
        r = subprocess.run(cmd, cwd=cwd)
        if r.returncode != 0:
            raise SystemExit(f"{' '.join(cmd)} 失败")
    print("完成。检查通过后：git add -A && git commit && git push（部署见 tools/publish_pages.py）")


if __name__ == "__main__":
    main()
