"""
Збирання презентації плагіном slide-creator (тема Enterprise Dark):
  python presentation/build_deck.py
1) main.py --generate з BRIEF.json (strict-валідація генератора);
2) доопрацювання готового HTML (рендерер теми не вставляє власні зображення):
   українські підписи замість службових англійських міток, ілюстрації проєкту
   (скриншоти Swagger, ER-діаграма), графік «до / після індексу»;
3) повторна strict-валідація готового файлу.
Усі зображення вбудовуються в HTML (base64), файл працює без інтернету.
"""
import base64
import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from bs4 import BeautifulSoup
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PLUGIN = Path(r"D:\Programs\slide-creator")
OUT = HERE / "Презентація_БД_Гогуля.html"
ENV = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")

LABELS = {1: "Курсова робота · Бази даних", 2: "Предметна область", 3: "Структура БД",
          4: "Цілісність даних", 5: "Серверна логіка", 6: "Безпека", 7: "Паралельний доступ",
          8: "Продуктивність", 9: "REST API", 10: "Підсумок"}


def run(args, allow=()):
    """allow — фрагменти назв перевірок, провал яких свідомо допускається."""
    r = subprocess.run([sys.executable, *args], cwd=PLUGIN, env=ENV, capture_output=True,
                       text=True, encoding="utf-8")
    print(r.stdout[-600:], r.stderr[-1500:])
    if r.returncode:
        bad = [ln for ln in r.stdout.splitlines() if ("✗" in ln or "⚠" in ln)
               and not any(a in ln for a in allow)]
        if bad or not allow:
            sys.exit(r.returncode)
        print("Допущено:", ", ".join(allow))


def img_uri(path, crop=None, width=1100, fmt="PNG"):
    im = Image.open(path).convert("RGB")
    if crop:
        im = im.crop(crop)
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, fmt, **({"quality": 88} if fmt == "JPEG" else {"optimize": True}))
    mime = "jpeg" if fmt == "JPEG" else "png"
    return f"data:image/{mime};base64," + base64.b64encode(buf.getvalue()).decode()


def perf_chart():
    """Малі мультиплікатори: кожен запит має власну шкалу (різні порядки величин)."""
    perf = json.loads((ROOT / "bd" / "protocols" / "09_performance.json").read_text(encoding="utf-8"))
    blocks = []
    for key, name in (("P1", "P1 · останні роботи студента"), ("P2", "P2 · агрегат за завданнями")):
        b, a = perf[key]["before"]["median_ms"], perf[key]["after"]["median_ms"]
        bb, ab = perf[key]["before"]["shared_hit"], perf[key]["after"]["shared_hit"]
        fmt = lambda v: f"{v:g}".replace(".", ",")
        rows = ""
        for label, v, buf, cls in (("до індексу", b, bb, "kr-bar--before"), ("після", a, ab, "kr-bar--after")):
            pct = max(v / b * 100, 1.2)
            rows += (f'<div class="kr-bar-row" title="{name}: {label} — медіана {fmt(v)} мс, буферів {buf}">'
                     f'<span class="kr-bar-label">{label}</span>'
                     f'<span class="kr-bar-track"><span class="kr-bar {cls}" style="width:{pct:.1f}%"></span></span>'
                     f'<span class="kr-bar-value">{fmt(v)} мс</span></div>')
        blocks.append(f'<div class="kr-chart-block"><div class="kr-chart-head"><span>{name}</span>'
                      f'<b>×{b / a:.0f}</b></div>{rows}</div>')
    return ('<figure class="kr-fig kr-chart" aria-label="Медіана часу виконання до та після індексу">'
            + "".join(blocks) +
            '<figcaption>Медіана EXPLAIN ANALYZE, база elearn_perf (136 000 здач). Шкала кожного запиту своя.</figcaption></figure>')


