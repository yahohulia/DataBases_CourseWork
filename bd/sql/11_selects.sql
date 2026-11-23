-- КОМАНДИ ЗАПУСКУ (Git Bash, з папки bd/)
-- ---------------------------------------------------------------------
-- 0. Підготовка сеансу: шлях до psql і змінні з .env (PGUSER=postgres, PGPASSWORD, ...).
--    Без цього кроку psql входить під користувачем Windows і падає з помилкою автентифікації —
--    тоді додавайте до команд psql параметр -U postgres (пароль — PGPASSWORD з .env).
--      export PATH="/c/Program Files/PostgreSQL/18/bin:$PATH"
--      set -a; . ./.env; set +a                # у т.ч. PGCLIENTENCODING=UTF8 — інакше кирилиця в Git Bash ламається
--
-- 1. Розгортання бази elearn_db з нуля (схема, логіка, представлення, дані, ролі)
--      bash run_all.sh                          # очікується: OK: база elearn_db розгорнута
--
-- 2. Інтерактивна консоль psql
--      psql -U postgres -d elearn_db            # далі: SET search_path = edu;  \dt  \dv  \df  \du
--
-- 3. Запити й тести
--      psql -d elearn_db -f sql/06_queries.sql  # 17 запитів Q01–Q17 і 5 змін M01–M05 (з ROLLBACK)
--      psql -d elearn_db -f sql/07_tests.sql    # 28 тестів, очікується: 28 | 0
--      psql -d elearn_db -f sql/11_selects.sql  # цей файл
--      psql -d elearn_db -c "SELECT * FROM edu.v_course_overview"   # один запит
--
-- 4. Паралельний доступ (два сеанси, FOR UPDATE, lock_timeout)
--      python sql/08_concurrency.py
--
-- 5. Продуктивність (окрема база elearn_perf, 136 000 здач)
--      createdb elearn_perf
--      for f in 01_schema 02_logic 03_views 09_perf_data; do psql -d elearn_perf -q -f sql/$f.sql; done
--      python sql/09_performance.py             # EXPLAIN ANALYZE до/після індексів
--
-- 6. Резервне копіювання й відновлення (pg_dump -> pg_restore у elearn_restore + звірка)
--      bash sql/10_backup_restore.sh            # очікується: усі контрольні показники збігаються
--
-- 7. REST API + Swagger
--      pip install -r api/requirements.txt
--      python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
--      Swagger UI: http://127.0.0.1:8000/docs     ReDoc: http://127.0.0.1:8000/redoc
--      python api/smoke_test.py                 # в іншому терміналі; очікується 43 PASS, 0 FAIL
--      (smoke-тест додає рядки в базу — після нього можна знову виконати bash run_all.sh)
--
-- 8. Демонстраційні матеріали (з кореня репозиторію, не з bd/)
--      python docs/er_diagram.py                # ER-діаграма з каталогу -> docs/er_diagram.png
--      python presentation/build_deck.py        # презентація -> presentation/*.html
--
-- Зміст: A прості вибірки · B фільтри · C з'єднання · D агрегати · E підзапити
--        F CTE · G віконні функції · H інші конструкції · I JSONB-аудит
--        J представлення й функції · K системний каталог · L плани виконання
-- =====================================================================
SET search_path = edu, public;
SET timezone = 'Europe/Kyiv';


-- =====================================================================
-- A. ПРОСТІ ВИБІРКИ: вміст кожної таблиці
-- =====================================================================

-- S01. Усі користувачі
SELECT id, email, full_name, role_code, is_active, created_at FROM users ORDER BY id;

-- S02. Категорії курсів (parent_id — батьківська категорія)
SELECT id, name, parent_id FROM categories ORDER BY id;

-- S03. Курси
SELECT id, code, title, status, category_id, teacher_id, start_date, end_date, max_students
FROM courses ORDER BY id;

-- S04. Модулі курсів
SELECT id, course_id, position, title FROM modules ORDER BY course_id, position;

-- S05. Навчальні матеріали
SELECT id, module_id, position, title, material_type, duration_min, url
FROM materials ORDER BY module_id, position;

