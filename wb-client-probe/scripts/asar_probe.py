#!/usr/bin/env python3
"""asar_probe.py — WorkBuddy 客户端 app.asar 机制取证工具（纯标准库）。

不解析 asar header（实测该 asar 头部非标准 Pickle 布局），直接按行流式全文搜字节串。

用法:
  python3 asar_probe.py <asar> lines <needle> [needle2 ...] [--cap N]
      打印含各 needle 的行（多针一次扫描，只读一遍文件）。默认每针最多 8 行。

  python3 asar_probe.py <asar> ctx <needle> [window_bytes] [--max-hits N]
      打印 needle 命中点前后各 window 字节的上下文（读源码原文用）。默认 window=900。
      注意：只报前 --max-hits 个命中点（默认 1）。

  python3 asar_probe.py <asar> range <start_line> <end_line> [--maxlen N]
      按行号区间读内嵌源码（读完某个 class / section 的实现用）。默认 maxlen=300。

  python3 asar_probe.py <asar> enum-max
      穷举所有 `var|const|let MAX_* = <数字>` 常量声明（★ 标记疑似注入相关）。
      **断言"某上限不存在"前的必备步骤** —— 见下文"纪律"第 4 条。

示例:
  A="/Applications/WorkBuddy.app/Contents/Resources/app.asar"
  python3 asar_probe.py "$A" lines MAX_MEMORY_CHARS MAX_USER_MEMORY_CHARS
  python3 asar_probe.py "$A" ctx "user-memory-collector.ts" 2500
  python3 asar_probe.py "$A" lines "mode/collectors/" --cap 60
  python3 asar_probe.py "$A" range 2146400 2146600        # 读 IdentityCollector
  python3 asar_probe.py "$A" enum-max                     # 穷举全部 MAX_* 常量

纪律:
  - 断言"零命中"前，必须先用一个已知存在的针做正对照（如 working_memory_content）。
  - 中文检索不要用本机 Bash grep（假阴性），用本工具或专用检索工具。
  - 多针要写成**多个独立参数**（`lines A B C`）；写成 `A|B` 会被当字面量 → 假零命中。
  - 断言"某上限不存在"前，先跑 `enum-max` 做**声明形式穷举**（var/const/let 全扫），
    不要只猜几个常量名。只猜名字 = 把"我没搜到"当成"不存在"（已犯过，见 SKILL.md 坑 5）。
"""
import sys


def parse(argv):
    if len(argv) < 3:
        print(__doc__)
        sys.exit(1)
    asar, mode = argv[1], argv[2]
    rest, opts = [], {}
    i = 3
    while i < len(argv):
        if argv[i] == "--cap":
            opts["cap"] = int(argv[i + 1]); i += 2
        elif argv[i] == "--max-hits":
            opts["max_hits"] = int(argv[i + 1]); i += 2
        else:
            rest.append(argv[i]); i += 1
    return asar, mode, rest, opts


def mode_lines(asar, needles, opts):
    cap = opts.get("cap", 8)
    found = {n: [] for n in needles}
    enc = {n: n.encode() for n in needles}
    with open(asar, "rb") as f:
        for lineno, line in enumerate(f, 1):
            for n in needles:
                if len(found[n]) >= cap:
                    continue
                if enc[n] in line:
                    s = line.decode("utf-8", "replace").strip()
                    j = s.find(n)
                    if j > 110:
                        s = "…" + s[j - 110: j + 150]
                    elif len(s) > 260:
                        s = s[:260] + "…"
                    found[n].append(f"  L{lineno}: {s}")
    for n in needles:
        exact = len(found[n]) < cap
        print(f"### '{n}' — 命中 {len(found[n])}{'' if exact else '+'} {'（零命中）' if not found[n] else ''}")
        for h in found[n]:
            print(h)
        print()


def mode_ctx(asar, needles, opts):
    needle = needles[0]
    win = int(needles[1]) if len(needles) > 1 and needles[1].isdigit() else 900
    max_hits = opts.get("max_hits", 1)
    nb = needle.encode()
    hits = 0
    with open(asar, "rb") as f:
        data = f.read()
    start = 0
    while True:
        i = data.find(nb, start)
        if i < 0:
            break
        lo, hi = max(0, i - win), min(len(data), i + win)
        print("=" * 74)
        print(f"命中 #{hits + 1}  绝对偏移≈{i}")
        print("-" * 74)
        print(data[lo:hi].decode("utf-8", "replace"))
        hits += 1
        start = i + 1
        if hits >= max_hits:
            break
    print(f"[总命中(截至上限): {hits}]")


def mode_range(asar, rest, opts):
    """按行号区间读内嵌源码（读某个 class/section 的实现用）。"""
    a, b = int(rest[0]), int(rest[1])
    maxlen = opts.get("maxlen", 300)
    with open(asar, "rb") as f:
        for i, line in enumerate(f, 1):
            if i < a:
                continue
            if i > b:
                break
            s = line.decode("utf-8", "replace").rstrip("\n")
            if len(s) > maxlen:
                s = s[:maxlen] + f" …[+{len(s)-maxlen}]"
            print(f"{i:>9}| {s}")


# 注入相关关键词：命中即在输出里打星标，防止漏看
_INJECT_HINT = ("CHARS", "MEMORY", "IDENTITY", "GUIDANCE", "RULE", "CUSTOM", "LAYOUT", "PROMPT")


def mode_enum_max(asar, opts):
    """穷举 `MAX_*` 常量声明 —— 两种声明形式都要扫。

    用途：断言"某上限不存在"之前的**必备步骤**。只猜几个常量名去搜 → 极易
    把"我没搜到"误判成"不存在"（本工具作者 2026-09-18 就因此错报 identity
    无上限，真名是 MAX_IDENTITY_FILE_CHARS）。

    必须覆盖的两种形态（踩过坑）：
      A. 声明式：`var|const|let MAX_X = 1500`
      B. **类字段式**：`\tMAX_X = 1500;`（无 var/const 前缀，如 bundler 内联的 class 字段）
         —— 只写 A 会漏掉 `MAX_CUSTOM_PROMPT_LENGTH = 1500`。
    """
    import re

    decl = re.compile(rb"\b(var|const|let)\s+(MAX_[A-Za-z0-9_]+)\s*=\s*([0-9eExX.*]+)")
    field = re.compile(rb"^[ \t]+(MAX_[A-Za-z0-9_]+)\s*=\s*([0-9eExX.*]+)\s*;?\s*$", re.M)
    seen = {}
    with open(asar, "rb") as f:
        data = f.read()
    for m in decl.finditer(data):
        seen.setdefault(m.group(2).decode(), {})["声明式"] = m.group(3).decode()
    for m in field.finditer(data):
        seen.setdefault(m.group(1).decode(), {}).setdefault("类字段式", m.group(2).decode())
    for name in sorted(seen):
        forms = " / ".join(f"{k}={v}" for k, v in sorted(seen[name].items()))
        star = "  ★注入相关" if any(k in name.upper() for k in _INJECT_HINT) else ""
        print(f"  {name:<48} = {forms}{star}")
    print(f"\n[共 {len(seen)} 个 MAX_* 常量；★ 为可能影响注入预算者，需逐个看上下文]")


def main():
    asar, mode, rest, opts = parse(sys.argv)
    if not rest and mode != "enum-max":
        print(__doc__)
        sys.exit(1)
    if mode == "lines":
        mode_lines(asar, rest, opts)
    elif mode == "ctx":
        mode_ctx(asar, rest, opts)
    elif mode == "range":
        mode_range(asar, rest, opts)
    elif mode == "enum-max":
        mode_enum_max(asar, opts)
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