CSS = """
<style id="kr-extras">
.ent-split-label{text-transform:none!important;letter-spacing:0!important}
.kr-media .ent-shell{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.1fr);
  column-gap:clamp(24px,3.5vw,56px);align-items:center;max-width:min(1320px,92vw)}
.kr-media .kr-text{min-width:0}
.kr-media .ent-arch-grid,.kr-media .ent-contrast-split,.kr-media .ent-cover-metric-row{grid-template-columns:1fr!important}
.kr-media .ent-cover-metric-row{display:grid;gap:10px}
.kr-media .ent-hero-title{font-size:clamp(28px,3.2vw,46px)!important;line-height:1.12;margin-bottom:8px}
.kr-media .ent-cover-metric-card{padding:12px 16px!important;min-height:0!important}
.kr-media .ent-cover-metric-index{display:none}
.kr-media .ent-cover-metric-title{margin:0!important;font-size:clamp(14px,1.3vw,17px)!important}
.kr-media .ent-arch-grid{gap:10px!important}
.kr-media .ent-arch-card{padding:12px 16px!important}
.kr-media .ent-arch-card h3{font-size:clamp(14px,1.3vw,17px)!important}
.kr-media .ent-title{font-size:clamp(26px,2.8vw,40px)!important}
.kr-facts{list-style:none;padding:0;margin:clamp(12px,2vw,24px) 0 0}
.kr-facts li{padding:10px 0;border-bottom:1px solid #30363d;color:#c9d1d9;font-size:clamp(14px,1.3vw,17px)}
.kr-facts li b{color:#e6edf3}
.kr-fig{margin:0;min-width:0}
.kr-fig img{display:block;width:100%;max-height:68vh;object-fit:cover;object-position:top;
  border:1px solid #30363d;border-radius:10px;box-shadow:0 18px 48px rgba(0,0,0,.45);background:#fff}
.kr-fig--browser{border:1px solid #30363d;border-radius:10px;overflow:hidden;box-shadow:0 18px 48px rgba(0,0,0,.45)}
.kr-fig--browser .kr-browser-bar{display:flex;gap:6px;align-items:center;padding:8px 12px;background:#21262d;
  border-bottom:1px solid #30363d;font:12px/1 'SF Mono',Consolas,monospace;color:#8b949e}
.kr-fig--browser .kr-browser-bar i{width:10px;height:10px;border-radius:50%;background:#30363d;display:inline-block}
.kr-fig--browser .kr-browser-bar span{margin-left:10px}
.kr-fig--browser img{border:0;border-radius:0;box-shadow:none;max-height:58vh}
.kr-fig--paper img{object-fit:contain;padding:10px;max-height:70vh}
.kr-fig figcaption{margin-top:10px;font-size:clamp(11px,1vw,13px);color:#8b949e}
.kr-chart{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:clamp(16px,2vw,28px)}
.kr-chart-block+.kr-chart-block{margin-top:clamp(18px,2.4vw,30px)}
.kr-chart-head{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:10px;
  color:#e6edf3;font-size:clamp(13px,1.2vw,16px)}
.kr-chart-head b{color:#3fb950;font-size:clamp(26px,3vw,40px);font-feature-settings:"tnum"}
.kr-bar-row{display:grid;grid-template-columns:7.5em 1fr 6.5em;align-items:center;gap:10px;margin:8px 0;
  color:#c9d1d9;font-size:clamp(12px,1.1vw,14px);font-feature-settings:"tnum"}
.kr-bar-track{height:14px;position:relative}
.kr-bar{position:absolute;left:0;top:0;bottom:0;border-radius:0 4px 4px 0}
.kr-bar--before{background:#6e7681}
.kr-bar--after{background:#388bfd}
.kr-bar-value{text-align:right;color:#e6edf3}
.kr-bar-row:hover .kr-bar{filter:brightness(1.2)}
@media (max-width:900px){.kr-media .ent-shell{grid-template-columns:1fr;row-gap:20px}}
/* --- вирівнювання стилів теми --- */
section.slide:not(.kr-media) .ent-shell{max-width:1120px!important}
section.slide>.slide-content{width:100%;box-sizing:border-box}
.ent-table{width:100%}
@media (min-width:901px){
  .ent-split{max-width:1120px!important;grid-template-columns:minmax(0,.9fr) minmax(0,1.1fr)!important;
    gap:clamp(32px,4vw,64px)!important;align-items:center!important}
}
.ent-split .ent-label-tag,.ent-shell>.ent-label-tag,.kr-text>.ent-label-tag{align-self:flex-start;width:auto!important;max-width:max-content}
.ent-split .ent-title{font-size:clamp(26px,2.8vw,40px)!important;line-height:1.15!important;max-width:none!important}
.ent-split .ent-sep{margin:4px 0!important}
.ent-split-label{font-size:clamp(15px,1.4vw,18px)!important;font-weight:400!important;color:var(--text-body)!important;
  line-height:1.6!important;border:0!important;padding:0!important;text-transform:none!important;letter-spacing:0!important}
.ent-table td:first-child,.ent-table th:first-child{white-space:nowrap;width:5.5em}
.enterprise-close .ent-code{font-family:inherit!important;font-size:clamp(15px,1.4vw,18px)!important;color:var(--text-body)!important;
  background:var(--bg-secondary)!important;border:1px solid var(--border)!important;border-left:3px solid var(--accent-blue)!important;
  border-radius:8px!important;padding:14px 18px!important;white-space:normal!important}
.enterprise-close .ent-kpi-number{color:var(--accent-green)!important}
.ent-kpi-label{text-transform:none!important;letter-spacing:0!important}
</style>
"""