-- S06. Завдання
SELECT id, module_id, title, max_score, max_attempts, due_at FROM assignments ORDER BY id;

-- S07. Записи студентів на курси
SELECT id, course_id, student_id, status, enrolled_at, final_score, completed_at
FROM enrollments ORDER BY id;

-- S08. Здані роботи
SELECT id, assignment_id, enrollment_id, attempt_no, status, is_late, submitted_at
FROM submissions ORDER BY id;

-- S09. Оцінки
SELECT id, submission_id, grader_id, score, feedback, graded_at FROM grades ORDER BY id;

-- S10. Прогрес перегляду матеріалів
SELECT enrollment_id, material_id, views_count, first_viewed_at, last_viewed_at
FROM material_progress ORDER BY enrollment_id, material_id;

-- S11. Журнал аудиту (останні 20 подій)
SELECT id, table_name, record_id, action, changed_by, changed_at
FROM audit_log ORDER BY id DESC LIMIT 20;

-- S12. Кількість рядків у кожній таблиці
SELECT 'users' AS table_name, count(*) FROM users
UNION ALL SELECT 'categories', count(*) FROM categories
UNION ALL SELECT 'courses', count(*) FROM courses
UNION ALL SELECT 'modules', count(*) FROM modules
UNION ALL SELECT 'materials', count(*) FROM materials
UNION ALL SELECT 'assignments', count(*) FROM assignments
UNION ALL SELECT 'enrollments', count(*) FROM enrollments
UNION ALL SELECT 'submissions', count(*) FROM submissions
UNION ALL SELECT 'grades', count(*) FROM grades
UNION ALL SELECT 'material_progress', count(*) FROM material_progress
UNION ALL SELECT 'audit_log', count(*) FROM audit_log;


-- =====================================================================
-- B. ФІЛЬТРАЦІЯ ТА СОРТУВАННЯ: WHERE, IN, BETWEEN, LIKE, IS NULL, LIMIT
-- =====================================================================

-- S13. Активні викладачі
SELECT id, full_name, email FROM users
WHERE role_code = 'teacher' AND is_active ORDER BY full_name;

-- S14. Опубліковані курси, що стартують у 2026 році
SELECT code, title, start_date FROM courses
WHERE status = 'published' AND start_date BETWEEN DATE '2026-01-01' AND DATE '2026-12-31'
ORDER BY start_date;

-- S15. Пошук курсів за фрагментом назви (без урахування регістру)
SELECT code, title FROM courses WHERE title ILIKE '%дан%';

-- S16. Матеріали типів «відео» та «pdf»
SELECT title, material_type, duration_min FROM materials
WHERE material_type IN ('video', 'pdf') ORDER BY duration_min DESC NULLS LAST;

-- S17. Матеріали без указаної тривалості (IS NULL)
SELECT id, title, material_type FROM materials WHERE duration_min IS NULL ORDER BY id;

-- S18. Роботи, здані із запізненням
SELECT id, assignment_id, enrollment_id, attempt_no, submitted_at FROM submissions
WHERE is_late ORDER BY submitted_at;

-- S19. П'ять останніх зданих робіт
SELECT id, enrollment_id, assignment_id, submitted_at FROM submissions
ORDER BY submitted_at DESC LIMIT 5;

-- S20. Друга сторінка списку користувачів (по 5 на сторінку)
SELECT id, full_name FROM users ORDER BY id LIMIT 5 OFFSET 5;

-- S21. Email-домени користувачів
SELECT DISTINCT split_part(email, '@', 2) AS domain FROM users ORDER BY domain;


-- =====================================================================
-- C. З'ЄДНАННЯ: INNER, LEFT, SELF JOIN, багатотабличні
-- =====================================================================

-- S22. Курси з назвою категорії та ПІБ викладача
SELECT c.code, c.title, cat.name AS category, t.full_name AS teacher
FROM courses c
JOIN categories cat ON cat.id = c.category_id
JOIN users t        ON t.id = c.teacher_id
ORDER BY c.code;

-- S23. Студенти кожного курсу зі статусом навчання
SELECT c.code, u.full_name AS student, e.status, e.final_score
FROM enrollments e
JOIN courses c ON c.id = e.course_id
JOIN users u   ON u.id = e.student_id
ORDER BY c.code, u.full_name;

