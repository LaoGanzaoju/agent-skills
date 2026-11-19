---
name: wb-client-probe
description: |
  WorkBuddy 客户端「机制级取证」——直接搜 app.asar 源码，实证平台到底注入/读取了哪些文件、
  各注入块字符上限是多少、某段提示语出自哪里、某个记忆/技能开关叫什么。当需要回答「X 文件会不会
  被平台注入／有没有上限／为什么我的文件被截断／这个截断标记是谁打的／这条规则该放哪个文件
  （personalization vs guidance vs .codebuddy/rules vs identity）／怎么把某层记忆关掉」时使用。
  含可复用脚本（lines/ctx/range/enum-max 四模式 + asar_multi_ctx.py 多针一次遍历）+ 2026-09-18
  已测基线（注入槽与上限常量全表 / 三个记忆开关 / 各槽语义原文 / identity 出生证状态机 /
  **注入面收口判据：三源穷举 + 观测集全覆盖**），便于版本升级后做 diff。
  含「**直接改 `app-config.json` 为什么无效且会被覆盖**」（§4.8：唯一权威写入方＝UI/daemon service 内存）。
  也回答「跨机迁移安不安全/会不会丢东西」：读**目标端写入函数**判覆盖与否（如 `writeFileIfMissing` ⇒ 先拷后启动）、
  核对**迁移工具的真实收集范围**（读收集函数，别信文档）。
  也回答「到底探完没有」：给出可验证的收口判据，而不是靠感觉说"够了"。
agent_created: true
---

# WorkBuddy 客户端机制取证

## 0. 何时用

- 想知道**某个文件会不会被平台自动注入上下文**（→ 决定要不要治理它的体量）。
- 想知道**某个注入块的字符上限**（→ 判断自己的记忆/配置文件是否会被截断）。
- 看到一段截断标记/提示语，要**定位它出自哪段代码**（→ 归因，别猜）。
- 升级客户端后**复核上限是否变了**（→ 与 §4 基线 diff）。

## 1. 取证载体

| 项 | 值 |
|---|---|
| 主载体 | `/Applications/WorkBuddy.app/Contents/Resources/app.asar`（≈298MB，内含全部 JS） |
| asar.unpacked | `/Applications/WorkBuddy.app/Contents/Resources/app.asar.unpacked/`（少数原生/内置插件） |
| 版本判据 | **asar 的 mtime**（例：2026-09-10 18:36）—— 结论带版本适用期 |

## 2. 方法（11 条硬纪律，按累积顺序）

