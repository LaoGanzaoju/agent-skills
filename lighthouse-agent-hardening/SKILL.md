---
name: lighthouse-agent-hardening
description: 在腾讯云轻量应用服务器(Lighthouse)上运行自主 Agent（如 Hermes，常驻、有真实能力、可经任意频道——微信/Telegram/企业微信/WorkBuddy 等——指挥）时，为非技术用户执行安全加固的操作指南。channel-agnostic：加固锁的是 Agent 自身能力边界，与"经哪个聊天频道触达它"无关。覆盖：跨地域定位实例、升级 Agent 修 CVE（pin tag 而非 bare update 防供应链风险）、收紧 SSH（先判断使用习惯再决定关门/钉 IP/禁密码）、设置到期续费提醒、经 SOUL.md 写入安全指令治本（数据外传需授权/付费先确认/防 prompt 注入）、出网白名单风险解释与权衡。强调先查后改、不向非技术用户甩技术选择题（先读用户文档自己判断再讲清理由）、OS 级 iptables 不宜经 TAT 手搓（过滤器会拦 nft 与 /etc/resolv.conf）。当用户要在 Lighthouse 上"升级/加固/安全/收紧"一个自主 Agent 实例，或问"SSH 该不该关""Agent 会不会乱连/乱发/乱调付费接口"时触发。
agent_created: true
display_name: Lighthouse 自主 Agent 安全加固
display_name_en: Lighthouse Autonomous Agent Hardening
description_zh: 在腾讯云轻量应用服务器上为常驻、有真实能力（命令/文件/外联/凭证）的自主 Agent 做安全加固的操作指南。channel-agnostic，加固锁的是 Agent 自身能力边界，与经哪个聊天频道指挥它无关。覆盖跨地域定位实例、升级修 CVE、收紧 SSH、到期续费提醒、写 SOUL 安全指令、出网白名单权衡。面向非技术用户，先查后改、不甩技术选择题。
description_en: A hardening playbook for autonomous agents (e.g. Hermes) running 24/7 on Tencent Cloud Lighthouse with real capabilities (command, file, network, credential). Channel-agnostic - it locks the agent's own capability boundaries regardless of which chat channel commands it. Covers locating instances, patching CVEs, tightening SSH, renewal reminders, SOUL security directives, and egress allowlist trade-offs.
category: devtools
version: 1.0.0
author: 甘晓东
---

# Lighthouse 自主 Agent 安全加固

本 skill 固化一套在腾讯云轻量应用服务器（Lighthouse）上为**常驻、有真实能力（命令执行/文件读写/外联/凭证使用）的自主 Agent**（典型如 Hermes）做安全加固的方法论。channel-agnostic：无论你经微信、Telegram、企业微信还是 WorkBuddy 哪个频道指挥它，加固锁的都是 Agent 自身的能力边界，不是入口。核心对象是非技术用户：他看不懂防火墙/iptables，但机器上跑着一个能自己决定外发和调外部服务的常驻 Agent——这是最该防的"自发风险"。

## 何时使用

- 触发词：升级 Hermes / 收紧 SSH / Agent 安全加固 / 出网白名单 / SSH 该不该关 / Agent 会不会乱连、乱发、乱调付费接口
- 用户要在 Lighthouse 实例上升级或加固一个自主 Agent
- 用户担心"Agent 自己抽风连了不该连的地方、发了不该发的数据、调了要花钱的接口"

## 适用范围与前置条件

- **适用**：腾讯云 Lighthouse 上、以 ubuntu 用户家目录常驻运行、有真实能力（命令/文件/外联/凭证）的 Hermes 类自主 Agent，需要非技术用户可操作的安全加固（与"经哪个频道指挥 Agent"无关）。
- **不适用**：CVM / 其他云 / 非 Hermes 类 Agent / 非 ubuntu 家目录部署（路径与 systemd 假设需另测）；纯前端或不开机器。
- **前置条件**：
  - 已连 Lighthouse MCP（`describe_*` / `execute_command`）；或至少能经 TAT / 控制台执行命令。
  - 实例真实 InstanceId（经 `describe_instances` 拿，勿硬编码）。
  - 理解本方法论是"非技术用户加固手册"——核心动作（关 SSH / 写 SOUL / 切档）都带"先解释风险、判断权留用户"。
