---
name: container-call-audit
description: 审计本地所有 WorkBuddy 容器（workspace）在指定时间窗内对某项能力（工具 / API / skill / 脚本）的调用量，按容器降序排列。触发词：查某能力调用量、哪些容器用了 X、X 用了多少次、审计容器内 X 调用、跨容器用量统计。
agent_created: true
---

# 跨容器能力调用量审计

统计"某个能力在各容器里被调用了多少次"。核心难点不是检索，是**区分真调用与提及**——首轮不探结构必然出假结论。

## 铁律 1：先探结构，禁止套用通用格式

本环境 session 记录在 `~/.workbuddy\projects\<容器>\<uuid>.jsonl`。

**工具调用的真实结构是 `type=function_call`（字段 `name` + `arguments`），不是 Anthropic 的 `tool_use`。** 套用 `tool_use` 会全部漏判，得出"0 次调用"的假绿结论。

动手前先跑探针脚本，打印一条记录的骨架：

```python
import json
fp = r"<任一 jsonl>"
lines = open(fp, encoding="utf-8", errors="replace").readlines()
import collections
print(collections.Counter((json.loads(l).get("type"), json.loads(l).get("role")) for l in lines))
for l in lines[:12]:
    o = json.loads(l)
    print(o.get("type"), o.get("role"), list(o.keys()))
```

已知字段结构（本机 2026-09 核实）：

| type | 关键字段 | 含义 |
|:--|:--|:--|
| `function_call` | `name`（工具名）、`arguments`（入参） | **工具调用** |
| `function_call_result` | `name`、`output` | 工具返回 |
| `reasoning` | `rawContent` / `content` | 模型推理文本 |
| `message` | `role`=user/assistant，content 块 `input_text`/`output_text` | 对话正文 |
| `file-history-snapshot` / `ai-title` | — | 元数据 |

## 铁律 2：三口径必须分开报，禁止混为一谈

| 口径 | 定义 | 证据强度 |
|:--|:--|:--|
| **真实调用量** | 实际打到 API / 产出结果 | 强（产出文件 + 入库记录） |
| **会话触发** | agent 在会话里执行了相关命令 | 中（要区分执行 vs `test -f`/`grep`/`cat` 探查） |
| **文本提及** | 对话 / 文档 / 推理里出现该词 | 弱（**不是调用**） |

用户问"有无调用、调用量降序"时，**默认给真实调用量做主表**，另两张作辅表，并在结论里点明差异（例如"583 次真实调用里只有 27 次由会话触发，其余走自动化链路"）。

## 铁律 3：真实调用量必须双源交叉验证

单一来源不算证据。找两个独立数据源：

1. **产出文件计数** —— 结果目录按文件名内嵌时间戳过滤时间窗
2. **入库记录去重** —— SQLite `distinct <业务主键>`（如 1 张截图 = 1 次调用）

两法结果应贴近（差 1~2 属跨日边界）。有差异要解释，不许直接取其一。

## 铁律 4：命令数 ≠ 调用量，先查有没有「批量编排层」

**这是最容易出假结论的地方。** 统计到"会话里只执行了 46 次命令"却产出 583 次调用时，**不要**直接写"大部分调用与会话无关"——几乎一定是漏了批量编排脚本。

编排脚本的典型特征：对一批输入逐个调底层单次脚本，且**自带去重**（查库跳过已处理）。典型命名与模式：

```python
# ocr_session.py 模式：编排层
for png in shots_dir.glob("shot_*.png"):
    if already_in_db(source, png):   # 去重，避免重复计费
        continue
    subprocess.run([VENV, "run_local.py", str(png)])   # 单次脚本
```

核查动作：
1. grep 工作区 `.py`，找**引用了目标能力**的脚本全集（注意：有的只在注释里提到路径，**本身不调用**，如 `collector.py` 只截图不 OCR）
2. 看是否存在"编排层 → 单次脚本"两层结构
3. **查去重逻辑**（按什么键去重）→ 决定计数是「处理次数」还是「计费次数」，报告里要写清

正确表述示例：*「46 次 Bash 命令产出 583 次 API 调用，因 ocr_session.py 一次批量处理当天全部未入库截图；且编排层自带去重，故 583 即计费次数而非处理次数。」*

## 铁律 5：调用量 ≠ 计费量 ≠ 费用，用户说"对不上"先查计费规则

用户拿账单质疑数量对不上时，**不要拿调用次数 × 单价去解释**。三者是不同概念：

