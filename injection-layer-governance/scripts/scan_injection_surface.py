#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
注入层体检脚本（纯只读 · 跨平台 macOS / Windows）

口径（均为"字符数"，不用行数、不用字节）：
  项目级工作记忆  <cwd>/.workbuddy/memory/MEMORY.md      上限 8000  超限=截断+追加强指令
  用户级记忆      ~/.workbuddy/MEMORY.md                 上限 4000  超限=截断
  规则            用户级 ~/.workbuddy/rules/             上限 40000/件  超限=整条丢弃
                  项目级 <cwd>/.codebuddy/rules/
  身份三件套      ~/.workbuddy/{SOUL,IDENTITY,USER}.md   上限 10000/件
  项目说明        <cwd>/CODEBUDDY.md | .codebuddy/CODEBUDDY.md | AGENTS.md  上限 8000
  目录清单        <cwd> 根目录非隐藏条目数                上限 40 条

容器全集 = 平台会话数据库 workspaces 表 ∪ sessions 表 distinct 工作目录。
          绝不使用目录列举（如 ls ~/WorkBuddy/*/）猜容器 —— 那会产生假阳性。

动态验证（--session）：读该容器【起点最新】会话（projects/<slug>/<uuid>.jsonl）的**开场注入块**，
          与磁盘真源逐项对照，回答「我改过的东西，到底有没有被真的注入」。
          选会话按**起点**而不是 mtime —— 你在会话里跑脚本时，那个会话自己会赢 mtime 竞争。
          也可用 --session-file 点名某一场具体会话。
          边界（重要）：身份三件套 / 规则 / 项目说明 / 目录清单 / customPrompt **可证**；
          工作记忆与云 profile 不走这个块（走系统提示，不落盘）—— 此法证不了。
          注入块 = 开局快照，同一会话内不刷新 ⇒ 只能用「改动之后启动」的会话去验。

本脚本不写任何文件、不改动任何目标；复制数据库仅为只读副本。
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile

M_LIMIT = 8000
USER_M_LIMIT = 4000
RULE_LIMIT = 40000
IDENTITY_LIMIT = 10000
GUIDANCE_LIMIT = 8000
LAYOUT_LIMIT = 40

LEVELS = ("越线", "贴线", "偏高", "安全")


# ---------- 环境探测 ----------

def find_config_dir():
    """定位平台配置目录（含 rules/ 与身份三件套）。返回 (路径, 是否存在)。"""
    home = os.path.expanduser("~")
    cands = [
        os.path.join(home, ".workbuddy"),
        os.path.join(os.environ.get("APPDATA", ""), "WorkBuddy") if os.environ.get("APPDATA") else None,
        os.path.join(home, "Library", "Application Support", "WorkBuddy"),
    ]
    for c in cands:
        if c and os.path.isdir(c):
            return c, True
    return cands[0], False


def find_db(config_dir):
    """定位平台会话数据库。返回 (路径, 是否存在)。"""
    home = os.path.expanduser("~")
    cands = [
        os.path.join(config_dir, "workbuddy.db"),
        os.path.join(home, ".workbuddy", "workbuddy.db"),
        os.path.join(os.environ.get("APPDATA", ""), "WorkBuddy", "workbuddy.db") if os.environ.get("APPDATA") else None,
        os.path.join(home, "Library", "Application Support", "WorkBuddy", "workbuddy.db"),
    ]
    for c in cands:
        if c and os.path.isfile(c):
            return c, True
    return cands[0], False


# ---------- 量体 ----------

def chars(path):
    """字符数（等价 wc -m 的 Unicode 码点口径）。文件不存在返回 None。"""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return len(f.read())
    except OSError:
        return None


def level(n, limit):
    if n is None:
        return "空槽"
    if n > limit:
        return "越线"
    pct = n / limit
    if pct >= 0.95:
        return "贴线"
    if pct >= 0.80:
        return "偏高"
    return "安全"


def mark(level_name):
    return {"越线": "🔴", "贴线": "🟠", "偏高": "🟡"}.get(level_name, "  ")


def layout_count(cwd):
    try:
        return len([e for e in os.listdir(cwd) if not e.startswith(".")])
    except OSError:
        return -1


def list_rules(d):
    if not os.path.isdir(d):
        return []
    return sorted(
        f for f in os.listdir(d)
        if f.lower().endswith((".md", ".mdc")) and os.path.isfile(os.path.join(d, f))
    )


# ---------- 容器全集 ----------

def load_cwds(db_path):
    """从会话数据库取容器全集：workspaces ∪ sessions distinct cwd。"""
    tag = hashlib.md5(db_path.encode("utf-8")).hexdigest()[:8]
    tmp = os.path.join(tempfile.gettempdir(), "wb_probe_ro_%s.db" % tag)
    try:
        if (not os.path.exists(tmp)) or os.path.getmtime(db_path) > os.path.getmtime(tmp):
            shutil.copy2(db_path, tmp)
        con = sqlite3.connect("file:%s?mode=ro" % tmp.replace("\\", "/"), uri=True)
    except Exception as e:                                    # noqa: BLE001
        print("!! 无法读取数据库：%s" % e)
        print("!! 请确认 --db 指向平台会话数据库，或先用平台正常启动过一次。")
        return []
    cur = con.cursor()
    try:
        ws = [r[0] for r in cur.execute("SELECT path FROM workspaces").fetchall()]
    except sqlite3.Error:
        ws = []
    try:
        ss = [r[0] for r in cur.execute("SELECT DISTINCT cwd FROM sessions").fetchall()]
    except sqlite3.Error:
        ss = []
    con.close()
    seen, out = set(), []
    for p in ws + ss:
        if p and p not in seen:
            seen.add(p)
            out.append((p, "W" if p in ws else "", "S" if p in ss else ""))
    return out


# ---------- 报告 ----------

# ---------- 动态验证：开场注入块（只读） ----------

# 平台默认身份模板的特征串（命中即说明该会话开局时身份文件还是旧内容）
IDENTITY_OLD_PROBES = (
    "SOUL.md Template", "not a chatbot", "Agent identity record",
    "User profile record", "Bootstrapping a workspace",
)

SLOTS = (
    ("身份三件套", "<identity_context"),
    ("军规一 customPrompt", "<user_custom_instructions>"),
    ("军规二~八 rules", "<project_rules"),
    ("项目说明 guidance", "<project_guidance"),
    ("目录清单 layout", "<project_layout"),
    ("工作记忆 M", "<working_memory_content"),
)


def find_projects_dir(config_dir):
    p = os.path.join(config_dir, "projects")
    return p if os.path.isdir(p) else None


def slugify(cwd):
    """容器目录 → 会话记录目录名（路径分隔符换 -，去首部 -）。"""
    return cwd.replace("\\", "/").replace("/", "-").lstrip("-")


def session_start_ts(path):
    """读会话第一条记录的 timestamp（毫秒）→ datetime；失败返回 None。"""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            first = f.readline()
        t = json.loads(first).get("timestamp")
        return datetime.datetime.fromtimestamp(t / 1000) if t else None
    except Exception:                                             # noqa: BLE001
        return None


def find_session_file(projects_dir, cwd):
    """返回 (最近的会话 jsonl, 该容器的会话目录)；找不到返回 (None, None)。

    选法 = **会话起点**最新（mtime 只作同起点时的兜底）。
    为什么不按 mtime：**你就在某个会话里跑本脚本时，那个会话自己一直在被追加写入**，
    它永远赢 mtime 竞争 ⇒ 会拿到「你正坐着的这个旧会话」，而不是你想验的「新开会话」。
    起点时间不会因为后续写入而变，所以按起点选才是对的。
    要指定别的会话，用 --session-file。
    """
    d = os.path.join(projects_dir, slugify(cwd))
    if not os.path.isdir(d):
        base = os.path.basename(cwd.rstrip("/\\"))
        hits = [os.path.join(projects_dir, x) for x in sorted(os.listdir(projects_dir))
                if os.path.isdir(os.path.join(projects_dir, x)) and base and x.endswith(base)]
        d = hits[0] if len(hits) == 1 else None
    if not d:
        return None, None
    fs = [os.path.join(d, f) for f in os.listdir(d) if f.endswith(".jsonl")]
    if not fs:
        return None, None

    def key(p):
        st = session_start_ts(p)
        return (st or datetime.datetime.fromtimestamp(os.path.getmtime(p)),
                os.path.getmtime(p))

    fs.sort(key=key, reverse=True)
    return fs[0], d


def list_container_sessions(projects_dir, cwd, limit=8):
    """列出该容器最近几个会话：[(jsonl, 起点, 末次写入, 大小)]，按起点倒序。"""
    d = os.path.join(projects_dir, slugify(cwd))
    if not os.path.isdir(d):
        return []
    fs = [os.path.join(d, f) for f in os.listdir(d) if f.endswith(".jsonl")]
    out = []
    for p in fs:
        st = session_start_ts(p)
        out.append((p, st,
                    datetime.datetime.fromtimestamp(os.path.getmtime(p)),
                    os.path.getsize(p)))
    out.sort(key=lambda x: (x[1] or datetime.datetime.min), reverse=True)
    return out[:limit]


def read_injection_block(path, max_lines=5):
    """取开场注入块：前若干条记录中第一条含注入标记的。返回 (行号, 原文)。"""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            if i >= max_lines:
                break
            if ("<user_info>" in line or "<identity_context" in line
                    or "<user_custom_instructions>" in line):
                return i + 1, line
    return None, None


def probe_strings(text, n=3):
    """从文件取用于比对的独特短串：frontmatter title / 标题行 / 首句正文。"""
    out = []
    m = re.search(r'^title:\s*"?([^"\n]+)"?', text, re.M)
    if m and m.group(1).strip():
        out.append(m.group(1).strip())
    for m in re.finditer(r"^#{1,3}\s+(.+?)\s*$", text, re.M):
        t = m.group(1).strip().strip("_")
        if t and t not in out:
            out.append(t)
        if len(out) >= n:
            return out
    for ln in text.split("\n"):
        t = ln.strip()
        if t and t[0] not in "#->|`*_" and len(t) >= 8:
            out.append(t)
            break
    return out[:n]


def section_of(block, tag):
    m = re.search(r"<%s[^>]*>(.*?)</%s>" % (tag, tag), block, re.S)
    return m.group(1) if m else None


def _read(p):
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def report_session(config_dir, cwd, sfile=None):
    print("\n== 动态验证：某次会话的开场注入块 ==")
    print("  原理：注入块 = 会话开局快照，原文落盘在会话记录 jsonl 的开头几条记录里。")
    print("        本模式只读它，回答「改过的东西到底有没有被真的注入」。")

    projects = find_projects_dir(config_dir)
    if not projects:
        print("  !! 找不到 %s/projects —— 无法做动态验证（不猜测）。" % config_dir)
        return

    d = None
    if sfile:
        sfile = os.path.abspath(os.path.expanduser(sfile))
        if not os.path.isfile(sfile):
            print("  !! --session-file 指向的文件不存在：%s" % sfile)
            return
        d = os.path.dirname(sfile)
    else:
        sfile, d = find_session_file(projects, cwd)
        if not sfile:
            print("  !! 没找到该容器对应的会话记录（slug=%s）。" % slugify(cwd))
            return

    st = session_start_ts(sfile)
    mt = datetime.datetime.fromtimestamp(os.path.getmtime(sfile))
    print("  容器     : %s" % cwd)
    print("  会话记录 : %s" % sfile)
    print("  会话起点 : %s   <<★ 判「能不能验到你的改动」看这个"
          % (st.strftime("%m-%d %H:%M:%S") if st else "未知"))
    print("  末次写入 : %s" % mt.strftime("%m-%d %H:%M:%S"))

    # 该容器还有哪些会话可选（帮你在选错时一眼改口）
    sibs = [x for x in list_container_sessions(projects, cwd)
            if os.path.abspath(x[0]) != os.path.abspath(sfile)]
    if sibs:
        print("\n  同容器其它会话（起点倒序，供 --session-file 指定）：")
        for p, s, m, sz in sibs:
            print("    %s  %s→%s  %6.1fKB  %s"
                  % (os.path.basename(p)[:8],
                     s.strftime("%m-%d %H:%M") if s else "未知",
                     m.strftime("%m-%d %H:%M"), sz / 1024.0, ""))

    ln, block = read_injection_block(sfile)
    if block is None:
        print("  判定     : ⚪ 开头找不到注入块（可能是子代理 / 特殊会话）")
        return
    print("  注入块   : 第 %d 条记录，%d 字符" % (ln, len(block)))

    print("\n  槽位在场性：")
    for label, tag in SLOTS:
        print("    %-22s %s" % (label, "✅ 在场" if tag in block else "— 不在本块内"))

    stale = []          # 收集「看起来过期」的证据

    print("\n  ▸ 身份三件套：块内内容 vs 磁盘真源")
    seg = section_of(block, "identity_context")
    if seg is None:
        print("    ⚪ 本块未含身份段")
    else:
        for f in ("SOUL.md", "IDENTITY.md", "USER.md"):
            p = os.path.join(config_dir, f)
            if not os.path.isfile(p):
                print("    %-12s 磁盘不存在" % f)
                continue
            probes = probe_strings(_read(p))
            hit = [x for x in probes if x in seg]
            if hit:
                print("    %-12s 特征 %d/%d → ✅ 已注入磁盘当前内容" % (f, len(hit), len(probes)))
            else:
                print("    %-12s 特征 0/%d → ⚠️ 未命中（该会话开局时还是旧内容）" % (f, len(probes)))
                stale.append("身份 " + f)
        old = [x for x in IDENTITY_OLD_PROBES if x in seg]
        if old:
            print("    ⚠️  命中平台默认模板特征：%s" % "、".join(old))

    print("\n  ▸ 规则：磁盘上哪几件真的进了注入块")
    rseg = section_of(block, "project_rules")
    if rseg is None:
        print("    ⚪ 本块未含规则段")
    else:
        m = re.search(r'<project_rules[^>]*description="([^"]*)"', block)
        if m:
            print("    守卫说明 : %s" % m.group(1)[:112])
        files = list_rules(os.path.join(config_dir, "rules"))
        if not files:
            print("    磁盘 ~/.workbuddy/rules/ 为空或不存在")
        else:
            miss = [f for f in files
                    if not any(x in rseg for x in probe_strings(_read(os.path.join(config_dir, "rules", f))))]
            print("    磁盘 %d 件 → 块内命中 %d 件" % (len(files), len(files) - len(miss)))
            if miss:
                print("    ⚠️  未命中：%s" % "、".join(miss))
                stale.append("规则 %d 件" % len(miss))

    print("\n  ▸ 项目说明 guidance")
    g = section_of(block, "project_guidance")
    gp = None
    for cand in ("CODEBUDDY.md", os.path.join(".codebuddy", "CODEBUDDY.md"), "AGENTS.md"):
        p = os.path.join(cwd, cand)
        if os.path.isfile(p):
            gp = p
            break
    disk = os.path.relpath(gp, cwd) if gp else None
    if g is None:
        print("    — 本块未含 guidance 段（磁盘%s / 或会话起点早于创建）"
              % ("上无 CODEBUDDY.md·AGENTS.md" if not gp else "有 " + disk))
        if gp:
            stale.append("guidance")
    elif gp:
        probes = probe_strings(_read(gp))
        hit = [x for x in probes if x in g]
        print("    磁盘 %s → 特征 %d/%d %s" % (disk, len(hit), len(probes),
                                             "✅ 已注入" if hit else "⚠️ 未命中"))
        if not hit:
            stale.append("guidance")
    else:
        print("    ⚪ 块内有段、磁盘上却没有 —— 需核对")

    print("\n  ▸ 军规一 customPrompt")
    cp = None
    for cand in (os.path.join(config_dir, "app", "app-config.json"),
                 os.path.join(config_dir, "app-config.json")):
        if os.path.isfile(cand):
            try:
                cp = (json.loads(_read(cand)).get("personalization") or {}).get("customPrompt")
            except Exception:                                     # noqa: BLE001
                cp = None
            break
    cseg = section_of(block, "user_custom_instructions")
    if cseg is None:
        print("    ⚪ 本块未含 custom 段")
    else:
        body = cseg.strip()
        print("    块内 %d 字符" % len(body))
        if cp:
            key = cp.strip()[:18]
            ok = bool(key) and key in block
            print("    配置盘 %d 字符；特征串「%s」→ %s" % (len(cp), key, "✅ 命中" if ok else "⚠️ 未命中"))
            if not ok:
                stale.append("customPrompt")

    print("\n  判读：")
    print("    · 块内出现的槽 = 该会话开局时平台真的注入过。")
    print("    · 未出现 ≠ 没配 —— 先排除「该会话起点早于你的改动」。")
    print("    · 工作记忆 / 云 profile 不走本块 ⇒ 这两个的「是否真注入」此法证不了。")
    if stale:
        print("    · ⚠️ 本次命中可疑项：%s" % "、".join(stale))
        print("      ⇒ 用**改动之后新开**的会话再跑一次本模式；仍不过才动机制层。")
    else:
        print("    · ✅ 未发现过期项。")


def report_global(config_dir, only):
    home = os.path.expanduser("~")
    print("\n== 用户级槽位 ==")
    hdr = "%-42s %8s %8s  %s" % ("对象", "字符", "上限", "判定")
    print(hdr)
    print("-" * 76)

    def row(label, n, limit):
        lv = level(n, limit)
        print("%-42s %8s %8d  %s %s" % (label, "—" if n is None else n, limit, mark(lv), lv))

    if only in (None, "user"):
        row("用户记忆 MEMORY.md", chars(os.path.join(config_dir, "MEMORY.md")), USER_M_LIMIT)
        for f in ("SOUL.md", "IDENTITY.md", "USER.md"):
            p = os.path.join(config_dir, f)
            if os.path.isfile(p):
                row("身份 " + f, chars(p), IDENTITY_LIMIT)
    if only in (None, "rules"):
        ur = list_rules(os.path.join(config_dir, "rules"))
        if ur:
            for f in ur:
                row("用户级规则 " + f, chars(os.path.join(config_dir, "rules", f)), RULE_LIMIT)
        else:
            print("%-42s" % "用户级规则 (目录为空或不存在)", "")

    # 用户级记忆的外移件（同级 memory_external 等）只报数，不判定
    ext = [d for d in os.listdir(config_dir)
           if os.path.isdir(os.path.join(config_dir, d)) and d.endswith("_external")]
    for d in ext:
        n = len([f for f in os.listdir(os.path.join(config_dir, d)) if os.path.isfile(os.path.join(config_dir, d, f))])
        print("%-42s %8s" % ("外移目录 " + d + "/ （文件数）", n))
    _ = home


def report_workspaces(rows, only):
    print("\n== 各容器 ==")
    hdr = "%-34s %8s %7s %-5s %8s %7s %-5s %6s %-5s" % (
        "容器", "工作记忆", "余量", "判定", "项目说明", "余量", "判定", "目录条", "判定")
    print(hdr)
    print("-" * 108)

    def col(n, limit):
        lv = level(n, limit)
        rest = "—" if n is None else str(limit - n)
        return n, rest, lv

    alerts = []
    for cwd, in_ws, in_ss in rows:
        name = os.path.basename(cwd.rstrip("/\\")) or cwd
        if not os.path.isdir(cwd):
            print("%-34s   目录不存在" % name[:34])
            continue

        m = c = None
        if only in (None, "workspaces", "user"):
            m = col(chars(os.path.join(cwd, ".workbuddy", "memory", "MEMORY.md")), M_LIMIT)
        gd = None
        if only in (None, "workspaces", "guidance"):
            gp = None
            for cand in ("CODEBUDDY.md", os.path.join(".codebuddy", "CODEBUDDY.md"), "AGENTS.md"):
                p = os.path.join(cwd, cand)
                if os.path.isfile(p):
                    gp = p
                    break
            gd = col(chars(gp), GUIDANCE_LIMIT) if gp else (None, "—", "空槽")

        lay = None
        if only in (None, "workspaces", "layout"):
            n = layout_count(cwd)
            lv = "越线" if n > LAYOUT_LIMIT else "安全"
            lay = (n, str(LAYOUT_LIMIT - n) if n >= 0 else "—", lv)

        def fmt(t, limit):
            if t is None:
                return "%8s %7s %-5s" % ("·", "·", "")
            n, rest, lv = t
            return "%8s %7s %-5s" % ("—" if n is None else n, rest, "%s%s" % (mark(lv), lv))

        print("%-34s %s %s %s" % (name[:34], fmt(m, M_LIMIT), fmt(gd, GUIDANCE_LIMIT), fmt(lay, LAYOUT_LIMIT)))

        for tag, t, limit in (("工作记忆", m, M_LIMIT), ("项目说明", gd, GUIDANCE_LIMIT), ("目录清单", lay, LAYOUT_LIMIT)):
            if t and t[2] in ("越线", "贴线"):
                alerts.append("%s · %s %s（%s/%s）" % (name, tag, t[2], t[0], limit))

    if only in (None, "rules", "identity"):
        print("\n  规则 / 身份（按容器）：")
        any_row = False
        for cwd, _w, _s in rows:
            if not os.path.isdir(cwd):
                continue
            items = []
            if only in (None, "rules"):
                for f in list_rules(os.path.join(cwd, ".codebuddy", "rules")):
                    p = os.path.join(cwd, ".codebuddy", "rules", f)
                    n = chars(p)
                    items.append("规则 %s %s/%s %s" % (f, n, RULE_LIMIT, level(n, RULE_LIMIT)))
            if items:
                any_row = True
                print("    %-32s %s" % (os.path.basename(cwd.rstrip("/\\"))[:32], " | ".join(items)))
        if not any_row and only in (None, "rules"):
            print("    （无项目级规则目录）")

    print("\n== 待办（仅 🔴越线 / 🟠贴线）==")
    if alerts:
        for a in alerts:
            print("  • " + a)
    else:
        print("  无 —— 全部对象在上限内。")


def main():
    ap = argparse.ArgumentParser(description="注入层体检（只读）")
    ap.add_argument("--root", default=None, help="容器根目录（仅用于显示，不用于枚举容器）")
    ap.add_argument("--db", default=None, help="手工指定会话数据库路径")
    ap.add_argument("--only", default=None,
                    choices=["workspaces", "user", "rules", "identity", "layout", "guidance"],
                    help="只看某一层")
    ap.add_argument("--session", action="store_true",
                    help="动态验证：读一次会话的开场注入块（只读；不需要数据库）")
    ap.add_argument("--cwd", default=None, help="动态验证用：容器目录（默认当前目录）")
    ap.add_argument("--session-file", default=None,
                    help="动态验证用：直接指定会话 jsonl（避开「当前会话赢 mtime 竞争」的坑）")
    a = ap.parse_args()

    print("== 环境 ==")
    cfg, cfg_ok = find_config_dir()
    print("  配置目录 : %s%s" % (cfg, "" if cfg_ok else "   << 不存在，请核对"))
    if a.db:
        db, db_ok = a.db, os.path.isfile(a.db)
    else:
        db, db_ok = find_db(cfg)
    print("  数据库   : %s%s" % (db, "" if db_ok else "   << 不存在，请用 --db 指定"))
    if a.root:
        print("  容器根   : %s（仅显示用；容器全集始终来自数据库）" % a.root)
    print("  口径     : 字符数（wc -m 等价）；行数/字节口径无效")

    if a.session or a.session_file:
        if a.session_file and not a.session:
            a.session = True
        report_session(cfg, a.cwd or os.getcwd(), a.session_file)
        return 0

    if not db_ok:
        print("\n!! 找不到会话数据库，无法取容器全集 —— 已停止（不做任何猜测式枚举）。")
        return 2

    rows = load_cwds(db)
    print("  容器全集 : %d 个（workspaces ∪ sessions distinct cwd）" % len(rows))

    if a.only != "workspaces":
        report_global(cfg, a.only)
    report_workspaces(rows, a.only)

    print("\n提示：治理前先备份；验收要带负控制（造假越线对象 → 脚本必须报红）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
