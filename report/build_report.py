"""
Збирання пояснювальної записки: титульний аркуш береться з ЕПЗ_Гогуля_8.docx
(змінено дисципліну, вид роботи й тему), далі — завдання, зміст і розділи.
Запуск: python report/build_report.py  -> report/КР_БД_Гогуля.docx
"""
import copy
import json
import sys
from pathlib import Path

import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Mm, Pt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from docx_helpers import Writer, add_field, setup_styles  # noqa: E402
import sections_a as A  # noqa: E402
import sections_b as B  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "report" / "КР_БД_Гогуля.docx"

DESCR = {
    "users.id": "Ідентифікатор користувача", "users.email": "Логін і e-mail; унікальний без регістру",
    "users.full_name": "ПІБ", "users.role_code": "Роль: student, teacher, admin",
    "users.is_active": "Ознака активного облікового запису", "users.created_at": "Момент реєстрації",
    "categories.id": "Ідентифікатор категорії", "categories.name": "Назва категорії",
    "categories.parent_id": "Батьківська категорія (NULL — корінь)",
    "courses.id": "Ідентифікатор курсу", "courses.code": "Код курсу (ABC-123)", "courses.title": "Назва",
    "courses.description": "Опис", "courses.category_id": "Категорія курсу",
    "courses.teacher_id": "Викладач курсу", "courses.status": "draft / published / archived",
    "courses.start_date": "Дата початку", "courses.end_date": "Дата завершення",
    "courses.max_students": "Максимальна кількість студентів", "courses.created_at": "Момент створення",
    "modules.id": "Ідентифікатор модуля", "modules.course_id": "Курс", "modules.title": "Назва модуля",
    "modules.position": "Порядковий номер у курсі",
    "materials.id": "Ідентифікатор матеріалу", "materials.module_id": "Модуль",
    "materials.title": "Назва", "materials.material_type": "video / pdf / link / text",
    "materials.url": "Посилання (для video, pdf, link)", "materials.content": "Текст (для text)",
    "materials.duration_min": "Тривалість відео, хв", "materials.position": "Порядок у модулі",
    "materials.created_at": "Момент створення",
    "assignments.id": "Ідентифікатор завдання", "assignments.module_id": "Модуль",
    "assignments.title": "Назва", "assignments.description": "Умова", "assignments.max_score": "Максимальний бал",
    "assignments.due_at": "Кінцевий термін здачі", "assignments.max_attempts": "Допустима кількість спроб",
    "assignments.created_at": "Момент створення",
    "enrollments.id": "Ідентифікатор запису", "enrollments.course_id": "Курс",
    "enrollments.student_id": "Студент", "enrollments.enrolled_at": "Момент запису",
    "enrollments.status": "active / completed / dropped", "enrollments.final_score": "Підсумковий бал 0–100",
    "enrollments.completed_at": "Момент завершення (лише для completed)",
    "submissions.id": "Ідентифікатор роботи", "submissions.assignment_id": "Завдання",
    "submissions.enrollment_id": "Запис студента на курс", "submissions.attempt_no": "Номер спроби (тригер)",
    "submissions.answer_text": "Текст відповіді", "submissions.answer_url": "Посилання на відповідь",
    "submissions.submitted_at": "Момент здачі", "submissions.is_late": "Здано після due_at (тригер)",
    "submissions.status": "submitted / graded / returned",
    "grades.id": "Ідентифікатор оцінки", "grades.submission_id": "Робота (не більше однієї оцінки)",
    "grades.grader_id": "Хто оцінив", "grades.score": "Бал (не більше max_score — тригер)",
    "grades.feedback": "Відгук викладача", "grades.graded_at": "Момент оцінювання",
    "material_progress.enrollment_id": "Запис студента", "material_progress.material_id": "Матеріал",
    "material_progress.first_viewed_at": "Перший перегляд", "material_progress.last_viewed_at": "Останній перегляд",
    "material_progress.views_count": "Кількість переглядів",
    "audit_log.id": "Ідентифікатор події", "audit_log.table_name": "Таблиця", "audit_log.record_id": "Ключ рядка",
    "audit_log.action": "INSERT / UPDATE / DELETE", "audit_log.old_data": "Стан до зміни",
    "audit_log.new_data": "Стан після зміни", "audit_log.changed_by": "Користувач СУБД",
    "audit_log.changed_at": "Момент зміни",
}


def set_text(par, idx_run, text):
    par.runs[idx_run].text = text