-- S24. Повна структура курсу: модуль → матеріали та завдання
SELECT c.code, m.position AS module_no, m.title AS module,
       'матеріал' AS kind, mt.title AS item
FROM courses c JOIN modules m ON m.course_id = c.id JOIN materials mt ON mt.module_id = m.id
UNION ALL
SELECT c.code, m.position, m.title, 'завдання', a.title
FROM courses c JOIN modules m ON m.course_id = c.id JOIN assignments a ON a.module_id = m.id
ORDER BY code, module_no, kind, item;

-- S25. Робота → завдання → студент → оцінка → хто оцінив (LEFT JOIN: неоцінені теж)
SELECT s.id AS submission_id, a.title AS assignment, st.full_name AS student,
       s.attempt_no, g.score, a.max_score, gr.full_name AS graded_by
FROM submissions s
JOIN assignments a ON a.id = s.assignment_id
JOIN enrollments e ON e.id = s.enrollment_id
JOIN users st      ON st.id = e.student_id
LEFT JOIN grades g ON g.submission_id = s.id
LEFT JOIN users gr ON gr.id = g.grader_id
ORDER BY s.id;

-- S26. Категорія та її батьківська категорія (SELF JOIN)
SELECT ch.name AS category, p.name AS parent
FROM categories ch LEFT JOIN categories p ON p.id = ch.parent_id
ORDER BY p.name NULLS FIRST, ch.name;

-- S27. Викладачі разом із курсами (LEFT JOIN — викладачі без курсів теж)
SELECT t.full_name, c.code, c.status
FROM users t LEFT JOIN courses c ON c.teacher_id = t.id
WHERE t.role_code = 'teacher'
ORDER BY t.full_name, c.code;

-- S28. Які матеріали переглянув кожен студент
SELECT u.full_name, c.code, mt.title AS material, mp.views_count
FROM material_progress mp
JOIN enrollments e ON e.id = mp.enrollment_id
JOIN users u       ON u.id = e.student_id
JOIN courses c     ON c.id = e.course_id
JOIN materials mt  ON mt.id = mp.material_id
ORDER BY u.full_name, c.code, mt.title;


-- =====================================================================
-- D. АГРЕГАЦІЯ: GROUP BY, HAVING, FILTER, ROLLUP
-- =====================================================================

-- S29. Кількість користувачів за ролями
SELECT role_code, count(*) AS users, count(*) FILTER (WHERE is_active) AS active
FROM users GROUP BY role_code ORDER BY role_code;

-- S30. Кількість курсів за статусами
SELECT status, count(*) FROM courses GROUP BY status ORDER BY status;

-- S31. Записи на кожен курс за статусами (FILTER)
SELECT c.code,
       count(e.id)                                        AS total,
       count(e.id) FILTER (WHERE e.status = 'active')     AS active,
       count(e.id) FILTER (WHERE e.status = 'completed')  AS completed,
       count(e.id) FILTER (WHERE e.status = 'dropped')    AS dropped
FROM courses c LEFT JOIN enrollments e ON e.course_id = c.id
GROUP BY c.code ORDER BY c.code;

-- S32. Середній, мінімальний і максимальний бал за кожне завдання
SELECT a.title, count(g.id) AS graded, round(avg(g.score), 2) AS avg_score,
       min(g.score) AS min_score, max(g.score) AS max_score, a.max_score
FROM assignments a
LEFT JOIN submissions s ON s.assignment_id = a.id
LEFT JOIN grades g      ON g.submission_id = s.id
GROUP BY a.id, a.title, a.max_score
ORDER BY a.id;

-- S33. Курси, на які записано більше 5 студентів (HAVING)
SELECT c.code, count(*) AS students
FROM enrollments e JOIN courses c ON c.id = e.course_id
GROUP BY c.code HAVING count(*) > 5 ORDER BY students DESC;

-- S34. Частка запізнень серед робіт для кожного курсу, %
SELECT c.code, count(s.id) AS submissions,
       round(100.0 * count(s.id) FILTER (WHERE s.is_late) / NULLIF(count(s.id), 0), 1) AS late_pct
