---
name: wb-transcript-mining
description: |
  从 WorkBuddy 本地会话 transcript（jsonl）里挖「历史对话原文 + 下文」。
  当需要**某段历史对话的逐字原文或它之后 AI 怎么回的/后续结论**，而 `conversation_search`
  只返回摘要（它无权访问当前会话、只给 summary）时使用。触发词：查历史会话、找回当时的下文、
  这句话当时上下文是什么、翻旧 session、transcript、会话原文、某容器历史对话。
  含：transcript 落盘位置、按关键词定位会话、按会话 id 精读、以及「中文/交替搜索」的静默失败陷阱。
---

# 挖历史会话原文（transcript mining）

## 何时用

- 用户贴回一段**旧 session 的原话**，追问「当时的下文 / AI 怎么回的 / 后续怎么定的」。
- 需要**逐字原文**做证据（`conversation_search` 只返回摘要，不能当原文）。
- 需要核「某结论当时是谁拍的、原话是什么」。

⛔ `conversation_search` **看得到历史、看不到当前会话**，且**只回摘要**。要原文必须走下面的 jsonl。

## 一、transcript 在哪

```
~/.workbuddy/projects/<workspace-slug>/<session-uuid>.jsonl
```

- `<workspace-slug>` ＝ workspace 绝对路径把 `/` 换成 `-`（中文原样保留）。
  例：`<工作目录>`
  → `Users-<用户名>-WorkBuddy-<工作区名>`（示例，按实际路径替换）
- `<session-uuid>` ＝ `conversation_search` 结果里的 `conversation_id`。
- 同目录还有 `<uuid>.file-rollback.ndjson`（文件改动回滚记录，可查某文件的**改前原文**）。

## 二、定位会话（两步）

**第 1 步 · 拿候选 session id**：调 `conversation_search`（query 写自包含、带上关键词与时间段）。

**第 2 步 · 直接在 transcript 里按关键词命中**（比 search 更准）：

```bash
cd "$HOME/.workbuddy/projects/<workspace-slug>"
grep -rlE "关键词甲|关键词乙" --include="*.jsonl" . | head
```

⚠️ **必须 `-E`**：`grep` 的 BRE `\|` 交替在本环境**静默返空且不报错**（陷阱②）。要交替一律 `grep -E "a|b"`。
⚠️ 目录大（数百个 jsonl、单文件可达十几 MB）：**只 grep `*.jsonl`**，别对整树 `find`（易被 OOM kill）。
⚠️ 中文目录核查用 `ls`/`Read`，不采信 `Glob` 空返回（陷阱⑤）。

## 三、精读：抽「原文 + 下文」

每行是一个 JSON；消息行 `type=="message"`，`role` ＝ user/assistant；正文在 `content`
（字符串，或 `[{type:"text"|"input_text", text:...}]`，工具结果在 `type=="tool_result"`）。

```bash
<工作目录> - <<'PY'
import json, re
FN = "<session-uuid>.jsonl"
KEY = re.compile(r"关键词甲|关键词乙")

def rows(fn):
    out = []
    with open(fn, encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except Exception:
                continue
            if o.get("type") != "message":
                continue
            c, t = o.get("content"), ""
            if isinstance(c, str):
                t = c
            elif isinstance(c, list):
                for p in c:
                    if isinstance(p, dict):
                        t += p.get("text", "") or p.get("input_text", "") or ""
                        if p.get("type") == "tool_result":
                            t += str(p.get("content", ""))
            out.append((i, o.get("role"), t))
    return out

R = rows(FN)
for idx, (i, role, t) in enumerate(R):
    if KEY.search(t):
        m = KEY.search(t)
        s, e = max(0, m.start() - 260), min(len(t), m.end() + 400)
        print("=" * 60)
        print(f"[line#{i}] {role}  len={len(t)}")
        print("…" + t[s:e].replace("\n", " ⏎ ") + "…")
        # 下文 = 紧随其后的 assistant 消息（打印前几条）
        for j in range(idx + 1, min(idx + 8, len(R))):
            k, kr, kt = R[j]
            if kr == "assistant" and kt.strip():
                print(f"  ↳ 下文 [line#{k}] {kt[:4000]}")
                break
PY
```

- 长会话有**多份 `<cb_summary>` 压缩包**（用户消息里回溯历史），命中处可能重复 —— 看 `len` 和上下文判断哪份是原始。
- 用户消息里含 `<system-reminder>` 注入噪音：分析前用正则剥掉 (`re.sub(r"<system-reminder.*?</system-reminder>", "", t, flags=re.S)`)。
- 想拿「某文件改前原文」：查同目录 `<uuid>.file-rollback.ndjson`，或找该 session 的 `Write`/`Edit` 工具调用。

## 四、铁律

- **只把读到的当真证据**（rule 05）：能引用 `session-uuid + line#` 的才算。
- **原始 transcript 是唯一原文真源**；`conversation_search` 摘要、别处的转述都只是线索。
- 挖到的「谁拍了什么、原话是什么」若与现有记忆冲突 ⇒ **以 transcript 原文为准，并当场更正记忆**（rule 13）。
