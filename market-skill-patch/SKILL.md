---
name: market-skill-patch
description: 修正从市场/第三方安装的 skill 时使用——保证补丁在 skill 升级后可对照重打，并区分「原有缺陷」与「自己引入的缺陷」。触发：市场技能有 bug 要改 / 已安装 skill 的脚本需要打补丁 / 改完怕升级覆盖。
trigger: 当需要修改、修复、给从市场（BuiltinMarket / SkillHub）安装的 skill 打补丁，或改动后要保证 skill 升级不丢补丁时使用。
agent_created: true
---

# 市场技能补丁维护

> 核心约束：市场 skill 升级会**整包覆盖** —— 改了不登记补丁，下次升级必丢。
> 所以每次动市场 skill，产出必须包含「可重打的补丁副本 + 重打判据」。

## 前置事实（本机）
- 用户级 skill 目录：`~/.workbuddy\skills\<skill-name>\`
- 市场 skill 的 `agent_created` 通常不是 `true` → **SkillManage 改不了它**，只能直接用 Edit/Write 改文件本身。
- 本机 Git Bash 的 `rm` / `mkdir` / `tail` 不可用 → 文件增删一律走 Python。

## 七步流程

1. **改前先建带时间戳回滚点**
   `<workspace>\_rollback_<skill>_<YYYYMMDD_HHMM>\`，把**要改的每个文件**复制成 `<name>.before_roundN`，并记 sha256。

2. **整篇读，别只读踩到的那一个**
   同一份逻辑常被复制到多个脚本（实测：`epub-to-txt` 的 `strip_html_tags` 存在 **4 份**）。先 grep 找同源函数的所有副本，一并评估范围。

3. **靶向补丁**
   用 Edit 做小改动，不整体重写；改完立刻对全部涉改脚本跑 `py_compile`。

4. **造夹具做隔离测试**
   产物全落临时目录，**绝不碰用户真实文件**；夹具要覆盖「包自带测试跑不到」的边界。

5. **出现新失败 → 先取证，别急着认领或归咎**
   用第 1 步回滚点的**原始版**跑**同一输入**：
   - 原始版也失败 ⇒ **原有缺陷**，可顺手修（并如实标注"既有缺陷"）
   - 原始版通过 ⇒ **自己的补丁引入**，回滚重来
   （实测：`mobi-to-txt-batch.py` 缺 mobi7 兜底 → 原始版同样 0/1 失败，确认为既有缺陷。）

6. **哈希对账 + 存最终态副本**
   「before ↔ now」逐文件比对，列出「改动 / 未动」；把最终态存成 `<name>.roundN_patched`（升级后对照重打用）。

7. **留重打判据 + 登记**
   给出「如何快速确认补丁还在」的判据（如 grep 新函数名），并把「升级会覆盖 + 副本路径 + 判据」写进项目 MEMORY。

## 顺带必做两件

- **查 SKILL.md 与包内文件是否双向一致**：文档引用的脚本是否都在包里、包里的脚本是否都被提到。**文档写旧行为会误导后续使用**。
- **补齐被漏发的声明文件**：市场包可能漏发自检/`--help` 引用的资源（实测：`cangjie-skill` 漏发 13 份 `schemas/`），导致自检恒 FAIL。
  取法优先顺序：
  1. `api.github.com/repos/<owner>/<repo>/contents/<路径>?ref=<tag>` —— 列目录（含子目录，递归）
  2. `raw.githubusercontent.com/<owner>/<repo>/<tag>/<路径>` —— 逐文件取原文
  ⚠️ `github.com/.../releases/download/...` 在本机常被重置（`ConnectionResetError WinError 10054`，走 objects 域）—— **别在这条路上耗时间，直接换上面的通道**。
  取回后**只新增、不覆盖**市场包已有文件；另存一份备份到 `<workspace>\_backup_<skill>_<版本>\` 供升级后重补。

## 验证底线（不可省）
- 全部涉改脚本 `py_compile` 通过
- 端到端夹具断言全绿（含"改前失败/改后成功"的对照）
- 哈希对账「改了几个、哪几个没动」说得出来
- `check_closeout.sh`（若动过它）或该 skill 自带自检命令实跑通过
