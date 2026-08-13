#!/usr/bin/env python3
"""Render the PeerForge documentation set to PDF.

Written rather than shelled out to pandoc because these documents lean hard on
two things a naive converter mangles: wide tables, and ASCII architecture
diagrams that must keep their alignment. Diagrams are laid out in a monospaced
frame and auto-shrunk to fit rather than wrapped.
"""
import html
import re
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Frame, HRFlowable, KeepTogether, ListFlowable, ListItem,
    NextPageTemplate, PageBreak, PageTemplate, Paragraph, Preformatted,
    Spacer, Table, TableStyle,
)

INK      = colors.HexColor("#1a1a1a")
MUTED    = colors.HexColor("#5b6470")
ACCENT   = colors.HexColor("#1f4e79")
RULE     = colors.HexColor("#d6dae0")
CODE_BG  = colors.HexColor("#f5f6f8")
HEAD_BG  = colors.HexColor("#eef1f5")

# The built-in Type 1 fonts are Latin-1 only: every box-drawing character in
# the architecture diagrams (─ │ ► └ ├ ▼) was silently dropped from the PDF
# stream — verified, not assumed. DejaVu covers them, so register the real
# family and use it throughout.
_DEJAVU = Path("/usr/share/fonts/truetype/dejavu")
_LIB = Path("/usr/share/fonts/truetype/liberation")

def _register_fonts():
    """Register each face independently.

    An all-or-nothing try/except here fell back to Latin-1 Helvetica for the
    whole set because ONE file (DejaVuSans-Oblique.ttf) is absent on this box —
    discarding three fonts that had registered perfectly well. Register each,
    and substitute only what is genuinely missing.
    """
    def reg(name, filename):
        for root in (_DEJAVU, _LIB):
            path = root / filename
            if path.exists():
                try:
                    pdfmetrics.registerFont(TTFont(name, str(path)))
                    return True
                except Exception:
                    pass
        return False

    sans   = "DejaVu"     if reg("DejaVu", "DejaVuSans.ttf")           else "Helvetica"
    bold   = "DejaVu-B"   if reg("DejaVu-B", "DejaVuSans-Bold.ttf")    else "Helvetica-Bold"
    italic = "DejaVu-I"   if reg("DejaVu-I", "DejaVuSans-Oblique.ttf") else bold
    mono   = "DejaVuMono" if reg("DejaVuMono", "DejaVuSansMono.ttf")   else "Courier"

    if sans.startswith("DejaVu"):
        pdfmetrics.registerFontFamily(
            sans, normal=sans, bold=bold, italic=italic, boldItalic=bold)
    if mono == "Courier":
        print("  WARNING: no Unicode mono font — diagrams will lose box-drawing glyphs")
    return sans, bold, italic, mono


SANS, SANS_B, SANS_I, MONO = _register_fonts()

PAGE_W, PAGE_H = A4
MARGIN = 20 * mm


def styles():
    """One explicit style per role — no shared **base, which collided with the
    per-style overrides for face and colour."""
    def P(name, **kw):
        kw.setdefault("fontName", SANS)
        kw.setdefault("textColor", INK)
        kw.setdefault("alignment", TA_LEFT)
        return ParagraphStyle(name, **kw)

    return {
        "title":  P("t",  fontName=SANS_B, fontSize=23, leading=28,
                    spaceAfter=4, textColor=ACCENT),
        "h1":     P("h1", fontName=SANS_B, fontSize=15.5, leading=20,
                    spaceBefore=17, spaceAfter=7, textColor=ACCENT),
        "h2":     P("h2", fontName=SANS_B, fontSize=12.5, leading=16,
                    spaceBefore=13, spaceAfter=5),
        "h3":     P("h3", fontName=SANS_B, fontSize=10.8, leading=14,
                    spaceBefore=10, spaceAfter=4),
        "body":   P("b",  fontSize=9.6, leading=14.2, spaceAfter=6),
        "bullet": P("bu", fontSize=9.6, leading=14),
        "quote":  P("q",  fontSize=9.6, leading=14.4, leftIndent=9,
                    borderPadding=(6, 6, 6, 9), backColor=CODE_BG,
                    textColor=MUTED, spaceAfter=7),
        "cellh":  P("ch", fontName=SANS_B, fontSize=8.4, leading=11),
        "cell":   P("cl", fontSize=8.4, leading=11),
        "foot":   P("f",  fontSize=7.6, textColor=MUTED),
    }


