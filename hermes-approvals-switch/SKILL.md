---
name: hermes-approvals-switch
description: 一键安全切换 Hermes Agent 的 approvals.mode 档位（日常 smart / 全确认 manual / 全托管 off）。带配置备份与正确重启路径，避免四处撞壁、改坏、重启卡死。触发短指令：切审批档 / 审批开关 / Hermes档 / 切档。
display_name: Hermes 审批档开关
display_name_en: Hermes Approvals Mode Switch
description_zh: 安全、幂等地在三个档位间切换 Hermes Agent 的 approvals.mode，日常 smart（风险动作前拦你确认）、全确认 manual（每步都问）、全托管 off（裸奔，不推荐）。每次切换带配置备份与正确重启路径，杜绝改坏、重启卡死、四处撞壁。触发短指令：切审批档 / 审批开关 / Hermes档 / 切档。
description_en: Safely and idempotently switch Hermes Agent's approvals.mode among three gears - smart (daily, intercepts risky actions), manual (asks every step), off (no guardrails, not recommended). Each switch backs up config and uses the correct restart path to avoid breakage or reboot hangs. Trigger phrases - 切审批档 / 审批开关 / Hermes档 / 切档.
category: devtools
version: 1.0.0
author: 甘晓东
---

# Hermes 审批档开关（轻量安全切换）

安全、幂等地在三个档位间切换 Hermes Agent 的 `approvals.mode`。每次切换都带**备份 + 正确重启**，杜绝"改坏 / 重启卡死 / 到处撞壁"。

## 档位（短指令：切审批档 / 审批开关 / Hermes档）

| 友好名 | mode 值 | 行为 | 适用 |
|---|---|---|---|
| 日常（甲） | `smart` | 机制强制：风险动作（外发数据 / 付费接口 / 危险命令）前拦下等你确认，日常自主 | **默认推荐** |
| 全确认 | `manual` | 机制强制：每步对外 / 危险动作都问你 | 想全程盯着 / 教学 |
| 全托管 | `off` | 机制强制但=裸奔：全部闸门关闭 | 仅纯沙箱信任环境；切它必须二次确认 + 警告 |

> 三个档**都是代码机制强制**，不靠 agent 自觉读文件。区别只是"多频繁拦你"。`off` 不推荐。

## 目标实例（默认值 + 首跑自检，可覆盖）

> 下面按"Lighthouse + Hermes + ubuntu 家目录"给出**默认假设**；首次运行先走文末「首跑自检清单」自动探测/确认，环境不同就覆盖变量，不要直接改源码硬值。

- 实例（默认示例）：`<实例ID>`（地域如 ap-beijing）—— 真实实例请经 `describe_instances` 拿到，勿凭记忆硬编码
- 配置：`/home/ubuntu/.hermes/config.yaml`
- gateway 进程特征：`hermes_cli.main gateway run`
- Hermes CLI：`/home/ubuntu/.hermes/hermes-agent/venv/bin/python -m hermes_cli.main`
- 日志：`/home/ubuntu/.hermes/logs/`

## 安全网（每次改动前必做）

1. **配置即时备份**（精确回滚点）：
   `cp /home/ubuntu/.hermes/config.yaml /home/ubuntu/.hermes/config.yaml.bak.$(date +%s)`
2. **系统盘快照**（重大变更前可选）：用 Lighthouse MCP `create_instance_snapshot` 打快照。

## 切换步骤（幂等、安全）

1. 确认实例在线（Lighthouse MCP `describe_instances`，拿到真实 InstanceId）。
2. 查当前 gateway 进程 PID（应恰好 1 个）：
   `ps -eo pid,cmd | grep 'hermes_cli.main gateway run' | grep -v grep`
3. 备份 config（见上）。
4. **精确改写**（只动 line 140 带引号的 mode，绝不碰 line 64 `session_reset: mode: none`）：
   `sed -i -E "s/^  mode: '(off|smart|manual)'$/  mode: '<TARGET>'/" /home/ubuntu/.hermes/config.yaml`
   - `<TARGET>` ∈ {smart, manual, off}
   - 切到 `off` 前必须向用户二次确认并警告"裸奔"。
