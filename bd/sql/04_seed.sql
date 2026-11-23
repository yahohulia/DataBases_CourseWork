-- =====================================================================
-- Скрипт 04: тестові дані (синтетичні, без реальних персональних даних)
-- Виконується на щойно створеній схемі: ідентифікатори 1..N відповідають
-- порядку вставлення.
-- =====================================================================
SET search_path = edu, public;
SET timezone = 'Europe/Kyiv';

-- Користувачі: 1 адміністратор, 4 викладачі (2–5), 16 студентів (6–21)
INSERT INTO edu.users (email, full_name, role_code, is_active, created_at) VALUES
 ('admin@elearn.test',        'Коваленко Олена Петрівна',     'admin',   true, '2026-08-01 09:00+03'),
 ('a.shevchenko@elearn.test', 'Шевченко Андрій Іванович',     'teacher', true, '2026-08-05 10:00+03'),
 ('i.bondarenko@elearn.test', 'Бондаренко Ірина Миколаївна',  'teacher', true, '2026-08-05 10:05+03'),
 ('s.melnyk@elearn.test',     'Мельник Сергій Олегович',      'teacher', true, '2026-08-06 11:00+03'),
 ('n.tkachenko@elearn.test',  'Ткаченко Наталія Василівна',   'teacher', true, '2026-08-06 11:30+03'),
 ('st01@elearn.test', 'Іваненко Максим Андрійович',    'student', true, '2026-08-20 12:00+03'),
 ('st02@elearn.test', 'Петренко Анна Сергіївна',       'student', true, '2026-08-20 12:10+03'),
 ('st03@elearn.test', 'Савченко Дмитро Олегович',      'student', true, '2026-08-21 09:15+03'),
 ('st04@elearn.test', 'Кравчук Юлія Василівна',        'student', true, '2026-08-21 14:40+03'),
 ('st05@elearn.test', 'Олійник Артем Ігорович',        'student', true, '2026-08-22 08:05+03'),
 ('st06@elearn.test', 'Лисенко Марія Павлівна',        'student', true, '2026-08-22 16:20+03'),
 ('st07@elearn.test', 'Руденко Владислав Юрійович',    'student', true, '2026-08-23 10:00+03'),
 ('st08@elearn.test', 'Мороз Софія Олександрівна',     'student', true, '2026-08-23 11:45+03'),
 ('st09@elearn.test', 'Гончаренко Богдан Миколайович', 'student', true, '2026-08-24 13:30+03'),
 ('st10@elearn.test', 'Поліщук Вікторія Романівна',    'student', true, '2026-08-24 18:10+03'),
 ('st11@elearn.test', 'Кузьменко Олег Тарасович',      'student', true, '2026-08-25 09:00+03'),
 ('st12@elearn.test', 'Литвиненко Дарина Ігорівна',    'student', true, '2026-08-25 09:30+03'),
 ('st13@elearn.test', 'Захарченко Назар Віталійович',  'student', true, '2026-08-26 15:00+03'),
 ('st14@elearn.test', 'Марченко Катерина Олегівна',    'student', true, '2026-08-27 17:25+03'),
 ('st15@elearn.test', 'Тимошенко Ілля Сергійович',     'student', true, '2026-08-28 12:00+03'),
 ('st16@elearn.test', 'Остапенко Ліна Андріївна',      'student', false,'2026-08-29 10:00+03');

-- Ієрархія категорій
INSERT INTO edu.categories (name, parent_id) VALUES
 ('Інформаційні технології', NULL),   -- 1
 ('Програмування',            1),      -- 2
 ('Веб-розробка',             2),      -- 3
 ('Бази даних',               1),      -- 4
 ('Математика',               NULL),   -- 5
 ('Статистика',               5),      -- 6
 ('Іноземні мови',            NULL),   -- 7
 ('Штучний інтелект',         2);      -- 8