FROM courses c
JOIN enrollments e ON e.course_id = c.id
JOIN submissions s ON s.enrollment_id = e.id
GROUP BY c.code ORDER BY late_pct DESC;

-- S35. Загальна тривалість матеріалів кожного курсу, хв
SELECT c.code, count(mt.id) AS materials, coalesce(sum(mt.duration_min), 0) AS total_min
FROM courses c
LEFT JOIN modules m    ON m.course_id = c.id
LEFT JOIN materials mt ON mt.module_id = m.id
GROUP BY c.code ORDER BY total_min DESC;

-- S36. Кількість робіт за місяцями
SELECT date_trunc('month', submitted_at)::date AS month, count(*) AS submissions
FROM submissions GROUP BY 1 ORDER BY 1;

-- S37. Проміжні та загальний підсумки записів: курс + статус (ROLLUP)
SELECT coalesce(c.code, 'УСЬОГО') AS course, coalesce(e.status, 'усі статуси') AS status, count(*)
FROM enrollments e JOIN courses c ON c.id = e.course_id
GROUP BY ROLLUP (c.code, e.status)
ORDER BY c.code NULLS LAST, e.status NULLS LAST;

-- S38. Список студентів курсу одним рядком (string_agg)
SELECT c.code, string_agg(u.full_name, ', ' ORDER BY u.full_name) AS students
FROM enrollments e JOIN courses c ON c.id = e.course_id JOIN users u ON u.id = e.student_id
GROUP BY c.code ORDER BY c.code;


-- =====================================================================
-- E. ПІДЗАПИТИ: IN, EXISTS / NOT EXISTS, скалярні, корельовані, ANY/ALL
-- =====================================================================

-- S39. Студенти, записані хоча б на один курс (IN)
SELECT id, full_name FROM users
WHERE id IN (SELECT student_id FROM enrollments) ORDER BY id;

-- S40. Студенти без жодного запису на курс (NOT EXISTS)
SELECT id, full_name FROM users u
WHERE role_code = 'student'
  AND NOT EXISTS (SELECT 1 FROM enrollments e WHERE e.student_id = u.id);

-- S41. Завдання, до яких ще не здано жодної роботи
SELECT a.id, a.title FROM assignments a
WHERE NOT EXISTS (SELECT 1 FROM submissions s WHERE s.assignment_id = a.id);

-- S42. Роботи, що очікують оцінки
SELECT s.id, s.submitted_at FROM submissions s
WHERE NOT EXISTS (SELECT 1 FROM grades g WHERE g.submission_id = s.id)
ORDER BY s.submitted_at;

-- S43. Кількість студентів курсу поруч із кожним курсом (скалярний підзапит)
SELECT c.code, c.max_students,
       (SELECT count(*) FROM enrollments e WHERE e.course_id = c.id) AS enrolled
FROM courses c ORDER BY c.code;

-- S44. Оцінки, вищі за середню оцінку свого завдання (корельований підзапит)
SELECT s.assignment_id, g.score
FROM grades g JOIN submissions s ON s.id = g.submission_id
WHERE g.score > (SELECT avg(g2.score) FROM grades g2
                 JOIN submissions s2 ON s2.id = g2.submission_id
                 WHERE s2.assignment_id = s.assignment_id)
ORDER BY s.assignment_id, g.score DESC;

-- S45. Курси з найбільшою кількістю модулів (>= ALL)
SELECT c.code, count(m.id) AS modules
FROM courses c JOIN modules m ON m.course_id = c.id
GROUP BY c.code
HAVING count(m.id) >= ALL (SELECT count(*) FROM modules GROUP BY course_id);

-- S46. Студенти, що мають хоча б одну оцінку >= 90 % максимуму завдання (= ANY)
SELECT full_name FROM users
WHERE id = ANY (SELECT e.student_id FROM grades g
                JOIN submissions s ON s.id = g.submission_id
                JOIN assignments a ON a.id = s.assignment_id
                JOIN enrollments e ON e.id = s.enrollment_id
                WHERE g.score >= 0.9 * a.max_score)
ORDER BY full_name;


