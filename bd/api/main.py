"""
REST API платформи дистанційного навчання (курсова робота, варіант 113).
CRUD-ендпоїнти для всіх таблиць схеми edu, виклик процедур і функцій,
звітні представлення. Документація OpenAPI: http://127.0.0.1:8000/docs (Swagger UI).

Запуск:  python -m uvicorn api.main:app --reload
"""
import inspect
from datetime import date, datetime
from typing import Any, Optional

from fastapi import APIRouter, FastAPI, HTTPException, Path, Query, Response, status
from psycopg2 import sql
from pydantic import BaseModel

from . import schemas as s
from .db import transaction

app = FastAPI(
    title="E-Learning Platform API",
    version="1.0.0",
    description=(
        "REST API бази даних платформи дистанційного навчання (PostgreSQL 18, схема `edu`).\n\n"
        "Кожна операція виконується в окремій транзакції від імені ролі `edu_api`. "
        "Бізнес-правила перевіряються на рівні СУБД (CHECK, UNIQUE, FOREIGN KEY, тригери); "
        "помилки СУБД повертаються як HTTP 409/422/403/404 з кодом SQLSTATE."
    ),
    openapi_tags=[
        {"name": "users", "description": "Учасники платформи"},
        {"name": "categories", "description": "Ієрархія категорій курсів"},
        {"name": "courses", "description": "Курси та звіти по курсу"},
        {"name": "modules", "description": "Модулі курсу"},
        {"name": "materials", "description": "Навчальні матеріали"},
        {"name": "assignments", "description": "Завдання"},
        {"name": "enrollments", "description": "Записи студентів на курси"},
        {"name": "submissions", "description": "Здані роботи"},
        {"name": "grades", "description": "Оцінки"},
        {"name": "material-progress", "description": "Перегляд матеріалів"},
        {"name": "reports", "description": "Представлення та аналітика"},
    ],
)


