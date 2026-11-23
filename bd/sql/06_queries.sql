-- =====================================================================
-- Скрипт 06: запити користувачів (SELECT) та операції зміни даних
-- Кожен запит позначено кодом Qnn і питанням користувача.
-- Операції зміни виконуються в транзакції з ROLLBACK, щоб скрипт
-- можна було запускати повторно без зміни тестових даних.
-- =====================================================================
SET search_path = edu, public;
SET timezone = 'Europe/Kyiv';

-- Q01. Які курси опубліковані, хто їх веде і скільки вільних місць?
SELECT code, title, teacher, students_cnt, max_students, free_seats
FROM edu.v_course_overview
WHERE status = 'published'
ORDER BY code;

-- Q02. Яка структура курсу DB-101: модулі та матеріали у порядку вивчення?
SELECT m.position AS module_no, m.title AS module, mt.position AS item_no,
       mt.title AS material, mt.material_type
FROM edu.courses c
JOIN edu.modules m    ON m.course_id = c.id
JOIN edu.materials mt ON mt.module_id = m.id
WHERE c.code = 'DB-101'
ORDER BY m.position, mt.position;

-- Q03. Скільки студентів кожного викладача навчається на всіх його курсах
--      (включно з викладачами без студентів)?
SELECT t.full_name AS teacher,
       count(DISTINCT c.id) AS courses,
       count(e.id) FILTER (WHERE e.status = 'active') AS active_students
FROM edu.users t
LEFT JOIN edu.courses c     ON c.teacher_id = t.id
LEFT JOIN edu.enrollments e ON e.course_id = c.id
WHERE t.role_code = 'teacher'
GROUP BY t.id, t.full_name
ORDER BY active_students DESC, teacher;

-- Q04. Які студенти не записані на жоден курс?
SELECT u.id, u.full_name, u.is_active
FROM edu.users u
WHERE u.role_code = 'student'
  AND NOT EXISTS (SELECT 1 FROM edu.enrollments e WHERE e.student_id = u.id)
ORDER BY u.id;

-- Q05. Які студенти курсу DB-101 не здали завдання «Аналіз плану запиту»?
SELECT u.full_name
FROM edu.enrollments e
JOIN edu.users u   ON u.id = e.student_id
JOIN edu.courses c ON c.id = e.course_id
WHERE c.code = 'DB-101' AND e.status = 'active'
  AND NOT EXISTS (
      SELECT 1 FROM edu.submissions s
      JOIN edu.assignments a ON a.id = s.assignment_id
      WHERE s.enrollment_id = e.id AND a.title = 'Аналіз плану запиту')
ORDER BY u.full_name;

-- Q06. Статистика завдань: кількість зданих робіт, частка запізнень,
--      середній бал у відсотках від максимуму (лише завдання з >= 5 роботами)
SELECT a.title,
       count(s.id)                                   AS submissions,
       count(s.id) FILTER (WHERE s.is_late)          AS late,
       round(100.0 * avg(g.score / a.max_score), 1)  AS avg_pct
FROM edu.assignments a
JOIN edu.submissions s ON s.assignment_id = a.id
LEFT JOIN edu.grades g ON g.submission_id = s.id
GROUP BY a.id, a.title
HAVING count(s.id) >= 5
ORDER BY avg_pct DESC NULLS LAST;

-- Q07. Остання здана робота кожного студента курсу WEB-201 (DISTINCT ON)
SELECT DISTINCT ON (e.id)
       u.full_name, a.title AS assignment, s.attempt_no, s.submitted_at
FROM edu.enrollments e
JOIN edu.users u       ON u.id = e.student_id
JOIN edu.submissions s ON s.enrollment_id = e.id
JOIN edu.assignments a ON a.id = s.assignment_id
WHERE e.course_id = (SELECT id FROM edu.courses WHERE code = 'WEB-201')
ORDER BY e.id, s.submitted_at DESC, s.id DESC;

-- Q08. Рейтинг студентів курсу DB-101 за підсумковим балом (віконна RANK)
SELECT u.full_name,
       edu.fn_enrollment_score(e.id) AS score,
       RANK() OVER (ORDER BY edu.fn_enrollment_score(e.id) DESC) AS place
FROM edu.enrollments e
JOIN edu.users u ON u.id = e.student_id
WHERE e.course_id = 1
ORDER BY place, u.full_name;

-- Q09. Динаміка студента: зміна балу між послідовними завданнями (LAG)
SELECT u.full_name, a.due_at::date AS due, a.title,
       round(100 * g.score / a.max_score, 1) AS pct,
       round(100 * g.score / a.max_score
             - LAG(100 * g.score / a.max_score) OVER w, 1) AS delta_pct
FROM edu.enrollments e
JOIN edu.users u       ON u.id = e.student_id
JOIN edu.submissions s ON s.enrollment_id = e.id
JOIN edu.grades g      ON g.submission_id = s.id
JOIN edu.assignments a ON a.id = s.assignment_id
WHERE u.email = 'st01@elearn.test'
WINDOW w AS (PARTITION BY e.id ORDER BY a.due_at, s.attempt_no)
ORDER BY e.id, a.due_at, s.attempt_no;

-- Q10. Накопичувальна кількість здач курсу DB-101 за днями (ковзна сума)
SELECT s.submitted_at::date AS day,
       count(*) AS per_day,
       sum(count(*)) OVER (ORDER BY s.submitted_at::date) AS running_total
FROM edu.submissions s
JOIN edu.enrollments e ON e.id = s.enrollment_id
WHERE e.course_id = 1
GROUP BY s.submitted_at::date
ORDER BY day;