-- =====================================================================
-- F. CTE (WITH) ТА РЕКУРСИВНІ ЗАПИТИ
-- =====================================================================

-- S47. Дерево категорій з рівнем вкладеності та повним шляхом (WITH RECURSIVE)
WITH RECURSIVE tree AS (
    SELECT id, name, parent_id, 1 AS lvl, name::text AS path
    FROM categories WHERE parent_id IS NULL
    UNION ALL
    SELECT c.id, c.name, c.parent_id, t.lvl + 1, t.path || ' / ' || c.name
    FROM categories c JOIN tree t ON c.parent_id = t.id
)
SELECT lvl, repeat('    ', lvl - 1) || name AS category, path
FROM tree ORDER BY path;

-- S48. Усі курси категорії «Інформаційні технології» з урахуванням підкатегорій
WITH RECURSIVE sub AS (
    SELECT id FROM categories WHERE name = 'Інформаційні технології'
    UNION ALL
    SELECT c.id FROM categories c JOIN sub ON c.parent_id = sub.id
)
SELECT c.code, c.title, cat.name AS category
FROM courses c JOIN categories cat ON cat.id = c.category_id
WHERE c.category_id IN (SELECT id FROM sub) ORDER BY c.code;

-- S49. Найкраща оцінка студента за кожне завдання та підсумок (кілька CTE)
WITH best AS (
    SELECT e.id AS enrollment_id, s.assignment_id, max(g.score) AS best_score
    FROM enrollments e
    JOIN submissions s ON s.enrollment_id = e.id
    JOIN grades g      ON g.submission_id = s.id
    GROUP BY e.id, s.assignment_id
), per_student AS (
    SELECT enrollment_id, count(*) AS graded_assignments, sum(best_score) AS points
    FROM best GROUP BY enrollment_id
)
SELECT c.code, u.full_name, p.graded_assignments, p.points
FROM per_student p
JOIN enrollments e ON e.id = p.enrollment_id
JOIN courses c     ON c.id = e.course_id
JOIN users u       ON u.id = e.student_id
ORDER BY c.code, p.points DESC;

-- S50. Календар: кількість робіт за кожен тиждень періоду, включно з порожніми (generate_series)
WITH weeks AS (
    SELECT generate_series(date_trunc('week', min(submitted_at)),
                           date_trunc('week', max(submitted_at)), interval '1 week') AS wk
    FROM submissions
)
SELECT w.wk::date AS week_start, count(s.id) AS submissions
FROM weeks w
LEFT JOIN submissions s ON date_trunc('week', s.submitted_at) = w.wk
GROUP BY w.wk ORDER BY w.wk;


-- =====================================================================
-- G. ВІКОННІ ФУНКЦІЇ
-- =====================================================================

-- S51. Рейтинг студентів у межах курсу за підсумковим балом (RANK, DENSE_RANK, ROW_NUMBER)
SELECT c.code, u.full_name, e.final_score,
       rank()       OVER w AS rnk,
       dense_rank() OVER w AS dense_rnk,
       row_number() OVER w AS row_no
FROM enrollments e
JOIN courses c ON c.id = e.course_id
JOIN users u   ON u.id = e.student_id
WHERE e.final_score IS NOT NULL
WINDOW w AS (PARTITION BY c.code ORDER BY e.final_score DESC)
ORDER BY c.code, rnk;

-- S52. Наростаючий підсумок робіт за датою (SUM ... OVER)
SELECT submitted_at::date AS day, count(*) AS per_day,
       sum(count(*)) OVER (ORDER BY submitted_at::date) AS running_total
FROM submissions GROUP BY submitted_at::date ORDER BY day;

-- S53. Зміна оцінки між спробами одного завдання (LAG)
SELECT e.student_id, s.assignment_id, s.attempt_no, g.score,
       g.score - lag(g.score) OVER (PARTITION BY s.enrollment_id, s.assignment_id
                                    ORDER BY s.attempt_no) AS delta
FROM submissions s
JOIN enrollments e ON e.id = s.enrollment_id
JOIN grades g      ON g.submission_id = s.id
ORDER BY e.student_id, s.assignment_id, s.attempt_no;