# ---------------------------------------------------------------------------
# Узагальнена фабрика CRUD-маршрутів
# ---------------------------------------------------------------------------
def crud_router(
    prefix: str,
    table: str,
    create_model: type[BaseModel] | None,
    out_model: type[BaseModel],
    update_model: type[BaseModel] | None = None,
    filters: dict[str, Any] | None = None,
    order_by: str = "id",
    pk: str = "id",
    put: bool = True,
    delete: bool = True,
) -> APIRouter:
    tag = prefix.strip("/")
    router = APIRouter(prefix=prefix, tags=[tag])
    filters = filters or {}
    tbl = sql.Identifier("edu", table)
    out_cols = sql.SQL(", ").join(sql.Identifier(c) for c in out_model.model_fields)
    single = tag.rstrip("s").replace("-", " ")

    # ---- READ (список з фільтрами та пагінацією)
    def list_items(**kw):
        limit, offset = kw.pop("limit"), kw.pop("offset")
        conds, args = [], []
        for name, value in kw.items():
            if value is not None:
                conds.append(sql.SQL("{} = %s").format(sql.Identifier(name)))
                args.append(value)
        where = sql.SQL(" WHERE ") + sql.SQL(" AND ").join(conds) if conds else sql.SQL("")
        q = sql.SQL("SELECT {} FROM {}{} ORDER BY {} LIMIT %s OFFSET %s").format(
            out_cols, tbl, where, sql.SQL(order_by))
        with transaction() as cur:
            cur.execute(q, args + [limit, offset])
            return cur.fetchall()

    params = [
        inspect.Parameter("limit", inspect.Parameter.KEYWORD_ONLY, annotation=int,
                          default=Query(100, ge=1, le=1000)),
        inspect.Parameter("offset", inspect.Parameter.KEYWORD_ONLY, annotation=int,
                          default=Query(0, ge=0)),
    ] + [
        inspect.Parameter(name, inspect.Parameter.KEYWORD_ONLY, annotation=Optional[typ],
                          default=Query(None, description=f"Фільтр за {name}"))
        for name, typ in filters.items()
    ]
    list_items.__signature__ = inspect.Signature(params)
    router.add_api_route("", list_items, methods=["GET"], response_model=list[out_model],
                         summary=f"Список ({table})")

    # ---- READ (один запис)
    def get_item(item_id: int = Path(..., ge=1)):
        q = sql.SQL("SELECT {} FROM {} WHERE {} = %s").format(out_cols, tbl, sql.Identifier(pk))
        with transaction() as cur:
            cur.execute(q, (item_id,))
            row = cur.fetchone()
        if row is None:
            raise HTTPException(404, detail=f"{single} {item_id} не знайдено")
        return row

    router.add_api_route("/{item_id}", get_item, methods=["GET"], response_model=out_model,
                         summary=f"Отримати запис ({table})")

    # ---- CREATE
    if create_model is not None:
        def create_item(body: create_model):  # type: ignore[valid-type]
            data = body.model_dump(exclude_unset=False)
            data = {k: v for k, v in data.items() if v is not None or k in body.model_fields_set}
            q = sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING {}").format(
                tbl, sql.SQL(", ").join(map(sql.Identifier, data)),
                sql.SQL(", ").join(sql.Placeholder() * len(data)), out_cols)
            with transaction() as cur:
                cur.execute(q, list(data.values()))
                return cur.fetchone()

        create_item.__annotations__["body"] = create_model
        router.add_api_route("", create_item, methods=["POST"], response_model=out_model,
                             status_code=201, summary=f"Створити запис ({table})")

    # ---- UPDATE
    def _update(item_id: int, data: dict):
        if not data:
            raise HTTPException(422, detail="Немає полів для оновлення")
        q = sql.SQL("UPDATE {} SET {} WHERE {} = %s RETURNING {}").format(
            tbl, sql.SQL(", ").join(sql.SQL("{} = %s").format(sql.Identifier(k)) for k in data),
            sql.Identifier(pk), out_cols)
        with transaction() as cur:
            cur.execute(q, list(data.values()) + [item_id])
            row = cur.fetchone()
        if row is None:
            raise HTTPException(404, detail=f"{single} {item_id} не знайдено")
        return row

    patch_model = update_model or (s.make_update(create_model, f"{create_model.__name__}Patch")
                                   if create_model else None)
    if patch_model is not None:
        def patch_item(body: patch_model, item_id: int = Path(..., ge=1)):  # type: ignore[valid-type]
            return _update(item_id, body.model_dump(exclude_unset=True))

        patch_item.__annotations__["body"] = patch_model
        router.add_api_route("/{item_id}", patch_item, methods=["PATCH"], response_model=out_model,
                             summary=f"Частково оновити запис ({table})")

    if put and create_model is not None and update_model is None:
        def put_item(body: create_model, item_id: int = Path(..., ge=1)):  # type: ignore[valid-type]
            return _update(item_id, body.model_dump())

        put_item.__annotations__["body"] = create_model
        router.add_api_route("/{item_id}", put_item, methods=["PUT"], response_model=out_model,
                             summary=f"Повністю замінити запис ({table})")

    # ---- DELETE
    if delete:
        def delete_item(item_id: int = Path(..., ge=1)):
            q = sql.SQL("DELETE FROM {} WHERE {} = %s").format(tbl, sql.Identifier(pk))
            with transaction() as cur:
                cur.execute(q, (item_id,))
                if cur.rowcount == 0:
                    raise HTTPException(404, detail=f"{single} {item_id} не знайдено")
            return Response(status_code=status.HTTP_204_NO_CONTENT)

        router.add_api_route("/{item_id}", delete_item, methods=["DELETE"], status_code=204,
                             summary=f"Видалити запис ({table})", response_class=Response)
    return router


