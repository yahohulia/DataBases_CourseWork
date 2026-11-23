-- =====================================================================
-- Скрипт 03: представлення
-- =====================================================================
SET search_path = edu, public;

-- V1. Огляд курсів: викладач, категорія, кількість модулів, матеріалів,
--     завдань, активних студентів і вільних місць
CREATE OR REPLACE VIEW edu.v_course_overview AS
SELECT c.id            AS course_id,
       c.code,
       c.title,
       c.status,
       cat.name        AS category,
       t.full_name     AS teacher,
       c.start_date,
       c.end_date,
       c.max_students,
       (SELECT count(*) FROM edu.modules m WHERE m.course_id = c.id)          AS modules_cnt,
       (SELECT count(*) FROM edu.modules m JOIN edu.materials mt ON mt.module_id = m.id
         WHERE m.course_id = c.id)                                             AS materials_cnt,
       (SELECT count(*) FROM edu.modules m JOIN edu.assignments a ON a.module_id = m.id
         WHERE m.course_id = c.id)                                             AS assignments_cnt,
       (SELECT count(*) FROM edu.enrollments e
         WHERE e.course_id = c.id AND e.status <> 'dropped')                   AS students_cnt,
       c.max_students - (SELECT count(*) FROM edu.enrollments e
         WHERE e.course_id = c.id AND e.status <> 'dropped')                   AS free_seats
FROM edu.courses c
JOIN edu.categories cat ON cat.id = c.category_id
JOIN edu.users t        ON t.id = c.teacher_id;

-- V2. Журнал успішності: найкраща оцінка студента за кожне завдання
CREATE OR REPLACE VIEW edu.v_gradebook AS
SELECT c.id          AS course_id,
       c.code        AS course_code,
       u.id          AS student_id,
       u.full_name   AS student,
       a.id          AS assignment_id,
       a.title       AS assignment,
       a.max_score,
       count(s.id)   AS attempts,
       max(g.score)  AS best_score,
       bool_or(s.is_late) AS was_late
FROM edu.enrollments e
JOIN edu.courses c      ON c.id = e.course_id
JOIN edu.users u        ON u.id = e.student_id
JOIN edu.modules m      ON m.course_id = c.id
JOIN edu.assignments a  ON a.module_id = m.id
LEFT JOIN edu.submissions s ON s.assignment_id = a.id AND s.enrollment_id = e.id
LEFT JOIN edu.grades g  ON g.submission_id = s.id
GROUP BY c.id, c.code, u.id, u.full_name, a.id, a.title, a.max_score;

-- V3. Черга перевірки для викладача: роботи без оцінки (остання спроба)
CREATE OR REPLACE VIEW edu.v_pending_reviews AS
SELECT DISTINCT ON (s.assignment_id, s.enrollment_id)
       s.id           AS submission_id,
       c.teacher_id,
       c.code         AS course_code,
       a.title        AS assignment,
       u.full_name    AS student,
       s.attempt_no,
       s.submitted_at,
       s.is_late
FROM edu.submissions s
JOIN edu.assignments a ON a.id = s.assignment_id
JOIN edu.modules m     ON m.id = a.module_id
JOIN edu.courses c     ON c.id = m.course_id
JOIN edu.enrollments e ON e.id = s.enrollment_id
JOIN edu.users u       ON u.id = e.student_id
WHERE s.status = 'submitted'
ORDER BY s.assignment_id, s.enrollment_id, s.attempt_no DESC;

-- V4. Матеріалізована статистика курсів для аналітика
CREATE MATERIALIZED VIEW edu.mv_course_stats AS
SELECT c.id AS course_id,
       c.code,
       count(DISTINCT e.id)                                    AS enrollments,
       count(DISTINCT e.id) FILTER (WHERE e.status = 'completed') AS completed,
       round(avg(e.final_score) FILTER (WHERE e.status = 'completed'), 2) AS avg_final,
       count(s.id)                                             AS submissions,
       round(100.0 * count(s.id) FILTER (WHERE s.is_late)
             / NULLIF(count(s.id), 0), 1)                      AS late_pct
FROM edu.courses c
LEFT JOIN edu.enrollments e ON e.course_id = c.id
LEFT JOIN edu.submissions s ON s.enrollment_id = e.id
GROUP BY c.id, c.code
WITH NO DATA;
CREATE UNIQUE INDEX mv_course_stats_pk ON edu.mv_course_stats (course_id);

-- Оновлення матеріалізованого представлення без прав власника
-- (виконується від імені власника схеми)
CREATE OR REPLACE FUNCTION edu.refresh_course_stats()
RETURNS void LANGUAGE sql
SECURITY DEFINER SET search_path = edu, pg_temp AS $$
    REFRESH MATERIALIZED VIEW CONCURRENTLY edu.mv_course_stats;
$$;