-- S54. Відхилення оцінки від середньої за завданням (AVG ... OVER PARTITION)
SELECT s.assignment_id, g.score,
       round(avg(g.score) OVER (PARTITION BY s.assignment_id), 2) AS avg_for_assignment,
       round(g.score - avg(g.score) OVER (PARTITION BY s.assignment_id), 2) AS diff
FROM grades g JOIN submissions s ON s.id = g.submission_id
ORDER BY s.assignment_id, g.score DESC;

-- S55. Розподіл оцінок на 4 групи — квартилі (NTILE) і процентиль (PERCENT_RANK)
SELECT g.id, g.score,
       ntile(4) OVER (ORDER BY g.score)                       AS quartile,
       round(percent_rank() OVER (ORDER BY g.score)::numeric, 2) AS pct_rank
FROM grades g ORDER BY g.score;

-- S56. Топ-3 студенти кожного курсу (ROW_NUMBER у підзапиті)
SELECT code, full_name, final_score FROM (
    SELECT c.code, u.full_name, e.final_score,
           row_number() OVER (PARTITION BY c.id ORDER BY e.final_score DESC) AS rn
    FROM enrollments e
    JOIN courses c ON c.id = e.course_id
    JOIN users u   ON u.id = e.student_id
    WHERE e.final_score IS NOT NULL
) t WHERE rn <= 3 ORDER BY code, final_score DESC;

-- S57. Перша й остання робота кожного запису на курс (FIRST_VALUE / LAST_VALUE)
SELECT DISTINCT enrollment_id,
       first_value(submitted_at) OVER w AS first_submission,
       last_value(submitted_at)  OVER w AS last_submission
FROM submissions
WINDOW w AS (PARTITION BY enrollment_id ORDER BY submitted_at
             ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING)
ORDER BY enrollment_id;


-- =====================================================================
-- H. ІНШІ КОНСТРУКЦІЇ: DISTINCT ON, CASE, UNION/INTERSECT/EXCEPT, дати
-- =====================================================================

-- S58. Остання спроба кожного студента за кожним завданням (DISTINCT ON)
SELECT DISTINCT ON (enrollment_id, assignment_id)
       enrollment_id, assignment_id, attempt_no, status, submitted_at
FROM submissions
ORDER BY enrollment_id, assignment_id, attempt_no DESC;

-- S59. Оцінка словами (CASE)
SELECT g.id, g.score, a.max_score,
       CASE WHEN g.score >= 0.9 * a.max_score THEN 'відмінно'
            WHEN g.score >= 0.75 * a.max_score THEN 'добре'
            WHEN g.score >= 0.6 * a.max_score THEN 'задовільно'
            ELSE 'незадовільно' END AS mark
FROM grades g
JOIN submissions s ON s.id = g.submission_id
JOIN assignments a ON a.id = s.assignment_id
ORDER BY g.id;

-- S60. Хто вчить і хто вчиться: викладачі та студенти одним списком (UNION)
SELECT full_name, 'викладає курс ' || c.code AS role FROM users u JOIN courses c ON c.teacher_id = u.id
UNION
SELECT full_name, 'навчається на ' || c.code FROM users u
JOIN enrollments e ON e.student_id = u.id JOIN courses c ON c.id = e.course_id
ORDER BY 1, 2;

-- S61. Студенти, записані і на DB-101, і на PY-101 (INTERSECT)
SELECT e.student_id FROM enrollments e JOIN courses c ON c.id = e.course_id WHERE c.code = 'DB-101'
INTERSECT
SELECT e.student_id FROM enrollments e JOIN courses c ON c.id = e.course_id WHERE c.code = 'PY-101';

-- S62. Студенти DB-101, які не навчаються на WEB-201 (EXCEPT)
SELECT e.student_id FROM enrollments e JOIN courses c ON c.id = e.course_id WHERE c.code = 'DB-101'
EXCEPT
SELECT e.student_id FROM enrollments e JOIN courses c ON c.id = e.course_id WHERE c.code = 'WEB-201';

-- S63. Тривалість курсів і скільки днів лишилося до завершення
SELECT code, start_date, end_date,
       end_date - start_date                        AS duration_days,
       GREATEST(end_date - current_date, 0)         AS days_left,
       to_char(start_date, 'DD.MM.YYYY')            AS start_formatted