| 概念 | 含义 | 例子 |
|:--|:--|:--|
| 调用次数 | 业务侧发起了多少次请求 | 632 次 |
| **计费次数/页数** | 云厂商实际扣减的额度 | 138 页（其余被免费额度覆盖） |
| 费用 | 计费量 × 单价（可能分档） | 61.64 元 |

必然要查的三件事：

1. **免费额度/资源包**：大部分调用可能被额度覆盖 → 计费量远小于调用量
   - ⚠️ **额度分两类，别当成一回事**（腾讯云文档 api/866/35945）：
     | 类型 | 典型商品 | 是否每月重置 |
     |:--|:--|:--|
     | **首开一次性** | 文档抽取 Agent 版/Pro 版、公式识别、试题识别、手写作文识别、卡证鉴伪、门头照 | ❌ **1000 次，每用户仅 1 次，有效期 1 年，用完全无** |
     | **每月重置** | 通用/卡证/票据/特定场景文字识别、表格识别 V3、文档智能 | ✅ 1000 次/月，每月 1 号发放 |
   - 后果：一次性额度耗尽后，**该商品永久进入全额计费**，降本方案不能再假设"降采样后落回免费额度"。
   - **本地估算脚本几乎都把两类混为一谈**（只看当月用量算余额），会持续显示"还剩很多额度"的假象。凡涉及额度余量，一律查官方文档，不采信本地常量。
2. **倍率规则**：很多 API 按参数规模倍数计费。**必查官方计费文档**，不要信本地脚本注释里的单价
   - 例：腾讯云实时文档抽取 Agent —— 自适应价格下**抽取字段 >10 记两次费用**，≤10 记一次
   - `items_real.json` 16 字段 → 判为「长文本」→ **1 次调用扣 2 页**，单价翻倍
3. **计价模式是否切换过**：账单里若同时出现两种模式（如固定价 + 自适应价），是配置层隐患，要报

**本地成本估算脚本的单价常常过期或错误**（曾见注释写 0.19 元/次，实际账单 0.40 元/页，差 2 倍）。写报告前一律以官方账单为准，本地脚本只当线索。

## 铁律 7：建议"砍字段/砍参数"降本时，必须给出精确清单，且依据 = 下游实际消费

说"减少字段能降本"却不说砍哪个 = 等于没说，用户会直接追问（真实发生）。给清单前必须查证，不能按"看起来不重要"拍。

**查证顺序**（四步，缺一不可）：

1. **找到当前链路上的消费者是谁** —— 老脚本会骗人。目录下常有 `build_dashboard_819.py` / `_v2` / `_skeleton` 等历史版本，引用大量字段但早已不跑。判据：查自动化任务的 `thread_title` 自述里出现了哪些脚本名，或按 mtime 判断。
2. **读消费者的字段常量定义** —— 硬编码的 dict 就是真相。例：`LIVE_M3_KEYS = {"直播曝光人数":"exp", ...}` 一眼看出只用 4 个字段，比 grep 全文准得多。
3. **核最终产物**（独立第二重证据）—— 打开最近一份生成物（HTML/报告），统计字段名出现次数。**注意别名陷阱**：产物里可能用简写（"在线人数"）而非全名，全名匹配为 0 不代表没用，要先用正则提取可见文本确认。
4. **区分"能自算" vs "真会丢"** —— 下游若自己算比率（如 `pclk/pexp`），那被抽的「点击率」字段就是纯冗余，砍了零损失。真会丢的要单独列出让用户拍板。

**两个高价值推论**：

- **同档位内砍到下限即可，不必砍到最少**。若价格规则是「≤N 个是同一价」（如自适应价格 ≤10 字段记 1 次），那砍到 N 就到价格地板，**从 N 再往下砍一分钱不省**。应砍到 N 而非砍到最少，把额度留给数据资产。
- **检查砍完是否要连带改下游**。若保留集恰好等于下游某个常量（如 `ACCUM_LIVE_KEYS`），则零改动，这是最优解，要主动指出。
- **派生字段（比率/均值）优先砍**：能由保留字段算出来的，砍掉零损失；瞬时值（当前在线人数之类）砍掉才真丢信息。

## 铁律 6：链路突然零产出 —— 先查外部服务是否还活着，别先怀疑自己的统计

