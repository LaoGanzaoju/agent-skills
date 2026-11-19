#!/usr/bin/env python3
"""一次 mmap 遍历，对多个针各输出若干处「前后上下文」。

用途：一轮取证闭掉多个疑点，避免反复扫 asar（每次全扫都慢）。
用法: python3 asar_probe_multi.py <app.asar> <针1> <针2> ... [--win N] [--hits N]
"""
import sys
import mmap

args = sys.argv[1:]
asar = args[0]
rest = args[1:]
WIN, HITS = 1600, 2
if "--win" in rest:
    i = rest.index("--win")
    WIN = int(rest[i + 1])
    rest = rest[:i] + rest[i + 2:]
if "--hits" in rest:
    i = rest.index("--hits")
    HITS = int(rest[i + 1])
    rest = rest[:i] + rest[i + 2:]

with open(asar, "rb") as f:
    mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    for needle in rest:
        nb = needle.encode()
        idxs = []
        pos = 0
        while len(idxs) < HITS:
            j = mm.find(nb, pos)
            if j < 0:
                break
            idxs.append(j)
            pos = j + len(nb)
        print("=" * 78)
        print(f"### 针 [{needle}]  命中 {len(idxs)} 处（上限 {HITS}）")
        if not idxs:
            print("    ★ 零命中")
        for j in idxs:
            lo = max(0, j - WIN // 4)
            hi = min(mm.size(), j + WIN)
            seg = mm[lo:hi].decode("utf-8", "replace")
            print("-" * 78)
            print(seg)
    mm.close()
