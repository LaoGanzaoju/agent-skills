#!/usr/bin/env python3
"""Convert Markdown to PDF with an embedded CJK font.

Usage:
    python3 md_to_pdf.py <input.md> <output.pdf> [--font FONT_FILE]
    python3 md_to_pdf.py <input.md> "<Document Title>" <output.pdf> [--font FONT_FILE]

First positional = input, last positional = output, a middle positional (if
any) = title rendered at the top. The output path is used exactly as given.

Font policy (details: references/font-and-delivery.md):
  * Candidates come from --font, else the platform-standard font directories.
  * A candidate is accepted only if reportlab can load it for embedding AND it
    maps every CJK character (Han / kana / hangul / CJK punctuation) used by
    the document. Symbol-only or Latin-only fonts fail this check by glyph
    coverage, not by file name.
  * No accepted font -> exit 2 with install guidance. The script never falls
    back to a non-embedded CID font (e.g. STSong-Light) or to Helvetica.

Exit codes: 0 ok | 1 bad arguments/input | 2 no usable embeddable CJK font |
            3 PDF written but the embedding self-check failed (do not deliver)
"""
import os
import re
import sys

# Probe used when the document has no CJK characters (skill is CJK-oriented).
FALLBACK_PROBE = "\u4e2d\u6587"

# Only colour-emoji files are skipped by name (huge, never text faces). Every
# other exclusion is decided by real glyph coverage.
NAME_SKIP_HINTS = ("emoji",)

# Name fragments that usually denote CJK text faces; used ONLY to try those
# files first, never to accept or reject a file.
NAME_PRIORITY_HINTS = (
    "cjk", "han", "hei", "song", "ming", "kai", "fang", "gothic", "mincho",
    "yahei", "msyh", "simsun", "simhei", "pingfang", "hiragino", "stheiti",
    "wqy", "noto", "source", "droidsansfallback", "unicode", "malgun",
    "nanum", "meiryo", "yugoth",
)

# OS-convention font directories (identical on every machine of that OS).
FONT_DIRS = {
    "linux": ["/usr/share/fonts", "/usr/local/share/fonts",
              "~/.fonts", "~/.local/share/fonts"],
    "darwin": ["/System/Library/Fonts", "/System/Library/Fonts/Supplemental",
               "/Library/Fonts", "~/Library/Fonts"],
    "win32": [os.path.join(os.environ.get("WINDIR") or r"C:\Windows", "Fonts"),
              os.path.join(os.environ.get("LOCALAPPDATA") or "~",
                           "Microsoft", "Windows", "Fonts")],
}
FONT_EXTS = (".ttf", ".ttc", ".otf")
MAX_CANDIDATES = 300


def is_cjk(ch):
    cp = ord(ch)
    return (0x2E80 <= cp <= 0x9FFF or 0xAC00 <= cp <= 0xD7AF
            or 0xF900 <= cp <= 0xFAFF or 0xFF00 <= cp <= 0xFFEF
            or 0x20000 <= cp <= 0x3FFFF)


def chars_needed(text):
    """Return (required CJK chars, optional other non-ASCII chars)."""
    required, optional = set(), set()
    for ch in set(text):
        if ord(ch) <= 0x7F or ch.isspace():
            continue
        (required if is_cjk(ch) else optional).add(ch)
    return (required or set(FALLBACK_PROBE)), optional


def platform_font_dirs():
    if sys.platform.startswith("win"):
        key = "win32"
    elif sys.platform == "darwin":
        key = "darwin"
    else:
        key = "linux"
    out = []
    for raw in FONT_DIRS[key]:
        path = os.path.expanduser(raw)
        if os.path.isdir(path) and path not in out:
            out.append(path)
    return out


