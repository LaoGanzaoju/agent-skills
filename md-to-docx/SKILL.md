---
name: md-to-docx
description: |
  Markdown → Word（「转 docx」）的固化路径。当甘晓东说「转docx / 转成 docx / md 转 Word / 出个正式件 / 出 docx」，
  或任何本地 .md 需要变成本地可编辑 .docx 时使用。默认走「轻量路」= 本地编辑器通道（create_doc → doc_insert_markdown → save_file），
  三步出结构保真的 docx；不够用才升级「公文路」= tencent-docx beautify_only。
  含强制独立核验（直读 OOXML，不信工具自报）、版面微调（首行缩进/引用块/页眉页脚/页码/目录）、转图目检。
  明确禁区：手搓 docx 脚本、裸标签选择器。
agent_created: true
---

# md → docx

把一份本地 Markdown 变成可编辑的本地 Word。**先选路，再动手。**

## 一、选路（每单第一件事）

| 路 | 是什么 | 什么时候走 |
|---|---|---|
| **轻量路**（默认） | 本地编辑器通道：`create_doc` → `doc_insert_markdown` → `save_file` | **默认走这条。**结构保真（标题层级/表格/列表/链接/加粗）够用，且免编排 |
| **公文路** | `tencent-docx` 的 `beautify_only`（S2→S3） | 轻量路不够时：需要**套现成公文/报告版式模板**，或需要**大面积字体字号分级**。代价见 [references/公文路.md](references/公文路.md) |
| **禁区** | — | 手搓 `docx` npm 脚本（内容硬编码在代码里，不是转换器）；裸标签选择器 `p { }` |

轻量路已实测能做：标题层级、带边框表格、列表、**首行缩进 2 字符**、**引用块**、页眉页脚、页码、目录、**转图目检**。先按这个清单试；试不动再升公文路。

## 二、轻量路 · 三步

`ED` 是编辑器 SDK 壳目录。它随应用包走，**升级后可能变**，路径不对时先找：

```bash
ED="/Applications/WorkBuddy.app/Contents/Resources/app.asar.unpacked/resources/plugins/workbuddy-builtin/skills/tencent-local-office-edit"
# 兜底定位：
# ED=$(dirname "$(find /Applications/WorkBuddy.app -name edsdk.py -maxdepth 12 2>/dev/null | head -1)")
```

### 第 1 步 · 建空白文档

```bash
cd "$ED"
FID=$(python3 edsdk.py call create_doc 2>&1 | grep -oE 'file_id=[^,]+' | cut -d= -f2)
```

**完成判据**：`FID` 非空且形如 `new_doc_<数字>_<hex>`。为空 = 编辑器池没起来，停下来报障，别往下编路径。

### 第 2 步 · 灌入 md

```bash
python3 edsdk.py call doc_insert_markdown \
  --json "{\"file_id\":\"$FID\",\"idx\":0,\"markdown\":\"file:///绝对路径/源文件.md\"}"
```

`markdown` 传 **`file://` + 绝对路径**，不要贴正文——省 token 且不破坏转义。

**完成判据**：回包含 `insert_markdown ok`。

### 第 3 步 · 落盘

```bash
python3 edsdk.py call save_file \
  --json "{\"file_id\":\"$FID\",\"file_path\":\"/绝对路径/目标.docx\"}"
```

**完成判据**：`File saved to:` + 目标文件存在且 > 2 KB。

## 三、出稿后必做 · 独立核验

工具说 `ok` 不算数——**self-report 不是证据**。直读 docx 包内 XML：

```bash
<工作目录> \
  <工作目录> \
  "/绝对路径/目标.docx" "关键串1" "关键串2" "关键串3"
```

关键串从源 md 里挑**分散在各章节的实义串**（标题、数字、专名），不要只挑开头那句。

**完成判据**：脚本退出码 0，且①表格数与源 md 一致 ②关键串全命中 ③`outlineLvl` 非空。任一条不过 → 报告异常，别宣布完成。

## 四、版面微调（按需，非默认）

读回确认用 `doc_get_paragraph_property`；目检用 `doc_to_image`（把 docx 渲染成逐页 PNG，一次会话末尾调一次即可）。

| 要什么 | 调什么 |
|---|---|
| 首行缩进 2 字符 | `doc_modify_paragraph` 传 `first_line_indent_chars: 2`（落成 `w:firstLineChars="200"`） |
| 引用块 | `doc_modify_paragraph` 传 `block_quote: true` |
| 页眉 / 页脚 / 页码 | `doc_insert_header` / `doc_insert_footer` / `doc_set_page_number` |
| 目录 | `doc_insert_toc`（前置条件：文档已有标题层级） |
| 命名样式 | `doc_apply_named_style`（套到段落）、`doc_update_named_style`（改样式定义） |

**位置一律用 `doc_resolve_document_structure` 的 range / `paragraph_id`，不手算字符数、不用段落序号。**

## 五、已知边界（实测）

1. **md 的 `>` 不会变成 Word 引用块**——插入后仍是普通段落，要显式调 `block_quote: true`。
2. **输出无命名样式**：标题靠 `outlineLvl` 承载 → 导航窗格 / 目录正常，但在 Word 里换主题字体时标题不跟动。要命名样式得另调 `doc_apply_named_style`（本条**未实测**）。
3. **围栏代码块会退化成普通正文**，不像代码块。需要等宽+底纹时手动补。
4. **属性互斥**：`first_line_indent` / `block_quote` / `indent` / `numbering` / `highlight_block` 五者互斥，且都不能与 `jc` / `spacing_*` / `line_spacing*` / `heading_lvl` 同包——同包会**报错**。要组合就分多次调用，每次只带一类属性。
5. **坐标会漂移**：每次写操作后重新解析结构，别复用旧快照。
6. **本机还有别的 md→docx 候选**（`minimax-docx`、`markitdown-skill`），未实测，**先走轻量路**，别重开探索。

## 六、禁区

- **别用项目里遗留的手搓转换脚本**（如 `公文写作/build_docx.js`）——那是把内容硬编码进代码的一次性产物，不是转换器。
- **别在 HTML 里写裸标签选择器**（`p { text-indent: 2em }`）——走公文路时会被静默丢掉，见 references。
- **别把「工具返回 ok」当交付完成**——核验脚本必须跑。

## 七、交付

1. 报文件绝对路径（纯文本代码块，不用 markdown 链接）。
2. 报核验结果：表格数、标题层级、关键串命中情况。**没跑核验就不要说完成。**
3. **保留源 md 不动**（md 是源材料，不是中间产物）。
