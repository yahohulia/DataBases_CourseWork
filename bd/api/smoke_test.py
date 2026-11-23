"""
Перевірка REST API (сервер має бути запущений: python -m uvicorn api.main:app).
Запуск: python api/smoke_test.py  -> протокол у stdout.
Усі створені тестові записи видаляються наприкінці.
"""
import json
import sys

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
c = httpx.Client(base_url=BASE, timeout=10)
results = []


def step(code, title, method, url, expected, **kw):
    r = c.request(method, url, **kw)
    ok = r.status_code == expected
    body = r.json() if r.content and r.headers.get("content-type", "").startswith("application/json") else None
    short = ""
    if isinstance(body, dict) and "detail" in body:
        short = body["detail"]
        if isinstance(short, dict):
            short = f"{short.get('error')}: {short.get('message')}"
        elif not isinstance(short, str):
            short = ""
    if isinstance(body, dict) and not short:
        short = json.dumps({k: body[k] for k in list(body)[:3]}, ensure_ascii=False, default=str)
    elif isinstance(body, list):
        short = f"{len(body)} записів"
    results.append((code, title, f"{method} {url}", expected, r.status_code, "PASS" if ok else "FAIL", short))
    print(f"{code:<5} {'PASS' if ok else 'FAIL'}  {method:<6} {url:<40} -> {r.status_code} (очік. {expected})  {short}")
    return body


print(f"API: {BASE}")
step("A01", "Перевірка з'єднання", "GET", "/health", 200)
step("A02", "Список опублікованих курсів", "GET", "/courses?status=published", 200)
course = step("A03", "Створення курсу (CREATE)", "POST", "/courses", 201, json={
    "code": "OPS-210", "title": "Основи DevOps", "category_id": 2, "teacher_id": 4,
    "start_date": "2027-02-01", "end_date": "2027-05-31", "max_students": 2})
cid = course["id"]
step("A04", "Читання курсу (READ)", "GET", f"/courses/{cid}", 200)
step("A05", "Часткове оновлення (PATCH) — публікація", "PATCH", f"/courses/{cid}", 200,
     json={"status": "published"})
step("A06", "Повна заміна (PUT)", "PUT", f"/courses/{cid}", 200, json={
    "code": "OPS-210", "title": "Основи DevOps і CI/CD", "category_id": 2, "teacher_id": 4,
    "status": "published", "start_date": "2027-02-01", "end_date": "2027-06-15", "max_students": 2})
step("A07", "Дублікат коду курсу", "POST", "/courses", 409, json={
    "code": "OPS-210", "title": "X", "category_id": 2, "teacher_id": 4,
    "start_date": "2027-02-01", "end_date": "2027-05-31"})
step("A08", "Дата завершення раніше початку", "POST", "/courses", 422, json={
    "code": "OPS-211", "title": "X", "category_id": 2, "teacher_id": 4,
    "start_date": "2027-02-01", "end_date": "2027-01-01"})
step("A09", "Викладач курсу — студент (тригер)", "POST", "/courses", 422, json={
    "code": "OPS-212", "title": "X", "category_id": 2, "teacher_id": 6,
    "start_date": "2027-02-01", "end_date": "2027-05-31"})
step("A10", "Невалідний код (валідація Pydantic)", "POST", "/courses", 422, json={
    "code": "bad", "title": "X", "category_id": 2, "teacher_id": 4,
    "start_date": "2027-02-01", "end_date": "2027-05-31"})
mod = step("A11", "Створення модуля", "POST", "/modules", 201,
           json={"course_id": cid, "title": "Контейнери", "position": 1})
mat = step("A12", "Створення матеріалу", "POST", "/materials", 201, json={
    "module_id": mod["id"], "title": "Docker docs", "material_type": "link",
    "url": "https://docs.docker.com", "position": 1})
asg = step("A13", "Створення завдання", "POST", "/assignments", 201, json={
    "module_id": mod["id"], "title": "Dockerfile", "max_score": 10,
    "due_at": "2027-03-01T23:59:00+02:00", "max_attempts": 2})
e1 = step("A14", "Запис студента (процедура enroll_student)", "POST", "/enrollments", 201,
          json={"course_id": cid, "student_id": 16})