# ── inline markdown ────────────────────────────────────────────────────────
def inline(text: str) -> str:
    """Markdown emphasis → ReportLab markup, escaping everything else."""
    out, i, n = [], 0, len(text)
    while i < n:
        # `code`
        if text[i] == "`":
            j = text.find("`", i + 1)
            if j > 0:
                out.append(f'<font face="{MONO}" size="8.6" backColor="#f0f1f4">'
                           + html.escape(text[i + 1:j]) + "</font>")
                i = j + 1
                continue
        # **bold**  /  *italic*  /  _italic_
        for mark, tag in (("**", "b"), ("*", "i"), ("__", "b"), ("_", "i")):
            if text.startswith(mark, i):
                j = text.find(mark, i + len(mark))
                if j > 0:
                    out.append(f"<{tag}>{inline(text[i + len(mark):j])}</{tag}>")
                    i = j + len(mark)
                    break
        else:
            out.append(html.escape(text[i]))
            i += 1
            continue
    s = "".join(out)
    # [label](url) — keep the label, drop the plumbing
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<font color="#1f4e79">\1</font>', s)
    return s


def code_block(lines, avail_w):
    """Monospaced, whitespace-preserved, shrunk to fit rather than wrapped.

    The architecture diagrams are the reason this exists: wrapping one destroys
    the alignment that carries the meaning.
    """
    widest = max((len(l) for l in lines), default=1)
    size = 8.2
    # DejaVu Sans Mono advance width is 0.602 em
    while size > 4.6 and widest * size * 0.6 > avail_w - 14:
        size -= 0.2
    st = ParagraphStyle("code", fontName=MONO, fontSize=size,
                        leading=size * 1.28, textColor=INK)
    body = Preformatted("\n".join(lines), st)
    t = Table([[body]], colWidths=[avail_w])
    t.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, -1), CODE_BG),
        ("BOX",         (0, 0), (-1, -1), 0.5, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING",(0, 0), (-1, -1), 7),
        ("TOPPADDING",  (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
    ]))
    return t


def build_table(rows, S, avail_w):
    header, body = rows[0], rows[1:]
    ncols = len(header)
    # Weight columns by the content they must carry, within sane bounds.
    weights = []
    for c in range(ncols):
        longest = max([len(header[c])] + [len(r[c]) for r in body if c < len(r)] or [1])
        weights.append(max(6, min(longest, 60)))
    total = sum(weights) or 1
    widths = [avail_w * w / total for w in weights]

    data = [[Paragraph(inline(c), S["cellh"]) for c in header]]
    for r in body:
        r = (r + [""] * ncols)[:ncols]
        data.append([Paragraph(inline(c), S["cell"]) for c in r])

    t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), HEAD_BG),
        ("LINEBELOW",    (0, 0), (-1, 0), 0.7, RULE),
        ("INNERGRID",    (0, 0), (-1, -1), 0.25, RULE),
        ("BOX",          (0, 0), (-1, -1), 0.5, RULE),
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafbfc")]),
    ]))
    return t


