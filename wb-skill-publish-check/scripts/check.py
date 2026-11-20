#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WB 市场 Skill 上架前置自检器
============================
把平台三轮驳回（目录超限 / 缺展示字段 / 头像>500KB）集成的硬约束一次性验完。

用法:
    python check.py <skill目录> [--avatar-max-kb 500] [--pack <输出zip路径>]

退出码:
    0 = 全绿，可交付上架
    1 = 有红项，禁止交付

约束来源（已写入用户级 ~/.workbuddy/MEMORY.md《WB 市场 Skill 上架硬约束》）：
  ① 目录最多两级（根/二级/文件）
  ② frontmatter 必填 11 字段
  ③ avatar.png <= 500KB
  ④ agent 无 publish 工具，上架走官方入口（本脚本只质检+可选打包）
"""
import os
import sys
import zipfile
import argparse

REQUIRED_FIELDS = [
    "name", "title", "display_name", "display_name_en",
    "description", "description_zh", "description_en",
    "version", "author", "trigger", "agent_created",
]
AVATAR_MAX_KB = 500
MAX_DEPTH = 2  # 根=1, 二级目录内=2


def parse_frontmatter(path):
    raw = open(path, encoding="utf-8").read().replace("\r\n", "\n")
    if not raw.startswith("---\n"):
        return None, "frontmatter 起始缺失"
    body = raw[len("---\n"):]
    lines = []
    for ln in body.split("\n"):
        lines.append(ln)
        if ln.strip() == "---":
            break
    fm = lines[:-1]
    top = {}
    i = 0
    while i < len(fm):
        line = fm[i]
        if not line.strip() or line.startswith(" "):
            i += 1
            continue
        if ":" not in line:
            i += 1
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if val == "|":
            buf = []
            j = i + 1
            while j < len(fm) and (fm[j].startswith("  ") or fm[j].strip() == ""):
                if fm[j].strip():
                    buf.append(fm[j].strip())
                j += 1
            top[key] = "\n".join(buf)
            i = j
        elif val == "":
            items = []
            j = i + 1
            while j < len(fm) and fm[j].startswith("  - "):
                items.append(fm[j].strip()[3:].strip())
                j += 1
            top[key] = items
            i = j
        else:
            top[key] = val
            i += 1
    return top, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("skill_dir")
    ap.add_argument("--avatar-max-kb", type=int, default=AVATAR_MAX_KB)
    ap.add_argument("--pack", default=None, help="可选：校验通过后打包到此 zip 路径")
    a = ap.parse_args()

    root = os.path.abspath(a.skill_dir)
    reds = []

    # ---- ① 目录层级 ----
    print("== ① 目录层级（最多两级）==")
    for base, dirs, files in os.walk(root):
        if "__pycache__" in dirs:
            dirs.remove("__pycache__")
        for f in files:
            if f.endswith(".pyc"):
                continue
            rel = os.path.relpath(os.path.join(base, f), root).replace("\\", "/")
            depth = rel.count("/") + 1
            if depth > MAX_DEPTH:
                reds.append(f"目录超限: {rel} (层级 {depth} > {MAX_DEPTH})")
                print(f"  [RED] {rel} 层级 {depth}")
            else:
                print(f"  [ok]  {rel}")
    if not reds:
        print("  -> 全部两级内 ✓")

    # ---- ② frontmatter 字段 ----
    print("\n== ② frontmatter 必填字段 ==")
    sm = os.path.join(root, "SKILL.md")
    if not os.path.exists(sm):
        reds.append("SKILL.md 不存在")
        print("  [RED] SKILL.md 不存在")
    else:
        top, err = parse_frontmatter(sm)
        if err:
            reds.append(f"frontmatter 解析失败: {err}")
            print(f"  [RED] {err}")
        else:
            for fld in REQUIRED_FIELDS:
                v = top.get(fld)
                present = bool(v) and not (isinstance(v, list) and len(v) == 0)
                if not present:
                    reds.append(f"缺字段: {fld}")
                    print(f"  [RED] {fld}")
                else:
                    disp = v if isinstance(v, str) else f"list[{len(v)}]"
                    print(f"  [ok]  {fld}: {disp[:40]}")
            # description 质量：问题先行
            desc = top.get("description", "")
            if not any(k in desc for k in ("？", "失忆", "事故", "？")):
                print("  [warn] description 建议问题先行（含问号/失忆/事故）")

    # ---- ③ 头像体积 ----
    print(f"\n== ③ 头像体积（≤{a.avatar_max_kb}KB）==")
    av = os.path.join(root, "avatar.png")
    if not os.path.exists(av):
        print(f"  [warn] 无 avatar.png（如不需要头像可忽略）")
    else:
        kb = os.path.getsize(av) / 1024
        if kb > a.avatar_max_kb:
            reds.append(f"头像超体积: {kb:.1f}KB > {a.avatar_max_kb}KB")
            print(f"  [RED] {kb:.1f}KB 超标")
        else:
            print(f"  [ok]  {kb:.1f}KB")

    # ---- 结论 ----
    print("\n" + ("=" * 40))
    if reds:
        print(f"RESULT: RED（{len(reds)} 项未过，禁止交付）")
        for r in reds:
            print("  - " + r)
        return 1
    print("RESULT: GREEN（全过，可打包交付上架）")

    # ---- 可选打包 ----
    if a.pack:
        out = os.path.abspath(a.pack)
        if os.path.exists(out):
            os.remove(out)
        n = 0
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for base, dirs, files in os.walk(root):
                if "__pycache__" in dirs:
                    dirs.remove("__pycache__")
                for f in files:
                    if f.endswith(".pyc"):
                        continue
                    rel = os.path.relpath(os.path.join(base, f), root).replace("\\", "/")
                    z.write(os.path.join(base, f),
                            os.path.join(os.path.basename(root), rel))
                    n += 1
        print(f"已打包: {n} 文件 -> {out} ({os.path.getsize(out)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
