"""Розділи 3–4, висновки, список джерел, додатки."""
import json
import re

QUERY_NOTES = {
    "Q01": "Представлення v_course_overview приховує з’єднання трьох таблиць і підзапити підрахунку. "
           "Курс PY-101 заповнений (0 вільних місць) — саме на ньому перевіряється правило BR15.",
    "Q02": "INNER JOIN трьох таблиць; порядок вивчення задано унікальними парами (course_id, position) і "
           "(module_id, position), тому сортування однозначне.",
    "Q03": "LEFT JOIN зберігає викладачів без студентів; COUNT ... FILTER рахує лише активні записи, "
           "а COUNT(DISTINCT c.id) усуває дублювання курсів після з’єднання із записами.",
    "Q04": "Антиз’єднання через NOT EXISTS. Знайдено одну неактивну студентку — вона не може бути "
           "записана (BR05).",
    "Q05": "NOT EXISTS із корельованим підзапитом: 4 студенти з 10 ще не здали поточне завдання.",
    "Q06": "Групування з HAVING відкидає завдання з малою кількістю робіт; FILTER рахує запізнення; "
           "для завдання без оцінок середнє дорівнює NULL і за NULLS LAST виводиться останнім.",
    "Q07": "DISTINCT ON вибирає останню роботу кожного запису; додатковий ключ s.id DESC робить вибір "
           "однозначним при однаковому часі здачі.",
    "Q08": "Віконна функція RANK присвоює однакове місце однаковим балам (два студенти на 3-му місці, "
           "далі 5-те). Бал рахується від усіх завдань курсу, тому неперевірене поточне завдання "
           "зменшує підсумок.",
    "Q09": "LAG у вікні PARTITION BY запис ORDER BY due_at обчислює зміну відсотка відносно "
           "попереднього завдання того самого курсу; для першого завдання кожного курсу значення NULL.",
    "Q10": "Агрегування за днями і віконна сума за замовчуванням рамки (від початку до поточного "
           "рядка) дають накопичувальний підсумок.",
    "Q11": "Рекурсивний CTE будує повний шлях категорії; LEFT JOIN показує категорії без курсів.",
    "Q12": "Два рівні агрегування в CTE: середній відсоток студента порівнюється із середнім по "
           "курсу (порівняння з агрегованим результатом).",
    "Q13": "Використано SQL-функцію fn_course_progress і LEFT JOIN до переглядів.",
    "Q14": "Представлення v_pending_reviews повертає останню неоцінену спробу кожного студента для "
           "кожного завдання.",
    "Q15": "PL/pgSQL-функція повертає набір рядків (RETURNS TABLE) — готовий звіт по курсу.",
    "Q16": "Скалярний підзапит у SELECT дає знаменник (кількість записів на курс); NULLIF захищає "
           "від ділення на нуль.",
    "Q17": "Читання jsonb-полів журналу аудиту операцією ->>; запис зроблено тригером під час "
           "архівування курсу ENG-120.",
}


def parse_queries(sql_text):
    blocks = re.split(r"\n(?=-- (?:Q|M)\d\d\. )", sql_text)
    out = {}
    for b in blocks:
        m = re.match(r"-- ((?:Q|M)\d\d)\. ([^\n]*)\n((?:--[^\n]*\n)*)([\s\S]*)", b)
        if not m:
            continue
        code, title, more, body = m.groups()
        title = title + " " + " ".join(l[2:].strip() for l in more.splitlines())
        body = body.split("\n-- =====")[0].strip()
        if code == "M05":
            body = body.split("\n\nROLLBACK")[0]
        out[code] = (title.strip(), body.strip())
    return out


def parse_results(text):
    lines = text.splitlines()
    res, i = [], 0
    while i < len(lines):
        if re.match(r"^-+(\+-+)*$", lines[i]) and i > 0:
            start = i - 1
            j = i + 1
            while j < len(lines) and not re.match(r"^\(\d+ rows?\)$", lines[j]):
                j += 1
            res.append(lines[start:j + 1])
            i = j + 1
        else:
            i += 1
    return res


def shorten(block, max_rows=12):
    if len(block) <= max_rows + 3:
        return "\n".join(block)
    return "\n".join(block[:max_rows + 2] + [" ...", block[-1]])


