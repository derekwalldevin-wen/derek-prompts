#!/usr/bin/env python3
"""Separate the real prompt from the social-media copy that was appended to it.

X 帖子里「🔁延伸玩法 / ⚙️参数技巧 / 📌一句话总结」以及「评论区返图」「#标签」
是发帖用的文案，不是提示词。本脚本：

  prompt_raw  原始整段（一字不改，留作凭据，并用 prompt-hashes.json 校验）
  prompt      仅保留真正可粘贴到模型里的提示词（= prompt_raw 的**前缀**截断，不改字）

同时把 entries/*.md 的 ``` 提示词 ``` 区块同步为清洗后的文本。

    python tools/clean_prompts.py --dry-run   # 只打印删了什么
    python tools/clean_prompts.py             # 写入 data/prompts.json + entries/
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "prompts.json"
ENTRIES = ROOT / "entries"

# 社媒段落的分节标记（出现即视为提示词结束）
MARKS = [
    "🔁", "⚙️", "⚙", "📌", "💡",
    "延伸玩法", "参数技巧", "一句话总结", "怎么用", "避坑", "记住一句", "记住这一句",
]

# 少数帖子的社媒尾巴没有分节标记，手工给出截断点（只截不删改正文）
EXTRA_CUTS = {
    "2117795655389433978": "\n\n你做出了什么好玩的东西",
    "2108040485990551623": "\n\n避坑：",
}

# 个别帖子在真正提示词之前有一段「怎么做 / 复制这段 / 完整版」的上手说明，
# 从这些字符串开始截掉（只删前缀，不改动提示词本体）
HEAD_CUTS = {
    "2108040485990551623": "请根据我的社交账号",
    "2108801352302219496": "请根据我上传的参考图片",
    "2116409808869818851": "生成一张独立3:4竖版时装概念摄影海报",
    "2116709485725339750": "生成一张3:4竖版“动作切片”",
    "2117077017598554604": "将照片中的主要主体转成刮刀厚涂油画",
}

# 句尾的社媒 CTA / hashtag（只在文本末尾匹配，避免误伤正文）
TAIL_PATTERNS = [
    r"\n*#[^\n#]{0,40}(?:\s+#[^\n#]{0,40})*\s*$",
    r"\n*[^\n]{0,50}(?:评论区|返图|👇)[^\n]{0,80}\s*$",
]

BLOCK = re.compile(r"(### 提示词\s*\n+\s*```[a-zA-Z]*\n)(.*?)(\n```)", re.S)


def clean(text: str, entry_id: str) -> tuple[str, str]:
    cut = len(text)
    for mark in MARKS:
        i = text.find(mark)
        if i != -1:
            cut = min(cut, i)
    extra = EXTRA_CUTS.get(entry_id)
    if extra and extra in text:
        cut = min(cut, text.find(extra))
    kept = text[:cut]
    for pat in TAIL_PATTERNS:
        kept = re.sub(pat, "", kept)
    head = HEAD_CUTS.get(entry_id)
    if head and head in kept:
        kept = kept[kept.find(head):]
    kept = kept.rstrip()
    removed = text[len(kept):]
    return kept, removed


def main() -> None:
    dry = "--dry-run" in sys.argv
    entries = json.loads(DATA.read_text(encoding="utf-8"))
    changed = 0
    rows = []
    for e in entries:
        raw = e.get("prompt_raw") or e.get("prompt") or ""
        kept, removed = clean(raw, str(e["id"]))
        if not kept.strip():
            raise SystemExit(f"cleaning removed everything for {e['id']} — abort")
        rows.append((e, raw, kept, removed))
        if kept != (e.get("prompt") or ""):
            changed += 1
            print(f"— {e['id']} {e['title'][:16]}  {len(raw)} → {len(kept)} 字")
            print(f"    保留结尾: …{kept[-40:]!r}")
            print(f"    删掉开头: {removed[:60]!r}")
        if not dry:
            e["prompt_raw"] = raw
            e["prompt"] = kept
            e["prompt_meta"] = {
                "chars_raw": len(raw),
                "chars_prompt": len(kept),
                "stripped_social_copy": bool(removed),
            }

    print(f"\n{changed} / {len(entries)} 条需要清洗")

    if dry:
        print("\n[dry-run] 未写入。")
        return

    DATA.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # 同步 entries/*.md 的提示词区块
    by_id = {str(e["id"]): e["prompt"] for e in entries}
    md_done = 0
    for md in sorted(ENTRIES.glob("*.md")):
        eid = md.name.split("-", 1)[0]
        if eid not in by_id:
            continue
        text = md.read_text(encoding="utf-8")
        m = BLOCK.search(text)
        if not m:
            print("  ! 未找到提示词代码块:", md.name)
            continue
        new = text[: m.start(2)] + by_id[eid].strip() + text[m.end(2):]
        if new != text:
            md.write_text(new, encoding="utf-8")
            md_done += 1
    print(f"data/prompts.json 已更新；entries/*.md 更新 {md_done} 个")


if __name__ == "__main__":
    main()