- **SSH 关不关由用户自述场景决定**：本手册不预设必须关。读用户的用法说明，若所有通路为 Agent 出网 + TAT 管理 + 控制台兜底，则建议关门；若用户确有 SSH 终端需求，改走密钥加固而非关门。

## 核心原则（务必先读，优先级高于具体步骤）

### 一、非技术用户交互纪律（最高优先级）

- **不要对非技术用户甩技术选择题**（如"选钉 IP / 禁密码 / 关门"）。正确动作：先读完用户提供的文档/上下文，**自己判断**该选哪种，用大白话讲清做法与理由，把最终判断权留给用户（一句"行/别"即可），而非让他替你做技术决策。
- 返回容器后先给**就绪摘要（已做 / 卡点）+ 待厘清问题**，再推进；不要高频用选择题催决策。
- 解释风险时用**大白话 + 表格**：把"不做会怎样""做了有什么代价"讲清楚，让用户自己判断要不要做。禁止反复抛选项逼拍板。
- 用户纠正"你该替我判断"时，立刻停止问询，改为读完上下文下结论、讲清理由再执行。

### 二、安全纪律

- **先查后改**：任何修改前先 `Describe` / 只读侦察，不臆造 ID、不用占位 ID。
- **高风险二次确认**：删除实例、回滚快照、删防火墙规则（虽低不可逆风险也要说明影响）须讲清影响再动。
- **升级不碰 main**：用 `git checkout <tag>` 钉死到指定 tag，绝不强拉上游——对自主 Agent 而言，每次 `hermes update` 一类动作 = 供应链代码注入通道。
- **可从文档推断的，不要问用户**：用户的用法说明 / 共识文档通常已写明未来用法，据此判断 SSH 是否需保留，而非反向逼问。

## 工作流（PDCA 四阶段，权重 P≥D）

### P — 定位与只读侦察

1. 实例定位：`describe_regions` 拿到地域清单后，并行对最可能地域 `describe_instances`，按名称（如 `MyAgent-01`）或公网 IP 定位目标 `<实例ID>`。
2. 只读侦察（经 `mcp__lighthouse-ops__execute_command`，以 ubuntu 用户 `su - ubuntu -c '...'` 跑，因 Agent 通常装在该用户家目录）：
   - 版本与 git 溯源：`git log -1`、`git remote -v`、`git status -sb`、`git tag`
   - 升级机制：`hermes update --help`、`--plan`（只读核验）
   - 使用习惯：查 SSH 登录日志（`/var/log/auth.log` 的 `Accepted` 行、`last`）判断是否有人用 SSH——非技术用户常为零，佐证"可关门"。
   - 防火墙：`describe_firewall_rules` 看 SSH(22) 是否 `<IP>/0` 全开。
   - 出网状态：`iptables -S`（看 OUTPUT 默认策略）、`ss -tnp` 看当前外部连接（TAT 平台通道 `169.254.x.x`、腾讯云监控 agent 必放行）。
3. 读用户文档判断"未来用法要不要 SSH / 出网白名单"，形成结论而非问题抛回。

### D1 — 升级 Agent 修 CVE（pin tag 路径）

> 坑：`hermes update --branch <tag>` 把 tag 当 branch 校验会拒升；bare `hermes update` 有回拉 main 的供应链风险——两者都不用。

确定性手动路径（杜绝误拉 main）：

1. `git stash push -m "pre-upgrade ..."` 收起工作树本地未提交改动（否则 update 会拒）。
2. `git checkout <tag>`（如 `v2026.9.7`）钉死到目标 commit；用 `git describe --tags` / `git rev-parse HEAD` 核实。
3. 同步依赖：venv 通常**无 pip**，用受管 `uv`（路径如 `/home/ubuntu/.hermes/bin/uv`）：`uv pip install -e . --upgrade --python <venv>/bin/python`。
4. 重启服务（正确路径）：杀掉当前 gateway 进程，让 systemd 自动拉起新进程加载新版本。
   `GW=$(ps -eo pid,cmd | grep 'hermes_cli.main gateway run' | grep -v grep | awk '{print $1}'); kill $GW`
   等待 ~12s 后验证新 PID 出现、单实例（进程数=1）。
   ❌ 不要用 `systemctl --user restart hermes-gateway.service`（本 TAT 环境查不到该 unit，会卡死）；
   ❌ 不要用 `hermes_cli.main gateway restart`（内部走 systemctl，同样挂死）。
   详见下方「重启路径权威说明」。