def iter_candidates():
    """Font files from platform dirs, CJK-looking names first, bounded."""
    first, rest, seen = [], [], set()
    for root in platform_font_dirs():
        for dirpath, dirnames, files in os.walk(root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for fn in files:
                low = fn.lower()
                if not low.endswith(FONT_EXTS) or any(h in low for h in NAME_SKIP_HINTS):
                    continue
                full = os.path.join(dirpath, fn)
                if full in seen:
                    continue
                seen.add(full)
                key = re.sub(r"[\s_\-]", "", low)
                (first if any(h in key for h in NAME_PRIORITY_HINTS) else rest).append(full)
    return (sorted(first) + sorted(rest))[:MAX_CANDIDATES]


def uncovered(font, chars):
    cmap = getattr(font.face, "charToGlyph", None) or {}
    return {ch for ch in chars if ord(ch) not in cmap}


def load_embeddable(path, required, max_subfonts=16):
    """Return a reportlab TTFont from `path` covering `required`, else None.

    For collections (.ttc) each sub-font is tried until one covers the
    document. Files reportlab cannot embed (e.g. CFF/PostScript outlines)
    raise on load and are rejected.
    """
    from reportlab.pdfbase.ttfonts import TTFont

    is_collection = path.lower().endswith(".ttc")
    for idx in range(max_subfonts if is_collection else 1):
        try:
            if is_collection:
                font = TTFont("CJKBody", path, subfontIndex=idx)
            else:
                font = TTFont("CJKBody", path)
        except Exception:
            # index 0 failing => format unsupported; later failure => end of collection
            return None
        if not uncovered(font, required):
            return font
    return None


def select_font(required, explicit=None):
    """Return (TTFont, path) or (None, reason)."""
    if explicit:
        if not os.path.isfile(explicit):
            return None, "--font file not found: %s" % explicit
        font = load_embeddable(explicit, required)
        if font is None:
            return None, ("--font %s cannot be embedded by reportlab or lacks "
                          "glyphs used by the document" % explicit)
        return font, explicit
    dirs = platform_font_dirs()
    candidates = iter_candidates()
    for path in candidates:
        font = load_embeddable(path, required)
        if font is not None:
            return font, path
    return None, ("searched %d font file(s) in %s; none is embeddable with "
                  "full coverage of the document's CJK characters"
                  % (len(candidates), ", ".join(dirs) or "(no font directories)"))


INSTALL_HINT = """\
Install a TrueType-outline CJK font, or pass one explicitly with --font FILE:
  Debian/Ubuntu : sudo apt install -y fonts-wqy-microhei   (or fonts-wqy-zenhei)
  RHEL/Fedora   : sudo dnf install -y wqy-microhei-fonts   (package names vary by release)
  macOS/Windows : system CJK fonts are searched automatically; if none qualifies,
                  pass a TrueType CJK font file with --font.
Note: Noto/Source Han CJK .ttc/.otf packages use CFF outlines, which reportlab
cannot embed, so having only those still ends in this error.
If installation is impossible or fails, tell the user that no PDF with
embedded CJK text could be produced; do not deliver a PDF made another way
without saying so."""


def parse_args(argv):
    """argv excludes the program name. Returns dict or raises ValueError."""
    font, pos, i = None, [], 0
    while i < len(argv):
        a = argv[i]
        if a == "--font":
            if i + 1 >= len(argv):
                raise ValueError("--font needs a file path")
            font = argv[i + 1]
            i += 2
            continue
        if a.startswith("--font="):
            font = a.split("=", 1)[1]
        else:
            pos.append(a)
        i += 1
    if len(pos) not in (2, 3):
        raise ValueError("expected <input.md> [\"Title\"] <output.pdf>")
    return {"input": pos[0], "output": pos[-1],
            "title": pos[1] if len(pos) == 3 else None, "font": font}


def clean_md(text):
    """Basic inline Markdown -> reportlab paragraph markup."""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"`(.+?)`", r'<font color="darkred">\1</font>', text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<![*\\])\*(?![\s*])([^*<>\n]+?)(?<![\s*])\*(?!\*)", r"<i>\1</i>", text)
    return text


