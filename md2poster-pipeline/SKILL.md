---
name: md2poster-pipeline
description: |
  贴图号编辑器的「约定符号 md → 贴图号 PNG」替补流水线。
  当 `web/mapper.py`（零触碰，只实现 `## ` 分页与 `|表格|`）无法识别 §六 约定符号
  (`# 主标题` / `> 引用` / `--- 分割` / `*整行* 超级符号`) 时，使用本流程出图。
version: 0.1.0
author: CCS
agent_created: true
trigger:
  - 贴图号
  - 符号不识别
  - md2structure
  - render_poster
  - 约定符号
  - mapper 报错
  - 出图
---

# md2poster-pipeline · 约定符号 md 出图替补流程

## 触发条件

- `python3 贴图号编辑器/web/mapper.py <xxx.md> --out x.structure.json` 失败或产物错误：
  - 首个 `## ` 前有空行 → `PageError`
  - `# 主标题` / `> 引用` / `--- 分割` / `*整行*` 被识别成普通 `para`
  - 页1 封面内容块被丢弃

## 为什么不直接修 mapper.py

`web/mapper.py` 在 CODEBUDDY §四 零触碰清单内，原地不动以保自动出图不断链。
本流程在零触碰区外新建/使用两个文件：

- `贴图号编辑器/md2structure.py` —— MD（§六 符号）→ `schema=1` 的 `.structure.json`
- `贴图号编辑器/render_poster.py` —— `.structure.json` → editorial HTML → `server.render_zip` → PNG

## 约定符号映射

| 符号 | 输出 role |
|---|---|
| `# ` | `main_title`（页1 抽成 cover.line1 hero） |
| `## ` | 分页符 + `kicker`（空 kicker 渲染时跳过） |
| `### ` | `kicker` |
| 空行分隔文本 | `para` |
| `> ` | `quote` |
| `---` / `———` | `rule` |
| `*整行*` | `supersym` |
| `|表格|` | `table` |
| `![alt](src)` | `image` |

## 命令串

```bash
# 1. 解析出结构
cd <工作目录>
python3 md2structure.py "<定稿.md>" \
  --out /tmp/<name>.structure.json \
  --title "栏目名" \
  --brand "出海口账号名"

# 2. 渲染出图
python3 render_poster.py /tmp/<name>.structure.json \
  --out "<工作目录>" \
  --brand "出海口账号名"
```

## 判据

- 解析后 structure.json 的页1 role 为 `cover`，且 `cover.line1` 是 `# ` 主标题。
- 页2 表格块 role 为 `table`。
- 页3 引用块 role 为 `quote`，分割块为 `rule`，结尾为 `supersym`。
- 渲染后 PNG 与原文逐页对应、无溢出。

## 已知限制

- 本流程走的是编辑器 `/render` HTML 路径，绕开了 `plan_adapter.py` → `build.py` 的杂志引擎；
  若后续需要 styleplan 旋钮，应回退到引擎链，此时仍需要修复 mapper.py 本身。
- `web/mapper.py` 仍保留为旧路径，未更新。

## 收尾

- 8731 服务如需浏览器交互：用 `start_new_session=True` 后台拉起，避免被 shell 回收：
  ```python
  import subprocess
  subprocess.Popen([
      '<工作目录>', 'server.py'
  ], cwd='<工作目录>',
     stdout=open('/tmp/editor_8731.log','w'), stderr=subprocess.STDOUT,
     start_new_session=True)
  ```
