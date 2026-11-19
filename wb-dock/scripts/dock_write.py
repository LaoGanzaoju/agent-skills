#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WB Dock 安全写入器 —— 给 AI 助手 / 终端用。

真相源：~/wb-dock/dock.json
（Windows 是 %USERPROFILE%\\wb-dock\\dock.json；本脚本两个环境变量都认）

────────────────────────────────────────────────────────────
为什么要有这个脚本，而不是让 AI 自己改 JSON
────────────────────────────────────────────────────────────
① **原子写**。先写同目录临时文件 → fsync → rename 覆盖。直接原地写会让面板
   读到半截 JSON —— 面板不会崩（watch.rs 会跳过解析失败的那次），但**这次更新
   就白写了**，面板不会刷新。
② **保留未知字段**。整个重写会把你、别的工具、或以后版本的 app 加的字段
   悄悄抹掉。本脚本是「读出来 → 只动目标那一条 → 写回去」，其余原样。
③ **只做允许的操作**。不碰 `settings`；不写 `ok` / `path` / `hotkey_active`
   —— 那三个是 app 只给界面看的视图字段，落盘就是污染。
④ **值与 app 同口径校验**。`status` 只能 todo/doing/done，`src` 只能 wb/human。
   和 write.rs 里的守卫一致，免得手滑写个 "Done" 进去，以后判断状态全乱。
⑤ **同名去重**。同集合里已有同名条目就拒绝，要强加得显式 `--force`。
   AI 重试/复跑很常见，这条挡的是「面板上冒出五条一模一样的待办」。

────────────────────────────────────────────────────────────
用法
────────────────────────────────────────────────────────────
  dock_write.py add task   --title "标题" [--note "备注"] [--src wb|human] [--status todo|doing|done]
  dock_write.py add rule   --title "标题" --body "内容"
  dock_write.py add prompt --title "标题" --body "内容"
  dock_write.py update task <id> [--title T] [--note N] [--src wb|human]
  dock_write.py status task <id> done
  dock_write.py list [task|rule|prompt]
  dock_write.py rm task <id>

（`--note` / `--body` / `--content` 三个写法等价，脚本按集合自动选对字段名。）

