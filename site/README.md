# 德里克文 · 提示词库 — 静态站

富设计感单页画廊（朱砂 `#c23b22` / 暖纸 `#f4efe6` 编辑风），数据来自 `../data/prompts.json`。
当前为 **42 条（图像 39 / 视频 3）**，配图已全部本地化为 webp，**页面零外部依赖**（字体、图片、脚本都在本目录内）。

## 本地预览

```bash
cd site
python build.py          # 生成 site/data/prompts.js，并构建可部署的 ../docs/
python -m http.server 8765
# 打开 http://127.0.0.1:8765/
```

## 自检

```bash
cd site
python verify.py         # 条目数 / prompt 原文哈希 / 本地图片 / docs 完整性
```

期望输出 `ALL OK — 42 条（图像 39 / 视频 3）…`。

## 改数据

只改 **`../data/prompts.json`**（唯一数据源，`prompt` 原文不要动），然后 `python build.py`。

- `media` — `[{src,w,h}]`，本地图片与尺寸（用于预留版位，避免布局跳动）
- `media_preview_urls` — 本地相对路径（旧字段，兼容用）
- 新增条目：把图放进 `img/<id>-<n>.webp`，并在 `media` 里登记宽高

## 功能

- 搜索标题 / 描述 / 模型 / 提示词正文（`/` 聚焦，Esc 清空），筛选状态写进 URL 可分享
- 分类：全部 | 图像 | 视频（带计数）；模型 chips 带计数
- CSS 多列瀑布流；长图自动裁切渐变 + 「长图」标记
- 详情：左图右文双栏、完整 prompt、一键复制（含非 https 环境降级）、X 原帖、Markdown 原文、上/下一条、方向键切换
- 深浅色切换（默认暖纸亮色，记住选择）；`prefers-reduced-motion` 友好
- 图片 `loading=lazy` + 宽高预留；失败回退 NO PREVIEW

## 生成物

- `data/prompts.js` — 由 `build.py` 生成，勿手改
- `../docs/` — `build.py` 输出的可部署目录（含 `.nojekyll`），GitHub Pages 直接指向它

## 注意

- 品牌为**德里克文**；不要改成归藏名义，也不要用归藏 Klein 蓝 `#002FA7`。
- 提示词与配图版权归德里克文所有；本站只做归档与检索。

## 工具

- `../tools/shot.mjs` — 无依赖 CDP 截图（全页/分段/移动端/暗色）
- `../tools/e2e.mjs` — 21 项功能验收（搜索、筛选、详情、复制、外链、本地化等）
- `../tools/apply_media.py` — 把下载清单合并回 `data/prompts.json`
- `../tools/localize_images.py` — 备用下载管线（走图片代理，可重跑）
