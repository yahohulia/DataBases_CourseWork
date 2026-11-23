-- =====================================================================
-- Скрипт 09: генерація великого набору даних для дослідження індексів.
-- Виконується в ОКРЕМІЙ базі elearn_perf після 01_schema, 02_logic, 03_views:
--   createdb elearn_perf; psql -d elearn_perf -f 01_schema.sql ... -f 09_perf_data.sql
-- Обсяг: 1 викладач, 4 000 студентів, 50 курсів, 150 модулів,
--        300 завдань, 20 000 записів на курси, ~120 000 зданих робіт.
-- Дані детерміновані (без random()), тому результат відтворюваний.
-- =====================================================================
SET search_path = edu, public;

INSERT INTO edu.users (email, full_name, role_code)
VALUES ('perf.teacher@elearn.test', 'Викладач Тестовий', 'teacher');

INSERT INTO edu.users (email, full_name, role_code, created_at)
SELECT format('perf%s@elearn.test', g), format('Студент %s', g), 'student',
       '2026-08-01'::timestamptz + g * interval '1 minute'
FROM generate_series(1, 4000) g;

INSERT INTO edu.categories (name) VALUES ('Навантажувальний тест');

INSERT INTO edu.courses (code, title, category_id, teacher_id, status,
                         start_date, end_date, max_students)
SELECT format('PERF-%s', lpad(g::text, 3, '0')), format('Курс %s', g), 1, 1,
       'published', '2026-09-01', '2026-12-31', 1000
FROM generate_series(1, 50) g;

INSERT INTO edu.modules (course_id, title, position)
SELECT c, format('Модуль %s.%s', c, p), p
FROM generate_series(1, 50) c, generate_series(1, 3) p;

INSERT INTO edu.assignments (module_id, title, max_score, due_at, max_attempts)
SELECT m.id, format('Завдання %s.%s', m.id, n), 20,
       '2026-09-15 23:59+03'::timestamptz + ((m.position - 1) * 30 + n * 10) * interval '1 day', 3
FROM edu.modules m, generate_series(1, 2) n;

-- кожен студент записаний на 5 курсів
INSERT INTO edu.enrollments (course_id, student_id, enrolled_at)
SELECT ((s * 7 + k * 11) % 50) + 1, s + 1,
       '2026-08-25'::timestamptz + (s % 120) * interval '1 hour'
FROM generate_series(1, 4000) s, generate_series(0, 4) k;

-- здані роботи: кожен запис здає 6 завдань свого курсу (частина — двічі)
INSERT INTO edu.submissions (assignment_id, enrollment_id, answer_url, submitted_at)
SELECT a.id, e.id, 'https://git.elearn.test/p/' || e.id || '/' || a.id,
       a.due_at - ((e.id + a.id) % 240) * interval '1 hour' + ((e.id % 10) = 0)::int * interval '12 days'
FROM edu.enrollments e
JOIN edu.modules m     ON m.course_id = e.course_id
JOIN edu.assignments a ON a.module_id = m.id;

INSERT INTO edu.submissions (assignment_id, enrollment_id, answer_url, submitted_at)
SELECT s.assignment_id, s.enrollment_id, s.answer_url || '/v2', s.submitted_at + interval '2 days'
FROM edu.submissions s
WHERE (s.enrollment_id + s.assignment_id) % 6 = 0;

ANALYZE;
