"""
Експорт презентації в редагований PPTX:
  python presentation/export_pptx.py
1) kai-html-export (режим native) перетворює HTML-слайди на текстові поля, фігури й таблиці;
2) доопрацювання результату, бо експортер:
   - пише шрифти macOS (PingFang SC) — замінюємо на Segoe UI, як у HTML-версії;
   - переносить крапки навігації як фігури — прибираємо;
   - пропускає вбудовані зображення й HTML-графік — вставляємо скриншоти на ті самі місця
     та будуємо на слайді 8 нативні діаграми PowerPoint (значення редагуються).
"""
import io
import json
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
HTML = HERE / "Презентація_БД_Гогуля.html"
PPTX = HERE / "Презентація_БД_Гогуля.pptx"
EXPORTER = Path(r"D:\Programs\kai-html-export\scripts\export-native-pptx.py")
W, H = 1440, 810                 # розмір сторінки, у якому експортер вимірює слайди
PX_PER_IN = W / 13.33            # як у експортері (13,33 дюйма на 1440 px)
FONT = "Segoe UI"
C = {"card": RGBColor(0x16, 0x1B, 0x22), "border": RGBColor(0x30, 0x36, 0x3D),
     "text": RGBColor(0xE6, 0xED, 0xF3), "muted": RGBColor(0x8B, 0x94, 0x9E),
     "before": RGBColor(0x6E, 0x76, 0x81), "after": RGBColor(0x38, 0x8B, 0xFD),
     "green": RGBColor(0x3F, 0xB9, 0x50)}


def inch(px):
    return Inches(px / PX_PER_IN)


def measure_figures():
    """Координати фігур .kr-fig відносно свого слайда + знімки зображень (2x)."""
    figs = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=2)
        page.goto(HTML.as_uri(), wait_until="networkidle")
        page.add_style_tag(content="*{animation:none!important;transition:none!important}"
                                   ".reveal{opacity:1!important;transform:none!important}")
        for n in range(1, 11):
            page.evaluate(f"document.getElementById('slide-{n}').scrollIntoView()")
            page.wait_for_timeout(150)
            for fig in page.query_selector_all(f"#slide-{n} .kr-fig"):
                box = page.evaluate("""el => {const s = el.closest('.slide').getBoundingClientRect();
                    const r = el.getBoundingClientRect();
                    return {x: r.left - s.left, y: r.top - s.top, w: r.width, h: r.height}}""", fig)
                item = {"box": box, "chart": "kr-chart" in (fig.get_attribute("class") or "")}
                if not item["chart"]:
                    # знімок рамки з картинкою (без підпису) — це і є зображення слайда
                    frame = fig.query_selector(".kr-fig--browser") or fig.query_selector("img")
                    fb = page.evaluate("""el => {const s = el.closest('.slide').getBoundingClientRect();
                        const r = el.getBoundingClientRect();
                        return {x: r.left - s.left, y: r.top - s.top, w: r.width, h: r.height}}""", frame)
                    item["img_box"] = fb
                    item["png"] = frame.screenshot()
                    cap = fig.query_selector("figcaption")
                    item["caption"] = cap.inner_text() if cap else ""
                figs.setdefault(n, []).append(item)
        browser.close()
    return figs


def fix_fonts(prs):
    for slide in prs.slides:
        for shape in slide.shapes:
            frames = []
            if shape.has_text_frame:
                frames.append(shape.text_frame)
            if shape.has_table:
                frames += [c.text_frame for row in shape.table.rows for c in row.cells]
            for tf in frames:
                for para in tf.paragraphs:
                    for run in para.runs:
                        run.font.name = FONT
                        rpr = run._r.get_or_add_rPr()
                        for tag in ("a:ea", "a:cs"):
                            el = rpr.find(qn(tag))
                            if el is None:
                                el = rpr.makeelement(qn(tag), {})
                                rpr.append(el)
                            el.set("typeface", FONT)


def drop_nav_dots(prs):
    limit = prs.slide_width - Inches(0.5)
    for slide in prs.slides:
        for shape in list(slide.shapes):
            if shape.left > limit and shape.width < Inches(0.2) and shape.height < Inches(0.2):
                shape._element.getparent().remove(shape._element)


def left_align_tables(prs):
    """Експортер переносить таблиці як фігури-комірки з текстом по центру;
    широкі комірки (колонка «Факт») вирівнюємо ліворуч, як у HTML."""
    for slide in prs.slides:
        for shape in slide.shapes:
            if (shape.shape_type == 1 and shape.has_text_frame and shape.text_frame.text.strip()
                    and shape.width > Inches(4)
                    and all(p.alignment == PP_ALIGN.CENTER for p in shape.text_frame.paragraphs)):
                shape.text_frame.margin_left = Inches(0.12)
                for para in shape.text_frame.paragraphs:
                    para.alignment = PP_ALIGN.LEFT