-- Курси (ENG-120 спочатку published, після завершення — archived)
INSERT INTO edu.courses (code, title, description, category_id, teacher_id,
                         status, start_date, end_date, max_students) VALUES
 ('DB-101',  'Бази даних та PostgreSQL',        'Проєктування та SQL', 4, 2, 'published', '2026-09-01', '2026-12-20', 25),
 ('WEB-201', 'Фронтенд-розробка на React',       'Компоненти, стан, хуки', 3, 3, 'published', '2026-09-08', '2026-12-15', 20),
 ('PY-101',  'Основи програмування на Python',  'Базовий курс', 2, 4, 'published', '2026-09-01', '2026-11-30', 6),
 ('STAT-110','Прикладна статистика',            'Описова статистика та гіпотези', 6, 5, 'published', '2026-09-15', '2026-12-25', 15),
 ('ENG-120', 'Англійська мова для ІТ',          'Технічна лексика', 7, 3, 'published', '2026-02-01', '2026-06-30', 10),
 ('ML-301',  'Машинне навчання',                'Курс у розробці', 8, 2, 'draft',     '2027-02-01', '2027-05-31', 20);

-- Модулі
INSERT INTO edu.modules (course_id, title, position) VALUES
 (1, 'Реляційна модель', 1), (1, 'SQL-запити', 2), (1, 'Транзакції та індекси', 3),
 (2, 'JSX і компоненти', 1), (2, 'Стан і хуки', 2),
 (3, 'Змінні та типи', 1),   (3, 'Функції та цикли', 2),
 (4, 'Описова статистика', 1), (4, 'Перевірка гіпотез', 2),
 (5, 'Технічна лексика', 1),
 (6, 'Вступ до ML', 1);

-- Навчальні матеріали (по два-три на модуль)
INSERT INTO edu.materials (module_id, title, material_type, url, content, duration_min, position) VALUES
 (1, 'Лекція: сутності та зв''язки', 'video', 'https://video.elearn.test/db/1', NULL, 45, 1),
 (1, 'Конспект: нормальні форми',    'pdf',   'https://files.elearn.test/db/nf.pdf', NULL, NULL, 2),
 (2, 'Лекція: SELECT і JOIN',        'video', 'https://video.elearn.test/db/2', NULL, 50, 1),
 (2, 'Шпаргалка з агрегатних функцій','text', NULL, 'COUNT, SUM, AVG, MIN, MAX; GROUP BY; HAVING', NULL, 2),
 (2, 'Документація PostgreSQL: SELECT','link','https://www.postgresql.org/docs/18/sql-select.html', NULL, NULL, 3),
 (3, 'Лекція: MVCC і блокування',    'video', 'https://video.elearn.test/db/3', NULL, 40, 1),
 (3, 'Практикум: EXPLAIN ANALYZE',   'text',  NULL, 'Порівняйте плани до і після створення індексу', NULL, 2),
 (4, 'Лекція: JSX',                  'video', 'https://video.elearn.test/web/1', NULL, 35, 1),
 (4, 'Приклад компонента',           'link',  'https://code.elearn.test/web/card', NULL, NULL, 2),
 (5, 'Лекція: useState і useEffect', 'video', 'https://video.elearn.test/web/2', NULL, 55, 1),
 (5, 'Конспект: правила хуків',      'pdf',   'https://files.elearn.test/web/hooks.pdf', NULL, NULL, 2),
 (6, 'Лекція: типи даних Python',    'video', 'https://video.elearn.test/py/1', NULL, 30, 1),
 (6, 'Вправи на змінні',             'text',  NULL, 'Обчисліть площу кола радіуса r', NULL, 2),
 (7, 'Лекція: функції',              'video', 'https://video.elearn.test/py/2', NULL, 40, 1),
 (7, 'Конспект: рекурсія',           'pdf',   'https://files.elearn.test/py/rec.pdf', NULL, NULL, 2),
 (8, 'Лекція: середнє, медіана, мода','video','https://video.elearn.test/stat/1', NULL, 45, 1),
 (8, 'Набір даних для практики',     'link',  'https://data.elearn.test/stat/set1.csv', NULL, NULL, 2),
 (9, 'Лекція: t-критерій Стьюдента', 'video', 'https://video.elearn.test/stat/2', NULL, 50, 1),
 (9, 'Таблиця критичних значень',    'pdf',   'https://files.elearn.test/stat/t.pdf', NULL, NULL, 2),
 (10,'Глосарій: бази даних',         'text',  NULL, 'table, row, column, key, index, query', NULL, 1),
 (10,'Відеоурок: code review',       'video', 'https://video.elearn.test/eng/1', NULL, 25, 2),
 (11,'Вступна лекція з ML',          'video', 'https://video.elearn.test/ml/1', NULL, 60, 1);

