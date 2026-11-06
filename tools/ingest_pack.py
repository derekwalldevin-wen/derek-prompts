#!/usr/bin/env python3
"""导入 Grok 的「每日一词 + 视频」增量包（固定目录 current/）。

    python tools/ingest_pack.py --dry-run        # 只看会新增什么、提示词裁了什么
    python tools/ingest_pack.py                  # 下载配图 + 合并 + 生成 md + 重建 + 自检
    python tools/ingest_pack.py --no-download    # 只合并数据

数据源默认：
    C:\\Users\\derek\\Documents\\derek-prompt-library\\current\\data\\daily-word-and-video.json

映射规则：
    type=daily_word → 图像；type=video / both → 视频
    models 为空时：图像补「通用图像模型」，视频补「通用视频工作流」
    description 取 hook（导语），过短时补提示词首句
    prompt_raw  = 包里给的 prompt（一个字符都不改）
    prompt      = 用 clean_prompts 裁掉 💡核心逻辑 / ⚙️关键控制点 / 延伸玩法 / 标签 等发帖文案
    media       = media_notes.preview_urls 下载为 webp（≤900，q82）
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "prompts.json"
HASHES = ROOT / "data" / "prompt-hashes.json"
IMG = ROOT / "site" / "img"
PACK = Path(os.path.expanduser(r"~\Documents\derek-prompt-library\current\data\daily-word-and-video.json"))

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121 Safari/537.36"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cp = _load(ROOT / "tools" / "clean_prompts.py", "clean_prompts")
ib = _load(ROOT / "tools" / "ingest_batch.py", "ingest_batch")


def fetch(url: str) -> bytes | None:
    raw = re.sub(r"^https?://", "", url)
    candidates = [url]
    for tpl in ("https://images.weserv.nl/?url={q}", "https://i0.wp.com/{r}", "https://i1.wp.com/{r}"):
        candidates.append(tpl.format(q=urllib.parse.quote(url, safe=""), r=raw))
    for cand in candidates:
        for attempt in range(2):
            try:
                req = urllib.request.Request(cand, headers={"User-Agent": UA, "Accept": "image/*,*/*"})
                with urllib.request.urlopen(req, timeout=40) as r:
                    body = r.read()
                if body[:2] == b"\xff\xd8" or body[:4] == b"RIFF" or body[:8] == b"\x89PNG\r\n\x1a\n":
                    return body
            except Exception:  # noqa: BLE001
                time.sleep(0.6 * (attempt + 1))
    return None


def make_description(hook: str, prompt: str) -> str:
    hook = (hook or "").strip()
    first = re.split(r"[。！？\n]", (prompt or "").strip())[0].strip()
    text = hook
    if len(text) < 24 and first:
        text = (text + " " + first).strip() if text else first
    if len(text) > 90:
        text = text[:88].rstrip() + "…"
    return text


# 纯「工作流 / 实测 / 感想」帖：没有可复制提示词，按 Derek 的规则不进提示词库
NON_PROMPT = {
    "2099321649518797090": "白模预演再渲染：纯工作流说明，无可复制提示词",
    "2100065439812554875": "Blender 白模工作流续篇：纯工作流说明",
    "2100807790138999020": "白模动画当提示词：纯观点长文",
    "2103676902112460890": "Space Bunny 鹈鹕骑单车：产品感想 + 链接，无提示词",
    "2104099902246867059": "Space Bunny 3D 小游戏：产品感想，无提示词",
    "2104411596940595391": "舞蹈动作 Blender 再编辑：工作流描述，无提示词",
    "2104968377764827568": "可灵 4.0 Flash 实测：产品评测，无提示词",
}

# 结尾的解释性收束语（不是提示词）
TAIL_CUTS = [
    "这类提示词的核心公式",
    "这套提示词最重要的一句",
    "最关键的一句",
    "核心公式是",
    "最重要的这句",
    "记住这一句",
]


def polish(text: str) -> str:
    """去掉开头残留的冒号／空行，和结尾的解释性收束语。"""
    text = text.lstrip()
    text = re.sub(r"^[:：；;，,、\s]+", "", text)
    for mark in TAIL_CUTS:
        i = text.find(mark)
        if i > len(text) * 0.5:  # 只在后半段出现时才认，避免误伤正文
            text = text[:i]
    return text.rstrip()


def looks_like_prompt(text: str) -> bool:
    """粗判是否像提示词：有指令动词或占位符，且不是纯口语感想。"""
    if len(text) < 120:
        return False
    if re.search(r"(我觉得|你觉得|大家|卧槽|震惊|真的|说真的)", text) and "生成" not in text:
        return False
    if "https://t.co/" in text:
        return False
    return bool(re.search(r"(生成|制作|上传|请|【|保留|禁止|使用|要求)", text))


def map_entry(e: dict) -> dict:
    kind = e.get("type") or "daily_word"
    cat = "image" if kind == "daily_word" else "video"
    raw = e.get("prompt") or ""
    kept, _ = cp.clean(raw, str(e["id"]))
    models = list(e.get("models") or [])
    if not models:
        models = ["通用图像模型"] if cat == "image" else ["通用视频工作流"]
    kept = polish(kept)
    return {
        "id": str(e["id"]),
        "title": (e.get("title") or "").strip(),
        "description": make_description(e.get("hook") or "", raw),
        "category": cat,
        "models": models,
        "date": e.get("date") or "",
        "x_url": e.get("url") or f"https://x.com/derek_wall90176/status/{e['id']}",
        "prompt": kept,
        "prompt_raw": raw,
        "media": [],
        "media_preview_urls": list((e.get("media_notes") or {}).get("preview_urls") or []),
        "notes": "",
    }


def main() -> None:
    args = sys.argv[1:]
    pack_path = Path(args[args.index("--pack") + 1]) if "--pack" in args else PACK
    dry = "--dry-run" in args
    no_dl = "--no-download" in args

    if not pack_path.exists():
        raise SystemExit(f"找不到增减包: {pack_path}")

    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    data = json.loads(DATA.read_text(encoding="utf-8"))
    have = {str(x["id"]) for x in data}
    skipped = [e for e in pack if str(e["id"]) not in have and str(e["id"]) in NON_PROMPT]
    fresh = [map_entry(e) for e in pack if str(e["id"]) not in have and str(e["id"]) not in NON_PROMPT]

    print(f"包内 {len(pack)} 条；库里已有 {len(data)} 条；本次新增 {len(fresh)} 条；排除非提示词 {len(skipped)} 条")
    for e in skipped:
        print(f"  − {e.get('date')} {e.get('title')}：{NON_PROMPT[str(e['id'])]}")
    if not fresh:
        print("没有新内容，结束。")
        return

    trimmed = 0
    flagged = []
    for e in fresh:
        removed = len(e["prompt_raw"]) - len(e["prompt"])
        trimmed += 1 if removed > 0 else 0
        if not looks_like_prompt(e["prompt"]):
            flagged.append(e)
        print(f"  + {e['date']} [{e['category']}] {e['title'][:18]}  提示词 {len(e['prompt_raw'])}→{len(e['prompt'])} 字"
              f"  图 {len(e['media_preview_urls'])} 张  模型 {','.join(e['models'])}")
    print(f"其中 {trimmed} 条裁掉了社媒文案")
    if flagged:
        print("⚠ 疑似不是提示词，建议人工过一眼：")
        for e in flagged:
            print(f"    {e['id']} {e['title']}：{e['prompt'][:60]!r}")

    if dry:
        print("\n[dry-run] 未下载、未写入。")
        return

    IMG.mkdir(parents=True, exist_ok=True)
    ok_imgs = fail_imgs = 0
    for e in fresh:
        media = []
        wanted = len(e["media_preview_urls"])
        for n, url in enumerate(e["media_preview_urls"], 1):
            if no_dl:
                break
            dest = IMG / f"{e['id']}-{n}.webp"
            if dest.exists():
                with Image.open(dest) as im:
                    media.append({"src": f"img/{dest.name}", "w": im.width, "h": im.height, "bytes": dest.stat().st_size})
                ok_imgs += 1
                continue
            body = fetch(url)
            if not body:
                print(f"    ! 取不到 {e['id']}-{n}（保留远程 URL）")
                fail_imgs += 1
                continue
            saved = ib.save_webp(body, dest)
            if saved:
                media.append({"src": f"img/{dest.name}", "w": saved[0], "h": saved[1], "bytes": saved[2]})
                ok_imgs += 1
            else:
                fail_imgs += 1
        if media:
            e["media"] = media
            e["media_preview_urls"] = [m["src"] for m in media]  # 统一为本地相对路径
        print(f"  {e['title'][:16]}: 本地化 {len(media)}/{wanted} 张")

    data.extend(fresh)
    data.sort(key=lambda x: (x.get("date") or "", str(x.get("id"))), reverse=True)
    DATA.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"data/prompts.json: {len(data)} 条；图片 成功 {ok_imgs} / 失败 {fail_imgs}")

    # 给新条目补哈希基线（锁定 prompt_raw）
    import hashlib

    hashes = json.loads(HASHES.read_text(encoding="utf-8")) if HASHES.exists() else {}
    for e in fresh:
        hashes.setdefault(e["id"], {
            "sha256": hashlib.sha256(e["prompt_raw"].encode("utf-8")).hexdigest(),
            "chars": len(e["prompt_raw"]),
        })
    HASHES.write_text(json.dumps(hashes, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    ib.write_entries_md(fresh)
    ib.bump_expected(data)

    import subprocess

    for cmd in (["python", "build.py", "--both"], ["python", "verify.py"]):
        if subprocess.run(cmd, cwd=ROOT / "site").returncode != 0:
            raise SystemExit(f"{' '.join(cmd)} 失败")
    print("完成 → 检查通过后 git add -A && git commit && git push 即上线")


if __name__ == "__main__":
    main()