def add_caption(slide, x, y, w, text):
    tb = slide.shapes.add_textbox(inch(x), inch(y), inch(w), inch(22))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    r = tf.paragraphs[0].add_run()
    r.text = text
    r.font.size, r.font.name, r.font.color.rgb = Pt(10), FONT, C["muted"]


def add_picture(slide, item):
    b = item["img_box"]
    slide.shapes.add_picture(io.BytesIO(item["png"]), inch(b["x"]), inch(b["y"]), inch(b["w"]), inch(b["h"]))
    if item["caption"]:
        add_caption(slide, b["x"], b["y"] + b["h"] + 8, b["w"], item["caption"])


def add_perf_charts(slide, box):
    perf = json.loads((ROOT / "bd" / "protocols" / "09_performance.json").read_text(encoding="utf-8"))
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, inch(box["x"]), inch(box["y"]),
                                  inch(box["w"]), inch(box["h"]))
    card.adjustments[0] = 0.03
    card.fill.solid()
    card.fill.fore_color.rgb = C["card"]
    card.line.color.rgb = C["border"]
    card.line.width = Pt(0.75)
    pad, x0, inner_w = 22, box["x"] + 22, box["w"] - 44
    block_h = (box["h"] - 2 * pad - 30) / 2
    names = {"P1": "P1 · останні роботи студента", "P2": "P2 · агрегат за завданнями"}
    for i, key in enumerate(("P1", "P2")):
        b, a = perf[key]["before"]["median_ms"], perf[key]["after"]["median_ms"]
        y0 = box["y"] + pad + i * block_h
        head = slide.shapes.add_textbox(inch(x0), inch(y0), inch(inner_w), inch(30)).text_frame
        head.margin_left = head.margin_right = 0
        r = head.paragraphs[0].add_run()
        r.text, r.font.size, r.font.name, r.font.color.rgb = names[key], Pt(13), FONT, C["text"]
        ratio = slide.shapes.add_textbox(inch(x0), inch(y0 - 6), inch(inner_w), inch(40)).text_frame
        ratio.margin_left = ratio.margin_right = 0
        p = ratio.paragraphs[0]
        p.alignment = PP_ALIGN.RIGHT
        r = p.add_run()
        r.text, r.font.size, r.font.bold, r.font.name, r.font.color.rgb = f"×{b / a:.0f}", Pt(26), True, FONT, C["green"]

        data = CategoryChartData()
        fmt = lambda v: f"{v:g}".replace(".", ",")
        data.categories = [f"до індексу · {fmt(b)} мс", f"після · {fmt(a)} мс"]
        data.add_series("Медіана, мс", (b, a))
        gf = slide.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, inch(x0), inch(y0 + 34),
                                    inch(inner_w), inch(block_h - 44), data)
        ch = gf.chart
        ch.has_legend = False
        ch.has_title = False
        ch.font.name, ch.font.size, ch.font.color.rgb = FONT, Pt(11), C["text"]
        cat, val = ch.category_axis, ch.value_axis
        cat.reverse_order = True                       # «до індексу» зверху
        cat.format.line.fill.background()
        cat.tick_labels.font.color.rgb = C["muted"]
        val.visible = False
        val.has_major_gridlines = False
        val.minimum_scale = 0
        plot = ch.plots[0]
        plot.gap_width = 60
        for idx, color in enumerate((C["before"], C["after"])):
            pt = plot.series[0].points[idx]
            pt.format.fill.solid()
            pt.format.fill.fore_color.rgb = color
    add_caption(slide, x0, box["y"] + box["h"] - pad - 22, inner_w,
                "Медіана EXPLAIN ANALYZE, база elearn_perf (136 000 здач). Шкала кожного запиту своя.")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    r = subprocess.run([sys.executable, "-I", "-X", "utf8", str(EXPORTER), str(HTML), str(PPTX)],
                       capture_output=True, text=True, encoding="utf-8")
    print(r.stdout[-300:], r.stderr[-1500:])
    if r.returncode:
        sys.exit(r.returncode)
    figs = measure_figures()
    prs = Presentation(str(PPTX))
    fix_fonts(prs)
    drop_nav_dots(prs)
    left_align_tables(prs)
    for n, items in figs.items():
        slide = prs.slides[n - 1]
        for item in items:
            if item["chart"]:
                add_perf_charts(slide, item["box"])
            else:
                add_picture(slide, item)
    prs.save(str(PPTX))
    preview = HERE / (PPTX.stem + "-preview.png")
    preview.unlink(missing_ok=True)     # прев'ю експортера показує HTML, а не PPTX
    print("OK:", PPTX, f"{PPTX.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
