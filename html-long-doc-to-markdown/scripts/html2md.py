#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""培训手册 HTML → Markdown（无第三方依赖）。

v2 修复：
 1. VOID 只保留真 HTML 空元素；SVG 子元素（text/path/...）改为正常节点，避免图形文字错位。
 2. 隐式闭合规则：h1-h6 / p / li / td / th / tr 遇同级或块级新标签自动闭合
    —— 源 HTML 存在 <h3>…</h4> 错配（2 处），不修会吞掉后续整章。
 3. 结束标签宽容匹配：找不到同名祖先时，回退到同族（h1↔h6）。
 4. 行内元素成串分组：连续 inline 子节点合并为一段，不再拆成多个段落。
 5. 导出内嵌 SVG 为独立 .svg 文件，并在 md 中原位插入图片引用。
"""
import os
import re
import sys
from html.parser import HTMLParser

VOID = {"br", "hr", "img", "meta", "link", "input", "source", "wbr", "area", "col"}

HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
BLOCK = HEADINGS | {"p", "ul", "ol", "table", "blockquote", "pre", "hr", "svg"}
CONTAINERISH = BLOCK | {"div", "section"}

# 隐式闭合：key 为「即将打开」的新标签，value 为「它必须先关掉的、当前打开中的标签」
# 注意：过宽会误弹父级（曾把 td 的集合写成含 tr，导致 <td> 弹掉 <tr>、整表结构散架）
IMPLICIT_CLOSE = {
    "li": {"li", "p"} | HEADINGS,
    "p": {"p"} | HEADINGS,
    "tr": {"tr", "td", "th"},
    "td": {"td", "th"},
    "th": {"td", "th"},
    "ul": {"p"} | HEADINGS,
    "ol": {"p"} | HEADINGS,
    "table": {"p"} | HEADINGS,
    "div": {"p"} | HEADINGS,
    "section": {"p"} | HEADINGS,
    "blockquote": {"p"} | HEADINGS,
    "pre": {"p"} | HEADINGS,
}
for _h in HEADINGS:
    IMPLICIT_CLOSE[_h] = {"p"} | HEADINGS

FAMILY = {"h1": HEADINGS, "h2": HEADINGS, "h3": HEADINGS,
          "h4": HEADINGS, "h5": HEADINGS, "h6": HEADINGS}


class Node:
    __slots__ = ("tag", "attrs", "children", "parent")

    def __init__(self, tag="", attrs=None, parent=None):
        self.tag = tag
        self.attrs = dict(attrs or {})
        self.children = []
        self.parent = parent

    def text(self):
        return "".join(c.text() if isinstance(c, Node) else c for c in self.children)


class Builder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.cur = self.root
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script", "head", "title"):
            self.skip += 1
            return
        if self.skip:
            return
        # 隐式闭合
        allowed = IMPLICIT_CLOSE.get(tag, set())
        guard = 0
        while self.cur.tag in allowed and self.cur.parent is not None and guard < 50:
            self.cur = self.cur.parent
            guard += 1
        # h 遇新 h：无论层级都先闭合到最近的标题之外
        if tag in HEADINGS:
            g = 0
            while self.cur.tag in HEADINGS and self.cur.parent is not None and g < 50:
                self.cur = self.cur.parent
                g += 1
        n = Node(tag, attrs, self.cur)
        self.cur.children.append(n)
        if tag not in VOID:
            self.cur = n

    def handle_startendtag(self, tag, attrs):
        if self.skip or tag in ("style", "script", "head", "title"):
            return
        self.cur.children.append(Node(tag, attrs, self.cur))

    def handle_endtag(self, tag):
        if tag in ("style", "script", "head", "title"):
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if tag in VOID:
            return
        p = self.cur
        target = None
        while p is not None and p.tag != "root":
            if p.tag == tag:
                target = p
                break
            p = p.parent
        if target is None and tag in FAMILY:
            p = self.cur
            while p is not None and p.tag != "root":
                if p.tag in FAMILY[tag]:
                    target = p
                    break
                p = p.parent
        if target is not None and target.parent is not None:
            self.cur = target.parent

    def handle_data(self, data):
        if self.skip:
            return
        self.cur.children.append(data)


def walk_svg(n):
    if not isinstance(n, Node):
        return n
    attrs = "".join(f' {fix_attr_case(k)}="{v}"' for k, v in n.attrs.items()
                    if k not in ("data-page-node-id",))
    if not n.tag:
        return "".join(walk_svg(c) for c in n.children)
    inner = "".join(walk_svg(c) for c in n.children)
    if n.tag in VOID:
        return f"<{n.tag}{attrs}/>"
    return f"<{n.tag}{attrs}>{inner}</{n.tag}>"


# HTMLParser 会把属性名统一转小写，但 SVG 严格区分大小写（viewBox 写成 viewbox 会失效）
SVG_CASE = {
    "viewbox": "viewBox", "preserveaspectratio": "preserveAspectRatio",
    "markerwidth": "markerWidth", "markerheight": "markerHeight",
    "markerunits": "markerUnits", "refx": "refX", "refy": "refY",
    "gradientunits": "gradientUnits", "gradienttransform": "gradientTransform",
    "patternunits": "patternUnits", "patterncontentunits": "patternContentUnits",
    "patterntransform": "patternTransform", "clippathunits": "clipPathUnits",
    "textlength": "textLength", "lengthadjust": "lengthAdjust",
    "spreadmethod": "spreadMethod", "startoffset": "startOffset",
    "stddeviation": "stdDeviation", "basefrequency": "baseFrequency",
    "numoctaves": "numOctaves", "tablevalues": "tableValues",
    "attributename": "attributeName", "repeatcount": "repeatCount",
    "calcmode": "calcMode", "keytimes": "keyTimes", "keysplines": "keySplines",
    "keypoints": "keyPoints", "gradientref": "gradientRef",
    "filterunits": "filterUnits", "primitiveunits": "primitiveUnits",
    "xchannelselector": "xChannelSelector", "ychannelselector": "yChannelSelector",
}


def fix_attr_case(k):
    return SVG_CASE.get(k.lower(), k)


INLINE_WRAP = {"strong": "**", "b": "**", "em": "*", "i": "*", "code": "`"}


class Stub(Node):
    def __init__(self, children):
        super().__init__("stub")
        self.children = children


def inline(node, ctx):
    """行内渲染。ctx 用于卸载 SVG（返回占位符 id）。"""
    out = []

    def walk(n):
        for c in n.children:
            if isinstance(c, str):
                out.append(c)
            elif c.tag == "br":
                out.append(" ")
            elif c.tag == "svg":
                out.append(f"@@SVG{ctx.store(c)}@@")
            elif c.tag in INLINE_WRAP:
                t = inline(c, ctx).strip()
                out.append(f"{INLINE_WRAP[c.tag]}{t}{INLINE_WRAP[c.tag]}" if t else "")
            else:
                walk(c)

    walk(node)
    s = "".join(out).replace("\u00a0", " ")
    s = re.sub(r"[ \t]*\n[ \t]*", " ", s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    return s.strip()


def has_block(n):
    """判断节点是否含块级后代 —— 有则递归下钻，无则整体作为一段。
    div/section 也算容器：否则 .cards(含 5 个 .card) 会被压成一整段。"""
    if not isinstance(n, Node):
        return False
    for c in n.children:
        if isinstance(c, Node) and (c.tag in CONTAINERISH or has_block(c)):
            return True
    return False


# 叶子 div 里需要加粗的类名（卡片标题 / 步骤标题 / 提示标签）
BOLD_CLASSES = {"card-title", "step-title", "callout-label", "toc-chapter-title"}


def leaf_div_paragraph(node, ctx):
    t = inline(node, ctx)
    if not t:
        return ""
    cls = set((node.attrs.get("class") or "").split())
    if cls & BOLD_CLASSES:
        return f"**{t}**"
    return t


def render_table(node, ctx):
    """转 markdown 表格；支持 rowspan（向下填充原文）/ colspan（首列放文、其余留空）。"""
    raw_rows = []

    def collect(n):
        for c in n.children:
            if not isinstance(c, Node):
                continue
            if c.tag == "tr":
                cells = []
                for cell in c.children:
                    if isinstance(cell, Node) and cell.tag in ("td", "th"):
                        cells.append({
                            "text": inline(cell, ctx),
                            "rowspan": int(re.sub(r"\D", "", cell.attrs.get("rowspan", "1")) or 1),
                            "colspan": int(re.sub(r"\D", "", cell.attrs.get("colspan", "1")) or 1),
                        })
                if cells:
                    raw_rows.append(cells)
            else:
                collect(c)

    collect(node)
    if not raw_rows:
        return ""

    grid, pending = [], {}
    for raw in raw_rows:
        row, ci, ri = [], 0, 0
        while ri < len(raw) or ci in pending:
            if ci in pending:
                left, text = pending[ci]
                row.append(text)
                if left - 1 <= 0:
                    del pending[ci]
                else:
                    pending[ci][0] = left - 1
                ci += 1
                continue
            cell = raw[ri]
            ri += 1
            row.append(cell["text"])
            if cell["rowspan"] > 1:
                pending[ci] = [cell["rowspan"] - 1, cell["text"]]
            for _ in range(cell["colspan"] - 1):
                ci += 1
                row.append("")
                if cell["rowspan"] > 1:
                    pending[ci] = [cell["rowspan"] - 1, cell["text"]]
            ci += 1
        grid.append(row)

    w = max(len(r) for r in grid)
    grid = [r + [""] * (w - len(r)) for r in grid]
    esc = lambda s: s.replace("|", "\\|").replace("\n", " ").strip()
    out = ["| " + " | ".join(esc(c) for c in grid[0]) + " |",
           "|" + "|".join([" --- "] * w) + "|"]
    for r in grid[1:]:
        out.append("| " + " | ".join(esc(c) for c in r) + " |")
    return "\n".join(out)


def render_list(node, ctx, depth=0, ordered=False):
    lines = []
    idx = 1
    for c in node.children:
        if not isinstance(c, Node) or c.tag != "li":
            continue
        head, subs = [], []
        for k in c.children:
            (subs if isinstance(k, Node) and k.tag in ("ul", "ol") else head).append(k)
        body = inline(Stub(head), ctx).strip()
        lead = f"{idx}. " if ordered else "- "
        idx += 1
        lines.append("  " * depth + lead + body)
        for s in subs:
            lines.append(render_list(s, ctx, depth + 1, s.tag == "ol"))
    return "\n".join(l for l in lines if l.strip())


def render(node, ctx, out):
    buf = []

    def flush():
        if not buf:
            return
        t = inline(Stub(buf), ctx).strip()
        if t:
            out.append(t)
        buf.clear()

    prev_el = False
    for c in node.children:
        if isinstance(c, str):
            if c.strip():
                buf.append(c)
                prev_el = False
            continue
        if c.tag in HEADINGS:
            flush()
            out.append("#" * int(c.tag[1]) + " " + inline(c, ctx))
        elif c.tag == "p":
            flush()
            t = inline(c, ctx)
            if t:
                out.append(t)
        elif c.tag in ("ul", "ol"):
            flush()
            t = render_list(c, ctx, 0, c.tag == "ol")
            if t:
                out.append(t)
        elif c.tag == "table":
            flush()
            t = render_table(c, ctx)
            if t:
                out.append(t)
        elif c.tag == "blockquote":
            flush()
            t = inline(c, ctx)
            if t:
                out.append("> " + t)
        elif c.tag == "pre":
            flush()
            out.append("```\n" + c.text().strip("\n") + "\n```")
        elif c.tag == "hr":
            flush()
            out.append("---")
        elif c.tag == "svg":
            flush()
            out.append(f"@@SVG{ctx.store(c)}@@")
        elif has_block(c):
            flush()
            render(c, ctx, out)
        elif c.tag in ("div", "section"):
            flush()
            t = leaf_div_paragraph(c, ctx)
            if t:
                out.append(t)
        else:
            if prev_el:
                buf.append(" ")
            buf.append(c)
        prev_el = True
    flush()


class Ctx:
    def __init__(self, outdir, base):
        self.outdir = outdir
        self.base = base
        self.map = {}
        self.order = []

    def store(self, svg_node):
        if id(svg_node) in self.map:
            return self.map[id(svg_node)]
        idx = len(self.order) + 1
        self.map[id(svg_node)] = idx
        self.order.append((idx, svg_node))
        return idx


TITLES = {1: "不可能三角", 2: "人设树六步法"}


def main(src, dst):
    html = open(src, encoding="utf-8").read()
    b = Builder()
    b.feed(html)
    b.close()

    def find(n, tag):
        if isinstance(n, Node) and n.tag == tag:
            return n
        for c in (n.children if isinstance(n, Node) else []):
            r = find(c, tag)
            if r:
                return r
        return None

    body = find(b.root, "body") or b.root
    outdir = os.path.dirname(dst)
    base = os.path.splitext(os.path.basename(dst))[0]
    ctx = Ctx(outdir, base)

    out = []
    render(body, ctx, out)
    md = "\n\n".join(x for x in out if x.strip())
    md = re.sub(r"\n{3,}", "\n\n", md)

    # 落盘 SVG 并替换占位符
    for idx, node in ctx.order:
        title = TITLES.get(idx, f"图解{idx}")
        fname = f"{base}_图解{idx}_{title}.svg"
        raw = walk_svg(node)
        if not raw.lstrip().startswith("<svg"):
            raw = "<svg " + raw.lstrip("<svg").lstrip() if raw.lstrip().startswith("<svg") else raw
        with open(os.path.join(outdir, fname), "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n' + raw + "\n")
        md = md.replace(f"@@SVG{idx}@@", f"![图解{idx}：{title}]({fname})")
        print(f"SVG 写出: {fname}  ({len(raw)} 字符)")

    md = md + "\n"
    open(dst, "w", encoding="utf-8").write(md)
    print("MD 已写出:", dst)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