1. **不要解析 asar header**。实测该 asar 头部非标准 Pickle 布局（`04 00 00 00` + 三个递减的长度字段，JSON 起始于 offset 16），自己解析 header 易翻车。**直接按行流式全文搜字节串**最稳（脚本已实现）。
2. **必须有「正对照」**。搜一个**已知存在**的串（如 `working_memory_content`）验证脚本有效，再搜待测串。**只有"零命中"而没有正对照，结论无效**。
3. **准否定要穷举**。要断言"平台不注入 X"，不能只搜一次 —— 要**穷举同类机制的完整清单**（如全部注入器 `mode/collectors/`），再逐项排除。
4. **注入块反向验证**（2026-09-18 新增，最强的一条交叉验证）。**你自己的 system prompt 里就有活体样本**：若某个注入块的**尾部出现被腰斩的单词**（实例：云 profile 块砍在 `浏览器登录态：Chr` ＝ `Chrome` 被腰斩），就去源文件里定位该片段的偏移量 —— 它应约等于源码常量值。实测偏移 **10218** vs 常量 **10000**，差 **218 字符（2.2%）**，差值来自注入前 `sanitize`；**方向与量级双吻合即确认为独立验证**。同理，layout 槽"恰好列满 40 条后以 `...` 收尾"亦现场印证 `MAX_LAYOUT_ENTRIES = 40`。**这条方法不需要跑任何源码搜索，成本为零，应作为每轮开头的第一手校验。**
5. **警惕同词异指**。英文 `memory` 在本客户端至少指两个无关子系统：**用户记忆**（本 skill 主题）与**进程堆内存**（`MemoryMonitor`：`heapUsedMB` / `memoryPressure` / `disableMemoryManagement`）。**`disableMemoryManagement` 不是"记忆开关"** —— 曾误当作治理手段的候选，逐字读上下文才发现属于内存监控日志。**凡把某个变量/开关当方案前，必须先读它的上下文代码。**
6. **断言"某上限不存在"前，必须做「声明形式穷举」**（2026-09-18 新增，一条血的教训）。只猜几个常量名去搜 → **会把"我没搜到"当成"不存在"**。实例：曾搜 `MAX_IDENTITY_CHARS` / `MAX_SOUL_CHARS` 零命中 → 得出「identity 无上限」，**真名是 `MAX_IDENTITY_FILE_CHARS = 1e4`**。正解：跑 `enum-max` 把**全部** `MAX_*` 扫出来（且必须覆盖两种声明形态：`var|const|let` 声明式、**`\tMAX_X = 1500;` 类字段式** —— 后者无前缀，只扫前者会漏掉 `MAX_CUSTOM_PROMPT_LENGTH`）。
7. **要读整段实现就用 `range`，别用 `ctx` 猜窗口**。`ctx` 是字节窗口，读 class 实现时窗口开小了会漏、开大了会刷屏；已知行号时用 `range <start> <end>` 精确读。
8. **收口必须多源 —— 单源搜索必产生假否定**（2026-09-18 新增）。注入面至少有三个源，**只搜其一会把"我在 A 里没搜到"误判成"平台没有"**：
   - **S1 磁盘模板**：`app.asar.unpacked/resources/templates/**/*.tpl` —— **块标签**（`<xxx>`）与**占位符**（`{{Xxx}}`）主要在这里定义；
   - **S2 asar 代码**：块标签在代码里**硬编码拼接**（如 `getWorkingMemoryContent()` 直接写 `<working_memory_content>`），**这些标签不在 `.tpl` 里**；
   - **S3 运行时动态**：layout / binary / env / connector 等平台自动填。
   **实例**：首版收口脚本只搜 S2，把 `user_custom_instructions`、`tone_and_style` 报成"未定位（疑似隐藏通道）" —— 实际上这两个标签**只存在于 S1 的 `user-context-identity.tpl`**。**收口判据 = 三源穷举 + 观测集全覆盖**：把你自己上下文里**实际存在**的每个块逐个回查生产点，全部可追溯才算收口。
9. **别把"发现"当无限游戏**。源码永远可再挖，但**要问的不是"还有没有新东西"，而是"新发现是否改变方案骨架"**。若新发现只改变"哪些对象适用哪条手段"、不改变手段清单本身 —— **方案骨架已稳定，应冻结并转执行**。另有一类**结构上不可穷举**的东西：LLM 注意力可靠性 —— 它**不能靠"再探"或"换个槽放"解决**，只能机制化（脚本 / 门禁）。
10. **要判断"某文件能不能安全拷到另一台机器"，去读平台的初始化写入函数**（2026-09-18 新增）。关键是分清**补缺式写**与**覆盖式写**：`identity-collector.ts` 初始化三件套用的是 **`writeFileIfMissing`（只补缺、永不覆盖）** ⇒ **先拷文件再启动客户端，平台一字不动**；顺序反了（先启动让平台生成默认模板）就要多一道手工合并。
    **同源副产品**：该函数后半段有一条旁路 —— 若 `bootstrapSeededAt` / `onboardingCompletedAt` 皆空且无 `BOOTSTRAP.md`，则读 IDENTITY/USER 内容，**非默认模板即直接记 `onboardingCompletedAt`、不发出生证**。⇒ **拷文件 = 平台自动认可 onboarding 完成**（新机不会再来问一轮"你是谁"，且这是天然验收信号）。
    **通用教训**：凡"跨机搬文件"，先在源码里定位**目标端的写入函数**，确认它覆盖与否，再定操作顺序。
