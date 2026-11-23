---
name: wb-skill-publish-check
title: 上架前置自检
display_name: 上架前置自检
display_name_en: Pre-publish Skill Check
description: |
  打包 Skill 准备上架市场前的硬约束校验器。会不会目录层级超限？frontmatter 展示字段缺了哪几个？头像有没有超过 500KB？三轮驳回每次只报一条，很烦。本 skill 一次性验完这三道平台硬约束，全绿才允许打包交付。当用户说「发布前自检 / 上架校验 / 打包 skill」，或任何 skill 目录要打成 zip 交官方上架入口时使用。
description_zh: |
  上架打包前一次性验完三道平台硬约束：目录最多两级、frontmatter 必填 11 字段、头像不超过 500KB。全绿才打包，红项逐条列出，避免被平台三轮逐一驳回。
description_en: |
  Pre-flight checker for publishing a Skill to the marketplace. Verifies the three platform hard constraints in one pass: directory depth (max 2 levels), 11 required frontmatter fields, and avatar size (max 500KB). Returns GREEN only when all pass, with every red item listed.
version: 1.0.0
author: 甘晓东
trigger:
  - 打包 skill 准备上架市场前
  - 用户说「发布前自检」「上架校验」「打包 skill」
  - 任何 skill 目录要打成 zip 交官方上架入口前
agent_created: true
---

# 上架前置自检

## 用途

WorkBuddy 市场 skill 上架有三道硬约束，平台每次驳回只报一条。本 skill 一次性验完，红项逐条列出，全绿才打包。

## 何时用

- 准备把一个 skill 目录打包成 zip、交官方上架入口前；
- 改完已有 skill 的 frontmatter 或目录结构后；
- 被平台驳回、需要定位是哪条约束没过时。

## 三道约束

1. **目录层级**：最多两级（根目录 / 二级目录 / 文件）。三级及以上报红。
2. **frontmatter 字段**：`SKILL.md` 开头必须有 `---` 包裹的元信息，且包含 11 个必填字段：`name`、`title`、`display_name`、`display_name_en`、`description`、`description_zh`、`description_en`、`version`、`author`、`trigger`、`agent_created`。缺 `---` 边界或任一字段报红。
3. **头像体积**：`avatar.png` 不超过 500KB（可用 `--avatar-max-kb` 调整）。无头像只警告不报红。

## 怎么用

在 skill 所在机器的终端执行（脚本为纯 Python 标准库，无需装包）：

```bash
python scripts/check.py <skill目录>
```

通过后可选打包：

```bash
python scripts/check.py <skill目录> --pack <输出zip路径>
```

## 退出码（可机读）

- `0` = 全绿，可交付上架
- `1` = 有红项，禁止交付

输出末尾会打 `RESULT: GREEN` 或 `RESULT: RED（N 项未过）`，并逐条列出红项。

## 注意

- 本 skill 只做质检与可选打包。当前 agent 没有 publish 工具，实际上架仍走官方入口。
- 目录里的 `__pycache__` 与 `.pyc` 会被忽略，不影响层级判定。
