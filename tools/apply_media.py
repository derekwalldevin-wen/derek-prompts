#!/usr/bin/env python3
"""Merge the downloaded-media manifest into data/prompts.json.

- Replaces remote X CDN URLs with local relative paths (img/<id>-<n>.webp).
- Adds a `media` array with per-image width/height so the page can reserve
  layout space (no CLS) and clamp very tall images.
- Never touches `prompt`, `title`, `description` or any other editorial field.

Run:  python tools/apply_media.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "prompts.json"
MANIFEST = ROOT / "data" / "media-manifest.json"


def main() -> None:
    raw = json.loads(DATA.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    by_id: dict[str, list] = {}
    for m in manifest:
        by_id.setdefault(m["id"], []).append(m)

    total = missing = 0
    for entry in raw:
        rows = sorted(by_id.get(entry["id"], []), key=lambda m: m["n"])
        ok = [m for m in rows if m.get("ok")]
        missing += len(rows) - len(ok)
        entry["media_preview_urls"] = [m["file"] for m in ok]
        entry["media"] = [
            {"src": m["file"], "w": m["w"], "h": m["h"], "bytes": m["bytes"]} for m in ok
        ]
        total += len(ok)

    DATA.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"merged {total} local images into {len(raw)} entries ({missing} unavailable on X CDN)")
    no_media = [e["id"] for e in raw if not e["media_preview_urls"]]
    if no_media:
        print("entries with no local media:", no_media)


if __name__ == "__main__":
    main()