step("A15", "Повторний запис", "POST", "/enrollments", 409, json={"course_id": cid, "student_id": 16})
e2 = step("A16", "Другий студент (останнє місце)", "POST", "/enrollments", 201,
          json={"course_id": cid, "student_id": 17})
step("A17", "Запис понад ліміт місць", "POST", "/enrollments", 422, json={"course_id": cid, "student_id": 18})
sub = step("A18", "Здача роботи (тригер attempt_no, is_late)", "POST", "/submissions", 201, json={
    "assignment_id": asg["id"], "enrollment_id": e1["id"], "answer_url": "https://git.test/df",
    "submitted_at": "2027-03-02T10:00:00+02:00"})
step("A19", "Робота з чужого курсу", "POST", "/submissions", 422,
     json={"assignment_id": 1, "enrollment_id": e1["id"], "answer_text": "x"})
step("A20", "Оцінка понад max_score", "POST", "/grades", 422,
     json={"submission_id": sub["id"], "grader_id": 4, "score": 11})
step("A21", "Оцінювання (процедура grade_submission)", "POST", "/grades", 201,
     json={"submission_id": sub["id"], "grader_id": 4, "score": 9, "feedback": "Добре"})
step("A22", "Статус роботи змінив тригер", "GET", f"/submissions/{sub['id']}", 200)
step("A23", "Перегляд матеріалу (UPSERT)", "POST", "/material-progress", 201,
     json={"enrollment_id": e1["id"], "material_id": mat["id"]})
step("A24", "Повторний перегляд (views_count + 1)", "POST", "/material-progress", 201,
     json={"enrollment_id": e1["id"], "material_id": mat["id"]})
step("A25", "Прогрес студента (функції)", "GET", f"/enrollments/{e1['id']}/progress", 200)
step("A26", "Звіт по курсу (fn_course_report)", "GET", f"/courses/{cid}/report", 200)
step("A27", "Структура курсу", "GET", f"/courses/{cid}/structure", 200)
step("A28", "Завершення навчання (complete_enrollment)", "POST", f"/enrollments/{e1['id']}/complete", 200)
step("A29", "Видалення курсу з записами (RESTRICT)", "DELETE", f"/courses/{cid}", 409)
step("A30", "Журнал аудиту", "GET", "/reports/audit-log?table_name=grades&limit=3", 200)
step("A31", "Огляд курсів (представлення)", "GET", "/reports/course-overview?status=published", 200)
step("A32", "Статистика з оновленням MV", "GET", "/reports/course-stats?refresh=true", 200)
step("A33", "Рейтинг студентів (RANK)", "GET", "/reports/top-students?course_id=1&limit=3", 200)
step("A34", "Дерево категорій (рекурсивний CTE)", "GET", "/categories/tree", 200)
step("A35", "Неіснуючий курс", "GET", "/courses/9999", 404)
step("A36", "Звіт неіснуючого курсу", "GET", "/courses/9999/report", 404)

# ---- прибирання (DELETE) у порядку залежностей
step("A37", "DELETE оцінки", "DELETE", f"/grades/{c.get('/grades', params={'submission_id': sub['id']}).json()[0]['id']}", 204)
step("A38", "DELETE роботи", "DELETE", f"/submissions/{sub['id']}", 204)
step("A39", "DELETE перегляду", "DELETE", f"/material-progress/{e1['id']}/{mat['id']}", 204)
step("A40", "DELETE записів на курс", "DELETE", f"/enrollments/{e1['id']}", 204)
c.delete(f"/enrollments/{e2['id']}")
step("A41", "DELETE завдання", "DELETE", f"/assignments/{asg['id']}", 204)
step("A42", "DELETE курсу (каскадно модулі й матеріали)", "DELETE", f"/courses/{cid}", 204)
step("A43", "Курс видалено", "GET", f"/courses/{cid}", 404)

passed = sum(1 for r in results if r[5] == "PASS")
print(f"\nРазом: {passed} PASS, {len(results) - passed} FAIL")
with open(__file__.replace("smoke_test.py", "../protocols/11_api_results.json"), "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=1)