5. **重启 gateway（正确路径，关键）**：
   - ❌ 不要用 `systemctl --user` —— 本 TAT 环境查不到该 unit，会卡死。
   - ❌ 不要用 `hermes_cli.main gateway restart` —— 内部走 systemctl，在本机会挂起。
   - ✅ 杀掉当前 gateway 进程，**让 systemd 自动拉起**新进程加载新配置：
     `GW=$(ps -eo pid,cmd | grep 'hermes_cli.main gateway run' | grep -v grep | awk '{print $1}'); kill $GW`
     等待 ~12s，systemd 会自动 respawn（已验证：杀掉后新 PID 出现）。
   - ⚠️ 杀进程后**不要手动再起一个**，否则出现重复 gateway 抢 `gateway.sock`。
   - 若等待后进程数仍为 0（systemd 未自动拉起），才用兜底 detached 启动：
     `cd /home/ubuntu/.hermes; setsid nohup /home/ubuntu/.hermes/hermes-agent/venv/bin/python -m hermes_cli.main gateway run >> /home/ubuntu/.hermes/logs/gateway-$(date +%s).log 2>&1 < /dev/null & disown`
6. **验证**：
   - 进程数=1：`ps -eo pid,cmd | grep 'hermes_cli.main gateway run' | grep -v grep | wc -l`
   - 配置已落盘：`grep -n '^  mode:' /home/ubuntu/.hermes/config.yaml`（仅 140 变目标，64 仍 `none`）
   - 健康：`cat /home/ubuntu/.hermes/gateway_state.json`

## 回滚

`cp /home/ubuntu/.hermes/config.yaml.bak.<ts> /home/ubuntu/.hermes/config.yaml` 然后走上面重启步骤。

## 已知坑（固化，避免重踩）

- `^  mode:` 在 config 里出现 2 次：line 140（`mode: 'xxx'`）与 line 64（`session_reset: mode: none`）。sed 必须带引号 + 行首锚定，避免误改 `none`。
- TAT 里 `systemctl --user` 看不到 `hermes-gateway.service`（虽 systemd 实际在管），导致官方 restart 卡死 —— 一律走"杀进程 + systemd 自动拉起"。
- `approvals.mode` 只有 3 个合法值（源码 `approval_context.py:197` `_VALID_MODES = ("manual", "smart", "off")`）。写错值会被告警并回退到 `manual`。

## 适用范围

- **适用**：在腾讯云 Lighthouse（或同类 systemd 托管的自主 Agent 环境）上、以 ubuntu 用户家目录常驻运行的 Hermes 类 Agent，需要安全地切换审批档位（与"经哪个频道指挥 Agent"无关，channel-agnostic）。
- **不适用**：非 systemd 托管 / 容器 / 非 ubuntu 家目录部署的 Agent；需要把 SOUL 软规则变硬（那是 `lighthouse-agent-hardening` 的范围）。
- 本 skill **只**控制 `approvals.mode` 档位（轴 1：围栏宽窄），不负责把 SOUL 软规则变硬。

## 前置条件（首跑前确认）

- 已拿到目标实例的**真实 InstanceId**（经 Lighthouse MCP `describe_instances`，不要凭记忆硬编码）。
- 知道 Hermes 家目录与 CLI 路径（默认见上方；不同环境覆盖变量）。
- 已理解三档语义：`smart`=机制强制且日常自主（默认推荐）、`manual`=每步问、`off`=裸奔不推荐。

## 首跑自检清单（默认值 + 自动探测，不硬扛我们的机器）

1. **定位实例**：`describe_instances` 拿真实 InstanceId；实例在线且 gateway 在跑。
2. **探测路径**（与默认值不同就覆盖下列变量再执行）：
   - `HERMES_HOME`：默认 `/home/ubuntu/.hermes`
   - `CONFIG`：`$HERMES_HOME/config.yaml`
   - `CLI`：默认 `$HERMES_HOME/hermes-agent/venv/bin/python -m hermes_cli.main`
   - `PROC`：默认 `hermes_cli.main gateway run`（进程特征）
3. **确认当前档位**：`grep -n '^  mode:' $CONFIG`（仅 line 140 变目标，64 仍 `none`）。
4. **验证重启路径可用**：本环境 `systemctl --user` 不可见会卡死，重启一律走"杀进程 + systemd 自动拉起"（见 `lighthouse-agent-hardening` 的「重启路径权威说明」）；禁 `systemctl --user restart` / `hermes_cli.main gateway restart`。
5. **备份已就位**：每次改前 `cp $CONFIG $CONFIG.bak.$(date +%s)`。

> 默认值按"Lighthouse + Hermes + ubuntu 家目录"假设；其他环境改环境变量/参数覆盖即可，不要改源码里的硬值。