def render(md: str, S, avail_w):
    story, lines, i = [], md.split("\n"), 0
    pending_list, list_ordered = [], False

    def flush_list():
        nonlocal pending_list
        if pending_list:
            story.append(ListFlowable(
                [ListItem(Paragraph(x, S["bullet"]), leftIndent=13) for x in pending_list],
                bulletType="1" if list_ordered else "bullet",
                bulletFontSize=8, leftIndent=13, spaceBefore=1, spaceAfter=6,
            ))
            pending_list = []

    while i < len(lines):
        ln = lines[i]

        if ln.strip().startswith("```"):
            flush_list()
            i += 1
            buf = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i].rstrip())
                i += 1
            i += 1
            if buf:
                story.append(Spacer(1, 3))
                story.append(code_block(buf, avail_w))
                story.append(Spacer(1, 7))
            continue

        if ln.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:\-|]+\|?\s*$", lines[i + 1]):
            flush_list()
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                if not re.match(r"^\|[\s:\-|]+\|?\s*$", lines[i]):
                    rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            if rows:
                story.append(Spacer(1, 3))
                story.append(build_table(rows, S, avail_w))
                story.append(Spacer(1, 9))
            continue

        if re.match(r"^\s*(---|===|\*\*\*)\s*$", ln):
            flush_list()
            story.append(Spacer(1, 5))
            story.append(HRFlowable(width="100%", thickness=0.6, color=RULE))
            story.append(Spacer(1, 7))
            i += 1
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", ln)
        if m:
            flush_list()
            lvl, txt = len(m.group(1)), m.group(2).strip()
            key = "title" if lvl == 1 else ("h1" if lvl == 2 else ("h2" if lvl == 3 else "h3"))
            story.append(Paragraph(inline(txt), S[key]))
            i += 1
            continue

        if ln.strip().startswith(">"):
            flush_list()
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            story.append(Paragraph(inline(" ".join(buf)), S["quote"]))
            continue

        m = re.match(r"^\s*[-*+]\s+(.*)$", ln)
        if m:
            if pending_list and list_ordered:
                flush_list()
            list_ordered = False
            pending_list.append(inline(m.group(1)))
            i += 1
            continue

        m = re.match(r"^\s*\d+[.)]\s+(.*)$", ln)
        if m:
            if pending_list and not list_ordered:
                flush_list()
            list_ordered = True
            pending_list.append(inline(m.group(1)))
            i += 1
            continue

        if not ln.strip():
            flush_list()
            i += 1
            continue

        flush_list()
        buf = []
        while i < len(lines) and lines[i].strip() and not re.match(
                r"^(#{1,6}\s|\||```|>|\s*[-*+]\s|\s*\d+[.)]\s|---\s*$)", lines[i]):
            buf.append(lines[i].strip())
            i += 1
        if buf:
            story.append(Paragraph(inline(" ".join(buf)), S["body"]))

    flush_list()
    return story


def make_pdf(md_path: Path, out_path: Path, subtitle: str):
    S = styles()
    avail_w = PAGE_W - 2 * MARGIN
    md = md_path.read_text(encoding="utf-8")
    title = md.split("\n", 1)[0].lstrip("# ").strip() or md_path.stem

    def decorate(canvas, doc):
        canvas.saveState()
        canvas.setFont(SANS, 7.6)
        canvas.setFillColor(MUTED)
        canvas.drawString(MARGIN, 12 * mm, "PeerForge — " + subtitle)
        canvas.drawRightString(PAGE_W - MARGIN, 12 * mm, f"{doc.page}")
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.4)
        canvas.line(MARGIN, 15 * mm, PAGE_W - MARGIN, 15 * mm)
        canvas.restoreState()

    doc = BaseDocTemplate(
        str(out_path), pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=22 * mm,
        title=title, author="PeerForge", subject=subtitle,
    )
    frame = Frame(MARGIN, 22 * mm, avail_w, PAGE_H - MARGIN - 22 * mm, id="main")
    doc.addPageTemplates([PageTemplate(id="all", frames=[frame], onPage=decorate)])
    doc.build(render(md, S, avail_w))
    return out_path


DOCS = [
    ("USER_MANUAL.md",  "User Manual"),
    ("FEATURES.md",     "Features and Functionality"),
    ("ARCHITECTURE.md", "Technical Architecture"),
    ("MARKETING.md",    "Marketing"),
    ("PITCH_DECK.md",   "Pitch Deck"),
]

if __name__ == "__main__":
    here = Path(__file__).parent
    out = here / "pdf"
    out.mkdir(exist_ok=True)
    for name, subtitle in DOCS:
        src = here / name
        if not src.exists():
            print(f"  MISSING {name}")
            continue
        dst = out / (src.stem + ".pdf")
        make_pdf(src, dst, subtitle)
        print(f"  {dst.name:24} {dst.stat().st_size // 1024:>5} KB")
