"""Допоміжні функції оформлення пояснювальної записки (python-docx)."""
import re

from docx.enum.section import WD_SECTION
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Mm, Pt, RGBColor

FONT = "Times New Roman"
MONO = "Courier New"


def _rfonts(rpr_owner, name):
    rpr = rpr_owner.get_or_add_rPr() if hasattr(rpr_owner, "get_or_add_rPr") else rpr_owner
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts")
        rpr.insert(0, rf)
    for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rf.set(qn(a), name)


def setup_styles(doc):
    st = doc.styles

    def pstyle(name, base=None):
        try:
            s = st[name]
        except KeyError:
            s = st.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
        if base:
            s.base_style = st[base]
        return s

    body = pstyle("KR Body")
    body.font.name, body.font.size = FONT, Pt(14)
    _rfonts(body.element, FONT)
    pf = body.paragraph_format
    pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    pf.first_line_indent = Cm(1.25)
    pf.line_spacing = 1.5
    pf.space_before = pf.space_after = Pt(0)
    pf.widow_control = True

    for name, size, center, upper in (("Heading 1", 14, True, True), ("Heading 2", 14, False, False),
                                      ("Heading 3", 14, False, False)):
        h = st[name]
        h.font.name, h.font.size, h.font.bold = FONT, Pt(size), True
        h.font.italic = False
        h.font.color.rgb = RGBColor(0, 0, 0)
        h.font.all_caps = False
        _rfonts(h.element, FONT)
        f = h.paragraph_format
        f.alignment = WD_ALIGN_PARAGRAPH.CENTER if center else WD_ALIGN_PARAGRAPH.LEFT
        f.first_line_indent = Cm(0) if center else Cm(1.25)
        f.left_indent = Cm(0)
        f.line_spacing = 1.5
        f.space_before = Pt(0 if center else 12)
        f.space_after = Pt(12 if center else 6)
        f.keep_with_next = True
        f.page_break_before = center
        pPr = h.element.get_or_add_pPr()
        for old in pPr.findall(qn("w:outlineLvl")):
            pPr.remove(old)
        ol = OxmlElement("w:outlineLvl")
        ol.set(qn("w:val"), str(int(name[-1]) - 1))
        pPr.append(ol)

    cap = pstyle("KR Caption")
    cap.font.name, cap.font.size = FONT, Pt(14)
    _rfonts(cap.element, FONT)
    f = cap.paragraph_format
    f.alignment = WD_ALIGN_PARAGRAPH.LEFT
    f.first_line_indent = Cm(0)
    f.line_spacing = 1.0
    f.space_before, f.space_after = Pt(6), Pt(6)
    f.keep_with_next = True

    tbl = pstyle("KR Table")
    tbl.font.name, tbl.font.size = FONT, Pt(12)
    _rfonts(tbl.element, FONT)
    f = tbl.paragraph_format
    f.alignment = WD_ALIGN_PARAGRAPH.LEFT
    f.first_line_indent = Cm(0)
    f.line_spacing = 1.0
    f.space_before = f.space_after = Pt(0)

    code = pstyle("KR Code")
    code.font.name, code.font.size = MONO, Pt(10)
    _rfonts(code.element, MONO)
    f = code.paragraph_format
    f.alignment = WD_ALIGN_PARAGRAPH.LEFT
    f.first_line_indent = Cm(0)
    f.left_indent = Cm(0.5)
    f.line_spacing = 1.0
    f.space_before = f.space_after = Pt(0)

    toc = pstyle("KR TOC")
    toc.font.name, toc.font.size = FONT, Pt(14)
    for lvl in (1, 2):
        try:
            t = st[f"TOC {lvl}"] if f"TOC {lvl}" in [s.name for s in st] else st.add_style(f"toc {lvl}", WD_STYLE_TYPE.PARAGRAPH)
        except Exception:
            continue
        t.font.name, t.font.size = FONT, Pt(14)
        _rfonts(t.element, FONT)
        t.paragraph_format.line_spacing = 1.5
        t.paragraph_format.left_indent = Cm(0 if lvl == 1 else 0.75)
        t.paragraph_format.space_after = Pt(0)