-- Q11. Повний шлях категорій курсів (рекурсивний CTE)
WITH RECURSIVE tree AS (
    SELECT id, name, parent_id, name::text AS path, 1 AS depth
    FROM edu.categories WHERE parent_id IS NULL
    UNION ALL
    SELECT c.id, c.name, c.parent_id, t.path || ' / ' || c.name, t.depth + 1
    FROM edu.categories c JOIN tree t ON c.parent_id = t.id
)
SELECT t.path, t.depth, count(co.id) AS courses
FROM tree t
LEFT JOIN edu.courses co ON co.category_id = t.id
GROUP BY t.path, t.depth
ORDER BY t.path;

-- Q12. Студенти, чий середній відсоток вищий за середній по курсу
--      (CTE + порівняння з агрегованим результатом)
WITH per_student AS (
    SELECT e.course_id, e.id AS enrollment_id, u.full_name,
           avg(100 * g.score / a.max_score) AS avg_pct
    FROM edu.enrollments e
    JOIN edu.users u       ON u.id = e.student_id
    JOIN edu.submissions s ON s.enrollment_id = e.id
    JOIN edu.grades g      ON g.submission_id = s.id
    JOIN edu.assignments a ON a.id = s.assignment_id
    GROUP BY e.course_id, e.id, u.full_name
)
SELECT c.code, p.full_name, round(p.avg_pct, 1) AS student_pct,
       round(ca.course_pct, 1) AS course_pct
FROM per_student p
JOIN edu.courses c ON c.id = p.course_id
JOIN (SELECT course_id, avg(avg_pct) AS course_pct
      FROM per_student GROUP BY course_id) ca ON ca.course_id = p.course_id
WHERE p.avg_pct > ca.course_pct
ORDER BY c.code, student_pct DESC;

-- Q13. Прогрес перегляду матеріалів студентами курсу PY-101
SELECT u.full_name,
       edu.fn_course_progress(e.id) AS progress_pct,
       coalesce(sum(mp.views_count), 0) AS total_views,
       max(mp.last_viewed_at) AS last_activity
FROM edu.enrollments e
JOIN edu.users u ON u.id = e.student_id
LEFT JOIN edu.material_progress mp ON mp.enrollment_id = e.id
WHERE e.course_id = 3
GROUP BY u.full_name, e.id
ORDER BY progress_pct DESC, u.full_name;

-- Q14. Черга перевірки викладача Шевченка А. І. (представлення)
SELECT course_code, assignment, student, attempt_no, submitted_at, is_late
FROM edu.v_pending_reviews
WHERE teacher_id = 2
ORDER BY submitted_at;

-- Q15. Звіт по курсу STAT-110 (таблична функція)
SELECT * FROM edu.fn_course_report(4);

-- Q16. Найпопулярніші матеріали: частка студентів курсу, що їх переглянули
SELECT c.code, mt.title,
       count(mp.enrollment_id) AS viewers,
       round(100.0 * count(mp.enrollment_id)
             / NULLIF((SELECT count(*) FROM edu.enrollments e2
                        WHERE e2.course_id = c.id), 0), 1) AS reach_pct
FROM edu.materials mt
JOIN edu.modules m ON m.id = mt.module_id
JOIN edu.courses c ON c.id = m.course_id
LEFT JOIN edu.material_progress mp ON mp.material_id = mt.id
WHERE c.status <> 'draft'
GROUP BY c.id, c.code, mt.id, mt.title
ORDER BY reach_pct DESC, c.code, mt.title
LIMIT 8;

-- Q17. Журнал аудиту: останні зміни статусів курсів
SELECT record_id AS course_id, old_data->>'status' AS old_status,
       new_data->>'status' AS new_status, changed_by
FROM edu.audit_log
WHERE table_name = 'courses'
ORDER BY changed_at DESC;

-- =====================================================================
-- Операції зміни даних (M01–M05)
-- =====================================================================
BEGIN;

-- M01. INSERT ... RETURNING: новий матеріал до модуля 3 курсу DB-101
INSERT INTO edu.materials (module_id, title, material_type, url, position)
VALUES (3, 'Документація: EXPLAIN', 'link',
        'https://www.postgresql.org/docs/18/using-explain.html', 3)
RETURNING id, title, material_type;

-- M02. UPDATE: продовження терміну здачі поточного завдання на 2 дні
UPDATE edu.assignments
SET due_at = due_at + interval '2 days'
WHERE title = 'Аналіз плану запиту'
RETURNING id, title, due_at;

-- M03. UPSERT (ON CONFLICT): повторний перегляд матеріалу збільшує лічильник
INSERT INTO edu.material_progress (enrollment_id, material_id)
VALUES (1, 1)
ON CONFLICT (enrollment_id, material_id) DO UPDATE
   SET views_count = edu.material_progress.views_count + 1,
       last_viewed_at = greatest(now(), edu.material_progress.last_viewed_at)
RETURNING enrollment_id, material_id, views_count;

-- M04. DELETE: видалення порожнього модуля чернетки курсу ML-301
DELETE FROM edu.materials WHERE module_id = 11;
DELETE FROM edu.modules
WHERE id = 11
  AND NOT EXISTS (SELECT 1 FROM edu.assignments a WHERE a.module_id = 11)
RETURNING id, title;

-- M05. Виклик процедур: оцінювання роботи та запис на курс
-- робота id 50 — перша здана робота завдання 3 «Аналіз плану запиту»
CALL edu.grade_submission(50, 2, 18, 'Добрий аналіз плану', NULL);
SELECT s.id, s.status, g.score FROM edu.submissions s
JOIN edu.grades g ON g.submission_id = s.id WHERE s.id = 50;
CALL edu.enroll_student(1, 16, NULL);   -- студент id 16 на курс DB-101

ROLLBACK;
