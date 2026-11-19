#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
docx 独立核验器 —— 不依赖生成工具的自报结果，直读 OOXML 包内 XML。

用法:
    python3 verify_docx.py <文件.docx> [期望命中的关键串 ...]

退出码: 0=结构正常; 1=发现异常(空壳/表格丢失/结构可疑)
"""
import sys, os, zipfile, re, collections

try:
    from docx import Document
    HAS_PYDOCX = True
except Exception:
    HAS_PYDOCX = False

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def main():
    if len(sys.argv) < 2:
        print("用法: python3 verify_docx.py <文件.docx> [期望命中的关键串 ...]")
        return 2
    path = sys.argv[1]
    keys = sys.argv[2:]
    if not os.path.exists(path):
        print("✘ 文件不存在:", path)
        return 1

    size = os.path.getsize(path)
    print("文件:", path)
    print("体积: %.1f KB" % (size / 1024.0))
    if size < 2000:
        print("⚠️  体积过小，可能是空壳")

    try:
        z = zipfile.ZipFile(path)
        names = z.namelist()
    except zipfile.BadZipFile:
        print("✘ 不是合法 docx（不是 zip 包）—— 可能只是改了后缀的文本文件")
        return 1
    except Exception as e:
        print("✘ 打不开文件: %s: %s" % (type(e).__name__, e))
        return 1
    if "word/document.xml" not in names:
        print("✘ 包内无 word/document.xml —— 不是合法 docx")
        return 1
    xml = z.read("word/document.xml").decode("utf-8", "replace")

    styles_xml = ""
    if "word/styles.xml" in names:
        styles_xml = z.read("word/styles.xml").decode("utf-8", "replace")
    defined = set(re.findall(r'w:styleId="([^"]+)"', styles_xml))
    used = collections.Counter(re.findall(r'<w:pStyle w:val="([^"]+)"', xml))

    # ---- 1. 内容骨架 ----
    print("\n=== 1. 内容骨架 ===")
    print("  段落数(w:p)      :", len(re.findall(r"<w:p[ >]", xml)))
    print("  表格数(w:tbl)    :", xml.count("<w:tbl>"))
    print("  带边框表格数      :", len(re.findall(r"<w:tblBorders>", xml)))
    print("  图片/绘制对象     :", len(re.findall(r"<w:drawing>", xml)))
    print("  超链接            :", len(re.findall(r"<w:hyperlink[ >]", xml)))

    if HAS_PYDOCX:
        d = Document(path)
        nonempty = [p for p in d.paragraphs if p.text.strip()]
        print("  python-docx 复核 : %d 个非空段落 / %d 张表 / %d 个内联图"
              % (len(nonempty), len(d.tables), len(d.inline_shapes)))
        for i, t in enumerate(d.tables):
            print("     表%d: %d行 x %d列 | 表头: %s"
                  % (i + 1, len(t.rows), len(t.columns),
                     " / ".join(c.text[:12] for c in t.rows[0].cells)))

    # ---- 2. 段落级格式：首行缩进 / 引用块 ----
    print("\n=== 2. 段落级格式 ===")
    flc = re.findall(r'w:firstLineChars="(\d+)"', xml)
    fl = re.findall(r'w:firstLine="(\d+)"', xml)
    print("  首行缩进 firstLineChars:", len(flc), "处", sorted(set(flc))[:6])
    print("  首行缩进 firstLine     :", len(fl), "处", sorted(set(fl))[:6])
    print("  左缩进 w:ind left      :", len(re.findall(r'w:left="(\d+)"', xml)), "处")
    print("  引用块(左框线/竖线)    :",
          len(re.findall(r"<w:pBdr>", xml)), "处带段落边框")
    print("  段落底边框(分隔线)     :", len(re.findall(r'w:val="single"', xml)))

    # ---- 3. 标题层级承载方式 ----
    print("\n=== 3. 标题层级承载 ===")
    outl = collections.Counter(re.findall(r'<w:outlineLvl w:val="(\d+)"', xml))
    print("  outlineLvl 分布 :", dict(sorted(outl.items())) or "无")
    print("  实际使用的样式  :", dict(used) or "无")
    dangling = [k for k in used if k not in defined and used[k] and not k.isdigit()]
    if defined:
        heads = sorted(s for s in defined if "eading" in s or s in ("Title", "Subtitle"))
        print("  styles.xml 定义的标题样式:", heads[:10] or "无")
    else:
        print("  styles.xml 无任何命名样式（极简模板）")
    if xml.count("<w:pStyle") and not defined:
        print("  ⚠️ 有 pStyle 引用但样式未定义 —— 潜在悬空引用")
    if dangling:
        print("  ⚠️ 悬空样式引用:", dangling)

    navigation_ok = bool(outl) or bool(defined and heads)
    print("  → 导航窗格/目录可用:", "是" if navigation_ok else "否（无 outlineLvl 也无标题样式）")

    # ---- 4. 关键串命中 ----
    all_text = "\n".join(z.read(n).decode("utf-8", "replace")
                         for n in names if n.startswith("word/") and n.endswith(".xml"))
    if keys:
        print("\n=== 4. 关键串命中 ===")
        miss = []
        for k in keys:
            ok = k in all_text
            print(("  ✔ " if ok else "  ✘ ") + k)
            if not ok:
                miss.append(k)
    else:
        miss = []

    # ---- 结论 ----
    print("\n=== 结论 ===")
    problems = []
    if size < 2000:
        problems.append("体积过小")
    if xml.count("<w:tbl>") == 0 and "表格" in all_text:
        problems.append("疑似丢表")
    if not navigation_ok:
        problems.append("无层级信息")
    if miss:
        problems.append("关键串缺失: " + ", ".join(miss))
    if problems:
        print("  ⚠️ 需复核:", "; ".join(problems))
        return 1
    print("  ✔ 结构与内容核验通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