11. **断言一个工具/流程的覆盖范围，要读它的收集函数，别信它的文档**（2026-09-18 新增，一条会静默丢数据的坑）。实例：`workbuddy-asset-migration` 的文档写「**Memory 由云端同步**，请在目标客户端设置中同步」—— 读起来像"记忆不用管"。但读 `export.py:576` 的 `_write_memory_export_markdown()` 才发现：它只 glob **`<root>/memory/*_memory.md`**（云 profile 缓存），**根本不读 `<root>/MEMORY.md`（本地用户级记忆）与 `memory_external/`** —— 而这两样恰恰是**不随云端走的纯本地文件**。⇒ **照文档理解 = 静默丢掉本地记忆。**
    **判据**：文档描述「意图」，收集函数描述「事实」。凡涉及"会不会丢"的问题，**只认函数**。

> ⚠️ 附带的通病：本机 Bash `grep` 对**中文**会出**假阴性**（静默空 + rc=1）。凡中文检索，一律换专用检索工具复核。

## 3. 脚本

`scripts/asar_probe.py`（纯标准库，Python 3.9+ 可用）：

```bash
P=<工作目录>
A="/Applications/WorkBuddy.app/Contents/Resources/app.asar"

# ① 命中行（多针，一次扫描；输出紧凑，先跑这个）
$P scripts/asar_probe.py "$A" lines MAX_MEMORY_CHARS HANDOFF.md AGENTS.md

# ② 上下文（要读源码原文时用，字节窗口）
$P scripts/asar_probe.py "$A" ctx "MAX_USER_MEMORY_CHARS" 1500

# ③ 穷举某目录/命名空间下的全部组件（注意：`--cap N` 才是条数，裸写数字会被当成 needle）
$P scripts/asar_probe.py "$A" lines "mode/collectors/" --cap 60

# ④ 按行号区间读源码（已知行号、要读完整实现在用；比 ctx 精确）
$P scripts/asar_probe.py "$A" range 2146400 2146600

# ⑤ 穷举全部 MAX_* 常量（★ 标注入相关）—— 断言"某上限不存在"前的必备步骤
$P scripts/asar_probe.py "$A" enum-max
```

`scripts/asar_multi_ctx.py`（**多针 × 多命中点 × 带上下文**，一次 mmap 遍历读完所有疑点）：

```bash
# 一轮闭掉 N 个疑点：每针各报前 --hits 处、每处前后 --win 字节
$P scripts/asar_multi_ctx.py "$A" "getDisableLocalSkillsMemoryFromAppConfig" \
    "getUserLocalMemoryContent" "generateMemoryEnabled" --win 1500 --hits 2
```

> 用它的场景：**手上一次攒了 3~5 个待查针**。`ctx` 一次只能喂一个针且要重扫全文件（每次 20–40 秒），
> 多针攒着用本脚本**只读一遍**。**注意 `--win` / `--hits` 必须写在所有针之后**（否会被当成待搜针）。

一次扫描约 20–40 秒（298MB），多针共扫**只读一遍**，尽量一次带足所有针。

## 4. 已测基线（2026-09-18，asar mtime 2026-09-10）

### 4.1 注入槽与上限（全部为**写死字符常量**，非动态计算）

