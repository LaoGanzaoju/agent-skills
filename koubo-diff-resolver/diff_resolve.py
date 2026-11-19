#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
koubo-diff-resolver: 自动识别用户修改版与草稿原文的差异。

设计目标：用户把草稿复制到 Word 修改后，直接贴回聊天框，
agent 不需要用户说明"改了哪里"，自动对比原文输出结构化变更。

支持两种输入方式：
  方式A（文件）：diff_resolve.py <original_file> <modified_file>
  方式B（stdin）：把原文和改后版用单独一行的 ===== 分隔，通过 stdin 传入

输出：
  【删除】/【新增】/【修改】分段的结构化变更
  若无变更则输出「【无变更】原文与修改版一致」
"""

import sys
import difflib


def read_text(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        return f.read().splitlines()


def resolve(orig_lines: list, mod_lines: list) -> str:
    matcher = difflib.SequenceMatcher(None, orig_lines, mod_lines)
    changes = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        elif tag == "delete":
            block = "\n".join(orig_lines[i1:i2]).strip()
            if block:
                changes.append("【删除】\n" + block)
        elif tag == "insert":
            block = "\n".join(mod_lines[j1:j2]).strip()
            if block:
                changes.append("【新增】\n" + block)
        elif tag == "replace":
            old = "\n".join(orig_lines[i1:i2]).strip()
            new = "\n".join(mod_lines[j1:j2]).strip()
            if old and new:
                changes.append("【修改】\n原:\n" + old + "\n新:\n" + new)
            elif old and not new:
                changes.append("【删除】\n" + old)
            elif not old and new:
                changes.append("【新增】\n" + new)

    if not changes:
        return "【无变更】原文与修改版一致"
    return "\n\n".join(changes)


def main():
    if len(sys.argv) == 3:
        orig = read_text(sys.argv[1])
        mod = read_text(sys.argv[2])
    elif not sys.stdin.isatty():
        data = sys.stdin.read()
        sep = "====="
        if sep not in data:
            print("错误：stdin 模式需用单独一行的 ===== 分隔原文与改后版", file=sys.stderr)
            sys.exit(1)
        parts = data.split(sep, 1)
        orig = parts[0].strip().splitlines()
        mod = parts[1].strip().splitlines()
    else:
        print("用法：", file=sys.stderr)
        print("  文件模式: diff_resolve.py <original> <modified>", file=sys.stderr)
        print("  stdin模式: 原文\\n=====\\n改后版 | python3 diff_resolve.py", file=sys.stderr)
        sys.exit(1)

    print(resolve(orig, mod))


if __name__ == "__main__":
    main()