# ---------------------------------------------------------------------------
# Спеціальні ендпоїнти (мають бути зареєстровані до узагальнених /{item_id})
# ---------------------------------------------------------------------------
courses_extra = APIRouter(prefix="/courses", tags=["courses"])


@courses_extra.get("/{course_id}/report", summary="Звіт по курсу (функція fn_course_report)")
def course_report(course_id: int = Path(..., ge=1)):
    with transaction() as cur:
        cur.execute("SELECT * FROM edu.fn_course_report(%s)", (course_id,))
        return cur.fetchall()


@courses_extra.get("/{course_id}/structure", summary="Модулі, матеріали та завдання курсу")
def course_structure(course_id: int = Path(..., ge=1)):
    with transaction() as cur:
        cur.execute("SELECT id, code, title, status FROM edu.courses WHERE id = %s", (course_id,))
        course = cur.fetchone()
        if course is None:
            raise HTTPException(404, detail=f"course {course_id} не знайдено")
        cur.execute("""
            SELECT m.id, m.position, m.title,
                   COALESCE((SELECT json_agg(json_build_object('id', mt.id, 'title', mt.title,
                                     'type', mt.material_type) ORDER BY mt.position)
                             FROM edu.materials mt WHERE mt.module_id = m.id), '[]') AS materials,
                   COALESCE((SELECT json_agg(json_build_object('id', a.id, 'title', a.title,
                                     'max_score', a.max_score, 'due_at', a.due_at) ORDER BY a.due_at)
                             FROM edu.assignments a WHERE a.module_id = m.id), '[]') AS assignments
            FROM edu.modules m WHERE m.course_id = %s ORDER BY m.position""", (course_id,))
        course["modules"] = cur.fetchall()
        return course


enroll_extra = APIRouter(prefix="/enrollments", tags=["enrollments"])


@enroll_extra.post("", status_code=201, response_model=s.EnrollmentOut,
                   summary="Записати студента на курс (процедура enroll_student)")
def enroll(body: s.EnrollmentCreate):
    with transaction() as cur:
        cur.execute("CALL edu.enroll_student(%s, %s, NULL)", (body.course_id, body.student_id))
        new_id = cur.fetchone()["p_enrollment_id"]
        cur.execute("SELECT * FROM edu.enrollments WHERE id = %s", (new_id,))
        return cur.fetchone()


@enroll_extra.post("/{enrollment_id}/complete", response_model=s.EnrollmentOut,
                   summary="Завершити навчання (процедура complete_enrollment)")
def complete(enrollment_id: int = Path(..., ge=1)):
    with transaction() as cur:
        cur.execute("CALL edu.complete_enrollment(%s, NULL)", (enrollment_id,))
        cur.execute("SELECT * FROM edu.enrollments WHERE id = %s", (enrollment_id,))
        return cur.fetchone()


@enroll_extra.get("/{enrollment_id}/progress", summary="Прогрес і поточний бал студента")
def progress(enrollment_id: int = Path(..., ge=1)):
    with transaction() as cur:
        cur.execute("""SELECT e.id AS enrollment_id, e.course_id, e.student_id, e.status,
                              edu.fn_course_progress(e.id)  AS progress_pct,
                              edu.fn_enrollment_score(e.id) AS score
                       FROM edu.enrollments e WHERE e.id = %s""", (enrollment_id,))
        row = cur.fetchone()
    if row is None:
        raise HTTPException(404, detail=f"enrollment {enrollment_id} не знайдено")
    return row


grades_extra = APIRouter(prefix="/grades", tags=["grades"])


@grades_extra.post("", status_code=201, response_model=s.GradeOut,
                   summary="Оцінити роботу (процедура grade_submission, UPSERT)")
def grade(body: s.GradeCreate):
    with transaction() as cur:
        cur.execute("CALL edu.grade_submission(%s, %s, %s, %s, NULL)",
                    (body.submission_id, body.grader_id, body.score, body.feedback))
        gid = cur.fetchone()["p_grade_id"]
        cur.execute("SELECT * FROM edu.grades WHERE id = %s", (gid,))
        return cur.fetchone()


