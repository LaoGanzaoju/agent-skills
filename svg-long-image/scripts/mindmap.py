#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mindmap.py — 缩进大纲 / markdown → 手绘风脑图 PNG

链路：大纲 → 树布局 → SVG（拟手绘渲染）→ 包 HTML → Chrome headless 截图 → PNG
依赖：仅 Python 标准库 + 本机 Chrome（与 svg-long-image/render.py 同链路，零第三方依赖）

拟手绘原理（对应 rough.js 的做法，此处用纯 Python 实现）：
  把每条几何路径拆成采样点 → 每个点施加高斯随机偏移 → 用 Catmull-Rom 转贝塞尔平滑连接。
  盒子/胶囊 = 沿轮廓采样后扰动再平滑；分支 = 锥形笔触填充路径（根部粗、末端细）。

用法：
  python3 mindmap.py outline.md --out map.png --layout vtree     # 上下树（portrait 默认）
  python3 mindmap.py outline.md --out map.png --layout htree     # 向右逻辑树
  python3 mindmap.py outline.md --out map.png --layout mtree     # 左右双侧脑图
  python3 mindmap.py outline.md --out map.png --layout radial    # 径向脑图
  python3 mindmap.py - --out map.png --style ink                 # 从 stdin 读，国风墨色

大纲格式（缩进用 2 空格或 Tab；也支持 markdown 的 # 与 - 列表）：
  # 中心主题
  - 分支一
    - 子项
    - 子项
  - 分支二
