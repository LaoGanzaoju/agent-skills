# Font selection and delivery checks

## How `scripts/md_to_pdf.py` picks a font

1. If `--font FILE` is given, only that file is tried.
2. Otherwise it scans the OS-standard font directories for `.ttf` / `.ttc` / `.otf`:
   - Linux: `/usr/share/fonts`, `/usr/local/share/fonts`, `~/.fonts`, `~/.local/share/fonts`
   - macOS: `/System/Library/Fonts` (+ `Supplemental`), `/Library/Fonts`, `~/Library/Fonts`
   - Windows: `%WINDIR%\Fonts`, `%LOCALAPPDATA%\Microsoft\Windows\Fonts`
3. A file is accepted only if **both** hold:
   - reportlab can load it as an embeddable TrueType font (each sub-font of a `.ttc` is tried);
   - its character map covers **every** CJK character (Han, kana, hangul, CJK/full-width
     punctuation) that the document and title actually use.
   Symbol-only fallback fonts, Latin-only fonts and math fonts fail the coverage test, so no
   name list is needed to exclude them.
4. Other non-ASCII characters the font lacks (curly quotes, dashes, arrows...) produce a
   `warning:` listing their code points: they will show as blank boxes. Replace them in the
   Markdown or choose a font with `--font` that covers them.
5. No accepted font → **exit 2** with install guidance. There is no fallback to Helvetica or
   to non-embedded CID fonts (e.g. STSong-Light): those render as blanks/garbage on viewers
   without the font, and that is the failure this policy prevents.

### Fonts that do NOT work with reportlab

Noto Sans/Serif CJK and Source Han `.ttc`/`.otf` use CFF (PostScript) outlines. reportlab
rejects them, so a machine with only those packages still gets exit 2. Install a
TrueType-outline CJK font instead:

| Platform | Typical choice |
|---|---|
| Debian/Ubuntu | `fonts-wqy-microhei` or `fonts-wqy-zenhei` (apt) |
| RHEL/Fedora | `wqy-microhei-fonts` / `wqy-zenhei-fonts` (names vary by release) |
| macOS | system fonts are scanned; if none qualifies, pass a TrueType CJK file via `--font` |
| Windows | system fonts (e.g. YaHei / SimSun collections) are scanned; else `--font` |

Package names differ between distributions and releases; if the package is not found, report
that instead of guessing further. Installing system packages changes the user's machine: ask first. If installation is not
possible, report that no PDF with embedded CJK text could be produced.

## Exit codes

| Code | Meaning | Action |
|---|---|---|
| 0 | PDF written, every text-drawing font embedded | do the visual check below |
| 1 | bad arguments / input missing | fix the command |
| 2 | no embeddable font covering the document | install a font or pass `--font`; do not deliver |
| 3 | PDF written but self-check found non-embedded text fonts | do not deliver; investigate |

The self-check uses PyMuPDF when available (fonts used by text spans vs. embedded fonts).
Without PyMuPDF it falls back to a byte scan, which is weaker: say so in the report.

## Delivery checklist (required before telling the user the PDF is ready)

Text extraction (pypdf, `pdftotext`, `get_text`) only proves the characters are in the file;
it does **not** prove they are drawn. A visual check is required:

1. Render every page to PNG into a new, empty directory next to the output (never reuse an
   old render directory, so stale images cannot be mistaken for the new ones), e.g.:
   ```python
   import pymupdf, os
   doc = pymupdf.open("output.pdf")
   out = "output_pages"; os.makedirs(out)          # fails if it exists: pick a new name
   for i, page in enumerate(doc, 1):
       page.get_pixmap(dpi=100).save(os.path.join(out, "p%03d.png" % i))
   ```
   `pdftoppm -r 100 -png output.pdf output_pages/p` works too.
2. Open and look at each page image. Confirm:
   - CJK text is real glyphs (no boxes, blanks, mojibake or repeated placeholder shapes);
   - quote blocks, lists and code blocks are rendered and readable;
   - long tables wrap inside the page width and continue across pages with the header row;
   - page breaks do not cut off or overlap content; page count is plausible.
3. Report honestly:
   - what was checked and how (self-check result + which pages were viewed);
   - if images could not be viewed, or no renderer was available, state that the PDF was
     **not visually verified**;
   - only name operating systems / viewers you actually tested on.
4. Remove the render directory afterwards if the user does not need it.
