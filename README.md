# 德里克文 · 提示词库

> 德里克文（[@derek_wall90176](https://x.com/derek_wall90176)）在 X 上发布的原创图像／视频 AI 提示词归档。
> **42 条 · 图像 39 / 视频 3**，每条都有完整可复制的提示词、本地化配图、X 原帖与 Markdown 原文。

静态单页，无框架、无第三方请求（字体／图片／脚本全在仓库内），朱砂 `#c23b22` / 暖纸 `#f4efe6`。

**在线浏览：https://derekwalldevin-wen.github.io/derek-prompts/**

## 浏览

- **搜索**：标题、描述、模型、提示词正文（按 `/` 聚焦，Esc 清空），筛选状态写进 URL 可分享
- **筛选**：全部 / 图像 / 视频，模型 chips（均带计数）
- **详情**：左图右文双栏、完整 prompt、一键复制、X 原帖、Markdown 原文、上/下一条（← → 键）
- **深色模式**：右上角 ◐（默认暖纸亮色）
- 移动端可用；图片懒加载并预留宽高，不会跳动

## 本地运行

```bash
cd site
python build.py             # 生成 site/data/prompts.js，并构建 docs/
python -m http.server 8765  # 打开 http://127.0.0.1:8765/
python verify.py            # 自检
```

`verify.py` 会检查：42/39/3 条目数、**prompt 原文与交接快照逐条哈希一致（未被改写）**、150 张本地 webp 齐全、无远程图片 URL、每条都有 Markdown、`docs/` 可部署。期望以 `ALL OK` 结尾。

> macOS/Linux 上把 `python` 换成 `python3` 即可。

## 目录

```
data/prompts.json          唯一数据源（prompt 原文，勿改写）
data/media-manifest.json   媒体下载清单（每张图的来源、尺寸、成败）
data/prompt-hashes.json    交接时的 prompt 哈希快照，用于校验原文未被改动
entries/*.md               42 篇 Markdown 原文
site/                      站点源码（index.html / build.py / verify.py / img / fonts）
docs/                      构建产物，可直接部署（GitHub Pages 指向这里，含 .nojekyll）
tools/                     截图、端到端验收、媒体本地化、发布脚本
HANDOFF-DeepSeek.md        原始交接说明（Grok）
DESIGN-SPEC.md / GAPS.md   设计规格 / 收录缺口
```

## 工具

| 脚本 | 用途 |
|------|------|
| `tools/shot.mjs` | 无依赖 CDP 截图（全页／分段／移动端／暗色） |
| `tools/e2e.mjs` | 21 项功能验收（搜索、筛选、详情、复制、外链、本地化、主题…） |
| `tools/apply_media.py` | 把下载清单合并回 `data/prompts.json` |
| `tools/localize_images.py` | 备用下载管线：走图片代理抓 X CDN，断点续传，写 `site/img_local/` |
| `tools/publish_pages.py` | 一键发布到 GitHub Pages（默认 dry-run，需 `--yes` 才真推） |

需要 Node 18+ 才能跑 `shot.mjs` / `e2e.mjs`；Python 脚本需要 Pillow。

## 媒体说明

- 配图已本地化为 webp（最长边 ≤ 900，q82），共 150 张，全部来自对应 X 原帖。
- 有 1 张图在 X 上已被删除（帖子 `2105130671031427095` 的第 1 张，22 种官方尺寸变体 + archive.org 全部 404），因此该条只有 2 张配图 —— 数据与页面均按实际可用图片自洽。
- 想重新抓取（例如开了代理）：`python tools/localize_images.py --mode direct --proxy http://127.0.0.1:7890`。

## 版权

提示词与配图来自德里克文的 X 原创帖，版权归德里克文所有。本仓库只做归档与检索，不重新发布到第三方平台。
当前数据范围：2026-09-28 → 2026-11-04（Asia/Shanghai）。