def section3(w, ctx, root):
    sqlq = parse_queries((root / "bd" / "sql" / "06_queries.sql").read_text(encoding="utf-8"))
    results = parse_results((root / "bd" / "protocols" / "06_queries_output.txt").read_text(encoding="utf-8"))
    qcodes = [f"Q{i:02d}" for i in range(1, 18)]

    w.h1("3 РЕАЛІЗАЦІЯ БАЗИ ДАНИХ")
    w.h2("3.1 Створення структури й тестових даних")
    w.p("Структура створюється скриптами, які виконуються послідовно в порожній базі `elearn_db` "
        "(таблиця 3.1). Повні тексти скриптів наведено в додатку Б, порядок запуску — у додатку В.")
    rows = [
        ["01_schema.sql", "Схема edu, 11 таблиць, PK/FK/UNIQUE/CHECK, індекси для зовнішніх ключів"],
        ["02_logic.sql", "7 тригерних функцій і тригерів, 3 функції, 3 процедури"],
        ["03_views.sql", "3 представлення, матеріалізоване представлення, функція його оновлення"],
        ["04_seed.sql", "Тестові дані з детермінованими значеннями"],
        ["05_roles.sql", "Ролі edu_teacher, edu_student, edu_analyst, edu_api та права"],
        ["06_queries.sql", "17 запитів SELECT і 5 операцій зміни (у транзакції з ROLLBACK)"],
        ["07_tests.sql", "28 перевірок правил, прав і відкату"],
        ["08_concurrency.py", "Сценарії конкурентного доступу у двох підключеннях"],
        ["09_perf_data.sql, 09_performance.py", "Генерація 136 000 робіт і порівняння планів"],
        ["10_backup_restore.sh", "pg_dump, pg_restore у окрему базу, звірка показників"],
        ["run_all.sh", "Повне розгортання elearn_db однією командою"],
    ]
    w.table("Склад SQL-скриптів", ["Файл", "Призначення"], rows, [5.2, 11.5], "3.1")
    w.p("Фрагмент створення таблиці робіт показує, як правила задаються безпосередньо у схемі:")
    w.code("""CREATE TABLE edu.submissions (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    assignment_id  integer NOT NULL
                   REFERENCES edu.assignments(id) ON DELETE RESTRICT,
    enrollment_id  integer NOT NULL
                   REFERENCES edu.enrollments(id) ON DELETE RESTRICT,
    attempt_no     smallint NOT NULL CHECK (attempt_no > 0),
    answer_text    text,
    answer_url     varchar(500),
    submitted_at   timestamptz NOT NULL DEFAULT now(),
    is_late        boolean NOT NULL DEFAULT false,
    status         varchar(10) NOT NULL DEFAULT 'submitted'
                   CHECK (status IN ('submitted', 'graded', 'returned')),
    CONSTRAINT submissions_attempt_uq
        UNIQUE (assignment_id, enrollment_id, attempt_no),
    CONSTRAINT submissions_answer_chk
        CHECK (answer_text IS NOT NULL OR answer_url IS NOT NULL)
);""")
    r = ctx["rows"]
    w.p("Тестові дані синтетичні й відображають процеси системи: курси в різних станах (4 опубліковані, "
        "1 архівний, 1 чернетка), заповнений курс, неактивний студент без записів, роботи вчасно і з "
        "запізненням, повторні спроби, неоцінені роботи, завершені й відраховані записи. Значення "
        "обчислюються детермінованими формулами (без random()), тому результат запитів відтворюваний. "
        "Кількість рядків після розгортання наведено в таблиці 3.2.")
    names = ["users", "categories", "courses", "modules", "materials", "assignments", "enrollments",
             "submissions", "grades", "material_progress", "audit_log"]
    w.table("Обсяг тестових даних", ["Таблиця"] + names[:6], [["Рядків"] + [r[n] for n in names[:6]]],
            [2.4] + [2.38] * 6, "3.2", font_size=11)
    w.table("Обсяг тестових даних (продовження)", ["Таблиця"] + names[6:],
            [["Рядків"] + [r[n] for n in names[6:]]], [2.4] + [2.86] * 5, None, font_size=11)
    w.p("Записи журналу аудиту створено тригерами під час наповнення (оцінювання робіт і архівування "
        "курсу), а не вставлено вручну.")

    w.h2("3.2 Запити та представлення")
    w.p("Запити сформовано з інформаційних потреб користувачів і охоплюють усі групи способів "
        "оброблення з таблиці 5.4 методичних рекомендацій: з’єднання (Q02, Q03), групування з HAVING і "
        "FILTER (Q03, Q06), підзапити EXISTS/NOT EXISTS і порівняння з агрегатом (Q04, Q05, Q12, Q16), "
        "DISTINCT ON (Q07), віконні функції RANK, LAG, накопичувальна сума (Q08–Q10), CTE і рекурсивний "
        "CTE (Q11, Q12), представлення й табличну функцію (Q01, Q14, Q15). Повний набір із результатами "
        "наведено в додатках Б.6 і В.3. Нижче детально розглянуто сім запитів, що демонструють "
        "основні способи оброблення (питання користувача, SQL-код, фактичний результат і пояснення); "
        "решту подано в таблиці 3.3.")
    key = ["Q03", "Q06", "Q07", "Q08", "Q09", "Q11", "Q12"]
    for i, code in enumerate(qcodes):
        if code not in key:
            continue
        title, body = sqlq[code]
        w.h3(f"{code}. {title}")
        w.code(body, size=9)
        w.p("Результат:", italic=True)
        w.code(shorten(results[i], 10), size=8)
        w.p(QUERY_NOTES[code])
    rows = []
    for i, code in enumerate(qcodes):
        if code in key:
            continue
        nrows = re.search(r"\((\d+) rows?\)", results[i][-1]).group(1)
        rows.append([code, sqlq[code][0], QUERY_NOTES[code], nrows])
    w.table("Інші запити (SQL — додаток Б.6, результати — додаток В.3)",
            ["Код", "Питання користувача", "Засоби та пояснення результату", "Рядків"], rows,
            [1.3, 5.6, 8.3, 1.5], "3.3", font_size=10)

    w.p("Представлення реалізовано для повторного використання вибірок і обмеження доступу "
        "(таблиця 3.4).")
    rows = [
        ["v_course_overview", "Огляд курсів: викладач, категорія, кількість модулів, матеріалів, завдань, "
         "студентів і вільних місць", "Студент, викладач, аналітик"],
        ["v_gradebook", "Журнал успішності: найкраща оцінка, кількість спроб, ознака запізнення",
         "Викладач, аналітик"],
        ["v_pending_reviews", "Черга перевірки: остання неоцінена спроба (DISTINCT ON)", "Викладач"],
        ["mv_course_stats", "Матеріалізована статистика курсів (частка запізнень, середній підсумок); "
         "оновлюється функцією refresh_course_stats() без блокування читання (CONCURRENTLY)", "Аналітик"],
    ]
    w.table("Представлення", ["Представлення", "Зміст", "Користувачі"], rows, [4.0, 9.2, 3.5], "3.4")
    w.p("Операції зміни даних (таблиця 3.5) виконуються в транзакції, що завершується ROLLBACK, тому "
        "скрипт запитів можна запускати повторно.")
    mres = results[17:]
    rows = [
        ["M01", "INSERT ... RETURNING", "Новий матеріал до модуля 3", "id = 23 повернуто"],
        ["M02", "UPDATE ... RETURNING", "Продовження терміну завдання 3 на 2 дні",
         "due_at = 2026-11-15 23:59+02"],
        ["M03", "INSERT ... ON CONFLICT DO UPDATE", "Повторний перегляд матеріалу",
         "views_count: 3 → 4"],
        ["M04", "DELETE ... RETURNING", "Видалення порожнього модуля курсу-чернетки", "Видалено модуль 11"],
        ["M05", "CALL", "grade_submission і enroll_student", "Оцінка 18, статус graded; новий запис"],
    ]
    w.table("Операції зміни даних", ["Код", "Оператор", "Дія", "Фактичний результат"], rows,
            [1.4, 4.8, 5.8, 4.7], "3.5", font_size=11)

    w.h2("3.3 Функції, процедури та тригери")
    w.p("Програмовані об’єкти застосовано лише там, де правило не виражається стандартним обмеженням "
        "або операція має виконуватися узгоджено (таблиця 3.6). Позначення волатильності відповідають "
        "поведінці: функції, що читають змінювані таблиці, оголошено STABLE, а не IMMUTABLE.")
    rows = [
        ["fn_course_progress(enrollment_id)", "SQL-функція, STABLE → numeric", "Відсоток переглянутих "
         "матеріалів курсу; 0 для курсу без матеріалів"],
        ["fn_enrollment_score(enrollment_id)", "SQL-функція, STABLE → numeric", "Бал 0–100 за найкращими "
         "оціненими спробами; незданi завдання = 0"],
        ["fn_course_report(course_id)", "PL/pgSQL, STABLE → TABLE", "Звіт по курсу; no_data_found для "
         "неіснуючого курсу"],
        ["enroll_student(course, student, OUT id)", "Процедура, SECURITY DEFINER", "Запис на курс з "
         "блокуванням рядка курсу FOR UPDATE і контролем місць"],
        ["grade_submission(sub, grader, score, fb, OUT id)", "Процедура", "UPSERT оцінки (ON CONFLICT)"],
        ["complete_enrollment(enrollment, OUT score)", "Процедура", "Фіксація підсумкового балу й "
         "статусу completed"],
        ["courses_teacher_check", "BEFORE INSERT/UPDATE", "BR04: викладач має роль teacher"],
        ["courses_status_transition", "BEFORE UPDATE OF status", "BR08: дозволені переходи статусу"],
        ["enrollments_check", "BEFORE INSERT/UPDATE", "BR05, BR06: активний студент, опублікований курс"],
        ["submissions_before_insert", "BEFORE INSERT", "BR11–BR13: курс, ліміт спроб, attempt_no, is_late"],
        ["grades_check", "BEFORE INSERT/UPDATE", "BR07, BR09: бал ≤ max_score, оцінює викладач курсу"],
        ["grades_audit", "AFTER INSERT/UPDATE/DELETE", "BR16: статус роботи й журнал аудиту"],
        ["courses_status_audit", "AFTER UPDATE OF status WHEN", "Аудит зміни статусу курсу"],
    ]
    w.table("Функції, процедури та тригери", ["Об’єкт", "Вид", "Призначення"], rows,
            [5.8, 4.4, 6.5], "3.6", font_size=11)
    w.p("Ключовою є процедура запису на курс. Рядок курсу блокується `SELECT ... FOR UPDATE`, тому дві "
        "одночасні спроби зайняти останнє місце виконуються послідовно, і друга бачить уже "
        "зафіксований запис першої (перевірено в 4.2):")
    w.code("""CREATE OR REPLACE PROCEDURE edu.enroll_student(
    IN p_course_id integer, IN p_student_id integer, OUT p_enrollment_id integer)
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = edu, pg_temp AS $$
DECLARE v_max integer; v_taken integer;
BEGIN
    SELECT max_students INTO v_max FROM edu.courses
    WHERE id = p_course_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Курс % не знайдено', p_course_id USING ERRCODE = 'no_data_found';
    END IF;
    SELECT count(*) INTO v_taken FROM edu.enrollments
    WHERE course_id = p_course_id AND status <> 'dropped';
    IF v_taken >= v_max THEN
        RAISE EXCEPTION 'На курсі % немає вільних місць (% з %)', p_course_id, v_taken, v_max
            USING ERRCODE = 'check_violation';
    END IF;
    INSERT INTO edu.enrollments (course_id, student_id)
    VALUES (p_course_id, p_student_id) RETURNING id INTO p_enrollment_id;
END; $$;""", size=9)
    w.p("Тригер `submissions_before_insert` блокує рядок запису студента (FOR UPDATE), тому паралельні "
        "здачі одного студента нумеруються послідовно, а ліміт спроб не може бути перевищений. "
        "Повторне вставлення з тим самим номером додатково відхиляє UNIQUE (assignment_id, "
        "enrollment_id, attempt_no). Фрагмент тригера:")
    w.code("""    SELECT course_id, status INTO v_enroll_course, v_enroll_status
    FROM edu.enrollments WHERE id = NEW.enrollment_id FOR UPDATE;
    ...
    IF v_assign_course <> v_enroll_course THEN
        RAISE EXCEPTION 'Завдання % не належить курсу запису %', ...
            USING ERRCODE = 'check_violation';
    END IF;
    SELECT count(*) INTO v_used FROM edu.submissions
    WHERE assignment_id = NEW.assignment_id AND enrollment_id = NEW.enrollment_id;
    IF v_used >= v_max_attempts THEN
        RAISE EXCEPTION 'Вичерпано ліміт спроб (%) для завдання %', ...;
    END IF;
    NEW.attempt_no := v_used + 1;
    NEW.is_late    := NEW.submitted_at > v_due;""", size=9)
    w.p("Тригер аудиту оцінок працює в тій самій транзакції, що й зміна оцінки: після ROLLBACK "
        "скасовуються і оцінка, і запис журналу (тест T15). Помилки бізнес-правил генеруються зі "
        "стандартними кодами SQLSTATE (check_violation, no_data_found), тому клієнт (API) обробляє їх "
        "так само, як порушення декларативних обмежень.")

    w.h2("3.4 Транзакції, ролі та права доступу")
    w.p("Межі транзакцій визначено бізнес-операціями. Запис на курс — одна транзакція, що містить "
        "блокування курсу, підрахунок місць і вставлення. Оцінювання — одна транзакція, у якій тригери "
        "змінюють оцінку, статус роботи і журнал аудиту. Завершення навчання — обчислення балу та "
        "оновлення трьох полів запису. У REST API кожен HTTP-запит виконується в окремій транзакції: "
        "COMMIT при успіху, ROLLBACK при будь-якій помилці. Після помилки стан бази залишається таким, "
        "як до початку операції.")
    w.p("Використано рівень ізоляції READ COMMITTED (за замовчуванням) [10]. Його достатньо, бо "
        "критичні перевірки виконуються після явного блокування рядків: у PL/pgSQL кожен оператор "
        "отримує новий знімок, тому після зняття блокування процедура бачить зміни конкурента. "
        "Рівень SERIALIZABLE також запобіг би перевищенню ліміту, але вимагав би повторення "
        "транзакцій після помилки serialization_failure.")
    w.p("Права задано скриптом `05_roles.sql` через GRANT/REVOKE: у PUBLIC відкликано CREATE у схемі "
        "та EXECUTE функцій; ролі отримують лише потрібні привілеї, зокрема на рівні стовпців "
        "(викладач може змінювати в `enrollments` тільки `status`, `final_score`, `completed_at`). "
        "Фрагмент:")
    w.code("""GRANT SELECT ON edu.v_course_overview, edu.v_gradebook, edu.mv_course_stats,
                edu.courses, edu.categories TO edu_analyst;
GRANT SELECT, INSERT ON edu.submissions TO edu_student;
GRANT EXECUTE ON PROCEDURE edu.enroll_student(integer, integer) TO edu_student;
GRANT SELECT, INSERT, UPDATE ON edu.grades TO edu_teacher;
GRANT UPDATE (status, final_score, completed_at) ON edu.enrollments TO edu_teacher;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA edu TO edu_api;
REVOKE INSERT, UPDATE, DELETE ON edu.audit_log FROM edu_api;
REVOKE ALL ON edu.audit_log FROM edu_teacher, edu_student, edu_analyst;""", size=9)
    w.p("Правильність прав перевірено від імені самих ролей (SET ROLE), а не власником таблиць — "
        "тести T19–T26 у розділі 4.1. Пароль сервісної ролі передається змінною psql і в скриптах не "
        "зберігається.")

    w.h2("3.5 REST API та документація Swagger")
    w.p("Для роботи з базою через HTTP розроблено REST API на FastAPI [15]. Сервер автоматично формує "
        "специфікацію OpenAPI 3.1 [16] та інтерактивну документацію Swagger UI за адресою "
        "`http://127.0.0.1:8000/docs`. API підключається до PostgreSQL через пул з’єднань psycopg2 [20] "
        "від імені ролі `edu_api`; перед видачею з’єднання з пулу виконується перевірка (pre-ping), щоб "
        "API відновлювався після перезапуску сервера БД.")
    w.p("CRUD-маршрути для всіх таблиць згенеровано узагальненою фабрикою `crud_router`: GET (список з "
        "фільтрами й пагінацією), GET /{id}, POST, PUT (повна заміна), PATCH (часткове оновлення), "
        "DELETE. Назви таблиць і стовпців підставляються як ідентифікатори (`psycopg2.sql.Identifier`), "
        "значення — лише як параметри запиту, що виключає SQL-ін’єкції. Операції з бізнес-логікою "
        "викликають процедури й функції бази (таблиця 3.7).")
    rows = [
        ["/users, /categories, /courses, /modules, /materials, /assignments", "GET, POST, GET/{id}, PUT, PATCH, DELETE",
         "Прямий CRUD таблиць"],
        ["/enrollments", "POST", "CALL enroll_student"],
        ["/enrollments, /submissions, /grades", "GET, GET/{id}, PATCH, DELETE", "CRUD таблиць"],
        ["/submissions", "POST", "INSERT; attempt_no і is_late встановлює тригер"],
        ["/grades", "POST", "CALL grade_submission (UPSERT)"],
        ["/enrollments/{id}/complete", "POST", "CALL complete_enrollment"],
        ["/enrollments/{id}/progress", "GET", "fn_course_progress, fn_enrollment_score"],
        ["/courses/{id}/report, /courses/{id}/structure", "GET", "fn_course_report; json_agg"],
        ["/material-progress", "GET, POST, DELETE", "UPSERT ON CONFLICT"],
        ["/categories/tree", "GET", "Рекурсивний CTE"],
        ["/reports/course-overview, gradebook, pending-reviews", "GET", "Представлення"],
        ["/reports/course-stats, top-students, audit-log", "GET", "MV з оновленням, RANK, журнал"],
    ]
    w.table("Ендпоїнти REST API", ["Маршрут", "Методи", "Реалізація в БД"], rows, [7.0, 4.6, 5.1], "3.6",
            font_size=11)
    w.p("Помилки СУБД перетворюються на HTTP-відповіді за кодом SQLSTATE: unique_violation, "
        "foreign_key_violation і restrict_violation — 409 Conflict; check_violation і помилки формату — "
        "422; insufficient_privilege — 403; no_data_found — 404; lock_not_available — 423. Тіло "
        "відповіді містить код SQLSTATE, повідомлення та назву порушеного обмеження. Загальний вигляд "
        "Swagger UI наведено на рисунках 3.1–3.2, виконання запитів — на рисунках 3.3–3.4.")
    w.figure(root / "docs" / "swagger_part1.png", "Swagger UI: CRUD-ендпоїнти users, categories, courses",
             "3.1", width_cm=15.5)
    w.figure(root / "docs" / "swagger_part2.png",
             "Swagger UI: записи, роботи, оцінки, перегляди та звіти", "3.2", width_cm=15.5)
    w.figure(root / "docs" / "swagger_exec_top.png",
             "Виконання GET /reports/top-students у Swagger UI (віконна функція RANK)", "3.3", width_cm=12.5)
    w.figure(root / "docs" / "swagger_exec_404.png",
             "Обробка помилки: звіт для неіснуючого курсу повертає 404 з кодом SQLSTATE P0002", "3.4",
             width_cm=12.5)