def prepare_template():
    doc = docx.Document(str(ROOT / "ЕПЗ_Гогуля_8.docx"))
    ps = doc.paragraphs
    # дисципліна
    set_text(ps[4], 1, "Бази даних")
    # вид роботи
    for r in ps[5].runs[1:]:
        r.text = ""
    ps[5].runs[0].text = "КУРСОВА РОБОТА"
    ps[5].paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    ps[5].paragraph_format.left_indent = Cm(0)
    # тема
    ps[6].runs[1].text = A.TOPIC
    for r in ps[6].runs[3:]:
        r.text = ""
    ps[6].paragraph_format.line_spacing = 1.0
    ps[6].paragraph_format.left_indent = Cm(1.0)
    ps[6].paragraph_format.right_indent = Cm(1.0)
    ps[9].paragraph_format.space_before = Cm(2.5)  # блок «Виконав» трохи вище, щоб місто/рік вмістилися
    # видалити все після абзацу 16 (решту лабораторної)
    body = doc.element.body
    keep_until = ps[14]._p
    found = False
    for el in list(body):
        if el is keep_until:
            found = True
            continue
        if found and el.tag != qn("w:sectPr"):
            body.remove(el)
    # місто й рік
    p = doc.add_paragraph()
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Cm(1.0)
    r = p.add_run("Київ – 2026")
    r.font.name, r.font.size = "Times New Roman", Pt(14)
    r.add_break(WD_BREAK.PAGE)
    return doc


def setup_page(doc):
    s = doc.sections[0]
    s.page_width, s.page_height = Mm(210), Mm(297)
    s.left_margin, s.right_margin = Mm(25), Mm(15)
    s.top_margin, s.bottom_margin = Mm(20), Mm(20)
    s.header_distance = Mm(10)
    pgMar = s._sectPr.find(qn("w:pgMar"))
    if pgMar is not None and pgMar.get(qn("w:gutter")) is None:
        pgMar.set(qn("w:gutter"), "0")
    s.different_first_page_header_footer = True
    hp = s.header.paragraphs[0] if s.header.paragraphs else s.header.add_paragraph()
    hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = add_field(hp, "PAGE", "2")
    for r in hp.runs:
        r.font.name, r.font.size = "Times New Roman", Pt(14)
    # Word оновить поле змісту під час відкриття
    settings = doc.settings.element
    upd = OxmlElement("w:updateFields")
    upd.set(qn("w:val"), "true")
    after = ["hdrShapeDefaults", "footnotePr", "endnotePr", "compat", "docVars", "rsids", "mathPr",
             "attachedSchema", "themeFontLang", "clrSchemeMapping", "doNotIncludeSubdocsInStats",
             "doNotAutoCompressPictures", "forceUpgrade", "captions", "readModeInkLockDown",
             "smartTagType", "schemaLibrary", "shapeDefaults", "doNotEmbedSmartTags", "decimalSymbol",
             "listSeparator"]
    nxt = next((c for c in settings if c.tag.split("}")[1] in after), None)
    if nxt is not None:
        nxt.addprevious(upd)
    else:
        settings.append(upd)


def toc(w):
    p = w.doc.add_paragraph("ЗМІСТ", style="Heading 1")
    # заголовок змісту не повинен потрапляти в зміст
    p.paragraph_format.keep_with_next = True
    pPr = p._p.get_or_add_pPr()
    ol = OxmlElement("w:outlineLvl"); ol.set(qn("w:val"), "9"); pPr.append(ol)
    tp = w.doc.add_paragraph(style="KR Body")
    add_field(tp, 'TOC \\o "1-2" \\h \\z \\u',
              "Зміст буде сформовано автоматично: у Word натисніть «Так» на запит про оновлення полів "
              "або клацніть правою кнопкою → «Оновити поле».")


def main():
    ctx = json.loads((ROOT / "report" / "data.json").read_text(encoding="utf-8"))
    ctx["descr"] = DESCR
    doc = prepare_template()
    setup_page(doc)
    setup_styles(doc)
    w = Writer(doc)

    A.task_page(w, ctx)
    toc(w)
    A.intro(w, ctx)
    A.section1(w, ctx)
    A.section2(w, ctx, ROOT)
    B.section3(w, ctx, ROOT)
    B.section4(w, ctx, ROOT)
    B.conclusions(w, ctx)
    B.sources(w)
    B.appendix_a(w, ctx)
    B.appendix_b(w, ROOT)
    B.appendix_c(w, ROOT)
    B.appendix_d(w, ROOT)
    # шаблон Google Docs містить дробові значення twips — округлюємо до цілих (вимога схеми OOXML)
    for el in doc.element.body.iter():
        if el.tag in (qn("w:ind"), qn("w:spacing")):
            for k, v in list(el.attrib.items()):
                if "." in v:
                    try:
                        el.set(k, str(round(float(v))))
                    except ValueError:
                        pass
    doc.core_properties.title = A.TOPIC
    doc.core_properties.author = "Гогуля Ярослав Сергійович"
    doc.save(str(OUT))
    print("saved", OUT)


if __name__ == "__main__":
    main()
