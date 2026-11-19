---
name: wb-library-access
description: |
  WB 资料库（workbuddy 内置资料库）读写 canonical 路径与鉴权流程。
  凡涉及 资料库 / 空间文档 / 老甘素材库 的读、写、搜、列操作，或 space_api.py 报错时使用。
  触发词：资料库、素材库、space_api、空间文档、老甘素材库。
  判据真源：本文件。军规 `~/.workbuddy/rules/10-知识库访问钉死.md` 只留触发与钉死 ID。
version: 1.0.0
author: 甘晓东
agent_created: true
---

# WB 资料库访问（反绕路）

> 2026-09-19 甘晓东痛点：「批量读/写时 wb 链接总抽风：文件夹 id 出错、或 ccs 自己绕路写脚本」。
> 2026-09-25 甘晓东裁定：细节不该住军规，迁入本 skill；军规只留触发器。
> （IMA 已弃用，相关钉死内容整体移除。）

## 铁律

- **永远走 `space_api.py`，禁止手搓等价脚本**：禁止自己拼 HTTP 调 workbuddy 接口。
- **token 只从官方通道取，禁止探测**：只经 `connect_open_platform`（DeferExecuteTool）获取；禁 env / 文件 / 凭证目录 / 进程 / RPC 探测，禁 `space_api.py connect_open_platform`。
- 一不顺手就绕路 = 抽风根因。卡住先回查本文件，不另起脚本。

## 入口

- 脚本（唯一）：`/Applications/WorkBuddy.app/Contents/Resources/app.asar.unpacked/resources/plugins/workbuddy-builtin/skills/library/space_api.py`
- Python 用托管版：`<工作目录>`

## 鉴权三步（抽风头号原因）

1. 先静默跑 `python3 "${CODEBUDDY_SKILL_DIR}/runtime_context.py"` 判 `mode=sandbox|client`（Mac=client）。
2. `mode=client` → **必须** `ToolSearch connect_open_platform` → `DeferExecuteTool connect_open_platform`（`skill_id:"library"`）取 token；把 token 经 stdin 首行传给脚本：`printf '%s' "<token>" | python3 space_api.py <api> --token-stdin ...`。
3. token 不落地、不写文件、不跨进程复用；**每次 session 网络命令前都换一次**（过期即 AUTH_REQUIRED）。

## search vs list 铁则（防「以为库没了」误判）

- `space.searcher.search-nodes` **只索引正文，不索引文件夹标题**——搜「老甘/造局/素材库」返回空是正常，不代表不存在。
- 找文件夹 / 列目录 → 用 `space.workspace.list-node`（`--space-id` + `--parent-node-id`）。
- 取节点内容 → 先 `space.workspace.node-info` 读 `kind`，再按 kind 走 `doc/link/database/...` entry。

## 响应约定

- 成功：stdout `KS_*` 前缀行 / 单行 JSON；失败：stdout 一行 `{"error":"<脱敏>"}` 后 `exit 0`。
- 收到 `{"error":...}` 按官方 `error_handling.md`（skill 同目录）行动。

## 错误→fix 速查

| 现象 | 根因 | 修复（钉死动作） |
|---|---|---|
| `AUTH_REQUIRED` | 没换票或 token 过期 | `ToolSearch connect_open_platform` → DeferExecuteTool 重取 → `--token-stdin` |
| 搜「老甘」返回空 | search 不索标题 | 改用 `list-node` 列目录 |
| 直接裸跑 `space_api.py` 报错 | 绕路未换票 | 回到上面鉴权三步，禁止裸跑 |