def section4(w, ctx, root):
    w.h1("4 ПЕРЕВІРКА ТА ДОСЛІДЖЕННЯ РОБОТИ БАЗИ ДАНИХ")
    w.h2("4.1 Функціональні й негативні перевірки")
    w.p("Перевірки сформовано з вимог (таблиця 1.3). Скрипт `07_tests.sql` виконує кожну команду в "
        "обробнику винятків, порівнює отриманий SQLSTATE з очікуваним і записує результат до тимчасової "
        "таблиці; уся перевірка виконується в транзакції з ROLLBACK, тож початковий стан відновлюється. "
        "Перевірки прав доступу виконуються після `SET ROLE` від імені відповідної ролі. Тест T15 "
        "запускається в окремій транзакції: значення до, всередині й після відкату фіксуються "
        "змінними psql. Фактичні результати наведено в таблиці 4.1.")
    text = (root / "bd" / "protocols" / "07_tests_output.txt").read_text(encoding="utf-8")
    rows = []
    for line in text.splitlines():
        m = re.match(r"^ (T\d+\w?)\s+\|(.*?)\|(.*?)\|(.*?)\|\s*(PASS|FAIL)\s*$", line)
        if m:
            code, action, exp, act, res = [x.strip() for x in m.groups()]
            act = act if len(act) < 95 else act[:92] + "…"
            rows.append([code, action, exp, act, res])
    w.table("Протокол перевірок (07_tests.sql)", ["Код", "Дія", "Очікувано", "Фактично", "Рез."], rows,
            [1.2, 4.6, 3.0, 6.6, 1.3], "4.1", font_size=10)
    passed = sum(1 for r in rows if r[4] == "PASS")
    w.p(f"Результат: {passed} з {len(rows)} перевірок пройдено. Під час першого запуску тест T08 "
        "очікував foreign_key_violation (23503), але PostgreSQL 18 для зовнішнього ключа з дією "
        "ON DELETE RESTRICT повертає окремий код restrict_violation (23001). Очікуване значення тесту й "
        "обробник помилок API виправлено, сценарій повторено. Також виявлено, що ідентифікатори IDENTITY "
        "після відкатів мають пропуски — тести не покладаються на неперервність нумерації.")
    api = json.loads((root / "bd" / "protocols" / "11_api_results.json").read_text(encoding="utf-8"))
    ok = sum(1 for r in api if r[5] == "PASS")
    w.p(f"Додатково скрипт `api/smoke_test.py` перевіряє REST API: {ok} з {len(api)} сценаріїв "
        "пройдено. Сценарій створює курс, виконує всі операції CRUD (POST, GET, PATCH, PUT, DELETE), "
        "запис студентів до вичерпання місць, здачу роботи, оцінювання, перегляд матеріалів, звіти, а "
        "також негативні випадки; наприкінці всі тестові дані видаляються через DELETE-ендпоїнти. "
        "Протокол наведено в додатку В (таблиця В.2).")

    w.h2("4.2 Конкурентний доступ")
    w.p("Конкурентні сценарії виконано скриптом `08_concurrency.py` у двох незалежних підключеннях "
        "(`sess_A`, `sess_B`) з окремим третім підключенням `monitor`, яке читає `pg_stat_activity`; "
        "це підтверджує, що сеанси справді різні. Сеанс B запускається в окремому потоці, поки "
        "транзакція A відкрита.")
    w.p("**Сценарій К1 — запис двох студентів на останнє місце.** Для курсу STAT-110 ліміт тимчасово "
        "встановлено так, щоб залишилося одне місце. Протокол:")
    conc = (root / "bd" / "protocols" / "08_concurrency_output.txt").read_text(encoding="utf-8")
    k1 = conc.split("=== К2")[0].split("===\n", 1)[1] if "===\n" in conc else conc
    w.code(k1.strip(), size=8)
    w.p("Сеанс B чекав (wait_event_type = Lock) на блокування рядка курсу, утримуване процедурою в "
        "сеансі A. Після COMMIT сеансу A процедура в сеансі B отримала блокування, побачила 8 записів "
        "з 8 і відхилила запис з check_violation. Перевищення ліміту немає. Без `FOR UPDATE` обидві "
        "транзакції за READ COMMITTED порахували б по 7 записів і обидві вставили б рядок.")
    w.p("**Сценарій К2 — блокування рядка і тайм-аут.** Протокол:")
    k2 = conc.split("=== К2", 1)[1].split("===\n", 1)[1]
    w.code(k2.strip(), size=8)
    w.p("UPDATE у сеансі B чекав на блокування `FOR UPDATE` сеансу A і через 2 с завершився помилкою "
        "lock_not_available (55P03) за `SET LOCAL lock_timeout`. Після ROLLBACK сеансу A повторний "
        "UPDATE виконався без очікування; завершальний ROLLBACK зберіг початкові дані. REST API "
        "повертає для цієї помилки HTTP 423.")

    w.h2("4.3 Аналіз планів та індексів")
    perf = json.loads((root / "bd" / "protocols" / "09_performance.json").read_text(encoding="utf-8"))
    w.p("Для дослідження створено окрему базу `elearn_perf` з тією самою схемою і детермінованим "
        "набором даних (`09_perf_data.sql`): 4 000 студентів, 50 курсів, 300 завдань, 20 000 записів, "
        "136 000 робіт (таблиця submissions — 15 MB). Обрано два запити, що відповідають типовим "
        "операціям: останні роботи студента (екран «Мої роботи») і статистика здач за тиждень "
        "(звіт викладача). Порядок експерименту: VACUUM ANALYZE, перший запуск і п’ять повторів "
        "EXPLAIN (ANALYZE, BUFFERS) [5], створення одного індексу, повторення вимірювань за тих самих "
        "параметрів. Результати наведено в таблицях 4.2 і 4.3.")
    for code, num in (("P1", "4.2"), ("P2", "4.3")):
        d = perf[code]
        b, a = d["before"], d["after"]
        rows = [
            ["Версія СУБД і обсяг таблиці", "PostgreSQL 18.3; 136 000 рядків", "Ті самі умови"],
            ["Параметри запиту", "enrollment_id = 7777, LIMIT 10" if code == "P1"
             else "10.10.2026–17.10.2026", "Ті самі значення"],
            ["Основні вузли плану", "\n".join(x.strip() for x in b["plan"]), "\n".join(x.strip() for x in a["plan"])],
            ["Фактичні рядки та loops", f"{int(b['rows'])} рядків, loops=1", f"{int(a['rows'])} рядків, loops=1"],
            ["Execution Time: перший запуск", f"{b['first_ms']} мс", f"{a['first_ms']} мс"],
            ["Execution Time: медіана 5 повторів (min–max)", f"{b['median_ms']} мс ({b['min_ms']}–{b['max_ms']})",
             f"{a['median_ms']} мс ({a['min_ms']}–{a['max_ms']})"],
            ["Buffers shared hit / read", f"{b['shared_hit']} / {b['shared_read']}", f"{a['shared_hit']} / {a['shared_read']}"],
            ["Оцінка вартості (cost)", f"{b['total_cost']}", f"{a['total_cost']}"],
            ["Вартість індексу", "Відсутній", f"{d['index_size']}"],
        ]
        w.p(f"Запит {code}: {d['title']}.")
        w.code(re.sub(r"\n\s+", "\n", d["sql"]).strip(), size=9)
        w.p("Зміна: " + "`" + d["index"] + "`.")
        w.table(f"Порівняння планів запиту {code}", ["Показник", "До зміни", "Після зміни"], rows,
                [4.6, 6.0, 6.1], num, font_size=10)
    b1, a1 = perf["P1"]["before"], perf["P1"]["after"]
    b2, a2 = perf["P2"]["before"], perf["P2"]["after"]
    w.p(f"**Пояснення P1.** До зміни планувальник PostgreSQL 18 не виконував послідовного сканування: він "
        f"використав наявний унікальний індекс `submissions_attempt_uq (assignment_id, enrollment_id, "
        f"attempt_no)`, хоча `enrollment_id` у ньому не перший стовпець. Це skip scan — нова можливість "
        f"версії 18: індекс переглядається окремо для кожного значення першого стовпця (у плані "
        f"«Index Searches: 302»), після чого потрібне сортування. Новий індекс `(enrollment_id, "
        f"submitted_at DESC)` повністю відповідає умові WHERE та ORDER BY, тому сортування зникло, "
        f"а LIMIT зупиняє читання після потрібних рядків: прочитано {a1['shared_hit']} буферів замість "
        f"{b1['shared_hit']}, медіанний час зменшився з {b1['median_ms']} до {a1['median_ms']} мс.")
    w.p(f"**Пояснення P2.** Умова за діапазоном `submitted_at` відбирає 3 338 рядків із 136 000 (2,5 %), "
        f"тому без індексу виконувалося послідовне сканування з відкиданням 132 662 рядків. Покривний "
        f"індекс `(submitted_at) INCLUDE (assignment_id, is_late)` містить усі потрібні запиту стовпці, "
        f"і після VACUUM (актуальна карта видимості) план став Index Only Scan [23]: {a2['shared_hit']} "
        f"буферів замість {b2['shared_hit']}, медіана {a2['median_ms']} мс замість {b2['median_ms']} мс. "
        f"Без VACUUM (у першому прогоні експерименту) той самий індекс використовувався через Bitmap "
        f"Heap Scan і давав менший виграш — стан карти видимості суттєво впливає на результат.")
    ins = perf["insert"]
    w.p("**Вартість індексів.** Кожен індекс займає близько 4 MB. Вплив на вставлення оцінено "
        "вставленням 2 000 робіт (з ROLLBACK) з індексами і без них, по 5 повторів після прогріву: "
        f"{', '.join(str(x[1]) for x in ins['with'])} мс з індексами та "
        f"{', '.join(str(x[1]) for x in ins['without'])} мс без них. Розкид між повторами більший за "
        "різницю між станами: час вставлення визначають тригер `submissions_before_insert` (три "
        "запити на рядок) і накопичення мертвих версій рядків після відкатів, тому вплив двох "
        "додаткових індексів у цьому вимірюванні не виявлено. Обидва індекси рекомендовано залишити; "
        "для рідкісних звітів P2 можна розглянути BRIN-індекс, якщо роботи вставлятимуться в порядку "
        "часу.")

    w.h2("4.4 Резервне копіювання і відновлення")
    w.p("Резервну копію бази `elearn_db` створено логічним дампом у форматі custom (`pg_dump -Fc`) [6] "
        "і відновлено в окрему порожню базу `elearn_restore` утилітою `pg_restore --exit-on-error`. "
        "Ролі існують на рівні кластера, тому права (GRANT) відновлюються без параметра --no-owner. "
        "Після відновлення скрипт `10_backup_restore.sh` порівнює показники в обох базах: кількість "
        "таблиць, представлень, індексів, функцій, тригерів, обмежень, рядків, контрольну суму "
        "md5 вмісту `submissions`, суму балів, результат функції звіту, кількість прав аналітика.")
    bk = (root / "bd" / "protocols" / "10_backup_restore_output.txt").read_text(encoding="utf-8")
    w.code(bk.strip(), size=8)
    w.p("Усі 19 контрольних показників збігаються; у відновленій базі працюють обмеження (спроба "
        "вставити дублікат e-mail відхилена індексом `users_email_uq`). Логічний дамп однієї бази не "
        "охоплює ролі кластера та не забезпечує відновлення на момент часу; для цього потрібні "
        "`pg_dumpall --roles-only` і фізичне резервування з архівуванням WAL.")

    w.h2("4.5 Порівняння моделей зберігання та обмеження рішення")
    w.p("Для процесу «вміст курсу» розглянуто альтернативу на документній СУБД MongoDB [13]: курс "
        "можна зберігати одним документом з вкладеними модулями, матеріалами й завданнями. Це зручно "
        "для читання структури курсу одним запитом (аналог ендпоїнта `/courses/{id}/structure`) і для "
        "матеріалів зі змінним набором атрибутів. Проте роботи, оцінки та записи пов’язують курси з "
        "тисячами студентів і постійно змінюються; їх вкладення в документ курсу призвело б до "
        "необмеженого росту документа, а винесення в окремі колекції — до перевірки зв’язків у коді "
        "застосунку замість FOREIGN KEY. Правила BR03, BR07, BR11–BR15 вимагають транзакційної "
        "узгодженості кількох таблиць, яку PostgreSQL забезпечує декларативно.")
    rows = [
        ["Структура даних", "Нормалізовані таблиці; вміст курсу збирається JOIN/json_agg",
         "Документ курсу з вкладеними модулями"],
        ["Типові операції", "Запис, здача, оцінювання, звіти з агрегуванням",
         "Швидке читання структури курсу"],
        ["Узгодженість", "ACID, FK, CHECK, тригери", "Перевірка зв’язків у застосунку; "
         "багатодокументні транзакції за потреби"],
        ["Масштабування", "Вертикальне, репліки читання", "Горизонтальне шардування"],
        ["Відновлення", "pg_dump/pg_restore, PITR", "mongodump/mongorestore"],
    ]
    w.table("Порівняння PostgreSQL і MongoDB для платформи", ["Критерій", "PostgreSQL", "MongoDB"], rows,
            [3.4, 6.7, 6.6], "4.4", font_size=11)
    w.p("Доречним розширенням є кеш Redis [14] для показника «вільні місця» і рейтингу курсу: дані "
        "основного сховища залишаються в PostgreSQL, кеш оновлюється після COMMIT запису на курс, "
        "має обмежений термін життя і за втрати відновлюється запитом до `v_course_overview`. "
        "Документна модель доцільна лише для вмісту курсу, якщо типи матеріалів стануть суттєво "
        "різнорідними; у межах варіанта 113 реляційна модель повністю покриває вимоги.")
    w.p("Обмеження рішення: немає історії версій матеріалів і змін максимального балу; автентифікація "
        "кінцевих користувачів у API не реалізована (розмежування прав перевірено на рівні СУБД); "
        "дослідження продуктивності виконано на одному локальному сервері з даними в кеші.")