-- Завдання
INSERT INTO edu.assignments (module_id, title, description, max_score, due_at, max_attempts) VALUES
 (1, 'ER-модель предметної області', 'Побудувати ER-діаграму', 10, '2026-09-25 23:59+03', 3),  -- 1
 (2, 'Запити з JOIN та GROUP BY',    '10 запитів до навчальної БД', 20, '2026-10-16 23:59+03', 3), -- 2
 (3, 'Аналіз плану запиту',          'EXPLAIN до та після індексу', 20, '2026-11-13 23:59+02', 2), -- 3
 (4, 'Компонент картки товару',      'React-компонент', 15, '2026-10-05 23:59+03', 3),            -- 4
 (5, 'Todo-застосунок з хуками',     'useState, useEffect', 25, '2026-11-01 23:59+02', 3),      -- 5
 (6, 'Калькулятор ІМТ',              'Програма з введенням даних', 10, '2026-09-20 23:59+03', 3), -- 6
 (7, 'Рекурсивні функції',           'Факторіал, Фібоначчі', 10, '2026-10-10 23:59+03', 3),      -- 7
 (8, 'Розрахунок описових показників','Обробка CSV', 20, '2026-10-20 23:59+03', 3),            -- 8
 (9, 't-тест для двох вибірок',      'Звіт з висновком', 20, '2026-11-25 23:59+02', 2),        -- 9
 (10,'Глосарій термінів',            '30 термінів з прикладами', 10, '2026-04-15 23:59+03', 1); -- 10

-- Записи на курси (ідентифікатори 1–34)
INSERT INTO edu.enrollments (course_id, student_id, enrolled_at)
SELECT 1, s, '2026-08-28 10:00+03'::timestamptz + (s - 6) * interval '3 hours'
FROM generate_series(6, 15) AS s                       -- id 1–10
ORDER BY s;
INSERT INTO edu.enrollments (course_id, student_id, enrolled_at)
SELECT 2, s, '2026-09-02 12:00+03'::timestamptz + (s - 6) * interval '2 hours'
FROM unnest(ARRAY[6, 8, 10, 12, 14, 16, 17]) WITH ORDINALITY AS t(s, n)  -- id 11–17
ORDER BY n;
INSERT INTO edu.enrollments (course_id, student_id, enrolled_at)
SELECT 3, s, '2026-08-30 09:00+03'::timestamptz + n * interval '1 hour'
FROM unnest(ARRAY[7, 9, 11, 13, 15, 18]) WITH ORDINALITY AS t(s, n)       -- id 18–23 (6 з 6)
ORDER BY n;
INSERT INTO edu.enrollments (course_id, student_id, enrolled_at)
SELECT 4, s, '2026-09-10 15:00+03'::timestamptz + n * interval '5 hours'
FROM unnest(ARRAY[6, 7, 16, 17, 18, 19, 20]) WITH ORDINALITY AS t(s, n)   -- id 24–30
ORDER BY n;
INSERT INTO edu.enrollments (course_id, student_id, enrolled_at)
SELECT 5, s, '2026-01-25 10:00+02'::timestamptz + n * interval '1 day'
FROM unnest(ARRAY[8, 9, 10, 19]) WITH ORDINALITY AS t(s, n)               -- id 31–34
ORDER BY n;

