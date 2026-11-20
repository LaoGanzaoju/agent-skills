name: wb-skill-publish-check
title: 上架前置自检
description: |
  WorkBuddy 市场 skill 上架前置校验器。打包发布任何 skill 之前先跑它，
  把「目录层级 / frontmatter 展示字段 / 头像体积」三道平台硬约束一次性验完，
  全绿再交用户上传，避免被平台逐轮驳回（装机伴侣 skill 实测踩过三轮坑才集齐这些规则）。
version: 1.0.0
author: 甘晓东
agent_created: true
trigger:
  - 打包 skill 准备上架市场前
  - 用户说「发布前自检」「上架校验」「打包 skill」
  - 任何 skill 目录要打成 zip 交官方上架入口前