def conclusions(w, ctx):
    w.h1("ВИСНОВКИ")
    w.p("У курсовій роботі спроєктовано та реалізовано базу даних платформи дистанційного навчання "
        f"(варіант 113) у PostgreSQL {ctx['version']} та REST API з документацією Swagger.")
    w.p("Конкретні результати:")
    w.bullets([
        "проаналізовано 7 процесів предметної області та 3 аналоги (Moodle, Canvas LMS, Google "
        "Classroom); сформульовано 6 функціональних, 4 нефункціональні вимоги та 17 бізнес-правил з "
        "кодами перевірок;",
        "побудовано модель з 11 таблиць у 3НФ; два похідні атрибути (is_late, final_score) збережено "
        "свідомо як історичні факти, їхню узгодженість підтримують тригер і процедура;",
        "реалізовано 7 тригерів, 3 функції, 3 процедури, 3 представлення й 1 матеріалізоване, 4 ролі; "
        "правила, що залежать від інших рядків, захищено блокуваннями FOR SHARE / FOR UPDATE;",
        "розроблено 17 запитів SELECT (з’єднання, групування з FILTER і HAVING, EXISTS, DISTINCT ON, "
        "RANK, LAG, накопичувальна сума, рекурсивний CTE) і 5 операцій зміни (INSERT, UPDATE, UPSERT, "
        "DELETE, CALL);",
        "28 автоматизованих перевірок пройдено; виявлено й виправлено відмінність коду помилки "
        "RESTRICT (23001) від загального порушення зовнішнього ключа (23503);",
        "конкурентний запис на останнє місце не перевищує ліміт: другий сеанс очікує блокування і "
        "отримує відмову; lock_timeout перериває очікування через 2 с;",
        "на 136 000 рядків індекс (enrollment_id, submitted_at DESC) зменшив кількість прочитаних "
        "буферів запиту P1 з 915 до 7, а покривний індекс для P2 — з 1948 до 17 (Index Only Scan); "
        "зафіксовано використання skip scan PostgreSQL 18 до створення індексу;",
        "резервну копію відновлено в окрему базу, усі 19 контрольних показників збігаються;",
        "REST API надає CRUD для всіх сутностей і виклик процедур/функцій, помилки СУБД повертаються з "
        "кодами SQLSTATE; 43 сценарії перевірки API пройдено.",
    ])
    w.p("Обмеження рішення та напрями розвитку: версіонування навчальних матеріалів, автентифікація "
        "користувачів API з відображенням на ролі СУБД (або RLS), кешування показників у Redis, "
        "фізичне резервування з відновленням на момент часу.")


