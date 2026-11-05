# DeepSeek 交接包 · 德里克文提示词库网站

> 给 Derek 粘贴给 DeepSeek Harness（DSH）用。Grok 已完成数据采集 + 静态预览站；请在本包基础上打磨、本地化媒体并可选部署。

---

## 1. 任务目标

做一套**类似「归藏的提示词库」**的公开 / 可部署图文视频提示词站：

- 参考站：https://op7418.github.io/guizang-s-prompt/
- 参考仓库：https://github.com/op7418/guizang-s-prompt
- 品牌归属：**德里克文 / Derek**（[@derek_wall90176](https://x.com/derek_wall90176)）
- 数据已由 Grok 从 X 原创帖收集，**不要重新编造提示词**

交付物优先级建议：

1. 可打开的设计感静态站（本包 `site/` 已有预览）
2. 预览图本地化（webp）后可 GitHub Pages 部署
3. 可选：补更早 X 帖、Text 类目

---

## 2. 已完成（Grok）

| 项 | 说明 |
|----|------|
| 条目数 | **42**（图像 39 · 视频 3） |
| 日期范围 | 约 **2026-09-28 → 2026-11-04**（Asia/Shanghai） |
| 结构化数据 | `data/prompts.json` |
| Markdown 条目 | `entries/*.md` ×42（归藏风格章节） |
| Grok Bot Page | https://cursor.com/canvas/store-2569aa4d-9eb4-4e0f-8358-d508125c7839/a97a5842-b2df-418f-83a4-9e2cfdebbf7e （可搜索筛选；**请保留，勿弄坏**） |
| 静态预览站 | `site/index.html`（朱砂 / 暖纸编辑风，非归藏克隆） |
| 重建脚本 | `site/build.py` → `site/data/prompts.js` |
| 缺口说明 | `GAPS.md` |
| 设计规格 | `DESIGN-SPEC.md` |

### 字段（`prompts.json` 每条）

```
id, title, description, category (image|video), models[], date,
x_url, prompt, media_preview_urls[], notes
```

- `category`：`image` → UI「图像」；`video` →「视频」
- `prompt`：单字符串；站内需包成 Guizang 式 `prompts:[{name,text}]`（`build.py` 已做）
- `media_preview_urls`：X CDN 远程图，**可能过期**；当前 42/42 条至少有 1 个 URL（多数 3–4 个）

### 模型分布（采集时）

- 通用图像模型 ×36
- MiniMax ×3
- GPT Image / ChatGPT ×2
- DeepSeek ×1
- 通用视频工作流 ×1
- 通用对话出图 ×1

---

## 3. 数据放哪里

### 在 Grok box 上的路径

```
/workspace/prompt-library/derek-site-handoff-2026-11-04/
├── HANDOFF-DeepSeek.md      ← 本文件
├── DESIGN-SPEC.md
├── GAPS.md
├── data/prompts.json        ← 源数据
├── entries/*.md             ← 42 篇
├── site/                    ← 预览站
│   ├── index.html
│   ├── build.py
│   ├── README.md
│   └── data/prompts.json + prompts.js
└── derek-prompt-library-handoff.zip
```

原始采集归档（含 raw 批次，**不必交给 DSH**）：

```
/workspace/prompt-library/derek-2026-11-04/
```

### Derek 应拷给 DSH 的内容

优先整包 zip：

**`derek-prompt-library-handoff.zip`**（本目录根下）

解压后工作区应含：`data/`、`entries/`、`site/`、`HANDOFF-DeepSeek.md`、`DESIGN-SPEC.md`、`GAPS.md`。

不要把 `_batches`、`raw-*.json`、`_page_source_preview.tsx` 等垃圾进 DSH（zip 已排除）。

---

## 4. 归藏参考拆解

### 仓库布局（精简）

```
guizang-s-prompt/
├── image/ | Video/ | Text/     ← 按类目的 .md / .json 提示词
├── gallery/
│   ├── template.html           ← 前端模板（/*DATA*/[] 占位）
│   ├── build.py                ← 解析 md → 卡片 JSON → 注入 docs/index.html
│   └── overrides.json
└── docs/
    ├── index.html              ← GitHub Pages 入口
    └── img/*.webp              ← 本地化预览
```

### 构建流

`python3 gallery/build.py`：

1. 扫描 `image/`、`Video/`、`Text/`
2. 解析 md（标题、概述、模型、提示词、相对路径配图）
3. PIL 缩略并转 **webp** 到 `docs/img/`
4. 把卡片数组 JSON 注入 `template.html` 的 `const D=/*DATA*/[]`
5. 写出 `docs/index.html`

### 模板能力（应对齐）

- sticky 搜索 + 分类 chips（全部/图像/视频/文本）+ 模型 chips
- CSS 多列瀑布流；卡片缩略图 / NO PREVIEW
- `<dialog>` 详情：多图、复制提示词、X 原帖、GitHub 文件链
- Inter + JetBrains Mono；奶油底 `#fafaf8`；强调色 `#002FA7`

### Derek JSON → Guizang 卡片 schema

| Guizang card | Derek 来源 |
|--------------|------------|
| `title` | `title` |
| `desc` | `description` |
| `cat` | `image`→`图像`，`video`→`视频` |
| `models` | `models` |
| `date` | `date`（已是上海时区日期字符串） |
| `source` | `x_url` |
| `images` | 现用 `media_preview_urls`；正式应改为本地 `img/*.webp` |
| `prompts` | `[{ "name": "提示词", "text": prompt }]` |
| `file` / `url` | 可用 `entries/{id}-….md`；GitHub blob 链在自建仓后填 |

本包 `site/build.py` 已做上述归一化 → `window.DEREK_PROMPTS`。

---

## 5. 设计规格 / 验收标准

详见 `DESIGN-SPEC.md`。硬性验收：

1. 搜索 + 分类（全部|图像|视频）+ 模型筛选
2. 瀑布流 / 卡片网格
3. 详情：全文 prompt + **复制** + **X 原帖**
4. 响应式、中文 UI
5. 品牌「德里克文」；**不冒充归藏**；主色勿用 Klein `#002FA7`（预览站用朱砂 `#c23b22`）
6. 图像尽量本地化 webp（归藏做法）；部署前不要依赖易过期 CDN
7. 可选：GitHub Pages（`docs/` 或 `gh-pages`，加 `.nojekyll`）

### 可选 GitHub Pages 步骤（给 DSH）

1. 新建公开仓，例如 `derek-prompts`
2. 将 `entries/` 按类目整理或保持扁平；`site/` 构建产物放到 `docs/`
3. 下载媒体 → `docs/img/{id}.webp`，改 `images` 为相对路径
4. Settings → Pages → Deploy from `docs/`
5. README 链到 Pages URL 与 X 账号

---

## 6. DSH 待办清单（可执行）

1. **审阅** `site/index.html` 预览；按 `DESIGN-SPEC.md` 微调字体/间距/动效（可更「设计感」，保持品牌）。
2. **下载** 每条 `media_preview_urls[0]`（及需要的多图）到本地，转 webp（建议最长边 ≤900），写入 `site/img/` 或 `docs/img/`，更新数据字段为相对路径。
3. CDN 已 404 的条目：用 NO PREVIEW 占位，或请 Derek 从 X 重新导出媒体。
4. 需要时把 `entries/*.md` 迁到 `image/` / `Video/` 目录并对齐归藏 md 结构，便于日后 `build.py` 扫描。
5. **补采集**（可选）：从开号日回扫更早带提示词的原创图/视频帖；规则同归档 README（不 OCR 臆造）。
6. 可选增加 **文本** 类目（若 Derek 有纯文提示词帖）。
7. 配置 **GitHub Pages** 并给 Derek 最终 URL。
8. 同步更新 Grok Bot Page 仅在 Derek 要求时；默认以本静态站 / Pages 为准。
9. 写简短 `README.md`（中英均可）：如何浏览、如何贡献新提示词、许可证（建议保留提示词原文版权归 Derek）。

---

## 7. 缺口（摘自 GAPS.md）

- 未做全量时间线回扫至开号日；本档约 2026-09-28 → 2026-11-04。
- 跳过无媒体、或无可复制正文提示词的帖（含部分可灵实测、镜头讨论、长文、返图帖）。
- 提示词只在图内需 OCR 的帖未收录。
- 「照片入青绿」保留最终编辑帖；编辑前完整双生稿仅备注。
- Canvas / 预览站不保证永久内嵌 X 媒体；**CDN 可能过期**。

---

## 8. 不要做

- **不要编造**提示词或「润色」到改变原意
- **不要改动**原始 `prompt` 正文（UI 文案、分类、模型标签可整理）
- **不要**冒充归藏或使用其品牌资产
- **不要**擅自发帖、公开部署到 Derek 未确认的域名、或产生费用（域名/CDN/API）——须 Derek 确认
- **不要**删除或覆盖 Grok Bot 上已有 Page，除非 Derek 明确要求替换

---

## 快速自检命令

```bash
# 解压后
cd derek-site-handoff-2026-11-04/site
python3 build.py
python3 -m http.server 8765
# 浏览器打开 http://127.0.0.1:8765/
python3 -c "import json;d=json.load(open('../data/prompts.json'));print(len(d), sum(1 for x in d if x['category']=='image'), sum(1 for x in d if x['category']=='video'))"
# 期望：42 39 3
```

— Grok Bot 交接 · 2026-11-04（Asia/Shanghai）