| 槽（注入标签） | 源 | 上限常量 | 值 |
|---|---|---|---|
| `<working_memory_content>` | `<cwd>/.workbuddy/memory/MEMORY.md` | `MAX_MEMORY_CHARS` | **8000 字符** |
| `<user_memory>` | `~/.workbuddy/MEMORY.md` | `MAX_USER_MEMORY_CHARS`（`memory-collector.ts`） | **4000 字符** |
| `<memory>`（云 profile） | 云端 `/api/memory/profile` 归档 | `MAX_USER_MEMORY_CHARS`（`user-memory-collector.ts`）**同名不同值** | **10000 字符** |
| `<project_context>` guidance | **仅** `CODEBUDDY.md` / `.codebuddy/CODEBUDDY.md` / `AGENTS.md` | `MAX_GUIDANCE_CHARS` | **8000 字符** |
| `<project_context>` layout | 自动扫 `<cwd>` 文件树 | `MAX_LAYOUT_ENTRIES` / `MAX_SUBTREE_DEPTH` / `MAX_TOP_EXTENSIONS` | 40 条 / 6 层 / 5 后缀 |
| `BinaryContext` | 二进制运行时信息 | `MAX_BINARY_CONTEXT_CHARS` | **10000 字符** |
| identity（SOUL / IDENTITY / USER / BOOTSTRAP） | `~/.workbuddy/*.md` | `MAX_IDENTITY_FILE_CHARS` | **10000 字符 / 每件**（⚠️ 本表曾错报"无上限"，见 §7） |
| `<project_rules>` | 用户级 `~/.workbuddy/rules/` ＋ 项目级 `<cwd>/.codebuddy/rules/` | `MAX_RULE_FILE_SIZE` | **40000 / 每文件**，超则**整条丢弃**（不截断）；未见目录级上限 |
| `<user_custom_instructions>` | `~/.workbuddy/app/app-config.json` → `personalization.customPrompt` | `MAX_CUSTOM_PROMPT_LENGTH`（**类字段式**声明，无 `var`） | **1500**，超则**静默丢弃**（输入框吞字、无报错） |
| `<tone_and_style>` | `personalization.toneStyle` → `unpacked/…/templates/style/style-*.md`（7 个预设） | — | 预设固定 1839~2579 字符 |
| env（Shell / git / locale） | 运行时探测 | 未见专用常量 | 未找到（≠不存在，见 §7） |
| **HANDOFF 等 H 类文件** | — | — | **不注入 → 无槽位** |

### 4.2 截断标记 → 出处对照（用于归因，别猜）

| 标记原文 | 出处 | 含义 |
|---|---|---|
| `... (user memory truncated — exceeded character limit)` | `user-memory-collector.ts`（`<memory>` 包裹行） | **云记忆**通道超 10000 |
| `... (user memory truncated)` | `memory-collector.ts` / `getUserLocalMemoryContent()` | **本地**用户级 MEMORY 超 4000 |
| `... (memory truncated — MEMORY.md is too large)` + `ACTION REQUIRED` | `memory-collector.ts` | **项目级** MEMORY 超 8000（附清理指令） |
| `... (binary context truncated — exceeded character limit)` | `binary-collector.ts` | BinaryContext 超 10000 |
| `[...too long, omitted...]` | `project-context-section.ts` | guidance 超 8000 |

### 4.3 平台注入器与 section（**2026-09-18 重测，修正此前的"共 11 个"**）

> ⚠️ 旧的"共 11 个"是**单源搜索**（只扫 `mode/collectors/` 一个路径前缀）的产物，**偏少**。按文件名全量扫 `collectors/` 得 **17 个**、`sections/` 得 **33 个** —— 但**这两组都含非注入类组件**，必须甄别，不能整组当注入器。

**`…/mode/collectors/`（17 个文件）** —— 其中**注入相关**（会往提示里填变量）：
`binary` / `collaboration` / `env` / `expert-operation-skill` / `expert-prompt-slot` / `identity` / `memory` / `memory-block-sanitizer` / `personalization` / `user-memory-collector`（10 个）。
**非注入类**（性能/健康/生命周期，不要算进注入面）：`chat-perf` / `cli-health` / `history-load` / `market-page-load` / `migration` / `startup-perf` / `proxy-agent-util`（7 个）。

**`…/user/sections/`（33 个文件）** —— **注入相关**：
`identity-context-section`（identity 槽）/ `project-context-section`（`<project_context>` + layout）/ `project-rules-section`（`<project_rules>`）/ `rules-section` / `user-info-section` / `additional-data-section` / `attached-skills-section` / `special-instructions-section` / `system-reminder-section` / `working-memory-reminder-section` / `current-expert-reminder-section` / `mode-transition-reminder-section` / `automation-system-reminder-section` / `user-command-section`。
**非注入类**（纯 UI 组件，别误当注入面）：`expert-card` / `expert-grid` / `expert-category-tabs` / `featured-scenes` / `installed-*` / `list-tabs-row` / `ardot-*` / `hash-proxy-url` / `proxy-test-status-line` / `schedule-url-input-report` 等。

**⇒ 命名纪律**：`collectors/` 与 `sections/` 是**目录名**，不等于"注入器清单"。断言"平台有 N 个注入器"前，必须**逐个读名字甄别**（性能采集器与 UI 组件都不注入提示）。