SOURCES = [
    "Робоча програма навчальної дисципліни «Бази даних». Освітньо-професійна програма «Інженерія "
    "програмного забезпечення», спеціальність F2. Київ, 2026. 15 с.",
    "Бази даних : методичні рекомендації до виконання курсової роботи / Київський авіаційний інститут, "
    "кафедра інженерії програмного забезпечення. Київ, 2027.",
    "PostgreSQL Global Development Group. PostgreSQL 18 Documentation. URL: "
    "https://www.postgresql.org/docs/18/ (дата звернення: 22.11.2026).",
    "PostgreSQL Global Development Group. Constraints. PostgreSQL 18 Documentation. URL: "
    "https://www.postgresql.org/docs/18/ddl-constraints.html (дата звернення: 22.11.2026).",
    "PostgreSQL Global Development Group. Using EXPLAIN. PostgreSQL 18 Documentation. URL: "
    "https://www.postgresql.org/docs/18/using-explain.html (дата звернення: 22.11.2026).",
    "PostgreSQL Global Development Group. SQL Dump. PostgreSQL 18 Documentation. URL: "
    "https://www.postgresql.org/docs/18/backup-dump.html (дата звернення: 22.11.2026).",
    "PostgreSQL Global Development Group. Window Functions. PostgreSQL 18 Documentation. URL: "
    "https://www.postgresql.org/docs/18/tutorial-window.html (дата звернення: 22.11.2026).",
    "PostgreSQL Global Development Group. CREATE FUNCTION. PostgreSQL 18 Documentation. URL: "
    "https://www.postgresql.org/docs/18/sql-createfunction.html (дата звернення: 22.11.2026).",
    "PostgreSQL Global Development Group. Trigger Functions. PostgreSQL 18 Documentation. URL: "
    "https://www.postgresql.org/docs/18/plpgsql-trigger.html (дата звернення: 22.11.2026).",
    "PostgreSQL Global Development Group. Transaction Isolation. PostgreSQL 18 Documentation. URL: "
    "https://www.postgresql.org/docs/18/transaction-iso.html (дата звернення: 22.11.2026).",
    "PostgreSQL Global Development Group. Explicit Locking. PostgreSQL 18 Documentation. URL: "
    "https://www.postgresql.org/docs/18/explicit-locking.html (дата звернення: 22.11.2026).",
    "PostgreSQL Global Development Group. GRANT. PostgreSQL 18 Documentation. URL: "
    "https://www.postgresql.org/docs/18/sql-grant.html (дата звернення: 22.11.2026).",
    "MongoDB. Data Modeling in MongoDB. MongoDB Manual. URL: "
    "https://www.mongodb.com/docs/manual/data-modeling/ (дата звернення: 22.11.2026).",
    "Redis. Redis documentation. URL: https://redis.io/docs/latest/ (дата звернення: 22.11.2026).",
    "FastAPI documentation. URL: https://fastapi.tiangolo.com/ (дата звернення: 22.11.2026).",
    "OpenAPI Initiative. OpenAPI Specification v3.1.0. URL: https://spec.openapis.org/oas/v3.1.0 "
    "(дата звернення: 22.11.2026).",
    "Moodle Docs. URL: https://docs.moodle.org/ (дата звернення: 22.11.2026).",
    "Instructure. Canvas LMS : source code repository. URL: https://github.com/instructure/canvas-lms "
    "(дата звернення: 22.11.2026).",
    "Google. Classroom Help. URL: https://support.google.com/edu/classroom (дата звернення: 22.11.2026).",
    "Psycopg 2 documentation. URL: https://www.psycopg.org/docs/ (дата звернення: 22.11.2026).",
    "DeBarros A. Practical SQL: A Beginner’s Guide to Storytelling with Data. 2nd ed. San Francisco : "
    "No Starch Press, 2022. 464 p.",
    "Beaulieu A. Learning SQL. 3rd ed. Sebastopol : O’Reilly Media, 2020. 380 p.",
    "PostgreSQL Global Development Group. Index-Only Scans and Covering Indexes. PostgreSQL 18 "
    "Documentation. URL: https://www.postgresql.org/docs/18/indexes-index-only-scans.html "
    "(дата звернення: 22.11.2026).",
]