**典型陷阱**：统计出"某窗口调用量为 0"，很容易写成"该能力没在用 / 已停用 / 额度重置"。**在业务看起来该在跑的时候，0 产出几乎总是故障信号，先查服务端。**

必查顺序：

1. **账户是否欠费**（最常见，且会**同时打停该账号下所有云能力**，连仍有额度的商品一起停）：
   ```
   DescribeAccountBalance → Balance / OweAmount（单位：分）/ IsAllowArrears
   ```
   示例：`Balance=-6256` = 欠费 62.56 元。此时任何调用都返回 `ResourceUnavailable.InArrears`。
2. **上游是否还在产原料**：对比"原料目录新增文件时间"与"结果库最新记录时间"。
   - **原料在涨、结果库不动 = 处理环节断了**（不是没在用），积压量 = 待补处理数，要一并报出来（它可能是一笔待发生的费用）。
3. **自动化日志自述**：`automation_runs.thread_title` 常直接写明失败根因（如「OCR 全部失败——账号欠费，89 张全失败」），比自己猜快得多。

**报告写法**：把"零产出"的原因**单独立节并标更正**（如果之前给过错误结论，显式推翻，不要静默改）。同时给出：欠费金额 / 停服影响范围 / 已损失的数据天数 / 积压量与补跑成本。

## 查真实账单：纯标准库手写 TC3 签名，无需装 SDK

密钥来源：容器里的 `.env`（如 `TENCENTCLOUD_SECRET_ID` / `TENCENTCLOUD_SECRET_KEY`）。**先验证该子账号有无 billing 权限**——返回参数错误说明有权限，返回鉴权失败才没有。

```
POST https://billing.tencentcloudapi.com/
签名 TC3-HMAC-SHA256（hashlib + hmac，stdlib 够用）
头：Authorization / Content-Type / Host / X-TC-Action / X-TC-Timestamp / X-TC-Version
```

| Action | 用途 | 必填坑 |
|:--|:--|:--|
| `DescribeAccountBalance` | **账户余额/欠费（铁律 6 首选）** | 无参；返回 `Balance` / `OweAmount`，**单位是分** |
| `DescribeCostSummaryByProduct` | 按产品汇总费用 | 需 `BeginTime`/`EndTime`；**必须带 `Offset`**；**不支持跨月**，要分月调 |
| `DescribeCostSummaryByResource` | **按商品/计费项拆费用（最有用）** | 同上；返回 `ComponentConfig` 直接给出用量（如"115 页"）；**响应里的 `ProductCode` 是后面查用量所需的正确值** |
| `DescribeDosageDetailByDate` | 每日用量 | 见下（坑最深） |

`DescribeDosageDetailByDate` 的正确参数（2026-09 逐项试出）：

- 用 `StartDate` / `EndDate`（**不是** BeginTime/EndTime）；**不认 `Limit`**
- **`ProductCode` 必须是 `sp_xxx` 形态**（从 `DescribeCostSummaryByResource` 响应里取，如 `sp_ai_image_ocr_doc_agent_fixed`）
  - ⚠️ 传 `BusinessCode`（如 `p_ai_image_ocr`）会报 `RetCode 108007 校验失败`
- **还必须同时传 `Domain`**（如 `ocr.tencentcloudapi.com`），否则报 `MissingParameter Domain`
- ⚠️ 即便参数全对，本账号实测 `DetailSets` 恒为 **0**（试遍 ProductCode×Domain 组合 + 缩日期范围）→ 判定**接口无数据**，此时如实写"拿不到每日用量"，不要反复重试浪费轮次。

`DescribeCostSummaryByResource` 的 `ComponentConfig` 是金矿——它同时给出**费用与计费用量**，可直接算出真实单价（46.00 元 / 115 页 = 0.40 元/页）。

拿到真实单价后立刻回头**核对本地估算脚本的常量**，错了就指出（不要静默）。

## 定位驱动源（谁触发的）

`schtasks.exe` **被安全策略 Program Blacklist 拦截，无法查询，不要重试**。替代方案：

```python
# workbuddy.db（只读打开，避免锁）
conn = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
# automations 表：id / name / prompt / cwds / rrule / valid_from / last_run_at
# automation_runs 表：automation_id / thread_title / source_cwd / metadata_json(含sessionId) / created_at(毫秒) / result_success
```