退出码：0 成功 / 2 用法或校验错误 / 3 文件状态异常（拒绝写入）
"""

import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime

KINDS = ("rules", "prompts", "tasks")
SINGULAR = {
    "task": "tasks", "tasks": "tasks",
    "rule": "rules", "rules": "rules",
    "prompt": "prompts", "prompts": "prompts",
}
# write.rs 的 content_field()：rules/prompts 叫 body，tasks 叫 note（PRD §6 定的，不改）
CONTENT_FIELD = {"rules": "body", "prompts": "body", "tasks": "note"}
ID_PREFIX = {"rules": "r", "prompts": "p", "tasks": "t"}
STATUSES = ("todo", "doing", "done")
SRCS = ("wb", "human")
# app 只给界面看、绝不落盘的字段（dock.rs::read_dock / write.rs::mutate 注入）
VIEW_ONLY = ("ok", "path", "hotkey_active", "error")


def die(msg, code=2):
    sys.stderr.write("ERROR: %s\n" % msg)
    sys.exit(code)


def home_dir():
    # dock.rs::home_dir() 同序：Windows 先 USERPROFILE，其余先 HOME
    return (os.environ.get("USERPROFILE") or os.environ.get("HOME") or ".").rstrip("/\\")


def dock_path():
    return os.path.join(home_dir(), "wb-dock", "dock.json")


def norm_kind(word):
    k = SINGULAR.get((word or "").strip().lower())
    if k is None:
        die("非法集合：%s（只能是 task / rule / prompt）" % word)
    return k


def stamp():
    """与 panel::stamp_iso() 同形：2026-09-13T22:20:11+08:00"""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def load(path):
    """读真相源。文件不存在 = 空对象（与 write.rs 闸门 2 的 NotFound => "" 一致）。"""
    if not os.path.exists(path):
        return {}, False
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    if not raw.strip():
        return {}, True
    try:
        root = json.loads(raw)
    except Exception as e:
        # dock.rs 的硬约束 3：JSON 坏了不修文件，只报错
        die("dock.json 当前不是合法 JSON，拒绝写入（文件未改动）：%s" % e, 3)
    if not isinstance(root, dict):
        die("dock.json 顶层不是对象，拒绝写入（文件未改动）", 3)
    return root, True


def arr_of(root, kind, create=False):
    arr = root.get(kind)
    if not isinstance(arr, list):
        if not create:
            die("dock.json 里没有 %s 数组（文件未改动）" % kind)
        arr = []
        root[kind] = arr
    return arr


def find_item(arr, iid):
    for it in arr:
        if isinstance(it, dict) and it.get("id") == iid:
            return it
    return None


def new_id(kind, used):
    base = "%s_%d" % (ID_PREFIX[kind], int(time.time() * 1000))
    cand, n = base, 0
    while cand in used:
        n += 1
        cand = "%s%02x" % (base, n)   # 同毫秒内重复就带后缀，撞不了
    return cand


def save(path, root):
    """.bak + 原子写 + 回读校验（对应 write.rs 的闸门 4、5）。"""
    for k in VIEW_ONLY:
        root.pop(k, None)   # 视图字段绝不落盘

    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)

    # 与 app 一致：serde_json::to_string_pretty 的等价写法（2 空格缩进、中文不转义）
    text = json.dumps(root, ensure_ascii=False, indent=2) + "\n"

    if os.path.exists(path):
        try:
            shutil.copy2(path, path + ".bak")
        except Exception as e:
            sys.stderr.write("WARN: 备份 .bak 失败（继续写）：%s\n" % e)

    tmp = os.path.join(d, ".dock.json.tmp.%d" % os.getpid())
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())          # 先落盘，rename 才是真原子
    os.replace(tmp, path)             # 同目录 rename：不会出现半个文件

    with open(path, "r", encoding="utf-8") as f:
        back = f.read()
    if back != text:
        die("写入后回读不一致！请立刻检查 %s" % path, 3)
    return text


def summarize(path, kind, item):
    print("OK %s" % path)
    print("   %s ← %s" % (kind, item.get("id")))
    print("   %s" % item.get("title"))


# ---------------- 子命令 ----------------

def cmd_add(args):
    kind = norm_kind(args.kind)
    path = dock_path()
    root, _ = load(path)
    arr = arr_of(root, kind, create=True)

    title = (args.title or "").strip()
    if not title:
        die("--title 不能为空")
    content = args.content if args.content is not None else ""

    if not args.force:
        dup = next((it for it in arr if isinstance(it, dict) and it.get("title") == title), None)
        if dup is not None:
            die("同集合里已有同名条目 id=%s。要再建一条加 --force；要改内容用 update。"
                % dup.get("id"))

    used = {it.get("id") for it in arr if isinstance(it, dict)}
    iid = new_id(kind, used)

    # 字段顺序与 write.rs::add_item 完全一致，盘上看起来就像 app 自己写的
    item = {"id": iid, "title": title, CONTENT_FIELD[kind]: content}
    if kind == "tasks":
        status = (args.status or "todo").strip().lower()
        if status not in STATUSES:
            die("非法状态：%s（只能是 %s）" % (args.status, "/".join(STATUSES)))
        src = (args.src or "wb").strip().lower()
        if src not in SRCS:
            die("非法来源：%s（只能是 %s）" % (args.src, "/".join(SRCS)))
        item["status"] = status
        item["src"] = src
        item["created"] = stamp()
        item["updated"] = ""
    else:
        item["pinned"] = False

    arr.append(item)
    save(path, root)
    summarize(path, kind, item)
    print("   status=%s src=%s  %s" % (item.get("status", "-"), item.get("src", "-"),
                                       ("共 %d 条" % len(arr))))


def cmd_update(args):
    kind = norm_kind(args.kind)
    path = dock_path()
    root, _ = load(path)
    arr = arr_of(root, kind)
    it = find_item(arr, args.id)
    if it is None:
        die("找不到条目 %s（可能已被外部删掉，先用 list 看当前的 id）" % args.id)

    if args.title is not None:
        t = args.title.strip()
        if not t:
            die("--title 不能为空")
        it["title"] = t
    if args.content is not None:
        it[CONTENT_FIELD[kind]] = args.content
    if kind == "tasks" and args.src is not None:
        src = args.src.strip().lower()
        if src not in SRCS:
            die("非法来源：%s（只能是 %s）" % (args.src, "/".join(SRCS)))
        it["src"] = src
    if kind == "tasks":
        it["updated"] = stamp()

    save(path, root)
    summarize(path, kind, it)


def cmd_status(args):
    if norm_kind(args.kind) != "tasks":
        die("只有任务有状态（规则 / 提示词没有）")
    status = args.value.strip().lower()
    if status not in STATUSES:
        die("非法状态：%s（只能是 %s）" % (args.value, "/".join(STATUSES)))

    path = dock_path()
    root, _ = load(path)
    it = find_item(arr_of(root, "tasks"), args.id)
    if it is None:
        die("找不到任务 %s" % args.id)

    it["status"] = status
    it["updated"] = stamp()
    save(path, root)
    print("OK %s" % path)
    print("   tasks ← %s  status=%s" % (args.id, status))
    print("   %s" % it.get("title"))


def cmd_list(args):
    path = dock_path()
    if not os.path.exists(path):
        print("（还没有 %s —— 文件不存在，等同于空）" % path)
        return
    root, _ = load(path)
    kinds = [norm_kind(args.kind)] if args.kind else list(KINDS)
    for kind in kinds:
        arr = root.get(kind)
        arr = arr if isinstance(arr, list) else []
        print("%s（%d 条）" % (kind, len(arr)))
        for it in arr:
            if not isinstance(it, dict):
                continue
            extra = ""
            if kind == "tasks":
                extra = " [%s/%s]" % (it.get("status", "?"), it.get("src", "?"))
            elif it.get("pinned"):
                extra = " [置顶]"
            print("   %-28s %s%s" % (it.get("id", "?"), it.get("title", "(无标题)"), extra))


def cmd_rm(args):
    kind = norm_kind(args.kind)
    path = dock_path()
    root, _ = load(path)
    arr = arr_of(root, kind)
    pos = next((i for i, it in enumerate(arr)
                if isinstance(it, dict) and it.get("id") == args.id), None)
    if pos is None:
        die("找不到条目 %s（可能已经被删了）" % args.id)
    gone = arr.pop(pos)
    save(path, root)
    print("OK %s" % path)
    print("   已删除 %s ← %s" % (kind, args.id))
    print("   %s" % gone.get("title"))


# ---------------- CLI ----------------

def build_parser():
    p = argparse.ArgumentParser(
        prog="dock_write.py",
        description="WB Dock 安全写入器（读改写 + 原子写 + 保留未知字段）",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="新增一条")
    a.add_argument("kind", help="task / rule / prompt")
    a.add_argument("--title", required=True)
    a.add_argument("--note", "--body", "--content", dest="content", default=None)
    a.add_argument("--src", default=None, help="仅任务：wb（AI 挂的）| human（我自己的）")
    a.add_argument("--status", default=None, help="仅任务：todo | doing | done")
    a.add_argument("--force", action="store_true", help="允许同名重复")
    a.set_defaults(func=cmd_add)

    u = sub.add_parser("update", help="改标题 / 内容")
    u.add_argument("kind")
    u.add_argument("id")
    u.add_argument("--title", default=None)
    u.add_argument("--note", "--body", "--content", dest="content", default=None)
    u.add_argument("--src", default=None)
    u.set_defaults(func=cmd_update)

    s = sub.add_parser("status", help="改任务状态")
    s.add_argument("kind")
    s.add_argument("id")
    s.add_argument("value")
    s.set_defaults(func=cmd_status)

    l = sub.add_parser("list", help="列出现有内容")
    l.add_argument("kind", nargs="?", default=None)
    l.set_defaults(func=cmd_list)

    r = sub.add_parser("rm", help="删除一条")
    r.add_argument("kind")
    r.add_argument("id")
    r.set_defaults(func=cmd_rm)

    return p


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