def sources(w):
    w.h1("СПИСОК ВИКОРИСТАНИХ ДЖЕРЕЛ")
    for i, s in enumerate(SOURCES, 1):
        p = w.p(f"{i}. {s}")


def appendix_a(w, ctx):
    w.h1("ДОДАТОК А\nПовна схема та словник даних")
    w.p("Словник отримано з системного каталогу бази `elearn_db` (скрипт `report/collect.py`), тому він "
        "відповідає версії структури у скрипті `01_schema.sql` і ER-діаграмі (рисунок 2.1).")
    order = ["users", "categories", "courses", "modules", "materials", "assignments", "enrollments",
             "submissions", "grades", "material_progress", "audit_log"]
    for n, t in enumerate(order, 1):
        rows = []
        for c in ctx["columns"][t]:
            cons = [x for x in c["cons"]]
            if c["not_null"] and "PK" not in cons:
                cons.insert(0, "NOT NULL")
            if c["identity"]:
                cons.append("IDENTITY")
            elif c["default"]:
                cons.append("DEFAULT " + c["default"].replace("::character varying", "").replace("::text", ""))
            rows.append([c["name"], c["type"], "; ".join(cons), ctx["descr"].get(f"{t}.{c['name']}", "")])
        w.table(f"{t} — {ctx['comments'].get(t, '')}", ["Стовпець", "Тип", "Обмеження", "Призначення"],
                rows, [3.2, 3.2, 5.6, 4.7], f"А.{n}", font_size=10)
        names = [c["name"] for c in ctx["columns"][t]]
        tbl = [c for c in ctx["constraints"].get(t, []) if c["type"] in ("u", "c", "p")
               and sum(1 for nm in names if re.search(r"(?<![a-z_])" + nm + r"(?![a-z_])", c["def"])) >= 2]
        if tbl:
            w.p("Табличні обмеження: " + "; ".join(f"`{c['name']}` {c['def']}" for c in tbl) + ".")
    w.p("Індекси схеми edu (крім створених для PRIMARY KEY):")
    w.code("\n".join(d for _, n, d in ctx["indexes"] if not n.endswith("_pkey")), size=8)