-- Здані роботи. Детерміновані формули: частина робіт запізнюється
-- (enrollment_id % 4 = 0), частина студентів не здає завдання.
-- attempt_no та is_late встановлює тригер submissions_before_insert.
INSERT INTO edu.submissions (assignment_id, enrollment_id, answer_url, submitted_at)
SELECT a.id, e.id,
       'https://git.elearn.test/' || e.id || '/' || a.id,
       CASE WHEN e.id % 4 = 0
            THEN a.due_at + (e.id % 3 + 1) * interval '7 hours'
            ELSE a.due_at - (e.id % 5 + 1) * interval '1 day' + interval '3 hours' END
FROM edu.enrollments e
JOIN edu.modules m     ON m.course_id = e.course_id
JOIN edu.assignments a ON a.module_id = m.id
WHERE e.course_id IN (1, 2, 3, 4, 5)
  AND a.id NOT IN (3, 9)                      -- поточні завдання – окремо
  AND (e.id + a.id) % 7 <> 0                  -- деякі студенти не здали
ORDER BY a.id, e.id;

-- Поточне завдання 3: здала лише частина студентів
INSERT INTO edu.submissions (assignment_id, enrollment_id, answer_text, submitted_at)
SELECT 3, e.id, 'План: Seq Scan -> Index Scan', '2026-11-10 20:00+02'::timestamptz + e.id * interval '1 hour'
FROM edu.enrollments e WHERE e.course_id = 1 AND e.id <= 6
ORDER BY e.id;

-- Повторні спроби (attempt_no = 2) для слабких робіт завдання 2
INSERT INTO edu.submissions (assignment_id, enrollment_id, answer_url, submitted_at)
VALUES (2, 2, 'https://git.elearn.test/2/2-v2', '2026-10-15 18:00+03'),
       (2, 6, 'https://git.elearn.test/6/2-v2', '2026-10-16 21:30+03'),
       (4, 13,'https://git.elearn.test/13/4-v2','2026-10-04 12:00+03');

-- Оцінювання: перевірено всі роботи, крім завдання 3 та поточних спроб.
-- Бал детермінований: від 50 % до 98 % максимуму.
INSERT INTO edu.grades (submission_id, grader_id, score, feedback)
SELECT s.id, c.teacher_id,
       round(a.max_score * (50 + (s.enrollment_id * 13 + a.id * 7 + s.attempt_no * 11) % 49) / 100.0, 0),
       CASE WHEN s.is_late THEN 'Здано із запізненням' ELSE 'Зараховано' END
FROM edu.submissions s
JOIN edu.assignments a ON a.id = s.assignment_id
JOIN edu.modules m     ON m.id = a.module_id
JOIN edu.courses c     ON c.id = m.course_id
WHERE a.id <> 3
  AND NOT (s.assignment_id = 2 AND s.enrollment_id = 6 AND s.attempt_no = 2)
ORDER BY s.id;

-- Прогрес перегляду матеріалів
INSERT INTO edu.material_progress (enrollment_id, material_id, first_viewed_at, last_viewed_at, views_count)
SELECT e.id, mt.id,
       c.start_date + (mt.position + m.position * 7) * interval '1 day' + interval '19 hours',
       c.start_date + (mt.position + m.position * 7 + (e.id % 4)) * interval '1 day' + interval '21 hours',
       1 + (e.id + mt.id) % 4
FROM edu.enrollments e
JOIN edu.courses c    ON c.id = e.course_id
JOIN edu.modules m    ON m.course_id = c.id
JOIN edu.materials mt ON mt.module_id = m.id
WHERE (e.id + mt.id) % 5 <> 0;

-- Завершення курсу ENG-120: три студенти завершили, один відрахувався,
-- після чого курс переведено в архів (draft->published->archived)
CALL edu.complete_enrollment(31, NULL);
CALL edu.complete_enrollment(34, NULL);
CALL edu.complete_enrollment(33, NULL);
UPDATE edu.enrollments SET status = 'dropped' WHERE id = 32;
UPDATE edu.courses SET status = 'archived' WHERE code = 'ENG-120';

REFRESH MATERIALIZED VIEW edu.mv_course_stats;
ANALYZE;
