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
entries/*.md               64 篇 Markdown 原文
site/                      站点源码（index.html / build.py / verify.py / img / fonts）
docs/                      产物 ①：GitHub Pages 用（canonical / 分享卡指向 github.io）
cn/                        产物 ②：EdgeOne 国内版用（canonical / 分享卡指向 edgeone 域名）
tools/                     截图、端到端验收、媒体本地化、发布脚本
.githooks/pre-commit       提交前自动重建 docs/ + cn/（已 git config core.hooksPath .githooks）
```

## 两套站点 & 自动更新

| 产物 | 托管 | 域名 |
|---|---|---|
| `docs/` | GitHub Pages（main → /docs） | https://derekwalldevin-wen.github.io/derek-prompts/ |
| `cn/` | EdgeOne Makers（导入 Git 仓库，根目录 `cn`） | https://derekwen-aigc.edgeone.dev/ |

- 一次生成两套：`cd site && python build.py --both`
- 国内域名只写在一处：`site/build.py` 里的 `CN_BASE`，换域名改它再 `--both`
- **提交即自动重建**：装了 pre-commit hook，凡改动 `data/`、`entries/`、`site/`、`README.md`，提交时自动跑 `build.py --both` 并把 `docs/`、`cn/` 一起加入本次提交 → 推上去后 GitHub Pages 与 EdgeOne 各自重部署
- 没有 Git 集成时的手动兜底：`python tools/deploy_cn.py --url <国内域名>` 出 zip + 二维码，拖到 EdgeOne Drop

## 工具

| 脚本 | 用途 |
|------|------|
| `tools/shot.mjs` | 无依赖 CDP 截图（全页／分段／移动端／暗色） |
| `tools/e2e.mjs` | 21 项功能验收（搜索、筛选、详情、复制、外链、本地化、主题…） |
| `tools/clean_prompts.py` | 把「🔁延伸玩法／⚙️参数技巧／📌一句话总结」及评论区引导从提示词里裁掉（原文留存在 `prompt_raw`） |
| `tools/ingest_batch.py` | 把一批新帖 JSON 合并进库：去重、下载配图转 webp、生成 Markdown、重建、自检 |
| `tools/apply_media.py` | 把下载清单合并回 `data/prompts.json` |
| `tools/localize_images.py` | 备用下载管线：走图片代理抓 X CDN，断点续传，写 `site/img_local/` |
| `tools/publish_pages.py` | 一键发布到 GitHub Pages（默认 dry-run，需 `--yes` 才真推） |

需要 Node 18+ 才能跑 `shot.mjs` / `e2e.mjs`；Python 脚本需要 Pillow。

## 每日同步（Grok → 本站）

**主通道（固定目录，Grok 总管每天覆盖）：**

```
C:\Users\derek\Documents\derek-prompt-library\current\data\daily-word-and-video.json
```

```bash
python tools/ingest_pack.py --dry-run   # 先看会新增什么、裁掉了什么、哪些被排除
python tools/ingest_pack.py             # 下载配图 + 合并 + 生成 md + 重建 + 自检
git add -A && git commit -m "同步 YYYY-MM-DD" && git push   # Pages 约 1 分钟自动重建
```

`ingest_pack.py` 的规则：
- 按 `id` 去重，旧条目绝不覆盖；`type=daily_word` → 图像，`video`/`both` → 视频
- `models` 为空的：图像补「通用图像模型」，视频补「通用视频工作流」
- **纯工作流／实测／感想帖（没有可复制提示词）会被排除**，名单在脚本里的 `NON_PROMPT`，每次 dry-run 都会列出来
- 提示词只保留本体：裁掉 💡核心逻辑 / ⚙️关键控制点 / 延伸玩法 / 「核心公式是…」/ 评论区引导 / hashtag
- 配图从 `media_notes.preview_urls` 下载成 webp（本机被墙时自动走图片代理）

**备用通道（手动 JSON）：** 把 [`tools/grok-daily-prompt.md`](tools/grok-daily-prompt.md) 里的提示词丢给 Grok Bot，
把输出存成 `data/inbox/YYYY-MM-DD.json`，然后 `python tools/ingest_batch.py data/inbox/xxx.json`。

`verify.py` 用「不少于基线」判断：新增不会 FAIL，条目变少会 FAIL；基线在 `data/expected.json`。

## 提示词与社媒文案的分工

- `prompt`：**只放真正能粘贴进模型的提示词**。已把 35 条里的 🔁延伸玩法 / ⚙️参数技巧 /
  📌一句话总结 / 避坑 / 评论区引导 / hashtag / 「完整提示词，直接复制：」等发帖文案裁掉。
- `prompt_raw`：这些帖子的完整原文，逐字保留（`verify.py` 用交接快照的 sha256 校验它没被改过），
  用于溯源，不在页面上展示。
- 裁剪方式只做首尾截断，不重写、不重排：`verify.py` 会断言 `prompt` 是 `prompt_raw` 的连续子串。

## 媒体说明

- 配图已本地化为 webp（最长边 ≤ 900，q82），共 150 张，全部来自对应 X 原帖。
- 有 1 张图在 X 上已被删除（帖子 `2105130671031427095` 的第 1 张，22 种官方尺寸变体 + archive.org 全部 404），因此该条只有 2 张配图 —— 数据与页面均按实际可用图片自洽。
- 想重新抓取（例如开了代理）：`python tools/localize_images.py --mode direct --proxy http://127.0.0.1:7890`。

## 版权

提示词与配图来自德里克文的 X 原创帖，版权归德里克文所有。本仓库只做归档与检索，不重新发布到第三方平台。
当前数据范围：2026-09-28 → 2026-11-04（Asia/Shanghai）。