class Writer:
    def __init__(self, doc):
        self.doc = doc
        self.fig = {}
        self.tab = {}

    # ---------- текст ----------
    def _runs(self, p, text, bold=False, italic=False, size=None, font=None):
        # **жирний**, `моно`
        for part in re.split(r"(\*\*[^*]+\*\*|`[^`]+`)", text):
            if not part:
                continue
            if part.startswith("**"):
                r = p.add_run(part[2:-2]); r.bold = True
            elif part.startswith("`"):
                r = p.add_run(part[1:-1]); r.font.name = MONO; _rfonts(r._element, MONO)
                r.font.size = Pt(12) if (size is None or size >= 12) else Pt(size)
            else:
                r = p.add_run(part); r.bold = bold or None
            if italic:
                r.italic = True
            if size and not part.startswith("`"):
                r.font.size = Pt(size)
        return p

    def p(self, text, **kw):
        return self._runs(self.doc.add_paragraph(style="KR Body"), text, **kw)

    def center(self, text, bold=False, size=14, space_after=0, keep=False):
        p = self.doc.add_paragraph(style="KR Body")
        p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.first_line_indent = Cm(0)
        p.paragraph_format.space_after = Pt(space_after)
        p.paragraph_format.keep_with_next = keep
        self._runs(p, text, bold=bold, size=size)
        return p

    def bullets(self, items):
        for it in items:
            self.p("– " + it)

    def h1(self, text):
        return self.doc.add_paragraph(text, style="Heading 1")

    def h1_unnumbered(self, text):
        return self.h1(text)

    def h2(self, text):
        return self.doc.add_paragraph(text, style="Heading 2")

    def h3(self, text):
        return self.doc.add_paragraph(text, style="Heading 3")

    def page_break(self):
        self.doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    # ---------- код ----------
    def code(self, text, size=10):
        lines = text.rstrip("\n").split("\n")
        longest = max((len(l.replace("\t", "    ")) for l in lines), default=1)
        fit = 455 / (0.6 * max(longest, 1))  # ширина рядка ~455 pt; Courier: 0,6 em на символ
        size = max(6.5, min(size, int(fit * 2) / 2))
        for i, line in enumerate(lines):
            p = self.doc.add_paragraph(style="KR Code")
            r = p.add_run(line.replace("\t", "    ") if line else " ")
            r.font.size = Pt(size)
            if i < len(lines) - 1 and len(lines) <= 40:
                p.paragraph_format.keep_with_next = True
        sp = self.doc.add_paragraph(style="KR Code")
        sp.paragraph_format.space_after = Pt(6)

    # ---------- таблиці ----------
    def table(self, title, header, rows, widths_cm, number, font_size=12, bold_first_col=False):
        cap = self.doc.add_paragraph(style="KR Caption")
        self._runs(cap, f"Таблиця {number} — {title}" if number else title)
        t = self.doc.add_table(rows=1, cols=len(header))
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        set_table_borders(t)
        t.autofit = False
        for i, h in enumerate(header):
            c = t.rows[0].cells[i]
            c.width = Cm(widths_cm[i])
            c.paragraphs[0].style = self.doc.styles["KR Table"]
            c.paragraphs[0].paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
            self._runs(c.paragraphs[0], str(h), bold=True, size=font_size)
            shade(c, "D9E2F3")
        mark_header(t.rows[0])
        for row in rows:
            cells = t.add_row().cells
            for i, v in enumerate(row):
                cells[i].width = Cm(widths_cm[i])
                par = cells[i].paragraphs[0]
                par.style = self.doc.styles["KR Table"]
                lines = str(v if v is not None else "").split("\n")
                for j, line in enumerate(lines):
                    if j:
                        par = cells[i].add_paragraph(style="KR Table")
                    self._runs(par, line, bold=(bold_first_col and i == 0), size=font_size)
        set_col_widths(t, widths_cm)
        after = self.doc.add_paragraph(style="KR Code")
        after.paragraph_format.space_after = Pt(6)
        return t

    def figure(self, path, title, number, width_cm=16.5, new_page=False):
        p = self.doc.add_paragraph(style="KR Body")
        p.paragraph_format.page_break_before = new_page
        p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.first_line_indent = Cm(0)
        p.paragraph_format.keep_with_next = True
        p.add_run().add_picture(str(path), width=Cm(width_cm))
        cap = self.doc.add_paragraph(style="KR Caption")
        cap.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap.paragraph_format.keep_with_next = False
        cap.paragraph_format.space_after = Pt(12)
        self._runs(cap, f"Рисунок {number} — {title}")