def media_slide(soup, n, figure_html):
    sec = soup.select_one(f"#slide-{n}")
    shell = sec.select_one(".ent-shell")
    sec["class"] = sec.get("class", []) + ["kr-media"]
    text = soup.new_tag("div", attrs={"class": "kr-text"})
    for child in list(shell.children):
        text.append(child.extract())
    shell.append(text)
    shell.append(BeautifulSoup(figure_html, "html.parser"))


def browser(uri, url, alt, caption):
    return (f'<figure class="kr-fig reveal"><div class="kr-fig--browser"><div class="kr-browser-bar">'
            f'<i></i><i></i><i></i><span>{url}</span></div><img src="{uri}" alt="{alt}"></div>'
            f'<figcaption>{caption}</figcaption></figure>')


CREDIT_JS = re.compile(r"\(function\(\) \{\s*var slides = document\.querySelectorAll\('\.slide'\);"
                       r"[^}]*?slide-credit[\s\S]*?\}\)\(\);\s*")


def postprocess(html):
    html, n = CREDIT_JS.subn("", html)  # прибрати підпис генератора на останньому слайді
    assert n == 1, "credit block not found"
    soup = BeautifulSoup(html, "html.parser")
    for n, label in LABELS.items():
        tag = soup.select_one(f"#slide-{n} .ent-label-tag")
        if tag:
            tag.string = label
    title = soup.select_one("#slide-1 .ent-hero-title").get_text(strip=True)
    for card in soup.select("#slide-1 .ent-cover-metric-card"):
        if card.select_one(".ent-cover-metric-title").get_text(strip=True) == title:
            card.decompose()  # рендерер дописує назву як 3-тю картку, якщо фактів лише 2
    for el in soup.select(".ent-cover-metric-index"):
        el.string = el.get_text().replace("Signal", "Пункт")
    for th in soup.select(".ent-table th"):
        th.string = {"Source fact": "Факт"}.get(th.get_text(strip=True), th.get_text(strip=True))

    t8 = soup.select_one("#slide-8 .ent-title")
    t8.string = t8.get_text(strip=True).replace("15 разів", "15 разів")
    kpi = {"28 / 28 SQL-тестів": "SQL-тестів пройдено з 28", "43 / 43 API-сценаріїв": "API-сценаріїв PASS з 43",
           "19 / 19 показників після відновлення": "показників збіглися після відновлення з 19"}
    for el in soup.select("#slide-10 .ent-kpi-label"):
        el.string = kpi.get(el.get_text(strip=True), el.get_text(strip=True))
    docs = ROOT / "docs"
    media_slide(soup, 1, browser(img_uri(docs / "swagger_part1.png", crop=(0, 0, 1280, 900)),
                                 "127.0.0.1:8000/docs", "Swagger UI проєкту",
                                 "Swagger UI: автоматична документація всіх ендпоїнтів"))
    media_slide(soup, 3, '<figure class="kr-fig kr-fig--paper reveal"><img src="'
                + img_uri(docs / "er_diagram.png", width=1400) +
                '" alt="ER-діаграма бази даних"><figcaption>ER-діаграма схеми edu: 11 таблиць і зв\'язки 1 : N'
                '</figcaption></figure>')
    split = soup.select_one("#slide-8 .ent-contrast-split")
    split.replace_with(BeautifulSoup(
        '<ul class="kr-facts reveal">'
        '<li><b>P2:</b> Seq Scan → Index Only Scan (після VACUUM)</li>'
        '<li><b>Буфери:</b> 915 → 7 (P1), 1948 → 17 (P2)</li>'
        '<li><b>Дані:</b> 136 000 здач у тестовій базі elearn_perf</li></ul>', "html.parser"))
    media_slide(soup, 8, perf_chart())
    media_slide(soup, 9, browser(img_uri(docs / "swagger_exec_report.png", crop=(0, 0, 1280, 1100)),
                                 "127.0.0.1:8000/docs#/courses/report", "Виконаний запит у Swagger",
                                 "GET /courses/4/report → 200: дані з функції fn_course_report"))
    soup.head.append(BeautifulSoup(CSS, "html.parser"))
    return str(soup)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    run(["main.py", "--generate", "--brief", str(HERE / "BRIEF.json"),
         "--request-file", str(HERE / "SLIDE_REQUEST.json"), "--output", str(OUT)])
    OUT.write_text(postprocess(OUT.read_text(encoding="utf-8")), encoding="utf-8")
    # підпис генератора прибрано на прохання автора — це єдина допущена перевірка
    run(["scripts/validate_html.py", str(OUT), "--strict"], allow=("Watermark not detected", "missing watermark injection"))
    print("OK:", OUT, f"{OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