5. 升级前务必先 `hermes update --backup`（或手动 `zip` 备份 HERMES_HOME）作为回滚点。
6. 验证：`hermes --version`、`git merge-base --is-ancestor <CVE_FIX_COMMIT> HEAD` 确认修复在树中、防火墙未变。

### D2 — 收紧 SSH（读文档判断后执行）

1. 从用户文档提取"未来使用场景"：若全部通路为 Agent 自身出网、经 TAT 管理、控制台兜底——**无任何场景需人 SSH 登录** → 选"关门"。
2. 关门 = `delete_firewall_rules` 删 `SSH(22, <IP>/0)` 那条；保留 ICMP(Ping)（无害、便于测连通）。
3. 复查 `describe_firewall_rules` 确认仅剩 Ping。
4. 零不可逆风险：将来要 SSH 可由用户在控制台 10 秒重开，或由本方经防火墙工具即时加回。
5. 若用户确用 SSH 终端：改走"禁密码仅密钥"（`approvals` 之外的 sshd 加固），先确认其登录方式再动，避免锁死。

### D3 — 续费提醒

实例有到期日（如 2026-12-31）时，用 `automation_update` 建两个一次性提醒：

- 第一次：到期前约 5 天（`scheduleType: once`，`scheduledAt` 带时区 `+08:00`），提示续费/开自动续费。
- 第二次：到期前约 2 天，紧急提示避免停机/释放。
- prompt 写明实例 ID、名称、地域、公网 IP、到期日，便于用户直接行动。

### D4 — 出网白名单：解释而非盲做

- 向用户解释：出网全开（`OUTPUT ACCEPT`）防的是"已被攻破后扩散"或"Agent 自发/被诱导乱连"。对常驻自主 Agent，**自发风险（被聊天消息诱导外传、自己判断调付费接口）比被黑客攻破更现实**。
- **优先走软层 SOUL 治本**（见 A 阶段），而非 OS 级 iptables 围栏——后者域名多变、易掐断微信/TAT，且本通道过滤器禁区（见"已知坑"）不适合手搓。
- 若用户坚持做 OS 出网白名单：必须带"15 分钟自动回滚 + 钉死腾讯内网 `<IP>/16` 始终放行"安全网，否则易自锁。

### A — SOUL.md 治本（软层安全约束）

> 这是治本核心：给 Agent 的"宪法"追加红线，不破坏其本地分析/自主常驻/cron 的自主性，只拦"对外副作用"。

1. 备份：`cp SOUL.md SOUL.md.<date>.bak`。
2. 追加安全约束段（模板见 `references/soul-security-template.md`）：数据外传需授权 / 付费接口先确认 / 防 prompt 注入 / 仅连白名单地址 / 不可绕过。
3. 重启 gateway 加载新人格（走「重启路径权威说明」的杀进程 + systemd 自动拉起），复查新进程已起、SOUL 内容在。
4. 硬层（改 `config.yaml` 的 `approvals.mode` 从 `off` 改严）为第二步：高影响（Agent 变慢、多步需用户点头），其合法档位语义需进代码确认后再与用户对齐，**不盲改**。

## 重启路径权威说明（与 hermes-approvals-switch 一致）

改 SOUL.md / config.yaml 后，gateway 必须重启才加载新配置。本环境（Lighthouse + TAT + systemd 用户服务）的重启**只有一条正确路径**：

- ❌ `systemctl --user restart hermes-gateway.service` —— 本 TAT 环境查不到该 unit，命令挂死。
- ❌ `hermes_cli.main gateway restart` —— 内部仍走 systemctl，本机同样挂起。
- ✅ 杀掉当前 gateway 进程，让 systemd 自动拉起新进程（已验证：杀掉后约 12s 新 PID 出现，加载新配置）：
  `GW=$(ps -eo pid,cmd | grep 'hermes_cli.main gateway run' | grep -v grep | awk '{print $1}'); kill $GW`