FROM courses ORDER BY start_date;

-- S64. Завдання з дедлайном у найближчі 30 днів
SELECT title, due_at FROM assignments
WHERE due_at BETWEEN now() AND now() + interval '30 days' ORDER BY due_at;

-- S65. Наскільки раніше / пізніше дедлайну здано роботу
SELECT s.id, a.title, a.due_at, s.submitted_at,
       s.submitted_at - a.due_at AS vs_deadline, s.is_late
FROM submissions s JOIN assignments a ON a.id = s.assignment_id
ORDER BY vs_deadline DESC;

-- S66. Матеріали з порожнім URL замінюються на «—» (COALESCE)
SELECT title, material_type, coalesce(url, '—') AS url FROM materials ORDER BY id;


-- =====================================================================
-- I. ЖУРНАЛ АУДИТУ (JSONB)
-- =====================================================================

-- S67. Кількість подій аудиту за таблицями та діями
SELECT table_name, action, count(*) FROM audit_log GROUP BY table_name, action ORDER BY 1, 2;

-- S68. Історія змін оцінок: старе та нове значення з JSONB
SELECT record_id AS grade_id, action,
       old_data ->> 'score' AS old_score,
       new_data ->> 'score' AS new_score,
       changed_by, changed_at
FROM audit_log WHERE table_name = 'grades' ORDER BY changed_at;

-- S69. Історія змін статусу курсів
SELECT record_id AS course_id, old_data ->> 'status' AS from_status,
       new_data ->> 'status' AS to_status, changed_by, changed_at
FROM audit_log WHERE table_name = 'courses' ORDER BY changed_at;

-- S70. Події, у яких нові дані містять ключ feedback (оператор ?)
SELECT id, table_name, record_id, new_data -> 'feedback' AS feedback
FROM audit_log WHERE new_data ? 'feedback' LIMIT 10;


-- =====================================================================
-- J. ПРЕДСТАВЛЕННЯ ТА ФУНКЦІЇ БАЗИ
-- =====================================================================

-- S71. Огляд курсів: модулі, матеріали, завдання, студенти, вільні місця
SELECT * FROM v_course_overview ORDER BY code;

-- S72. Журнал оцінок (найкращий бал студента за кожне завдання)
SELECT * FROM v_gradebook ORDER BY course_code, student, assignment;

-- S73. Роботи, що чекають перевірки викладачем
SELECT * FROM v_pending_reviews ORDER BY submitted_at;

-- S74. Матеріалізована статистика курсів (оновлюється SELECT refresh_course_stats())
SELECT * FROM mv_course_stats ORDER BY code;

-- S75. Прогрес і поточний бал кожного запису на курс (функції бази)
SELECT e.id AS enrollment_id, c.code, u.full_name,
       fn_course_progress(e.id)  AS progress_pct,
       fn_enrollment_score(e.id) AS score
FROM enrollments e
JOIN courses c ON c.id = e.course_id
JOIN users u   ON u.id = e.student_id
ORDER BY c.code, progress_pct DESC;

-- S76. Звіт по курсу (табличний результат функції)
SELECT * FROM fn_course_report(1);

-- S77. Звіт по кожному опублікованому курсу (LATERAL-виклик функції)
SELECT c.code, r.*
FROM courses c CROSS JOIN LATERAL fn_course_report(c.id) r
WHERE c.status = 'published'
ORDER BY c.code, r.score DESC NULLS LAST;


-- =====================================================================
-- K. СИСТЕМНИЙ КАТАЛОГ: структура, обмеження, тригери, індекси, ролі
-- =====================================================================

-- S78. Таблиці схеми edu, кількість рядків і розмір на диску
SELECT c.relname AS table_name, c.reltuples::bigint AS approx_rows,
       pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'edu' AND c.relkind = 'r'
ORDER BY pg_total_relation_size(c.oid) DESC;

-- S79. Колонки таблиці courses з типами й обов'язковістю
SELECT column_name, data_type, character_maximum_length, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'edu' AND table_name = 'courses'
ORDER BY ordinal_position;