- 按 `source_cwd` 过滤目标容器，按 `created_at` 过滤时间窗
- **`thread_title` 常含执行自述**（如「OCR 完成：处理=87（live 55 + ad 32）」），可与自己的统计**逐日对账**
- **注意 `valid_from` 可能晚于实际首次运行**（字段后被改过），以 `automation_runs` 实际记录为准
- `metadata_json.sessionId` 在早期记录中可能为空 → **不能因 sid 匹配不上就判"手动"**，要以 `thread_title` 与执行日期为准

若官方台账（如费用周报）与库统计对不上：**如实标注差额与可能口径差异，绝不强行对齐取其一**。

## 执行步骤

1. **列容器**：`ls ~/.workbuddy\projects\`（目录名 `c-Users-<USER>-WorkBuddy-<容器名>`）。注意 `Claw` / `WorkBuddy内训` / `销售陪练引擎` 等工作区**无 session 记录目录**，视为该窗内无任务记录，需在报告里标注。
2. **探结构**（铁律 1）。
3. **算时间窗**：`date -d "2026-08-07 00:00:00" +%s` → 转毫秒（×1000）。jsonl 的 `timestamp` 是毫秒。
4. **关键词全量扫**：正则同时收中英文（如 `ExtractDoc|文档抽取`），按 `function_call` 的 `name` / `arguments` 分类：
   - 工具名命中 → 具名调用
   - Bash/Shell 工具且 arguments 命中 → 可能是执行，**必须人工看命令正文**（`test -f` / `ls` / `grep` / `sed` / `cat` 都是探查，不算调用）
   - 其余 → 提及
5. **反查代码链路**：grep 容器工作区 `.py`/`.js`，确认该能力由哪个脚本发起（例：`ingest.py` → subprocess 调 `tencentcloud-ocr-extractdocagent/scripts/main.py`）。
6. **双源计数**（铁律 3）。
7. **出报告**：结论先行 + 三口径表格 + 逐日分布 + 局限段。

## 已知坑

- **`schtasks.exe` 被安全策略 Program Blacklist 拦截**，无法验证 Windows 计划任务 → 走上面的 `automation_runs` 替代路径。
- **命令数与调用量不等价**（铁律 4），先查编排层再下结论。首轮曾据此误判"583 次调用与会话无关"，实为 `ocr_session.py` 批量编排所致。
- **产出反推是下限**：失败调用无产出文件会被漏计，报告里要写明。
- **系统注入污染**：每个 session 首条 user message 含 `<available_skills>` 全量 skill 清单，被审计的 skill 名几乎必然出现在里面 → 巨量伪命中。只看 `function_call` 层，别看 message 层。
- **容器名去前缀**：`c-Users-<USER>-WorkBuddy-` / `c-Users-<USER>-.workbuddy-` 要剥掉再展示。

## 已知坑（补充）

- **本地单价常量不可信**：`ocr_cost_estimate.py` 注释 0.19 元/次，真实账单 0.40 元/页（固定价）/ 0.68 元/页（自适应长文本）。凡涉及钱的结论，必须 API 直查。
- **本地免费额度模型也不可信（同一脚本的第二处错）**：`FREE_LIVE = 1000  # 每月免费次数` + `free_live_left = max(FREE_LIVE - 当月用量, 0)`，把**一次性**额度当成每月重置，导致自动化汇报长期输出「免费额度余量 943 次」的假象——实际早已归零且账号欠费停服。**教训：本地台账的额度/单价常量只能当线索，两处都要查官方文档或账单。**
- **欠费会连坐**：账号欠费时 `ResourceUnavailable.InArrears` 会打停**该账号下全部云能力**，连仍有月度免费额度的商品（如表格识别 V3）也一起失败。诊断时不要因为"ad 还有额度却也失败了"而困惑。
- **只在注释里提到路径的脚本不是调用方**：`collector.py` 注释写了 skill 路径，但它只截图不 OCR，差点被误判为调用方。

## 参考实例

完整审计案例：`<PROJECT_ROOT>`
费用真相与降本：`<PROJECT_ROOT>`
可复用脚本：`<PROJECT_ROOT>`
- `audit2` 分类 / `count_out` 产出计数 / `db_count` 入库交叉 / `bash_ocr` 会话命令 / `direct_calls` 触发明细 / `struct2` 结构探针
- **`bill_detail.py` —— 账单查询模板（TC3 签名 + 资源级明细 + 翻页），下次查任何云费用直接改 Action 复用**
- `bill_query*.py` —— API 参数踩坑过程记录（Offset / 跨月 / StartDate / Limit 各错误码）