"""

import argparse
import math
import os
import random
import re
import subprocess
import sys
import tempfile
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
RENDER_PY = os.path.join(HERE, "render.py")

# ---------------------------------------------------------------- 字体
FONT_HAND = "/Library/Fonts/叶根友优典手写.ttf"     # 手写标题 / 一级分支
FONT_HAND_ALT = "/Library/Fonts/叶根友钢笔行书2.0.ttf"
FONT_BODY = "PingFang SC"                            # 正文（系统字体，直接按名引用）


def _font_url(path):
    return "file://" + urllib.parse.quote(path)


# ---------------------------------------------------------------- 风格预设
STYLES = {
    # 纸感手写：暖纸底 + 墨色字 + 琥珀主色
    "handdrawn": dict(
        paper="#FBF8F1", ink="#332E28", sub="#7A7166", line="#E0D9C8",
        pal=["#D9694A", "#E8A33D", "#4E9184", "#5B7FBF", "#9B6BB5", "#6E9A52"],
        pill_fill="#FFFFFF", pill_line_w=2.2, roughness=1.5, grain=0.050,
        shadow=True, rx=18,
    ),
    # 国风墨色：宣纸米底 + 墨字 + 朱砂点睛
    "ink": dict(
        paper="#F7F3E8", ink="#2B2721", sub="#6E675C", line="#DCD3BE",
        pal=["#A8382C", "#3F4A52", "#6B7A5A", "#8A6A3E", "#4A5A6B", "#7A4A3A"],
        pill_fill="#FEFCF6", pill_line_w=2.0, roughness=1.8, grain=0.065,
        shadow=False, rx=6,
    ),
    # 漫画粗描边：白底 + 黑粗框 + 高饱和
    "comic": dict(
        paper="#FFFFFF", ink="#111111", sub="#555555", line="#111111",
        pal=["#E23B2E", "#F0A500", "#1E88C7", "#2FA36B", "#8E44AD", "#E0623B"],
        pill_fill="#FFFFFF", pill_line_w=4.0, roughness=1.1, grain=0.0,
        shadow=True, rx=4,
    ),
    # 现代圆润：冷白 + 蓝主色 + 大圆角，无手绘抖动放大
    "clean": dict(
        paper="#F7F9FC", ink="#16233A", sub="#5A6B85", line="#D8E2F2",
        pal=["#2B6CF6", "#12A594", "#E8772E", "#8B5CF6", "#E24A6F", "#0EA5E9"],
        pill_fill="#FFFFFF", pill_line_w=2.0, roughness=0.5, grain=0.0,
        shadow=True, rx=26,
    ),
}

# 字号（虚拟坐标，最终由 auto-fit 统一缩放）
FS_ROOT, FS_L1, FS_L2, FS_L3 = 46, 30, 23, 19
PAD_X, PAD_Y = 18, 11
SIB_GAP_X, SIB_GAP_Y = 26, 15      # vtree 用 GAP_X / htree 用 GAP_Y
LEVEL_GAP = 96                      # vtree 相邻层级纵向间距（可自适应拉大填满画布）
LEVEL_GAP_H = 46                    # htree / rtree 相邻层级横向间距（宽度是左右布局的命门）
RING_GAP = 210                      # radial 每层半径增量


# ---------------------------------------------------------------- 大纲解析
class Node:
    __slots__ = ("text", "children", "depth", "x", "y", "w", "h",
                 "color", "side", "angle", "r", "span", "_lines")

    def __init__(self, text, depth):
        self.text = text
        self.depth = depth
        self.children = []
        self.x = self.y = 0.0
        self.w = self.h = 0.0
        self.color = None
        self.side = 0        # htree: +1 右 / -1 左
        self.angle = 0.0
        self.r = 0.0
        self.span = 0.0


def clean_text(s):
    s = s.strip()
    s = re.sub(r"^[-*+]\s+", "", s)                       # 列表符号
    s = re.sub(r"^\d+[.、)]\s*", "", s)                    # 有序列表
    s = re.sub(r"^#{1,6}\s*", "", s)                       # 井号
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)        # 链接
    s = s.replace("**", "").replace("`", "")
    s = re.sub(r"^[""'']|[""'']$", "", s)
    return s.strip()


# ---------------------------------------------------------------- XMind 直读
def _xmind_title(s):
    if isinstance(s, dict):
        s = s.get("content", "")
    s = re.sub(r"<[^>]+>", "", s or "")
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">")):
        s = s.replace(a, b)
    return " ".join(s.split())


def _walk_json(t, depth, out):
    title = _xmind_title(t.get("title"))
    if title:
        out.append("  " * depth + ("# " + title if depth == 0 else "- " + title))
    for c in ((t.get("children") or {}).get("attached") or []):
        _walk_json(c, depth + 1, out)


def _walk_xml(t, depth, out):
    ti = t.find("title")
    title = _xmind_title(ti.text if ti is not None else "")
    if title:
        out.append("  " * depth + ("# " + title if depth == 0 else "- " + title))
    for topic in t.findall("./children/topics/topic"):
        _walk_xml(topic, depth + 1, out)


def xmind_to_outline(path):
    """XMind 文件 → 缩进大纲文本。兼容 Zen/2020+（content.json）与 XMind 8（content.xml）。"""
    import zipfile
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if "content.json" in names:
            import json as _json
            data = _json.loads(z.read("content.json").decode("utf-8", "ignore"))
            sheets = data if isinstance(data, list) else [data]
            out = []
            for k, sheet in enumerate(sheets):
                if len(sheets) > 1:
                    st = _xmind_title(sheet.get("title"))
                    if st:
                        out.append("  # " + st)      # 多画布时最外层补一层
                _walk_json(sheet.get("rootTopic") or {}, 1 if len(sheets) > 1 else 0, out)
            if out:
                return "\n".join(out)
        if "content.xml" in names:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(z.read("content.xml"))
            out = []
            for sheet in root.findall(".//sheet"):
                topic = sheet.find("topic")
                if topic is not None:
                    _walk_xml(topic, 0, out)
            if out:
                return "\n".join(out)
    raise ValueError("无法识别的 .xmind 结构（无 content.json / content.xml）：%s" % path)


def parse_outline(text):
    """缩进 / markdown 大纲 → 树。返回根节点。

    统一「rank」判据（解决 # 标题与缩进列表混用）：
      - `#`~`######` 行：rank = 井号个数
      - 缩进行：rank = 最近一个标题的 rank + 1 + 缩进/1000
    同级 rank 相等 → 互为兄弟；更大 → 成为子节点。
    """
    lines = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        if re.match(r"^\s*(-{3,}|={3,})\s*$", raw):
            continue
        if raw.lstrip().startswith("|"):        # 表格行跳过
            continue
        lines.append(raw)
    if not lines:
        raise ValueError("大纲为空：没有解析到任何节点")

    def indent_of(s):
        pre = s[:len(s) - len(s.lstrip(" \t"))]
        return pre.count(" ") + pre.count("\t") * 4

    HASH = re.compile(r"^\s*(#{1,6})\s+(.*\S)\s*$")

    root = None
    body = lines
    if HASH.match(lines[0]):
        m = HASH.match(lines[0])
        root = Node(clean_text(m.group(2)), 0)
        root_rank = float(len(m.group(1)))
        body = lines[1:]
    else:
        root_rank = 0.0

    entries = []                                 # (rank, label)
    cur_hash = root_rank
    for s in body:
        hm = HASH.match(s)
        if hm:
            cur_hash = float(len(hm.group(1)))
            entries.append((cur_hash, clean_text(hm.group(2))))
        else:
            lab = clean_text(s)
            if lab:
                entries.append((cur_hash + 1.0 + indent_of(s) / 1000.0, lab))

    if root is None:
        if not entries:
            raise ValueError("大纲为空：没有解析到任何节点")
        root = Node(entries[0][1], 0)
        root_rank = 0.0
        entries = entries[1:]

    stack = [(root_rank, root)]
    for rank, lab in entries:
        node = Node(lab, 0)
        while stack and stack[-1][0] >= rank:
            stack.pop()
        parent = stack[-1][1] if stack else root
        parent.children.append(node)
        stack.append((rank, node))

    _reindex(root, 0)
    return root


def _reindex(node, d):
    node.depth = d
    for c in node.children:
        _reindex(c, d + 1)


def count_leaves(n):
    if not n.children:
        return 1
    return sum(count_leaves(c) for c in n.children)


def max_depth(n):
    return n.depth if not n.children else max(max_depth(c) for c in n.children)


# ---------------------------------------------------------------- 文本度量
def text_w(s, fs):
    """按全角/半角粗估文本宽度（CJK 计 1.0，其余计 0.55）。"""
    w = 0.0
    for ch in s:
        w += fs * (1.0 if ord(ch) > 0x2E7F else 0.55)
    return w


def wrap_text(s, fs, max_w):
    """超宽文本折行（按字符切，中文友好）。"""
    if text_w(s, fs) <= max_w:
        return [s]
    lines, cur = [], ""
    for ch in s:
        if text_w(cur + ch, fs) > max_w and cur:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines[:3]


def measure(node, base_max_w):
    fs = font_size(node.depth)
    mw = base_max_w * (1.7 if node.depth == 0 else 1.3 if node.depth == 1 else 1.0)
    lines = wrap_text(node.text, fs, mw)
    node._lines = lines
    node.w = max(text_w(l, fs) for l in lines) + 2 * PAD_X
    node.h = len(lines) * fs * 1.42 + 2 * PAD_Y
    for c in node.children:
        measure(c, base_max_w)


def font_size(d):
    return FS_ROOT if d == 0 else FS_L1 if d == 1 else FS_L2 if d == 2 else FS_L3


# ---------------------------------------------------------------- 布局：vtree（上下树）
def layout_vtree(root, gap=None):
    """上下树：根在顶，子节点横向铺开、纵向按层递进。返回自然高度。"""
    gap = LEVEL_GAP if gap is None else gap
    level_h = {}

    def collect(n):
        level_h[n.depth] = max(level_h.get(n.depth, 0), n.h)
        for c in n.children:
            collect(c)
    collect(root)

    y_of_depth, acc = {}, 0.0
    for d in sorted(level_h):
        y_of_depth[d] = acc
        acc += level_h[d] + gap

    def span(n):
        if not n.children:
            n.span = n.w
        else:
            cw = sum(span(c) for c in n.children) + SIB_GAP_X * (len(n.children) - 1)
            n.span = max(n.w, cw)
        return n.span
    span(root)

    def assign(n, left):
        cx = left + n.span / 2
        n.x, n.y = cx, y_of_depth[n.depth]
        total = sum(c.span for c in n.children) + SIB_GAP_X * max(0, len(n.children) - 1)
        cur = cx - total / 2
        for c in n.children:
            assign(c, cur)
            cur += c.span + SIB_GAP_X
    assign(root, 0.0)

    last = max(y_of_depth)
    return y_of_depth[last] + level_h[last]


# ---------------------------------------------------------------- 布局：htree / mtree（左→右）
def layout_htree(root, two_sided=False):
    """two_sided=False → 向右逻辑树（rtree 用）；True → 左右双侧脑图。
    返回自然高度。"""
    kids = list(root.children)
    if two_sided and len(kids) > 1:
        kw = sorted(kids, key=count_leaves, reverse=True)
        L, R, wl, wr = [], [], 0, 0
        for k in kw:
            if wl <= wr:
                L.append(k); wl += count_leaves(k)
            else:
                R.append(k); wr += count_leaves(k)
        order = {id(k): i for i, k in enumerate(kids)}
        left_kids = sorted(L, key=lambda k: order[id(k)])
        right_kids = sorted(R, key=lambda k: order[id(k)])
    else:
        left_kids, right_kids = [], kids

    for c in left_kids:
        _mark_side(c, -1)
    for c in right_kids:
        _mark_side(c, +1)

    level_w = {}

    def collect(n):
        level_w[n.depth] = max(level_w.get(n.depth, 0), n.w)
        for c in n.children:
            collect(c)
    collect(root)
    maxd = max(level_w)

    def subtree_h(n):
        if not n.children:
            return n.h
        inner = sum(subtree_h(c) for c in n.children) + SIB_GAP_Y * (len(n.children) - 1)
        return max(n.h, inner)

    def side_height(nodes):
        if not nodes:
            return 0.0
        return sum(subtree_h(n) for n in nodes) + SIB_GAP_Y * (len(nodes) - 1)

    total_h = max(side_height(left_kids), side_height(right_kids), root.h)

    # 层级 x：按「上一层的半宽 + 间距 + 本层半宽」边到边累积，避免用整层最大宽度累计导致过宽
    def make_level_x(direction):
        xs = {0: 0.0}
        cur = 0.0
        prev_half = root.w / 2
        for d in range(1, maxd + 1):
            half = level_w.get(d, 0) / 2
            cur += prev_half + LEVEL_GAP_H + half
            xs[d] = direction * cur
            prev_half = half
        return xs

    right_x = make_level_x(+1)
    left_x = make_level_x(-1)

    def assign(n, ytop, xs):
        h_sub = subtree_h(n)
        n.y = ytop + h_sub / 2 - n.h / 2
        n.x = xs[n.depth]
        inner = sum(subtree_h(c) for c in n.children) + SIB_GAP_Y * max(0, len(n.children) - 1)
        cur = ytop + (h_sub - inner) / 2
        for c in n.children:
            assign(c, cur, xs)
            cur += subtree_h(c) + SIB_GAP_Y

    root.x, root.y, root.side = 0.0, 0.0, 0
    cur = -total_h / 2
    for c in right_kids:
        assign(c, cur, right_x)
        cur += subtree_h(c) + SIB_GAP_Y
    cur = -total_h / 2
    for c in left_kids:
        assign(c, cur, left_x)
        cur += subtree_h(c) + SIB_GAP_Y
    return total_h


def _mark_side(n, s):
    n.side = s
    for c in n.children:
        _mark_side(c, s)


# ---------------------------------------------------------------- 布局：radial（径向）
def layout_radial(root):
    leaves = []
    def collect(n):
        if not n.children:
            leaves.append(n)
            return
        for c in n.children:
            collect(c)
    collect(root)

    total = max(1, len(leaves))
    step = 2 * math.pi / total
    idx = {"i": 0}

    def set_angle(n):
        if not n.children:
            a = idx["i"] * step - math.pi / 2
            idx["i"] += 1
            n.angle = a
        else:
            for c in n.children:
                set_angle(c)
            # 角度取子节点均值（处理跨 0 度的环绕）
            n.angle = _mean_angle([c.angle for c in n.children])
        n.r = n.depth * RING_GAP
        n.x = n.r * math.cos(n.angle)
        n.y = n.r * math.sin(n.angle)

    set_angle(root)
    return "radial"


def _mean_angle(angles):
    sx = sum(math.cos(a) for a in angles)
    sy = sum(math.sin(a) for a in angles)
    return math.atan2(sy, sx)


# ---------------------------------------------------------------- 拟手绘基元
def catmull_bezier(pts, closed=False):
    """Catmull-Rom 采样点 → 三次贝塞尔 path d。"""
    n = len(pts)
    if n < 2:
        return ""
    if n == 2:
        return "M %.1f,%.1f L %.1f,%.1f" % (pts[0][0], pts[0][1], pts[1][0], pts[1][1])
    d = "M %.1f,%.1f " % (pts[0][0], pts[0][1])
    seg = n if closed else n - 1
    for i in range(seg):
        if closed:
            p0, p1, p2, p3 = pts[(i - 1) % n], pts[i % n], pts[(i + 1) % n], pts[(i + 2) % n]
        else:
            p0 = pts[i - 1] if i > 0 else pts[i]
            p1, p2 = pts[i], pts[i + 1]
            p3 = pts[i + 2] if i + 2 < n else pts[i + 1]
        c1x = p1[0] + (p2[0] - p0[0]) / 6.0
        c1y = p1[1] + (p2[1] - p0[1]) / 6.0
        c2x = p2[0] - (p3[0] - p1[0]) / 6.0
        c2y = p2[1] - (p3[1] - p1[1]) / 6.0
        d += "C %.1f,%.1f %.1f,%.1f %.1f,%.1f " % (c1x, c1y, c2x, c2y, p2[0], p2[1])
    if closed:
        d += "Z"
    return d


def rough_rrect(x, y, w, h, rx, rng, roughness=1.5, seed_pts=26):
    """拟手绘圆角矩形：沿轮廓采样 + 高斯扰动 + 平滑闭合。"""
    rx = min(rx, w / 2, h / 2)
    pts = []
    edges = [
        (x + rx, y, x + w - rx, y),              # 上
        (x + w, y + rx, x + w, y + h - rx),      # 右
        (x + w - rx, y + h, x + rx, y + h),      # 下
        (x, y + h - rx, x, y + rx),              # 左
    ]
    per_edge = max(2, seed_pts // 4)
    for (x1, y1, x2, y2) in edges:
        for i in range(per_edge):
            t = i / per_edge
            pts.append((x1 + (x2 - x1) * t, y1 + (y2 - y1) * t))
    # 四角圆弧
    arcs = [
        (x + w - rx, y + rx, -math.pi / 2, 0),
        (x + w - rx, y + h - rx, 0, math.pi / 2),
        (x + rx, y + h - rx, math.pi / 2, math.pi),
        (x + rx, y + rx, math.pi, math.pi * 1.5),
    ]
    a_pts = []
    for (cx, cy, a0, a1) in arcs:
        for i in range(3):
            a = a0 + (a1 - a0) * (i / 2.0)
            a_pts.append((cx + rx * math.cos(a), cy + rx * math.sin(a)))
    allp = a_pts + pts          # 角点 + 边点交替，顺序不重要（后面按角度排序）
    # 按相对中心角度排序，得到有序闭合轮廓
    cx0, cy0 = x + w / 2, y + h / 2
    allp = sorted(allp, key=lambda p: math.atan2(p[1] - cy0, p[0] - cx0))
    if roughness > 0:
        amp = 0.9 * roughness
        allp = [(px + rng.gauss(0, amp), py + rng.gauss(0, amp)) for (px, py) in allp]
    return catmull_bezier(allp, closed=True)


def rough_curve(a, b, rng, roughness=1.5, nseg=9, bow=None):
    """两点间拟手绘曲线（单笔）。bow = 中点偏移 (dx,dy)。"""
    ax, ay = a
    bx, by = b
    mid = ((ax + bx) / 2, (ay + by) / 2)
    if bow:
        mid = (mid[0] + bow[0], mid[1] + bow[1])
    pts = []
    L = math.hypot(bx - ax, by - ay) or 1.0
    nx, ny = -(by - ay) / L, (bx - ax) / L
    for i in range(nseg + 1):
        t = i / nseg
        x = (1 - t) ** 2 * ax + 2 * (1 - t) * t * mid[0] + t * t * bx
        y = (1 - t) ** 2 * ay + 2 * (1 - t) * t * mid[1] + t * t * by
        if 0 < i < nseg:
            j = rng.gauss(0, 0.36) * roughness * math.sin(math.pi * t)
            x += nx * j
            y += ny * j
        pts.append((x, y))
    return catmull_bezier(pts)


def tapered_branch(a, b, rng, w0, w1, bow=None, roughness=1.3, nseg=16):
    """锥形笔触分支：根部宽 w0 → 末端窄 w1，填充路径。"""
    ax, ay = a
    bx, by = b
    mid = ((ax + bx) / 2, (ay + by) / 2)
    if bow:
        mid = (mid[0] + bow[0], mid[1] + bow[1])
    left, right = [], []
    for i in range(nseg + 1):
        t = i / nseg
        x = (1 - t) ** 2 * ax + 2 * (1 - t) * t * mid[0] + t * t * bx
        y = (1 - t) ** 2 * ay + 2 * (1 - t) * t * mid[1] + t * t * by
        dx = 2 * (1 - t) * (mid[0] - ax) + 2 * t * (bx - mid[0])
        dy = 2 * (1 - t) * (mid[1] - ay) + 2 * t * (by - mid[1])
        L = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / L, dx / L
        w = w0 + (w1 - w0) * t
        wob = rng.gauss(0, 0.30) * roughness if 0 < i < nseg else 0.0
        left.append((x + nx * (w / 2 + wob), y + ny * (w / 2 + wob)))
        right.append((x - nx * (w / 2 + wob), y - ny * (w / 2 + wob)))
    dl = catmull_bezier(left)
    dr = catmull_bezier(list(reversed(right)))
    dr = dr.replace("M", "L", 1)
    return dl + " " + dr + " Z"


# ---------------------------------------------------------------- 渲染
def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def walk(n, fn):
    fn(n)
    for c in n.children:
        walk(c, fn)


def render_svg(root, layout, style, rng, footer=None, canvas=None, margin=64,
               seed_note=None):
    st = STYLES[style]
    pal = st["pal"]

    # 分支配色：一级分支各取一色，后代继承
    for i, c in enumerate(root.children):
        col = pal[i % len(pal)]
        def paint(x, col=col):
            x.color = col
            for y in x.children:
                paint(y, col)
        paint(c)

    nodes = []
    walk(root, lambda n: nodes.append(n))

    # ---- 层级前缀 / 分支路径
    parts = []
    if layout == "radial":
        cx0 = cy0 = 0.0
        for n in nodes:
            if n.depth == 0:
                continue
            p = _parent_of(root, n)
            col = n.color
            d = rough_curve((p.x, p.y), (n.x, n.y), rng,
                            roughness=st["roughness"] * 0.9, nseg=7)
            w = max(1.2, 3.4 - n.depth * 0.6)
            parts.append('<path d="%s" fill="none" stroke="%s" stroke-width="%.1f" '
                         'stroke-linecap="round" opacity="0.85"/>' % (d, col, w))
    else:
        for n in nodes:
            if n.depth == 0:
                continue
            p = _parent_of(root, n)
            col = n.color
            if layout == "vtree":
                a = (p.x, p.y + p.h / 2)
                b = (n.x, n.y - n.h / 2)
                bow = (0, 0)
            else:  # htree / mtree —— 水平连接，取节点竖向中心
                sgn = n.side
                a = (p.x + sgn * p.w / 2, p.y)
                b = (n.x - sgn * n.w / 2, n.y)
                bow = (0, 0)
            if n.depth == 1:
                d = tapered_branch(a, b, rng, 17.0, 7.0, bow=bow,
                                   roughness=st["roughness"] * 0.7)
                parts.append('<path d="%s" fill="%s" opacity="0.20"/>' % (d, col))
                parts.append('<path d="%s" fill="none" stroke="%s" stroke-width="1.5" '
                             'opacity="0.58"/>' % (d, col))
            else:
                d = rough_curve(a, b, rng, roughness=st["roughness"] * 0.8, nseg=8,
                                bow=bow)
                w = 2.6 if n.depth == 2 else 1.8
                parts.append('<path d="%s" fill="none" stroke="%s" stroke-width="%.1f" '
                             'stroke-linecap="round" opacity="0.75"/>'
                             % (d, col, w))

    # ---- 节点
    for n in nodes:
        fs = font_size(n.depth)
        lines = n._lines
        col = n.color or st["ink"]
        x, y, w, h = n.x - n.w / 2, n.y - n.h / 2, n.w, n.h

        if layout == "radial":
            if n.depth == 0:
                _pill(parts, x, y, w, h, st["rx"], rng, st, fill=st["ink"],
                      stroke=st["ink"], lw=st["pill_line_w"])
                _text(parts, n, x, y, w, h, fs, "#FFFFFF", "hand", st)
            else:
                parts.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s"/>'
                             % (n.x, n.y, 5.0 + (3 - min(3, n.depth)) * 1.2, col))
                anchor = "start" if math.cos(n.angle) >= 0 else "end"
                tx = n.x + (12 if anchor == "start" else -12)
                fam = "hand" if n.depth == 1 else "body"
                fill = col if n.depth == 1 else st["ink"]
                _text_raw(parts, n.text, tx, n.y, fs, fill, fam, st, anchor=anchor,
                          vertical=True)
            continue

        if n.depth == 0:
            _pill(parts, x, y, w, h, st["rx"], rng, st, fill=st["ink"], stroke=st["ink"],
                  lw=st["pill_line_w"])
            _text(parts, n, x, y, w, h, fs, "#FFFFFF", "hand", st)
        elif n.depth == 1:
            _pill(parts, x, y, w, h, st["rx"], rng, st, fill=st["pill_fill"],
                  stroke=col, lw=st["pill_line_w"])
            _text(parts, n, x, y, w, h, fs, col, "hand", st)
        elif n.depth == 2:
            _pill(parts, x, y, w, h, st["rx"], rng, st,
                  fill=_tint(col, 0.90), stroke=_tint(col, 0.55), lw=max(1.2, st["pill_line_w"] * 0.6))
            _text(parts, n, x, y, w, h, fs, st["ink"], "body", st)
        else:
            _pill(parts, x, y, w, h, st["rx"] * 0.8, rng, st,
                  fill="none", stroke=_tint(col, 0.60), lw=1.1, dash="5 4")
            _text(parts, n, x, y, w, h, fs, st["sub"], "body", st)

    return parts, nodes


def _parent_of(root, target, _p=None):
    if _p is None:
        _p = {}
        def build(n, parent):
            _p[id(n)] = parent
            for c in n.children:
                build(c, n)
        build(root, root)
    return _p[id(target)]


def _tint(hexcol, mix):
    """与白色混合：mix=1 → 纯色，mix=0 → 白。"""
    c = hexcol.lstrip("#")
    r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    r = int(r * mix + 255 * (1 - mix))
    g = int(g * mix + 255 * (1 - mix))
    b = int(b * mix + 255 * (1 - mix))
    return "#%02X%02X%02X" % (r, g, b)


def _pill(parts, x, y, w, h, rx, rng, st, fill="#FFFFFF", stroke="#000000",
          lw=2.0, dash=None):
    if st.get("shadow"):
        d = rough_rrect(x + 4, y + 5, w, h, rx, rng, roughness=st["roughness"] * 0.5)
        parts.append('<path d="%s" fill="%s" opacity="0.16"/>' % (d, stroke))
    d = rough_rrect(x, y, w, h, rx, rng, roughness=st["roughness"])
    da = ' stroke-dasharray="%s"' % dash if dash else ""
    parts.append('<path d="%s" fill="%s" stroke="%s" stroke-width="%.1f"%s '
                 'stroke-linejoin="round"/>' % (d, fill, stroke, lw, da))


def _text(parts, n, x, y, w, h, fs, fill, fam, st):
    lines = n._lines
    lh = fs * 1.42
    y0 = y + h / 2 - (len(lines) - 1) * lh / 2
    for i, line in enumerate(lines):
        _text_raw(parts, line, x + w / 2, y0 + i * lh, fs, fill, fam, st,
                  anchor="middle", vertical=True)


def _text_raw(parts, s, x, y, fs, fill, fam, st, anchor="middle", vertical=False):
    ff = FONT_HAND_FAM if fam == "hand" else "%s,sans-serif" % FONT_BODY
    if vertical:
        parts.append('<text x="%.1f" y="%.1f" font-family="%s" font-size="%.1f" '
                     'fill="%s" text-anchor="%s" dominant-baseline="central">%s</text>'
                     % (x, y, ff, fs, fill, anchor, esc(s)))
    else:
        parts.append('<text x="%.1f" y="%.1f" font-family="%s" font-size="%.1f" '
                     'fill="%s" text-anchor="%s">%s</text>'
                     % (x, y, ff, fs, fill, anchor, esc(s)))


FONT_HAND_FAM = "HandTitle"


def content_size(root, layout):
    """内容包围盒 (minx, miny, maxx, maxy)。radial 需把节点的文字外扩算进去。"""
    def ext(n):
        if layout == "radial" and n.depth > 0:
            tw = text_w(n.text, font_size(n.depth))
            if math.cos(n.angle) >= 0:
                x0, x1 = n.x - 12, n.x + 16 + tw
            else:
                x0, x1 = n.x - 16 - tw, n.x + 12
            r = font_size(n.depth) * 0.85
            return x0, x1, n.y - r, n.y + r
        return n.x - n.w / 2, n.x + n.w / 2, n.y - n.h / 2, n.y + n.h / 2
    e = [ext(n) for n in _iter(root)]
    return (min(v[0] for v in e), min(v[2] for v in e),
            max(v[1] for v in e), max(v[3] for v in e))


def prune_depth(node, maxd):
    """截断到指定层数，被砍掉的子孙数标注在节点文案后（+N）。"""
    if node.depth >= maxd:
        dropped = sum(1 for _ in _iter(node)) - 1
        node.children = []
        if dropped:
            node.text = "%s (+%d)" % (node.text, dropped)
        return
    for c in node.children:
        prune_depth(c, maxd)


def build_html(root, layout, style, rng, width, height, footer, margin, title):
    st = STYLES[style]
    parts, nodes = render_svg(root, layout, style, rng, footer=footer,
                              canvas=(width, height), margin=margin)

    minx, miny, maxx, maxy = content_size(root, layout)
    bw, bh = max(1.0, maxx - minx), max(1.0, maxy - miny)

    foot_h = 56 if footer else 0                       # 页脚单独预留，不混进内容包围盒
    avw, avh = width - 2 * margin, height - 2 * margin - foot_h
    s = min(avw / bw, avh / bh, 1.15)                  # 不无限放大
    if s < 0.62:
        sys.stderr.write("⚠️ 内容偏大，自动缩放仅 %.2f —— 建议：① --layout auto/vtree；"
                         "② --max-depth N 截断；③ 加大 --height；④ 缩短节点文案\n" % s)
    tx = margin + (avw - bw * s) / 2 - minx * s
    ty = margin + (avh - bh * s) / 2 - miny * s
    sys.stderr.write("  [fit] 布局=%-6s 缩放=%.3f 内容=%dx%d 画布占比=%.0f%%x%.0f%%\n"
                     % (layout, s, bw * s, bh * s,
                        100 * bw * s / width, 100 * bh * s / height))

    css = "@font-face{font-family:'%s';src:url('%s');}" % (
        FONT_HAND_FAM, _font_url(FONT_HAND if os.path.exists(FONT_HAND) else FONT_HAND_ALT))
    grain = ""
    if st["grain"] > 0:
        grain = ('<filter id="grain"><feTurbulence type="fractalNoise" baseFrequency="0.9" '
                 'numOctaves="4" stitchTiles="stitch"/><feColorMatrix type="saturate" '
                 'values="0"/></filter>'
                 '<rect width="%d" height="%d" filter="url(#grain)" opacity="%.3f"/>'
                 % (width, height, st["grain"]))

    head_txt = ""
    if title:
        head_txt = ('<text x="%.0f" y="%.0f" font-family="%s,sans-serif" font-size="19" '
                    'fill="%s" letter-spacing="3">%s</text>'
                    % (margin, margin - 22, FONT_BODY, st["sub"], esc(title)))

    foot_txt = ""
    if footer:
        foot_txt = ('<text x="%.0f" y="%.0f" font-family="%s,sans-serif" font-size="15" '
                    'fill="%s" text-anchor="end">%s</text>'
                    % (width - margin, height - margin + 34, FONT_BODY, st["sub"],
                       esc(footer)))

    svg = (
        '<svg width="%d" height="%d" viewBox="0 0 %d %d" xmlns="http://www.w3.org/2000/svg">'
        % (width, height, width, height)
        + '<rect width="%d" height="%d" fill="%s"/>' % (width, height, st["paper"])
        + '<rect x="0" y="0" width="%d" height="8" fill="%s"/>' % (width, st["pal"][0])
        + grain
        + head_txt
        + '<g transform="translate(%.2f,%.2f) scale(%.4f)">' % (tx, ty, s)
        + "".join(parts)
        + '</g>'
        + foot_txt
        + '</svg>'
    )
    return ('<!DOCTYPE html><html><head><meta charset="utf-8"><style>'
            + "html,body{margin:0;padding:0;background:" + st["paper"] + ";}"
            + css + '</style></head><body>' + svg + '</body></html>')


# ---------------------------------------------------------------- 入口
def main():
    ap = argparse.ArgumentParser(description="大纲 → 手绘风脑图 PNG")
    ap.add_argument("source", help="大纲文件路径（md/txt）或 - 表示 stdin")
    ap.add_argument("--out", required=True, help="输出 PNG 路径")
    ap.add_argument("--layout", default="auto",
                    choices=["auto", "vtree", "htree", "mtree", "radial"],
                    help="auto=自动选最适配布局（默认）/ vtree=上下树 / htree=向右逻辑树 / mtree=左右双侧脑图 / radial=径向脑图")
    ap.add_argument("--style", default="handdrawn", choices=list(STYLES),
                    help="风格预设")
    ap.add_argument("--width", type=int, default=1242)
    ap.add_argument("--height", type=int, default=1656)
    ap.add_argument("--scale", type=float, default=2.0, help="像素密度倍数")
    ap.add_argument("--title", default="", help="左上角小标（如「知识图解 · 001」）")
    ap.add_argument("--footer", default="", help="右下角落款")
    ap.add_argument("--margin", type=int, default=64)
    ap.add_argument("--seed", type=int, default=20260913, help="手绘抖动随机种子")
    ap.add_argument("--max-text-width", type=float, default=300.0, help="节点文本最大宽度（超出折行）")
    ap.add_argument("--max-depth", type=int, default=0, help="只保留到第 N 层（0=不限）；超出部分折叠并标注 +N")
    ap.add_argument("--emit-svg", default="", help="另存 SVG 源文件路径")
    args = ap.parse_args()

    if args.source == "-":
        raw = sys.stdin.read()
    elif args.source.lower().endswith(".xmind"):
        raw = xmind_to_outline(args.source)
        print("  [xmind 直读] %s" % os.path.basename(args.source))
    else:
        raw = open(args.source, encoding="utf-8").read()
    root = parse_outline(raw)
    if args.max_depth and args.max_depth > 0:
        before = sum(1 for _ in _iter(root))
        prune_depth(root, args.max_depth)
        print("  [截断] 层级 ≤ %d：节点 %d → %d"
              % (args.max_depth, before, sum(1 for _ in _iter(root))))
    measure(root, args.max_text_width)

    avw = args.width - 2 * args.margin
    avh = args.height - 2 * args.margin - (56 if args.footer else 0)

    def run_layout(name):
        if name == "vtree":
            nat_h = layout_vtree(root, LEVEL_GAP)
            na = list(_iter(root))
            minx, miny, maxx, maxy = content_size(root, "vtree")
            s_w = min(avw / max(maxx - minx, 1.0), 1.15)
            need = avh / s_w
            lv = max(n.depth for n in na)
            if lv >= 1 and need > nat_h * 1.02:
                layout_vtree(root, min(LEVEL_GAP + (need - nat_h) / lv, 340.0))
        elif name in ("htree", "mtree"):
            layout_htree(root, two_sided=(name == "mtree"))
            # 横向布局常受宽度限制 → 纵向拉开节点间距填满画布（只挪位置，字号不变）
            mx0, my0, mx1, my1 = content_size(root, name)
            s_w = min(avw / max(mx1 - mx0, 1.0), 1.15)
            s_h = avh / max(my1 - my0, 1.0)
            if s_h > s_w * 1.05:
                ky = min(s_h / s_w, 2.4)
                for nd in _iter(root):
                    nd.y *= ky
        else:
            layout_radial(root)

    def fit_scale(name):
        minx, miny, maxx, maxy = content_size(root, name)
        return min(avw / max(maxx - minx, 1.0),
                   avh / max(maxy - miny, 1.0), 1.15)

    rng = random.Random(args.seed)
    if args.layout == "auto":
        best, bs = None, -1.0
        for cand in ("vtree", "htree", "mtree", "radial"):
            run_layout(cand)
            sc = fit_scale(cand)
            print("    [auto] %-7s 适配系数 %.3f" % (cand, sc))
            if sc > bs:
                best, bs = cand, sc
        run_layout(best)
        args.layout = best
        print("  [auto] 选定布局 = %s（系数 %.3f）" % (best, bs))
    else:
        run_layout(args.layout)

    html = build_html(root, args.layout, args.style, rng, args.width, args.height,
                      args.footer, args.margin, args.title)

    tmp = tempfile.mkdtemp(prefix="mindmap_")
    hp = os.path.join(tmp, "map.html")
    with open(hp, "w", encoding="utf-8") as f:
        f.write(html)

    if args.emit_svg:
        with open(args.emit_svg, "w", encoding="utf-8") as f:
            f.write(html)

    cmd = [sys.executable, RENDER_PY, hp, "--width", str(args.width),
           "--height", str(args.height), "--scale", str(args.scale),
           "--out", args.out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stdout + r.stderr)
        sys.exit(r.returncode)
    n = count_leaves(root)
    print("%s | 布局=%s 风格=%s 节点=%d 叶=%d 画幅=%dx%d @%.1fx"
          % (args.out, args.layout, args.style,
             sum(1 for _ in _iter(root)), n, args.width, args.height, args.scale))


def _iter(n):
    yield n
    for c in n.children:
        for x in _iter(c):
            yield x


if __name__ == "__main__":
    main()