### 4.4 注入槽的「语义分派」（源码原文决定该往哪放）

别把"规则/说明"随便塞槽 —— 平台对每个槽的语义有明确措辞，**按源码原文分派**：

| 槽 | 源码原文 | 语义 ⇒ 该装什么 | 结构 |
|---|---|---|---|
| `personalization.customPrompt` | UI 描述 "Set a **few rules** … apply to **all future tasks**"、hint "apply to **all your conversations**" | **少量跨全部会话的个人说话规矩** | 一个文本块，1500 |
| `<project_guidance>` | `The project guidance below is **generated by the CodeBuddy IDE's AI**... File: …` | **项目说明书**（这个项目是什么 / 怎么跑） | **单文件，首个命中即停**，8000 |
| `<project_rules>` | `<project_rules description="… **Follow them as if the user stated them directly.**">` | **行为纪律（军规）** —— 语义最贴 | **多文件** `.md`/`.mdc`，40000/件 |
| `identity`（SOUL / IDENTITY / USER） | `If SOUL.md is present, **embody its persona and tone**.` | **人是谁**（人格 / 身份 / 用户档案） | 三件套，各 10000 |

**rules 的路径与 frontmatter**（`project-rules.ts`）：
- 路径：用户级 `~/.workbuddy/rules/`（`resolveUserConfigDir("rules")`）；项目级 `<cwd>/.codebuddy/rules/`（**目录名恒为 `.codebuddy`，不是 `.workbuddy`** —— 为与 CodeBuddy Code 的 `.codebuddy/rules/` 行为一致）
- 扩展名 `.md` / `.mdc`；加载 **user 先、project 后**（后出现者语义更强）；去重键 `realpath`
- frontmatter：`enabled`（仅显式 `false` 才关）／`paths`（glob → 条件规则）／`alwaysApply`（显式 `true` → always；无 globs 且非显式 `false` → 也默认 always）；派生 `type = (非always 且有globs) ? 'manual' : 'always'`
- ⚠️ **`manual`（带 `paths`）当前不注入** —— 源码注释：触发信号在 cbc 进程内、**daemon 侧拿不到**。**只有 `always` 真生效**

### 4.5 guidance / rules / identity 的注入时机都是 `first_turn`

`ProjectContextSection` / `ProjectRulesSection` / `IdentityContextSection` 三者 `stage = "first_turn"`（受 `alreadyInjectedUserContext` 门控）。**本平台没有"每轮重述"的规则槽** —— 换槽只解决**容量 / 语义 / 跨机同步 / 结构**，**不解决"模型注意力可靠性"**。想真正治行为漂移 → 走脚本 / 门禁，不是换槽。

### 4.6 identity 的「出生证」状态机（判断人设是否被实例化过）

`identity-collector.ts` 的 `ensureWorkBuddyPromptContextWorkspace()` 分两步跑：

**第一步：补文件（`writeFileIfMissing` ⇒ 只补缺、永不覆盖）**
```js
await Promise.all([
    this.writeFileIfMissing(soulPath,    DEFAULT_SOUL_CONTENT),
    this.writeFileIfMissing(identityPath, DEFAULT_IDENTITY_CONTENT),
    this.writeFileIfMissing(userPath,    DEFAULT_USER_CONTENT)
]);
```
⇒ **三件套永不被平台覆盖。** 这正是"**先拷文件、后启动客户端**"这条迁移顺序的源码依据。

**第二步：判定要不要发"出生证"**（同一段后半的逻辑）
```
若 bootstrapSeededAt 空 且 BOOTSTRAP.md 存在                → 记 bootstrapSeededAt
若 onboardingCompletedAt 空 且 bootstrapSeededAt 有值 且 BOOTSTRAP.md 不存在 → 记 onboardingCompletedAt
若 两者皆空 且 BOOTSTRAP.md 不存在:
      读 IDENTITY / USER 内容
      若内容 ≠ 默认模板  → 直接记 onboardingCompletedAt（判定"已完成"，不发出生证）
      否则               → 写 BOOTSTRAP.md + 记 bootstrapSeededAt
```
⇒ 平台写入 `BOOTSTRAP.md`（模板原文称其为 your **birth certificate**："update SOUL.md, IDENTITY.md, and USER.md, then **delete** BOOTSTRAP.md"）；**若用户已自己填过（内容 ≠ 默认）→ 直接记 `onboardingCompletedAt`，不发出生证。**