- ⚠️ 杀进程后**不要手动再起一个**，否则出现重复 gateway 抢 `gateway.sock`。
- 验证：进程数=1：`ps -eo pid,cmd | grep 'hermes_cli.main gateway run' | grep -v grep | wc -l`
- 兜底（仅当等待后进程数仍为 0、systemd 未自动拉起才用）：
  `cd /home/ubuntu/.hermes; setsid nohup /home/ubuntu/.hermes/hermes-agent/venv/bin/python -m hermes_cli.main gateway run >> /home/ubuntu/.hermes/logs/gateway-$(date +%s).log 2>&1 < /dev/null & disown`

> 本段为母/子两 skill 唯一权威重启口径，任何步骤需要重启 gateway 均引用此处，不再各写一套。

## 首跑自检清单（不硬扛我们的实例）

1. **定位实例**：`describe_regions` → `describe_instances` 拿真实 InstanceId + 家目录假设（默认 ubuntu）。
2. **只读侦察**：版本 / git 溯源 / SSH 日志 / 防火墙 / 出网 / `ps` 看 gateway 状态（本环境 `systemctl --user` 不可见，状态用 `ps` 看）。
3. **确认重启路径**：改 SOUL/config 后一律"杀进程 + systemd 自动拉起"，见「重启路径权威说明」；禁 `systemctl --user restart` / `hermes_cli.main gateway restart`。
4. **备份**：改前 `cp SOUL.md` / `cp config.yaml` 各留回滚点；重大变更前打系统盘快照。
5. **升级不碰 main**：用 `git checkout <tag>` + 受管 `uv`，绝不强拉上游。

## 已知坑（必读，避免重复踩）

- **TAT 命令过滤器禁区**：命令含 `nft` 关键词、或读 `/etc/resolv.conf`、或复杂正则 → 返回 `AccessDeny`。OS 级防火墙手术不宜经此通道盲改；改用 `iptables -S`（避免 nft）、避开 resolv.conf。
- **轻量云防火墙只管入站**：能关 SSH(22) 这种"谁能敲门"的规则；出网全开是 OS 内 `OUTPUT` 链默认 ACCEPT，不在轻量云防火墙功能内（那是付费"云防火墙"产品）。
- **`hermes update` 陷阱**：`--branch <tag>` 不支持 tag 校验会拒；bare 形式有回拉 main 风险。用 `git checkout tag` + `uv` 手动路径。
- **venv 无 pip**：依赖管理用受管 `uv`（如 `/home/ubuntu/.hermes/bin/uv`），非 `pip install`。
- **gateway 是 systemd 用户服务，由 systemd 自动管理**：改 SOUL/config 后须重启才加载新配置。但本 TAT 环境 `systemctl --user` 看不到该 unit（`hermes-gateway.service`）会卡死，一律走「杀进程 + systemd 自动拉起」（见下方「重启路径权威说明」），不要手搓 `systemctl --user restart`、也不要 `hermes_cli.main gateway restart`。TAT 默认以 root 执行，`hermes` 不在 root PATH，只读侦察用 `su - ubuntu -c` / `runuser -u ubuntu`。
- **工作树有未提交改动**会阻塞升级，先 `git stash`。

## 工具参考

- Lighthouse MCP：`describe_regions` / `describe_instances` / `describe_firewall_rules` / `delete_firewall_rules` / `execute_command`（`SystemType: Linux`，以 `su - ubuntu -c` 跑）。
- `automation_update`：建续费提醒（`mode: create`，`scheduleType: once`，`scheduledAt` ISO 带时区）。
- 远程只读命令：版本/ git 溯源 / SSH 日志 / `iptables -S` / `ss -tnp` / 进程状态用 `ps -eo pid,cmd | grep 'hermes_cli.main gateway run' | grep -v grep`（本 TAT 环境 `systemctl --user` 查不到 unit，状态也用 `ps` 看，不要 `systemctl --user status`）。

## 附：references

- `references/soul-security-template.md` — SOUL 安全约束段模板，可直接追加进运行实例。
- `references/lighthouse-recon.md` — 只读侦察命令清单（定位/版本/SSH 日志/防火墙/出网/服务）。
