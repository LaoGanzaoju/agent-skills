#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SVG / HTML -> PNG 长图渲染器（Chrome headless 通道）

零新增依赖：只要机器上有 Chrome（或 Chromium），无需 cairosvg / PIL / playwright。

用法：
    # 从 HTML 渲染（HTML 里含 SVG 或任意 DOM）
    python3 render.py page.html --width 1242 --height 1656 --out out.png --scale 2

    # 从 .svg 渲染（脚本自动包一层最小 HTML）
    python3 render.py page.svg --width 1242 --height 1656 --out out.png

    # 尺寸可省略 —— 会尝试从 SVG 的 width/height 或 viewBox 自动推断
    python3 render.py page.svg --out out.png

中文注意：HTML 里 @font-face 的字体路径若含中文，务必 urllib.parse.quote 编码，
否则 Chrome 加载不到（会静默 fallback）。
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
]
# 注意：此处不能用 str.format —— CSS 里的花括号会被当成占位符（已踩坑）
HTML_HEAD = (
    '<!DOCTYPE html><html><head><meta charset="utf-8">'
    '<style>html,body{margin:0;padding:0;background:#fff;}</style>'
    '</head><body>'
)
HTML_TAIL = '</body></html>'


def find_chrome():
    for c in CHROME_CANDIDATES:
        if os.path.exists(c):
            return c
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        p = shutil.which(name)
        if p:
            return p
    return None


def sniff_size(svg_text):
    """从 SVG 文本推断 (w, h)，供 --width/--height 省略时使用。"""
    m = re.search(r'<svg[^>]*\swidth=["\'](\d+(?:\.\d+)?)(?:px)?["\']', svg_text)
    n = re.search(r'<svg[^>]*\sheight=["\'](\d+(?:\.\d+)?)(?:px)?["\']', svg_text)
    if m and n:
        return int(float(m.group(1))), int(float(n.group(1)))
    v = re.search(r'viewBox=["\']\s*[\d.\-]+\s+[\d.\-]+\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s*["\']', svg_text)
    if v:
        return int(float(v.group(1))), int(float(v.group(2)))
    return None, None


def render(src, out, width, height, scale=1, timeout=120):
    chrome = find_chrome()
    if not chrome:
        return False, "未找到 Chrome / Chromium，无法渲染"

    src = os.path.abspath(src)
    if not os.path.exists(src):
        return False, "源文件不存在：%s" % src

    tmp_html = None
    if src.lower().endswith(".svg"):
        svg_text = open(src, encoding="utf-8").read()
        if not width or not height:
            w, h = sniff_size(svg_text)
            width = width or w
            height = height or h
            if not width or not height:
                return False, "无法从 SVG 推断画幅，请显式传 --width/--height"
        # 先剥掉 SVG 原有的 width/height，再注入精确值（保证与 --window-size 完全一致）
        cut = svg_text.find(">")
        if cut < 0:
            cut = len(svg_text)
        head, rest = svg_text[:cut], svg_text[cut:]
        head = re.sub(r'\swidth=["\'][^"\']*["\']', "", head)
        head = re.sub(r'\sheight=["\'][^"\']*["\']', "", head)
        head = head.replace("<svg", '<svg width="%d" height="%d"' % (width, height), 1)
        fd, tmp_html = tempfile.mkstemp(suffix=".html", prefix="svgrender_")
        os.close(fd)
        open(tmp_html, "w", encoding="utf-8").write(HTML_HEAD + head + rest + HTML_TAIL)
        target = tmp_html
    else:
        target = src

    out = os.path.abspath(out)
    cmd = [
        chrome,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--no-sandbox",
        "--force-device-scale-factor=%s" % scale,
        "--window-size=%d,%d" % (width, height),
        "--screenshot=%s" % out,
        "file://" + target,
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        if tmp_html:
            os.unlink(tmp_html)
        return False, "渲染超时（%ss）" % timeout

    if tmp_html:
        os.unlink(tmp_html)

    if os.path.exists(out) and os.path.getsize(out) > 0:
        return True, "%d bytes" % os.path.getsize(out)
    tail = (r.stderr or r.stdout or "").strip().splitlines()[-3:]
    return False, "渲染失败：" + " | ".join(tail)


def main():
    ap = argparse.ArgumentParser(description="SVG/HTML -> PNG（Chrome headless）")
    ap.add_argument("src", help="源文件：.html 或 .svg")
    ap.add_argument("--width", type=int, help="画幅宽（px）。SVG 可省略，自动推断")
    ap.add_argument("--height", type=int, help="画幅高（px）。SVG 可省略，自动推断")
    ap.add_argument("--out", help="输出 PNG 路径（默认与源文件同名 .png）")
    ap.add_argument("--scale", type=float, default=1, help="设备像素比，2 = @2x 高清（默认 1）")
    a = ap.parse_args()

    out = a.out or os.path.splitext(a.src)[0] + ".png"
    w, h = a.width, a.height
    if not w or not h:
        if a.src.lower().endswith(".svg"):
            got_w, got_h = sniff_size(open(a.src, encoding="utf-8").read())
            w, h = w or got_w, h or got_h
    if not w or not h:
        print("错误：必须提供 --width 与 --height（或让脚本从 SVG 推断）", file=sys.stderr)
        sys.exit(2)

    ok, msg = render(a.src, out, w, h, a.scale)
    print(("OK  %s  %dx%d @%gx  %s" % (out, w, h, a.scale, msg)) if ok else ("FAIL  " + msg))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