progress_router = APIRouter(prefix="/material-progress", tags=["material-progress"])


@progress_router.get("", response_model=list[s.ProgressOut], summary="Список переглядів")
def progress_list(enrollment_id: Optional[int] = None, limit: int = Query(100, ge=1, le=1000)):
    with transaction() as cur:
        cur.execute("""SELECT * FROM edu.material_progress
                       WHERE %(e)s::int IS NULL OR enrollment_id = %(e)s
                       ORDER BY enrollment_id, material_id LIMIT %(l)s""",
                    {"e": enrollment_id, "l": limit})
        return cur.fetchall()


@progress_router.post("", status_code=201, response_model=s.ProgressOut,
                      summary="Зафіксувати перегляд матеріалу (UPSERT ON CONFLICT)")
def progress_upsert(body: s.ProgressCreate):
    with transaction() as cur:
        cur.execute("""INSERT INTO edu.material_progress (enrollment_id, material_id)
                       VALUES (%s, %s)
                       ON CONFLICT (enrollment_id, material_id) DO UPDATE
                          SET views_count = material_progress.views_count + 1,
                              last_viewed_at = greatest(now(), material_progress.last_viewed_at)
                       RETURNING *""", (body.enrollment_id, body.material_id))
        return cur.fetchone()


@progress_router.delete("/{enrollment_id}/{material_id}", status_code=204,
                        summary="Видалити факт перегляду", response_class=Response)
def progress_delete(enrollment_id: int, material_id: int):
    with transaction() as cur:
        cur.execute("DELETE FROM edu.material_progress WHERE enrollment_id = %s AND material_id = %s",
                    (enrollment_id, material_id))
        if cur.rowcount == 0:
            raise HTTPException(404, detail="Запис не знайдено")
    return Response(status_code=204)


categories_extra = APIRouter(prefix="/categories", tags=["categories"])


@categories_extra.get("/tree", summary="Дерево категорій (рекурсивний CTE)")
def categories_tree():
    with transaction() as cur:
        cur.execute("""
            WITH RECURSIVE tree AS (
                SELECT id, name, parent_id, name::text AS path, 1 AS depth
                FROM edu.categories WHERE parent_id IS NULL
                UNION ALL
                SELECT c.id, c.name, c.parent_id, t.path || ' / ' || c.name, t.depth + 1
                FROM edu.categories c JOIN tree t ON c.parent_id = t.id)
            SELECT * FROM tree ORDER BY path""")
        return cur.fetchall()


reports = APIRouter(prefix="/reports", tags=["reports"])


@reports.get("/course-overview", summary="Огляд курсів (v_course_overview)")
def r_overview(status_: Optional[s.CourseStatus] = Query(None, alias="status")):
    with transaction() as cur:
        cur.execute("""SELECT * FROM edu.v_course_overview
                       WHERE %(s)s::text IS NULL OR status = %(s)s ORDER BY code""", {"s": status_})
        return cur.fetchall()


@reports.get("/gradebook", summary="Журнал успішності (v_gradebook)")
def r_gradebook(course_id: Optional[int] = None, student_id: Optional[int] = None):
    with transaction() as cur:
        cur.execute("""SELECT * FROM edu.v_gradebook
                       WHERE (%(c)s::int IS NULL OR course_id = %(c)s)
                         AND (%(st)s::int IS NULL OR student_id = %(st)s)
                       ORDER BY course_code, student, assignment_id""",
                    {"c": course_id, "st": student_id})
        return cur.fetchall()


@reports.get("/pending-reviews", summary="Черга перевірки викладача (v_pending_reviews)")
def r_pending(teacher_id: Optional[int] = None):
    with transaction() as cur:
        cur.execute("""SELECT * FROM edu.v_pending_reviews
                       WHERE %(t)s::int IS NULL OR teacher_id = %(t)s ORDER BY submitted_at""",
                    {"t": teacher_id})
        return cur.fetchall()