def appendix_b(w, root):
    w.h1("ДОДАТОК Б\nSQL-скрипти")
    w.p("Нижче наведено повні тексти SQL-скриптів у порядку виконання. Файли входять до електронного "
        "комплекту (каталог `sql`).")
    for i, f in enumerate(["01_schema.sql", "02_logic.sql", "03_views.sql", "04_seed.sql", "05_roles.sql",
                           "06_queries.sql", "07_tests.sql", "09_perf_data.sql"], 1):
        w.h2(f"Б.{i} Скрипт {f}")
        w.code((root / "bd" / "sql" / f).read_text(encoding="utf-8"), size=8)


def appendix_c(w, root):
    w.h1("ДОДАТОК В\nПротоколи перевірок та інструкція запуску")
    w.h2("В.1 Інструкція запуску")
    readme = (root / "bd" / "README.md").read_text(encoding="utf-8")
    w.code(readme.split("## Середовище", 1)[1].replace("## ", "").replace("```bash", "").replace("```", ""),
           size=9)
    w.h2("В.2 Протокол перевірки REST API")
    api = json.loads((root / "bd" / "protocols" / "11_api_results.json").read_text(encoding="utf-8"))
    rows = [[r[0], r[1], r[2], str(r[3]), str(r[4]), r[5]] for r in api]
    w.table("Сценарії перевірки REST API (api/smoke_test.py)",
            ["Код", "Сценарій", "Запит", "Очік.", "Факт.", "Рез."], rows,
            [1.2, 5.6, 5.9, 1.4, 1.4, 1.2], "В.2", font_size=9)
    w.h2("В.3 Результати запитів (06_queries.sql)")
    w.code((root / "bd" / "protocols" / "06_queries_output.txt").read_text(encoding="utf-8"), size=7)
    w.h2("В.4 Протокол дослідження продуктивності (09_performance.py)")
    w.code((root / "bd" / "protocols" / "09_performance_output.txt").read_text(encoding="utf-8"), size=7)
    w.h2("В.5 Скрипт конкурентного доступу (08_concurrency.py)")
    w.code((root / "bd" / "sql" / "08_concurrency.py").read_text(encoding="utf-8"), size=8)
    w.h2("В.6 Скрипт резервного копіювання (10_backup_restore.sh)")
    w.code((root / "bd" / "sql" / "10_backup_restore.sh").read_text(encoding="utf-8"), size=8)


def appendix_d(w, root):
    w.h1("ДОДАТОК Г\nВихідний код REST API")
    for i, f in enumerate(["db.py", "schemas.py", "main.py"], 1):
        w.h2(f"Г.{i} Файл api/{f}")
        w.code((root / "bd" / "api" / f).read_text(encoding="utf-8"), size=8)
