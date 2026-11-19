---
name: md-to-pdf-cjk
description: Convert Markdown files to professional PDF documents with full CJK (Chinese/Japanese/Korean) support. Uses reportlab for reliable rendering without external dependencies like wkhtmltopdf or LaTeX.
author: zacjiang
version: 1.0.1
tags: markdown, pdf, chinese, japanese, korean, CJK, convert, report, document
display_name: "md-to-pdf-cjk"
display_name_en: "md-to-pdf-cjk"
description_zh: "Convert Markdown files to professional PDF documents with full CJK (Chinese/Japanese/Korean) support. Uses reportlab for reliable rendering without external dependencies like wkhtmltopdf or LaTeX."
description_en: "Convert Markdown files to professional PDF documents with full CJK (Chinese/Japanese/Korean) support. Uses reportlab for reliable rendering without external dependencies like wkhtmltopdf or LaTeX."
visibility: "public"
---

# Markdown to PDF (CJK Support)

Convert Markdown to professional PDFs with full Chinese/Japanese/Korean text support.

## Why This Exists

Most Markdown-to-PDF tools break on CJK characters, require LaTeX, or need heavy dependencies. This skill uses reportlab for lightweight, reliable PDF generation that works on any server — including 2GB RAM VPS instances.

## Usage

```bash
python3 {baseDir}/scripts/md_to_pdf.py input.md output.pdf
python3 {baseDir}/scripts/md_to_pdf.py input.md "Document Title" output.pdf
python3 {baseDir}/scripts/md_to_pdf.py input.md output.pdf --font /path/to/CJKFont.ttf
```

First argument = input, last = output; an optional middle argument is printed as the title.
Exit codes: 0 ok, 1 bad arguments, 2 no usable embeddable CJK font, 3 embedding self-check failed.
Only exit 0 may lead to delivery, and only after the visual check below.

## Features

- ✅ CJK text rendered with an **embedded** TrueType font (never a silent fallback)
- ✅ Markdown headings, bold, italic, bullet/numbered lists, quote blocks, code blocks
- ✅ Tables whose cells wrap inside the page width; header row repeats across pages
- ✅ Automatic page breaks
- ✅ Lightweight — runs on minimal servers (2GB RAM)
- ✅ No LaTeX, no wkhtmltopdf, no Chrome/Puppeteer needed

## Supported Markdown Elements

- `# H1` through `#### H4` headings (deeper levels render as H4)
- `**bold**` and `*italic*`
- `- bullet lists` and `1. numbered lists` (single level)
- `> quote blocks`
- `| table | rows |` (pipe-delimited tables)
- `` `inline code` `` and ``` code blocks ```
- `---` horizontal rules

## Dependencies

```bash
pip3 install reportlab          # required
pip3 install pymupdf            # recommended: embedding self-check and page rendering
```

## Font Configuration

The script scans the standard font directories of Linux, macOS and Windows (or only the
file given with `--font`) and accepts a font only if reportlab can embed it **and** it covers
every CJK character the document uses. Symbol-only fonts fail the coverage test. If nothing
qualifies it stops with exit 2 and install guidance — it does not fall back to Helvetica or
to a non-embedded CID font.

Noto/Source Han CJK `.ttc`/`.otf` use CFF outlines that reportlab cannot embed; install a
TrueType CJK font instead (e.g. `fonts-wqy-microhei` on Debian/Ubuntu). Ask before installing
system packages. Full rules: `references/font-and-delivery.md`.

## Delivery Check (required)

Text extraction does not prove glyphs are drawn. Before reporting success, render every
page to PNG in a fresh directory, look at each image, and confirm CJK text, quote blocks,
long tables (wrapping + page continuation) and pagination. If you could not view the
images, say the PDF was not visually verified. Never claim an OS or viewer was tested
unless it was. Procedure: `references/font-and-delivery.md`.

## Use Cases

- Generate PDF reports from AI analysis (audit reports, summaries)
- Convert documentation to distributable format
- Create invoices, proposals, or contracts in CJK languages
- Batch convert multiple Markdown files to PDF
