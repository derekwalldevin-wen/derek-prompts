# DESIGN-SPEC · 德里克文提示词库

## 品牌

- 名称：**德里克文 · 提示词库** / Derek Prompt Gallery
- X：[@derek_wall90176](https://x.com/derek_wall90176)
- **不要**使用归藏 logo、名义或 Klein 蓝 `#002FA7` 作为主色

## 视觉方向（当前预览站已落地）

| Token | 值 | 说明 |
|------|-----|------|
| `--bg` | `#f4efe6` | 暖纸底 |
| `--paper` | `#fffdf8` | 卡片纸 |
| `--ink` | `#1a1612` | 深墨 |
| `--accent` | `#c23b22` | **朱砂**（区别归藏蓝） |
| `--gold` | `#b8893a` | 备注点缀 |
| 字体 | Instrument Serif + Noto Sans SC + IBM Plex Mono | 编辑感标题 + 中文正文 + 元数据 |

- Hero：大衬线标题 + 右侧统计卡（条目 / 图像 / 视频）
- Sticky：搜索 + 圆角 chips（分类朱砂高亮）
- 卡片：细墨线框、hover 上浮阴影、瀑布流 2–4 列
- Dialog：全屏/近全屏、分类 pill、多图、可展开 prompt、复制按钮、X 原帖链接
- 预览失败：格纹 + 二字标题 + `NO PREVIEW`

可选升级（DSH）：暗色主题切换、本地 webp、长图渐变遮罩（归藏 `thumb.long`）、Text 类目。

## 技术

- 静态单页：`site/index.html` + `site/data/prompts.js`
- 重建：`python3 site/build.py`
- 字段映射见 `HANDOFF-DeepSeek.md` §4

## 验收清单

- [ ] 搜索可用
- [ ] 全部 / 图像 / 视频筛选正确（42 = 39 图像 + 3 视频）
- [ ] 模型 chips 可筛
- [ ] 瀑布流卡片 + 点击详情
- [ ] 复制提示词成功
- [ ] X 原帖外链正确
- [ ] 移动端可读
- [ ] 中文 UI；品牌为德里克文
- [ ] 不冒充归藏