-- S80. Усі обмеження цілісності (PK, FK, UNIQUE, CHECK)
SELECT conrelid::regclass AS table_name, conname,
       CASE contype WHEN 'p' THEN 'PRIMARY KEY' WHEN 'f' THEN 'FOREIGN KEY'
                    WHEN 'u' THEN 'UNIQUE' WHEN 'c' THEN 'CHECK' END AS type,
       pg_get_constraintdef(oid) AS definition
FROM pg_constraint
WHERE connamespace = 'edu'::regnamespace
ORDER BY conrelid::regclass::text, type, conname;

-- S81. Зовнішні ключі та правила ON DELETE
SELECT conrelid::regclass AS child, confrelid::regclass AS parent, conname,
       CASE confdeltype WHEN 'a' THEN 'NO ACTION' WHEN 'r' THEN 'RESTRICT'
                        WHEN 'c' THEN 'CASCADE' WHEN 'n' THEN 'SET NULL' END AS on_delete
FROM pg_constraint
WHERE contype = 'f' AND connamespace = 'edu'::regnamespace
ORDER BY conrelid::regclass::text, conname;

-- S82. Тригери схеми edu
SELECT event_object_table AS table_name, trigger_name, action_timing, event_manipulation
FROM information_schema.triggers
WHERE trigger_schema = 'edu'
ORDER BY table_name, trigger_name, event_manipulation;

-- S83. Функції та процедури схеми edu
SELECT p.proname,
       CASE p.prokind WHEN 'f' THEN 'function' WHEN 'p' THEN 'procedure' END AS kind,
       pg_get_function_arguments(p.oid) AS arguments,
       pg_get_function_result(p.oid)    AS returns,
       p.prosecdef                      AS security_definer
FROM pg_proc p WHERE p.pronamespace = 'edu'::regnamespace
ORDER BY kind, p.proname;

-- S84. Індекси та їхні визначення
SELECT tablename, indexname, indexdef FROM pg_indexes
WHERE schemaname = 'edu' ORDER BY tablename, indexname;

-- S85. Наскільки часто використовуються індекси
SELECT relname AS table_name, indexrelname AS index_name, idx_scan, idx_tup_read
FROM pg_stat_user_indexes WHERE schemaname = 'edu'
ORDER BY idx_scan DESC;

-- S86. Ролі застосунку та їхні атрибути
SELECT rolname, rolcanlogin, rolinherit, rolconnlimit
FROM pg_roles WHERE rolname LIKE 'edu\_%' ORDER BY rolname;

-- S87. Права ролей на виконання функцій і процедур
SELECT grantee, routine_name, privilege_type
FROM information_schema.routine_privileges
WHERE routine_schema = 'edu' AND grantee LIKE 'edu\_%'
ORDER BY grantee, routine_name;

-- S88. Права ролей на таблиці й представлення
SELECT grantee, table_name, string_agg(privilege_type, ', ' ORDER BY privilege_type) AS privileges
FROM information_schema.role_table_grants
WHERE table_schema = 'edu' AND grantee LIKE 'edu\_%'
GROUP BY grantee, table_name
ORDER BY grantee, table_name;

-- S89. Представлення та їхній SQL
SELECT viewname, definition FROM pg_views WHERE schemaname = 'edu' ORDER BY viewname;

-- S90. Відомості про сервер і поточний сеанс
SELECT version() AS version, current_database() AS db, current_user AS usr,
       current_setting('transaction_isolation') AS isolation,
       pg_size_pretty(pg_database_size(current_database())) AS db_size;

-- S91. Активні підключення до бази
SELECT pid, usename, application_name, state, backend_start
FROM pg_stat_activity WHERE datname = current_database();


-- =====================================================================
-- L. ПЛАНИ ВИКОНАННЯ
-- =====================================================================

-- S92. План запиту без виконання
EXPLAIN
SELECT * FROM submissions WHERE enrollment_id = 7 ORDER BY submitted_at DESC LIMIT 10;

-- S93. План із фактичним виконанням, часом і буферами
EXPLAIN (ANALYZE, BUFFERS)
SELECT c.code, count(*) FROM enrollments e JOIN courses c ON c.id = e.course_id GROUP BY c.code;