@reports.get("/course-stats", summary="Статистика курсів (матеріалізоване представлення)")
def r_stats(refresh: bool = Query(False, description="Оновити mv_course_stats перед читанням")):
    with transaction() as cur:
        if refresh:
            cur.execute("SELECT edu.refresh_course_stats()")
        cur.execute("SELECT * FROM edu.mv_course_stats ORDER BY course_id")
        return cur.fetchall()


@reports.get("/top-students", summary="Рейтинг студентів курсу (віконна функція RANK)")
def r_top(course_id: int = Query(..., ge=1), limit: int = Query(10, ge=1, le=100)):
    with transaction() as cur:
        cur.execute("""SELECT u.id AS student_id, u.full_name,
                              edu.fn_enrollment_score(e.id) AS score,
                              RANK() OVER (ORDER BY edu.fn_enrollment_score(e.id) DESC NULLS LAST) AS place
                       FROM edu.enrollments e JOIN edu.users u ON u.id = e.student_id
                       WHERE e.course_id = %s ORDER BY place, u.full_name LIMIT %s""",
                    (course_id, limit))
        return cur.fetchall()


@reports.get("/audit-log", summary="Журнал аудиту (лише читання)")
def r_audit(table_name: Optional[str] = None, limit: int = Query(50, ge=1, le=500)):
    with transaction() as cur:
        cur.execute("""SELECT * FROM edu.audit_log
                       WHERE %(t)s::text IS NULL OR table_name = %(t)s
                       ORDER BY changed_at DESC LIMIT %(l)s""", {"t": table_name, "l": limit})
        return cur.fetchall()


@app.get("/health", tags=["reports"], summary="Перевірка з'єднання з БД")
def health():
    with transaction() as cur:
        cur.execute("SELECT current_user, current_database(), version() AS version, now() AS server_time")
        return cur.fetchone()


# ---------------------------------------------------------------------------
# Реєстрація маршрутів
# ---------------------------------------------------------------------------
app.include_router(categories_extra)
app.include_router(courses_extra)
app.include_router(enroll_extra)
app.include_router(grades_extra)
app.include_router(progress_router)
app.include_router(reports)

app.include_router(crud_router("/users", "users", s.UserCreate, s.UserOut,
                               filters={"role_code": str, "is_active": bool}))
app.include_router(crud_router("/categories", "categories", s.CategoryCreate, s.CategoryOut,
                               filters={"parent_id": int}))
app.include_router(crud_router("/courses", "courses", s.CourseCreate, s.CourseOut,
                               filters={"status": str, "teacher_id": int, "category_id": int}))
app.include_router(crud_router("/modules", "modules", s.ModuleCreate, s.ModuleOut,
                               filters={"course_id": int}, order_by="course_id, position"))
app.include_router(crud_router("/materials", "materials", s.MaterialCreate, s.MaterialOut,
                               filters={"module_id": int, "material_type": str},
                               order_by="module_id, position"))
app.include_router(crud_router("/assignments", "assignments", s.AssignmentCreate, s.AssignmentOut,
                               filters={"module_id": int}, order_by="due_at"))
# POST /enrollments та POST /grades реалізовано процедурами (вище)
app.include_router(crud_router("/enrollments", "enrollments", None, s.EnrollmentOut,
                               update_model=s.EnrollmentUpdate,
                               filters={"course_id": int, "student_id": int, "status": str}))
app.include_router(crud_router("/submissions", "submissions", s.SubmissionCreate, s.SubmissionOut,
                               update_model=s.SubmissionUpdate,
                               filters={"assignment_id": int, "enrollment_id": int, "status": str}))
app.include_router(crud_router("/grades", "grades", None, s.GradeOut, update_model=s.GradeUpdate,
                               filters={"submission_id": int, "grader_id": int}))
