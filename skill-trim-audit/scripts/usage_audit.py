#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
skill-trim-audit · 使用度审计核心脚本（2026-09-12 固化）

判据：A（能力集·规划需要）∪ B（使用集·近 N 天真实调用）→ 保留；两者皆非 → 候选瘦身。

实测口径（2026-09-12 定，勿随意放宽）：
  A = `Skill` 工具被**点名调用**（function_call.name == "Skill"，读 input.skill / input.command）
  B = 命令参数或工具返回文本中出现 `/skills/<名>`，且**该条只涉及这一个 skill**（过滤批量盘点噪声）
  ✗ 已弃用：裸 skill 名全文匹配 —— 读「瘦身清单」/系统注入的技能列表会让全部 skill 命中（实测假阳性 100%）

用法：
  python3 usage_audit.py                          # 近 30 天 + 默认能力集，人读格式
  python3 usage_audit.py --days 14                # 自定义时间窗
  python3 usage_audit.py --json --out /tmp/a.json # 机器可读（自动化消费）
  python3 usage_audit.py --allowlist /path/to/能力集.md
  python3 usage_audit.py --no-allowlist           # 只看使用集，不做 A∪B 分类
"""

import argparse
import collections
import datetime
import glob
import json
import os
import sys

DEFAULT_SKILLS_DIR = os.path.expanduser("~/.workbuddy/skills")
DEFAULT_PROJECTS_DIR = os.path.expanduser("~/.workbuddy/projects")
DEFAULT_ALLOWLIST = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "references",
    "能力集A_默认.md",
)

# 单条文本最多看这么多字符的 output，防超大 Read 结果拖垮内存
OUTPUT_CAP = 20000


def parse_allowlist(path):
    """解析能力集文件。一行一个 skill 名；`# 注释`；`## 分组` 建分组；容忍 - * 反引号 列表符号。"""
    names, groups = [], {}
    if not path or not os.path.isfile(path):
        return names, groups
    cur = "未分组"
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for raw in fh:
            s = raw.strip()
            if not s:
                continue
            # `## 分组名` 建分组；`#` 注释与 `>` 引用段一律跳过（否则说明文字会被当成 skill 名）
            if s.startswith("#") or s.startswith(">"):
                if s.startswith("##"):
                    cur = s.lstrip("#").strip()
                continue
            s = s.lstrip("-*+ ").replace("`", "").strip()
            if not s:
                continue
            name = s.split()[0].rstrip("：:,，。)）")
            if name:
                names.append(name)
                groups.setdefault(cur, []).append(name)
    seen, uniq = set(), []
    for n in names:
        if n not in seen:
            seen.add(n)
            uniq.append(n)
    return uniq, groups


def scan(skills_dir, projects_dir, days):
    """扫描会话留档，返回 (skills, A, B, Adays, Bdays, files_scanned)。"""
    if not os.path.isdir(skills_dir):
        sys.exit(f"[ERR] skills 目录不存在: {skills_dir}")
    if not os.path.isdir(projects_dir):
        sys.exit(f"[ERR] projects 目录不存在: {projects_dir}")

    skills = [d for d in sorted(os.listdir(skills_dir)) if os.path.isdir(os.path.join(skills_dir, d))]
    cutoff_ms = (datetime.datetime.now() - datetime.timedelta(days=days)).timestamp() * 1000
    files = [f for f in glob.glob(os.path.join(projects_dir, "*", "*.jsonl"))
             if os.path.getmtime(f) * 1000 >= cutoff_ms]

    A, B = collections.Counter(), collections.Counter()
    Adays, Bdays = collections.defaultdict(set), collections.defaultdict(set)
    files_scanned = 0

    for f in files:
        try:
            fh = open(f, errors="ignore")
        except OSError:
            continue
        files_scanned += 1
        with fh:
            for line in fh:
                if '"function_call' not in line:
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                t = d.get("type")
                if t not in ("function_call", "function_call_result"):
                    continue
                ts = d.get("timestamp") or 0
                day = datetime.datetime.fromtimestamp(ts / 1000).strftime("%m-%d") if ts else "?"

                raw = d.get("arguments")
                if isinstance(raw, str):
                    argtxt = raw
                elif raw is None:
                    argtxt = ""
                else:
                    argtxt = json.dumps(raw, ensure_ascii=False)

                # A：Skill 工具被点名
                if t == "function_call" and d.get("name") == "Skill":
                    try:
                        a = json.loads(argtxt) if argtxt else {}
                    except Exception:
                        a = {}
                    if not isinstance(a, dict):
                        a = {}
                    s0 = a.get("skill") or a.get("command")
                    if s0:
                        A[s0] += 1
                        Adays[s0].add(day)

                # B：专一的 /skills/<名> 路径引用
                txt = argtxt + " " + str(d.get("output") or "")[:OUTPUT_CAP]
                if "/skills/" in txt:
                    hits = [s for s in skills if "/skills/" + s in txt]
                    if len(hits) == 1:
                        B[hits[0]] += 1
                        Bdays[hits[0]].add(day)

    return skills, A, B, Adays, Bdays, files_scanned


def classify(skills, A, B, Adays, Bdays, allow):
    allowset = set(allow)
    installed = set(skills)
    used = set(A) | set(B)
    alldays = {k: (Adays[k] | Bdays[k]) for k in used}

    def days_of(k):
        return sorted(alldays.get(k, set()))

    def rank(keys):
        return sorted(keys, key=lambda k: (-len(alldays[k]), -(A[k] + B[k])))

    # 点名了、但不在本机 ~/.workbuddy/skills 目录里的 = 插件/内置/连接器 skill，
    # 不属于本机 skill 目录的瘦身范围，单独成组（避免污染"在用"判断）
    external = rank([k for k in used if k not in installed])
    used_local = [k for k in used if k in installed]

    core = rank([s for s in used_local if s in allowset])
    used_only = rank([s for s in used_local if s not in allowset])
    allow_used = set(core) | set(used_only)
    allow_only = sorted([s for s in allow if s not in allow_used])
    candidate = sorted([s for s in skills if s not in allowset and s not in used],
                       key=lambda s: s)

    return {
        "core": core,
        "used_only": used_only,
        "external": external,
        "allow_only": allow_only,
        "candidate": candidate,
        "detail": {k: {"a": A[k], "b": B[k], "days": days_of(k)} for k in rank(used)},
    }


def main():
    ap = argparse.ArgumentParser(description="skill 使用度审计 · A∪B 交叉瘦身判据")
    ap.add_argument("--days", type=int, default=30, help="统计窗口天数（默认 30）")
    ap.add_argument("--skills-dir", default=DEFAULT_SKILLS_DIR)
    ap.add_argument("--projects-dir", default=DEFAULT_PROJECTS_DIR)
    ap.add_argument("--allowlist", default=DEFAULT_ALLOWLIST, help="能力集 A 文件（一行一个 skill 名）")
    ap.add_argument("--no-allowlist", action="store_true", help="跳过能力集，只输出使用集")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--out", default=None, help="把 JSON 同时写到该文件")
    args = ap.parse_args()

    allow, groups = ([], {}) if args.no_allowlist else parse_allowlist(args.allowlist)
    skills, A, B, Adays, Bdays, nfiles = scan(args.skills_dir, args.projects_dir, args.days)

    # 名单里但不存在的名字：剔除并告警（可能是拼错、或 skill 已改名/退役）
    installed = set(skills)
    missing = [a for a in allow if a not in installed]
    allow = [a for a in allow if a in installed]

    res = classify(skills, A, B, Adays, Bdays, allow)

    payload = {
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "window_days": args.days,
        "files_scanned": nfiles,
        "skills_total": len(skills),
        "allowlist_size": len(allow),
        "allowlist_missing": missing,
        "buckets": {
            "core": res["core"],
            "used_only": res["used_only"],
            "external_plugin": res["external"],
            "allow_only": res["allow_only"],
            "candidate_trim": res["candidate"],
        },
        "usage_detail": res["detail"],
    }

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    w = args.days
    print(f"=== skill-trim-audit · 近 {w} 天 · {payload['generated_at']} ===")
    print(f"会话文件 {nfiles} 个 | 已装 skill {len(skills)} 个 | 能力集 A {len(allow)} 项")
    if missing:
        print(f"⚠️ 名单里 {len(missing)} 个名字当前未安装（已从保护清单剔除）：{'、'.join(missing)}")
    print()

    def line(k):
        d = res["detail"][k]
        return f"  {len(d['days']):>2}天 {d['a'] + d['b']:>4}次  {k}  (点名{d['a']}/路径{d['b']})"

    print(f"【核心】在 A 也在 B（{len(res['core'])} 个）")
    for k in res["core"]:
        print(line(k))
    print()
    print(f"【在用·A 集外】本机在用但不在能力集（{len(res['used_only'])} 个）← 需回补进能力集或判定为可弃")
    for k in res["used_only"]:
        print(line(k))
    print()
    print(f"【外部能力】点名了但非本机 skills 目录（{len(res['external'])} 个）← 插件/内置/连接器，不属本机瘦身范围")
    print("  " + "、".join(res["external"]))
    print()
    print(f"【规划需要·近 {w} 天未跑】在 A 不在 B（{len(res['allow_only'])} 个）← 保留，属能力缺口不属冗余")
    print("  " + "、".join(res["allow_only"]))
    print()
    print(f"【候选瘦身】两集合皆非（{len(res['candidate'])} 个）← 连续 {w} 天零使用且不属副业链路")
    for k in res["candidate"]:
        print("   " + k)
    print()
    print("提示：候选瘦身仅为建议，动手前须过一遍「历史约定 / 他空间依赖 / 同族连带」三项检查。")


if __name__ == "__main__":
    main()
