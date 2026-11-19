---
name: html-long-doc-to-markdown
description: >
  把「长 HTML 文档 / 网页版手册 / 平台导出的 HTML」保真转成 Markdown，并做结构对账。
  当需要「html 转 md / 网页转 markdown / 出一份 md 版 / 把 HTML 手册变文本 / 长文 HTML 转 markdown」，
  或要把 HTML 喂给写作管线、转 docx/PDF、做文本编辑时使用。
  适用特征：文件 >50KB、含大量表格/列表/SVG 图、带编辑器痕迹属性。
agent_created: true
---

# HTML 长文档 → Markdown（保真转换 + 对账）

## 何时用

- 只有 HTML、需要一份 Markdown 正文（编辑 / 喂管线 / 转 docx）。
- 官方工具缺失时（本机无 pandoc、无 markitdown、无 bs4/html2text）。
- 文档来自编辑器/平台导出，带 `data-page-node-id` 一类痕迹属性、标签可能有错配。

## 怎么做

```bash
PY=<工作目录>
S=<工作目录>
"$PY" "$S" "输入.html" "输出.md"
```

脚本会：正文转换 + 把内嵌 SVG 导出为同名 `.svg` 文件 + 在 md 中原位插入 `![...](xxx.svg)`。
中文路径直接传，无需转义。零第三方依赖（只用标准库 `html.parser`）。

## 必须走的验收（否则等于没验）

**1. 结构对账** —— 数 HTML 侧标签 vs md 侧语法，逐项比：

| 项目 | HTML 侧 | md 侧 |
|---|---|---|
| H1–H4 | `<h1\b`… | `^# ` / `^## ` / `^### ` / `^#### ` |
| 表格块 | `<table\b` | 连续 `^\|.*\|$` 行分块计数 |
| 表格数据行 | `<tr\b` | `^\|.*\|$` 总行数 − 表头行 |
| 列表项 | `<li\b` | `^\s*(?:-\|\d+\.) ` |

**2. 内容对账（逐条）** —— 把 `<td>/<th>/<p>/<li>/<h*>` 的文本逐条在 md 里检索。
> ⚠ 归一化必须**对称**：两侧都只做「去标签 + `html.unescape` + 压缩空白」。
> 一旦两侧剥的字符集不同（例如一侧剥了 `-`/`>` 另一侧没剥），会造出成片**假缺失**。
> 判定真假缺失的**唯一可靠方法**：拿原文子串直接 `in md`（最朴素检索），不要信自定义归一化。

**3. SVG 真渲染** —— headless Chrome 截图，肉眼确认非空白且图形正常：

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless --disable-gpu \
  --no-sandbox --hide-scrollbars --window-size=760,600 \
  --screenshot=/tmp/chk.png "file:///绝对路径/图.svg"
```

## 四个非显然的坑（都踩过）

1. **`viewBox` 被小写化** —— `HTMLParser` 把属性名统一转小写，SVG 严格区分大小写；
   `viewBox` → `viewbox` 后失效，图形不缩放。脚本里 `SVG_CASE` 表做还原
   （`viewBox/refX/refY/markerWidth/markerHeight/preserveAspectRatio`…）。
2. **源 HTML 标签错配导致整章被吞** —— 实例：`<h3>4.2.3…</h4>`（开 h3 闭 h4）。
   结束标签找不到祖先时若不处理，节点会一直挂在未闭合的标题下，**后续内容全被吞进标题**。
   对策：① 隐式闭合规则（新块级标签先关掉开着的 `p`/`h*`/`li`/`td`）② 结束标签同族回退（h1↔h6）。
3. **隐式闭合集合写宽了会弹掉父级** —— 曾把 `td` 的闭合集合写成含 `tr`，
   于是每个 `<td>` 都把 `<tr>` 弹掉，表格结构散架、27 张表全变空。
   `td→{td,th}`、`tr→{tr,td,th}`，别越级。
4. **容器 div 压成一整段** —— `.cards`（含 5 个 `.card`）若不含 `p/ul/table`，
   会被当成单个叶子节点合并成一行。对策：把 `div/section` 也当容器（`CONTAINERISH`），
   让 `.card-title`/`.step-title`/`.callout-label` 这类叶子 div 各自成段（并可加粗）。

## 交付注意

- **不要删原件**；输出新文件，md 与 .svg 同目录。
- `data-page-node-id` 一类编辑器痕迹属性：正文丢弃，SVG 导出时也剥掉。
- 合并单元格：`rowspan` 向下填充原文、`colspan` 首列放文其余留空，否则列会错位。
- 报告时给「结构对账表 + 内容对账条数 + SVG 渲染截图」三项证据，别只说“转好了”。