def build_styles(font_name):
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib import colors

    base = dict(fontName=font_name, bulletFontName=font_name, wordWrap="CJK")
    return {
        "body": ParagraphStyle("body", fontSize=10, leading=15, **base),
        "title": ParagraphStyle("title", fontSize=18, leading=24, spaceAfter=12, **base),
        "h1": ParagraphStyle("h1", fontSize=16, leading=22, spaceBefore=14, spaceAfter=8, **base),
        "h2": ParagraphStyle("h2", fontSize=14, leading=19, spaceBefore=12, spaceAfter=6, **base),
        "h3": ParagraphStyle("h3", fontSize=12, leading=17, spaceBefore=10, spaceAfter=5, **base),
        "h4": ParagraphStyle("h4", fontSize=11, leading=16, spaceBefore=8, spaceAfter=4, **base),
        "quote": ParagraphStyle("quote", fontSize=10, leading=15, leftIndent=12,
                                textColor=colors.HexColor("#444444"),
                                borderColor=colors.HexColor("#bbbbbb"),
                                borderWidth=0, borderPadding=4,
                                backColor=colors.HexColor("#f3f3f3"), **base),
        "code": ParagraphStyle("code", fontSize=9, leading=13, leftIndent=8,
                               backColor=colors.HexColor("#f6f6f6"), **base),
        "cell": ParagraphStyle("cell", fontSize=9, leading=12, **base),
        "list": ParagraphStyle("list", fontSize=10, leading=15, leftIndent=14,
                               bulletIndent=4, **base),
    }


def make_table(rows, styles, avail_width):
    """Table whose cells are Paragraphs so long text wraps inside the page."""
    from reportlab.platypus import Paragraph, Table, TableStyle
    from reportlab.lib import colors

    ncols = max(len(r) for r in rows)
    rows = [r + [""] * (ncols - len(r)) for r in rows]
    # weight columns by their longest cell, with a floor so none collapses
    weights = [max(8, min(60, max(len(r[c]) for r in rows))) for c in range(ncols)]
    total = float(sum(weights))
    widths = [avail_width * w / total for w in weights]
    data = [[Paragraph(clean_md(c), styles["cell"]) for c in r] for r in rows]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e0e0e0")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


def render(content, title, out_path, font_name, bullet="\u2022"):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Preformatted

    styles = build_styles(font_name)
    doc = SimpleDocTemplate(out_path, pagesize=A4, leftMargin=20 * mm,
                            rightMargin=20 * mm, topMargin=20 * mm,
                            bottomMargin=20 * mm, title=title or "")
    story = []
    if title:
        story.append(Paragraph(clean_md(title), styles["title"]))

    table_rows, quote_lines, code_lines, in_code = [], [], [], False

    def flush():
        if table_rows:
            story.append(make_table(list(table_rows), styles, doc.width))
            story.append(Spacer(1, 6))
            del table_rows[:]
        if quote_lines:
            story.append(Paragraph("<br/>".join(clean_md(q) for q in quote_lines),
                                   styles["quote"]))
            story.append(Spacer(1, 6))
            del quote_lines[:]

    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("```"):
            flush()
            if in_code:
                story.append(Preformatted("\n".join(code_lines), styles["code"]))
                story.append(Spacer(1, 6))
                code_lines = []
            in_code = not in_code
            continue
        if in_code:
            code_lines.append(line.rstrip())
            continue
        if stripped.startswith("|"):
            if quote_lines:
                flush()
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if cells and all(c and set(c) <= set("-: ") for c in cells):
                continue  # separator row
            table_rows.append(cells)
            continue
        if stripped.startswith(">"):
            if table_rows:
                flush()
            quote_lines.append(stripped.lstrip(">").strip())
            continue
        flush()
        if not stripped:
            story.append(Spacer(1, 5))
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            level = len(m.group(1))
            key = {1: "h1", 2: "h2", 3: "h3"}.get(level, "h4")
            story.append(Paragraph(clean_md(m.group(2)), styles[key]))
        elif re.match(r"^[-*+]\s+", stripped):
            story.append(Paragraph(clean_md(re.sub(r"^[-*+]\s+", "", stripped)),
                                   styles["list"], bulletText=bullet))
        elif re.match(r"^\d+[.)]\s+", stripped):
            num, rest = re.match(r"^(\d+[.)])\s+(.*)$", stripped).groups()
            story.append(Paragraph(clean_md(rest), styles["list"], bulletText=num))
        elif re.match(r"^(-{3,}|\*{3,}|_{3,})$", stripped):
            story.append(Spacer(1, 12))
        else:
            story.append(Paragraph(clean_md(stripped), styles["body"]))
    if in_code and code_lines:
        story.append(Preformatted("\n".join(code_lines), styles["code"]))
    flush()
    doc.build(story)