def shade(cell, color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), color)
    tcPr.append(shd)


def mark_header(row):
    trPr = row._tr.get_or_add_trPr()
    h = OxmlElement("w:tblHeader")
    h.set(qn("w:val"), "true")
    trPr.append(h)
    cs = OxmlElement("w:cantSplit")
    trPr.append(cs)


def set_table_borders(table):
    tblPr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "000000")
        borders.append(el)
    tblPr.append(borders)
    mar = OxmlElement("w:tblCellMar")
    for side, v in (("left", 70), ("right", 70)):
        e = OxmlElement(f"w:{side}")
        e.set(qn("w:w"), str(v))
        e.set(qn("w:type"), "dxa")
        mar.append(e)
    tblPr.append(mar)


def set_col_widths(table, widths_cm):
    tbl = table._tbl
    grid = tbl.tblGrid
    for i, gc in enumerate(grid.findall(qn("w:gridCol"))):
        gc.set(qn("w:w"), str(int(widths_cm[i] * 567)))
    tblPr = tbl.tblPr
    tw = OxmlElement("w:tblW")
    tw.set(qn("w:w"), str(int(sum(widths_cm) * 567)))
    tw.set(qn("w:type"), "dxa")
    for old in tblPr.findall(qn("w:tblW")):
        tblPr.remove(old)
    tblPr.append(tw)
    for old in tblPr.findall(qn("w:tblLayout")):
        tblPr.remove(old)
    lay = OxmlElement("w:tblLayout")
    lay.set(qn("w:type"), "fixed")
    tblPr.append(lay)
    order = ["tblStyle", "tblpPr", "tblOverlap", "bidiVisual", "tblStyleRowBandSize",
             "tblStyleColBandSize", "tblW", "jc", "tblCellSpacing", "tblInd", "tblBorders", "shd",
             "tblLayout", "tblCellMar", "tblLook", "tblCaption", "tblDescription"]
    kids = list(tblPr)
    for k in kids:
        tblPr.remove(k)
    for k in sorted(kids, key=lambda e: order.index(e.tag.split("}")[1]) if e.tag.split("}")[1] in order else 99):
        tblPr.append(k)


def add_field(paragraph, instr, placeholder=""):
    r = paragraph.add_run()
    b = OxmlElement("w:fldChar"); b.set(qn("w:fldCharType"), "begin"); r._r.append(b)
    r2 = paragraph.add_run()
    it = OxmlElement("w:instrText"); it.set(qn("xml:space"), "preserve"); it.text = instr; r2._r.append(it)
    r3 = paragraph.add_run()
    s = OxmlElement("w:fldChar"); s.set(qn("w:fldCharType"), "separate"); r3._r.append(s)
    r4 = paragraph.add_run(placeholder)
    r5 = paragraph.add_run()
    e = OxmlElement("w:fldChar"); e.set(qn("w:fldCharType"), "end"); r5._r.append(e)
    return r4
