#!/usr/bin/env python3
"""注入件一致性检查（只读 · 红项非零退出）

管的事：**同一容器里多份每轮注入的文件**（工作记忆 MEMORY.md / 项目说明 CODEBUDDY.md …）
对同一件事不许各说各话，也不许同一段东西抄两份。

为什么需要它：`injection-layer-governance` skill 的红线 3「同源文档不留双份」早写了，
但它只是一句话、没有触发点 ⇒ 直到两份注入件对同一事实说出**互相矛盾**的版本才被发现。
本脚本把那条红线变成能红能绿的机检。

三类判据（只用全等/存在性判定，不引相似度阈值）：
  P1 不冲突 · forbid 串在**任何**注入件里零命中（过时/错误表述不许复活）
  P2 不丢   · must  串在**至少一个**注入件里命中（别两边都删干净）
  P3 不重   · dup   串在注入件里**命中文件数 ≤ 1**（同一块内容不许抄两份）

用法：
    python3 check_parity.py --facts <facts.json> [--root <容器根>] [--neg]

facts.json 格式：
{
  "files":  {"工作记忆": ".workbuddy/memory/MEMORY.md", "项目说明": ".codebuddy/CODEBUDDY.md"},
  "facts":  [
    {"name": "转写·视频腿引擎", "must": ["--engine volcano"], "forbid": ["faster-whisper"]},
    {"name": "SOP 地图表", "dup": ["| **汇点** | ④ 素材底座"]}
  ]
}
每项至少给 must / forbid / dup 之一。
"""
import argparse
import json
import sys
from pathlib import Path


def load(root: Path, spec: dict):
    files = {}
    for label, rel in spec.get("files", {}).items():
        p = root / rel
        files[label] = p.read_text(encoding="utf-8") if p.exists() else None
    return files


def check(files: dict, facts: list):
    """返回 [(编号, 通过?, 红项细节)]"""
    out = []
    for f in facts:
        name = f.get("name", "?")
        must = f.get("must") or []
        forbid = f.get("forbid") or []
        dup = f.get("dup") or []

        # P1 不冲突
        if forbid:
            hits = [(lb, s) for lb, txt in files.items() if txt
                    for s in forbid if s in txt]
            out.append((f"P1 不冲突 · {name}", not hits,
                        f"过时/错误表述仍在这些注入件里：{hits}" if hits else ""))
        # P2 不丢
        if must:
            got = [lb for lb, txt in files.items() if txt and any(s in txt for s in must)]
            out.append((f"P2 不丢 · {name}", bool(got),
                        "" if got else f"{must} 在所有注入件里都找不到（可能被两边一起删了）"))
        # P3 不重
        if dup:
            owners = [lb for lb, txt in files.items() if txt and any(s in txt for s in dup)]
            out.append((f"P3 不重 · {name}", len(owners) <= 1,
                        f"同一块内容出现在 {len(owners)} 份注入件里：{owners}" if len(owners) > 1 else ""))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--facts", required=True, help="事实表 JSON 路径")
    ap.add_argument("--root", default=".", help="容器根目录（facts.files 的相对基准）")
    ap.add_argument("--neg", action="store_true", help="负控制：注入 1 处破损，须见红")
    a = ap.parse_args()

    spec = json.loads(Path(a.facts).read_text(encoding="utf-8"))
    files = load(Path(a.root).resolve(), spec)
    missing = [lb for lb, t in files.items() if t is None]
    if missing:
        print(f"❗ 注入件读不到（路径错了？）：{missing}")
        return 1

    facts = spec.get("facts", [])

    if a.neg:
        # 负控制：塞一条必然命中的 forbid（取第一份文件里确实存在的 20 字）
        probe = next(t for t in files.values() if t)[:20]
        facts = facts + [{"name": "负控制探针", "forbid": [probe]}]
        res = check(files, facts)
        flipped = [v for v, ok, _ in res if not ok and "负控制探针" in v]
        print("═══ 负控制（注入 1 处必然命中的 forbid 探针）═══")
        for v, ok, d in res:
            if "负控制探针" in v:
                print(f"  {'✅ 由绿转红' if not ok else '❌ 仍然绿'}：{v}  {d}")
        if flipped:
            print("\n负控制生效 ⇒ 检查器能红，非恒绿")
            return 0
        print("\n❌ 负控制失效：探针没被检出 ⇒ 断言恒真，不算证据")
        return 1

    res = check(files, facts)
    print("═══ 注入件一致性检查 ═══")
    for v, ok, d in res:
        print(f"  {'✅' if ok else '❗'} {v}" + (f"\n       ← {d}" if not ok and d else ""))
    red = [v for v, ok, _ in res if not ok]
    print()
    if red:
        print(f"RESULT: FAIL —— {len(red)}/{len(res)} 条红：{' / '.join(red)}")
        return 1
    print(f"RESULT: GREEN ({len(res)}/{len(res)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