def verify_embedding(pdf_path):
    """Return (ok, message). Every font that actually draws text must be embedded."""
    try:
        try:
            import pymupdf as fitz
        except ImportError:
            import fitz
    except ImportError:
        with open(pdf_path, "rb") as fh:
            data = fh.read()
        ok = b"/FontFile2" in data and b"STSong" not in data
        return ok, ("PyMuPDF not installed: byte scan only (%s); visual check "
                    "still required" % ("embedded font stream found" if ok
                                         else "no embedded TrueType stream"))
    try:
        doc = fitz.open(pdf_path)
        bad, pages = set(), doc.page_count
        for page in doc:
            embedded = {f[3].split("+")[-1] for f in page.get_fonts(full=True)
                        if f[0] and f[1] not in ("n/a", "")}
            used = set()
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        if span.get("text", "").strip():
                            used.add(span["font"].split("+")[-1])
            bad |= {u for u in used if u not in embedded}
        doc.close()
    except Exception as exc:  # corrupted output or PyMuPDF API mismatch
        return False, "self-check could not run: %s" % exc
    if bad:
        return False, "text drawn with non-embedded font(s): %s" % ", ".join(sorted(bad))
    return True, "%d page(s); all text-drawing fonts are embedded" % pages


def main(argv):
    try:
        args = parse_args(argv)
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 1
    if not os.path.isfile(args["input"]):
        print("error: input not found: %s" % args["input"], file=sys.stderr)
        return 1
    with open(args["input"], encoding="utf-8") as fh:
        content = fh.read()
    full_text = content + (args["title"] or "")
    required, optional = chars_needed(full_text)

    font, info = select_font(required, args["font"])
    if font is None:
        print("error: no usable embeddable CJK font (%s)" % info, file=sys.stderr)
        print(INSTALL_HINT, file=sys.stderr)
        return 2

    from reportlab.pdfbase import pdfmetrics
    pdfmetrics.registerFont(font)
    print("font: %s" % info)
    missing = sorted(uncovered(font, optional))
    if missing:
        print("warning: font lacks %d non-CJK character(s) used by the document "
              "(will render as blank boxes): %s"
              % (len(missing), " ".join("U+%04X" % ord(c) for c in missing)),
              file=sys.stderr)
    bullet = "\u2022" if not uncovered(font, "\u2022") else "-"

    out_dir = os.path.dirname(os.path.abspath(args["output"]))
    os.makedirs(out_dir, exist_ok=True)
    render(content, args["title"], args["output"], font.fontName, bullet)

    ok, msg = verify_embedding(args["output"])
    print("self-check: %s" % msg)
    if not ok:
        print("error: embedding self-check failed; do not deliver this PDF",
              file=sys.stderr)
        return 3
    print("%d bytes written to %s" % (os.path.getsize(args["output"]), args["output"]))
    print("next: render every page to an image and inspect it before delivery "
          "(see references/font-and-delivery.md)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