**状态落盘在 `~/.workbuddy/workspace-state.json`**：
```json
{"version":1,"bootstrapSeededAt":"…","onboardingCompletedAt":"…"}
```
判读：`bootstrapSeededAt` 有值 = 出生证发过；`onboardingCompletedAt` 有值 = 出生证已删（流程走完）。**配合三件套 mtime 判断"填了几件"**（实例：某机 SOUL.md mtime ＝平台首次写入时间，且内容逐字节等于 `DEFAULT_SOUL_CONTENT` ⇒ **从未被编辑**）。

**核验"某文件是否仍是默认模板"**：抽出 asar 内 `DEFAULT_SOUL_CONTENT` / `DEFAULT_IDENTITY_CONTENT` / `DEFAULT_USER_CONTENT` 模板字面量与磁盘文件比对（形如 ``var DEFAULT_SOUL_CONTENT = `…` ``，注意处理 `` \` `` 与 `\${` 转义）。

### 4.7 记忆相关的**开关**（2026-09-18 新增，此前未知）

查"上限"之外，还要查"**有没有开关**" —— 有时入口不在文件里，而在配置里。

| 开关 | 归属 | 效果 | 可用性 |
|---|---|---|---|
| `disableLocalSkillsMemory` | **`~/.workbuddy/app/app-config.json`（本地键，已确证）**；代码常量 `APP_CONFIG_KEY_DISABLE_LOCAL_SKILLS_MEMORY = "disableLocalSkillsMemory"` | 置 `true` → `WorkingMemoryContent` / `UserLocalMemoryContent` / `WorkbuddyMemory_1` **三个变量全部置空串**（＝项目级 M、本地用户级 M、三层记忆说明书 一起停注）| ⚠️ **等于放弃跨 session 记忆 —— 不建议**。源码注释逐字：**"不影响云端 `UserMemoryCollector`（云端长期记忆）与 `conversation_search` 工具"** |
| `generateMemoryEnabled` | configService（默认 `true`）| 置 `false` → **跳过云 profile 注入**，日志 `skipReason=cloud_memory_disabled` | 🟡 **能否本地直设未验证**（可能像 `prewarmPoolSize` 一样由远端 `/v3/config` 写入本地缓存）|
| `localMemoryEnabled` | configService（默认 `false`）| 云记忆的**本地回退**开关 | 🟡 未验证 |
| `DisableMemoryPersonalization` | **云端 `productFeatures`**（非本地）| 隐藏设置页 memory Tab + 禁用云 memory 注入（源码引 fix #70486）| ❌ 本地改不了 |

**读取现场配置的现状**（判断开关是否被设过）：`app-config.json` 的键可由脚本列举：
```python
import json; d=json.load(open('/Users/<u>/.workbuddy/app/app-config.json',encoding='utf-8'))
print(list(d.keys()), list(d.get('personalization',{}).keys()))
```
（2026-09-18 本机实测：仅 `personalization.toneStyle` / `personalization.customPrompt` / `locale` → **开关全为默认**。）

> ⚠️ **纠错留痕**：本文件（及三份报告）曾写「该文件含明文凭证（claw 通道 bot token）」——**2026-09-18 全文件实测证伪**：该文件全文 **1553 字符、仅 4 个叶子字段、不含任何凭证**；claw 类凭证实际在 `~/.workbuddy/connectors/<uid>/mcp.json`。**原错误是把 connectors 的性质错安到了 app-config.json 上。** 「跨机只搬 `personalization` 段」的建议保留，但理由改为**防配置污染**（覆盖目标端 `locale` 等键），**不是防泄密**。

### 4.8 `app-config.json` 的**唯一权威写入方＝UI**（2026-09-18 新增，一条会白干的坑）

**问题**：「我直接改 `~/.workbuddy/app/app-config.json` 里的值，有效吗？UI 侧会跟着变吗？」

**结论：无效，且会被覆盖 ⇒ 配置类改动一律走 UI。**

| 链路 | 代码位置（本 skill 的 asar 行号口径） |
|---|---|
| **UI 保存** | 设置面板 `savePersonalizationValues()`（L5046743）→ `adapter.savePersonalization({toneStyle, customPrompt})`（L5046749）→ `daemonClient.configSet("personalization", …)`（L3259938-3259940）→ daemon `handleRpc("configSet")`（L1954035）→ `AppConfigService.set()` → `commit()` → `save()`（`JSON.stringify(this.config, null, 2)` → 写 `.tmp` → `rename`，L1769487）→ `invalidateAppConfigFileCache()` |
| **注入读取** | `PersonalizationCollector.resolveSettings()` → **`this.appConfig.get("personalization")`**（L2146957）＝ `AppConfigService` 的**进程内内存副本**；而 `load()` **只在 constructor 里执行一次**（L1769415） |

⇒ **两条后果**：① **不生效** —— 盘上文件改了，daemon 内存不刷新，新 session 仍注入**旧值**；② **被覆盖** —— daemon 之后**任何一次** `configSet`（改 toneStyle ／ locale ／ 默认工作空间路径 ／ 任一设置项）都用**内存全文**重写整份文件 ⇒ 手改的东西被抹掉。

**旁路缓存（易误判）**：另有 `appConfigCache = new JsonFileCache(…)`（**mtime+size 失效**）供"绕开 service 直接 `readAppConfigFile`"的消费方使用 —— 这些消费方**能**感知手改，**但 `customPrompt` 的注入不在此列**（走 service 内存）。⚠️ 别把「某些旁路能感知」误当成「改文件有用」。**判据＝读的是哪个入口（service 内存 vs 文件缓存），不是"文件变了没有"。**

**对治理的用法**：凡「平台配置项」（`personalization.*` ／ `locale` ／ `defaultWorkspacePath` ／ `dataRetention` …）⇒ **正解＝让用户去 UI 改**；agent 只在**用户自己动手**的路径上给文本、给步骤，**不要写那个文件**。

**UI 侧可观测信号**（可直接当验收判据写给用户）：编辑后**失焦即自动保存**（`handleCustomPromptBlur` L5046763）＋ 出 `已保存` toast（`settings.personalization.saved` L5046757）；输入框**字符计数** >1200 变黄、>1500 变红（L5046775）；**超上限时输入被直接吞掉、无任何报错**（`if (value.length > MAX_CUSTOM_PROMPT_LENGTH) return;` L5046740）⇒ **「计数＝预期值」即通过信号**。

---

## 5. 关键判据（别再用错口径）

- **体量一律用字符数 `wc -m`**，不用行数、不用字节。中文 3 字节/字 → 字节口径会高估 3 倍；行数口径完全无效（同样 89 行，中英混排差 3 倍）。
- **H 类文件（HANDOFF）不进注入窗**：只在 agent 主动 Read 时进上下文，受 Read 工具限制（单次 2000 行 / 单行 2000 字符），与记忆预算无关。

## 6. 查出上限之后：治理判据（2026-09-18 新增）

查到上限只是第一步，**别按体量（KB / 行数）排治理优先级 —— 那是错的**。用两个正交维度：

| 维度 | 取值 |
|---|---|
| **A 急迫性** | 🔴 已越线（**正在故障**）> 🟠 贴线（余量 <10%，下次追加即爆）> 🟢 安全 |
| **B 可治性** | ✅ 用户可直接编辑 → 能治 ｜ 🟡 间接（改目录结构等）｜ ❌ 平台自动生成 → **只能换入口或接受** |

**按槽分派的五种手段**：

| 手段 | 适用槽 | 要领 |
|---|---|---|
| **A 拆 + 外移** | 项目级 / 用户级 MEMORY | 主文件留黄金区 + 指针行，块迁到同级 `<对象>_外移_<年月>.md`；**目标留 20% 安全余量**（如上限 8000 → 主文件 ≤6400）|
| **B 节流 + 写入前预算校验** | 同上 | **每次写入前先 `wc -m` 确认余量**；装不下就改写进项目级 M 或外移文件，**不要硬塞用户级** |
| **C 结构瘦身** | layout 槽 | 根目录条目数 >40 时，从第 41 条起**完全不可见**。把过程文件（备份 / 试点 / 快照 / 对比 html）收进子目录即可腾名额。**这是"可见性"问题，不是磁盘问题** |
| **D 换入口 / 用开关** | 云 profile | ⚠️ **2026-09-18 修正：不是"本地不可治"** —— 原证据仍成立（`path-resolver.ts`「写入目标：仅 primaryDir」，`/api/memory/profile` 由主机侧 **10min 轮询**拉取 → **手改缓存必被覆盖**），但确证存在 **configService 层开关 `generateMemoryEnabled`**（默认 `true`；置 `false` → 跳过云记忆注入，日志 `skipReason=cloud_memory_disabled`）。**能否由本地 `app-config.json` 直设未验证**（可能像 `prewarmPoolSize` 一样由远端写入本地缓存）。**处置建议仍是「接受截断」**（砍的是 memoryBlock 尾部「近期动态」段）。**不要**用改权限之类硬堵手段（会破坏锁与轮询）|
| **E 仅立规则** | guidance / BinaryContext / identity / H 类 | 槽空或非用户资产 → 不治；仅需一条自律规则（如"guidance 一旦启用即 ≤6400"）|

**云 profile 本体的定位**（易被当成"本地文件"误治）：
`~/.workbuddy/memory/<uid>_memory.md` —— 结构为 `# User Memory Profile` + `## Memory Block` + `<!-- RAW_JSON_START … RAW_JSON_END -->`（末段是 JSON 备份，**不注入**）。真正注入的只有 `## Memory Block` 段；用脚本拆段量体：
```python
s=open(p,encoding='utf-8').read()
start=s.find('\n', s.find('## Memory Block'))+1
block=s[start:s.find('<!-- RAW_JSON_START')]
print(len(block))   # 这才是要跟 10000 比的值
```
> 同一 uuid 另有 `_memory.md.bak`（上一次版本，含旧时间戳），正常备份机制、非异常。

## 7. 常见误用（都是已踩过的坑）

- 子命令共 **4 个**：`lines` / `ctx` / `range` / `enum-max`。**没有 `text`** —— 报"用法提示"通常就是参数写错（子命令拼错、或该带参数没带）。
- **多针要写成多个独立参数**（`lines A B C`）。写成 `lines "A|B"` 会被当**字面量**去搜 → 假零命中（已踩过）。
- `lines` 的条数上限参数是 **`--cap N`**；裸写数字会被当成 needle。
- `ctx` 只报前 N 个命中点的上下文，默认 N=1 —— 要多处对比须显式 `--max-hits`；要读整段实现改用 `range`。
- 断言"零命中"前**必须**先跑正对照（见 §2 第 2 条），本 skill 的 `lines` 支持多针一次扫描，把正对照针**和**待测针一起带上。
- ⚠️ **最大的坑：猜常量名 = 制造假零命中**。见 §2 第 6 条 —— 断言"某上限不存在"必须用 `enum-max` 做声明形式穷举，且**两种声明形态都要覆盖**（`var|const|let` 式 ＋ 无前缀的**类字段式** `\tMAX_X = 1500;`）。本 skill 的 §4.1 基线表就因此错标过 identity "无上限"。
- 报告体量数字前重测一次：文件改动会使旧计数**漂移**（本 skill 的基线表也可能滞后于现场）。
- **纠错要留痕**：发现自己发过的结论有错时，**在原文处标注「曾错报 + 纠正依据」**，不要静默改数 —— 否则下次没人知道这条结论被推翻过。
- ⚠️ **同一处错报会被复制到多个文档 —— 纠正时务必全库扫一遍**。实例：错误结论「`app-config.json` 含明文凭证」当时同时存在于此 skill、实证报告、通用版清单、明细表**四处**；只改一处等于没改。做法：用**专用检索工具**（非 Bash grep，见下）扫关键短语，逐处打补丁并留痕。
