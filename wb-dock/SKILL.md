---
name: wb-dock
description: 把待办/规则/提示词写进 WB Dock 面板（真相源 ~/wb-dock/dock.json，Windows 是 %USERPROFILE%\wb-dock\dock.json）。当用户说「挂到 dock」「写进 dock」「把这条待办放面板上」「记到面板上」「把这条规则加到 dock」「从别的容器/别的机器往面板里塞东西」，或需要读取面板现有内容时使用。也用于回答「面板里现在有什么」。附带把该能力打包成可复制接入卡（给别人的机器/别人的 AI 用）。
agent_created: true
---

# WB Dock · 面板读写

## 一句话

WB Dock 的真相源就是一个 JSON 文件。**app 在实时监听它**（`watch.rs`），写进去面板秒级刷新。
所以「让 AI 把待办记到面板上」= 让 AI 改这个文件，不需要任何插件或 API。

## 真相源路径

| 系统 | 路径 |
|---|---|
| macOS | `~/wb-dock/dock.json` |
| Windows | `%USERPROFILE%\wb-dock\dock.json` |

同目录还有 app 自己写的东西：`dock.json.bak`（上一版备份）、`dock.log`（监听日志）、
`m5.log`（写操作日志）、`dock.conflict.<毫秒>.json`（冲突副本）。
**目录里的日志文件不要动**，`watch.rs` 靠文件名过滤避免自触发。

## 数据契约

```jsonc
{
  "version": 1,
  "rules":   [ { "id", "title", "body",   "pinned" } ],   // id 前缀 r_
  "prompts": [ { "id", "title", "body",   "pinned" } ],   // id 前缀 p_
  "tasks":   [ { "id", "title", "note", "status", "src", "created", "updated" } ],  // t_
  "settings":{ "hotkey": "..." }
}
```

| 字段 | 约束 |
|---|---|
| `status` | 只能是 `todo` / `doing` / `done`（`write.rs` 会拒绝别的值） |
| `src` | 只能是 `wb`（AI 挂的任务，界面显示 **WB**）/ `human`（自己的事，显示 **我**） |
| 内容字段名 | rules / prompts 用 **`body`**，tasks 用 **`note`** —— 注意这个不对称 |
| `pinned` | 只对 rules / prompts 有意义，每 Tab ≤5；tasks 不支持置顶（用拖序） |
| `version` | **app 从不写盘**（只在返回给界面时补上）。脚本也跟着不写，别自作聪明加 |

**只读视图字段**：`ok` / `path` / `hotkey_active` 是 app 注入给前端的，**绝不能落盘**。

> **与 app 的一处刻意差异（不是 bug）**：app 对 `status` / `src` 是**精确匹配**
> （写 `Done` 会被拒，因为它面向面板按钮，值只可能来自点击）；脚本则先**规范化**
> （`Done` → `done`、`WB` → `wb`）。理由：AI 手写大小写不一是常态，
> 此时规范化比报错更有用，且**落盘值一定合法**。值域本身两者一致 —— 越界值（如
> `finished`、`robot`）一律拒绝。

## 怎么用

优先调脚本（已封装全部安全逻辑）：

```bash
python3 ~/.workbuddy/skills/wb-dock/scripts/dock_write.py \
    add task --title "标题" --note "备注" --src wb
```

| 命令 | 作用 |
|---|---|
| `list [task\|rule\|prompt]` | 看面板里现在有什么（先 list 再 add，避免重名） |
| `add task --title T [--note N] [--src wb] [--status todo]` | 挂一条待办 |
| `add rule --title T --body B` | 加一条规则 |
| `add prompt --title T --body B` | 加一条提示词 |
| `update task <id> [--title T] [--note N] [--src wb]` | 改内容 |
| `status task <id> done` | 勾选（todo / doing / done） |
| `rm task <id>` | 删除 |

**没有脚本的场合**（别的机器、别的 agent），按下面四条自己做。这四条是脚本存在的**全部理由**，不是建议：

1. **读改写，不整体重写。** 盘上可能有别的工具或别人在写；整体重写会抹掉你不认识的字段。
2. **原子写**：临时文件写在同一目录 → `fsync` → `rename` 覆盖。直接原地写会让面板读到半截
   JSON —— 面板不会崩（`watch.rs` 会跳过解析失败那次），但**这次更新不会显示**。
3. **不碰 `settings`**，不写 `ok` / `path` / `hotkey_active`。
4. **文件不存在就按契约新建**（连目录一起建）。不存在 ≠ 出错：app 的读路径会报红字，
   但写路径把「文件不存在」当空文件处理 —— 所以你一写它就活了。

## 冲突时会发生什么（不是 bug）

app 的写操作有冲突检测：如果面板最后一次读到之后**盘上被外部改过**，
它不覆盖，而是把改动另存 `dock.conflict.<毫秒>.json` 并提示。
所以你写完之后、面板还没刷新（200ms 防抖窗口）时，用户正好在面板上点了一下 ——
**他那一下会落到冲突副本里**，主文件不受影响，也不丢数据。正常现象，说明机制在工作。

## 把能力搬给别人（重要）

同事 / 另一台机器 / 另一个账号的 AI **不知道这套约定** —— 靠它自己搜，会搜很久。
所以要把下面的**接入卡**整段复制给对方，粘进对方的「自定义指令 / 系统提示词 / 记忆」：

```
我有一个「WB Dock」面板（Mac 菜单栏小工具 / Windows 托盘小工具），数据是一个 JSON 文件，
面板在实时监听它 —— 你写进去，我面板上立刻能看到，不用重启、不用点刷新。

数据文件位置：
  macOS:   ~/wb-dock/dock.json
  Windows: %USERPROFILE%\wb-dock\dock.json

文件格式：
- "tasks": 待办。每条 = { id, title, note, status, src, created, updated }
    status 只能是 "todo" / "doing" / "done"
    src    只能是 "wb"（AI 挂的任务）或 "human"（我自己的事）
- "rules" / "prompts": 规则 / 提示词。每条 = { id, title, body, pinned }

写的时候守四条：
1. 先读整份文件，只改要动的那一条，其余原样写回 —— 别整体重写。
2. 先写同目录临时文件再改名覆盖，别直接覆盖原文件。
3. 不碰 "settings"，也不写 "ok" / "path" / "hotkey_active"。
4. 我让你记待办时，写进 "tasks"，"src" 用 "wb"。

文件或目录不存在就按上面格式新建。
```

## 已知边界

- **面板不显示实时校验**：写坏了 JSON 面板会跳过这一次并保持旧内容，不会弹错误吓人 ——
  所以写完最好自己回读一次比对（脚本已内置）。
- **`settings.data_dir` 不存在**（S2 未做）：路径写死在代码里，改不了。
- **Win 侧未在同一版本验证过写路径**（W1 包在此基础上无 S 层）。
