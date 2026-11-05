#!/usr/bin/env python3
"""Self-check for the gallery. Exit code 0 = everything matches the handoff.

    cd site && python verify.py

Checks
  1. 42 entries / 39 image / 3 video
  2. prompt text byte-identical to the handoff snapshot (data/prompt-hashes.json)
  3. every referenced image exists locally, is non-empty webp
  4. no remote (http) image URLs left in the data
  5. every entry has a Markdown file in entries/
  6. docs/ is complete and deployable (index.html, data/prompts.js, .nojekyll, img/)
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = ROOT / "data" / "prompts.json"
HASHES = ROOT / "data" / "prompt-hashes.json"
DOCS = ROOT / "docs"

ok = True
problems: list[str] = []


def check(cond: bool, msg: str, detail: str = "") -> None:
    global ok
    if cond:
        print(f"PASS  {msg}")
    else:
        ok = False
        problems.append(msg + (f" — {detail}" if detail else ""))
        print(f"FAIL  {msg}" + (f"  — {detail}" if detail else ""))


def main() -> None:
    entries = json.loads(DATA.read_text(encoding="utf-8"))
    hashes = json.loads(HASHES.read_text(encoding="utf-8")) if HASHES.exists() else {}

    img = sum(1 for e in entries if e.get("category") == "image")
    vid = sum(1 for e in entries if e.get("category") == "video")
    check(len(entries) == 42 and img == 39 and vid == 3, f"条目数 42 / 图像 39 / 视频 3", f"got {len(entries)}/{img}/{vid}")

    changed = []
    for e in entries:
        want = (hashes.get(str(e["id"])) or {}).get("sha256")
        got = hashlib.sha256((e.get("prompt") or "").encode("utf-8")).hexdigest()
        if want and want != got:
            changed.append(e["id"])
    check(not changed, "提示词原文与交接快照一致（未被改写）", ",".join(changed))

    missing, remote, not_webp, total = [], [], [], 0
    for e in entries:
        media = e.get("media") or []
        if not media:
            missing.append(e["id"] + "(no media)")
        for m in media:
            total += 1
            src = m.get("src", "")
            if src.startswith("http"):
                remote.append(e["id"])
                continue
            p = HERE / src
            if not p.exists() or p.stat().st_size == 0:
                missing.append(src)
            elif p.suffix.lower() != ".webp":
                not_webp.append(src)
    check(not remote, "数据中无远程图片 URL（已本地化）", ",".join(sorted(set(remote))))
    check(not missing, f"本地图片齐全（{total} 张）", ",".join(missing[:6]))
    check(not not_webp, "图片格式均为 webp", ",".join(not_webp[:6]))

    md_missing = [e["id"] for e in entries if not list((ROOT / "entries").glob(f"{e['id']}-*.md"))]
    check(not md_missing, "每条都有对应 Markdown 原文", ",".join(md_missing))

    if DOCS.exists():
        need = [DOCS / "index.html", DOCS / "data" / "prompts.js", DOCS / ".nojekyll"]
        check(all(p.exists() for p in need), "docs/ 含 index.html + data/prompts.js + .nojekyll")
        docs_img = len(list((DOCS / "img").glob("*.webp"))) if (DOCS / "img").is_dir() else 0
        check(docs_img == total, f"docs/img 图片数 = {total}", f"got {docs_img}")
    else:
        check(False, "docs/ 已构建（python build.py）")

    print()
    if ok:
        print(f"ALL OK — 42 条（图像 39 / 视频 3），{total} 张本地 webp，prompt 原文未改动。")
    else:
        print("FAILED:")
        for p in problems:
            print("  -", p)
        sys.exit(1)


if __name__ == "__main__":
    main()
