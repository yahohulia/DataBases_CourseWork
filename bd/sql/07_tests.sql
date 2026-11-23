-- =====================================================================
-- Скрипт 07: протокол функціональних, негативних і граничних перевірок
-- Запуск: psql -d elearn_db -f 07_tests.sql
-- Усі зміни виконуються в транзакції і скасовуються наприкінці (ROLLBACK),
-- тому скрипт можна запускати повторно. Результати — таблиця test_results.
-- =====================================================================
SET search_path = edu, public;
SET client_min_messages = warning;

-- ---------------------------------------------------------------------
-- T15 (окрема транзакція): зміна оцінки + ROLLBACK скасовує і оцінку,
-- і запис аудиту, створений тригером
-- ---------------------------------------------------------------------
SELECT (SELECT score FROM edu.grades WHERE submission_id = 1) AS t15_b_score,
       (SELECT count(*) FROM edu.audit_log) AS t15_b_audit \gset
BEGIN;
UPDATE edu.grades SET score = score - 1 WHERE submission_id = 1;
SELECT (SELECT score FROM edu.grades WHERE submission_id = 1) AS t15_i_score,
       (SELECT count(*) FROM edu.audit_log) AS t15_i_audit \gset
ROLLBACK;

-- ---------------------------------------------------------------------
BEGIN;
CREATE TEMP TABLE test_results (
    code text, action text, expected text, actual text, passed boolean
) ON COMMIT DROP;

-- Допоміжна тимчасова процедура: виконати SQL і порівняти SQLSTATE з очікуваним
CREATE PROCEDURE pg_temp.expect(p_code text, p_action text, p_sql text, p_expected text)
LANGUAGE plpgsql AS $$
DECLARE v_state text := 'OK'; v_msg text := '';
BEGIN
    BEGIN
        EXECUTE p_sql;
    EXCEPTION WHEN OTHERS THEN
        GET STACKED DIAGNOSTICS v_state = RETURNED_SQLSTATE, v_msg = MESSAGE_TEXT;
        v_state := CASE v_state
            WHEN '23505' THEN 'unique_violation'
            WHEN '23503' THEN 'foreign_key_violation'
            WHEN '23001' THEN 'restrict_violation'
            WHEN '23514' THEN 'check_violation'
            WHEN '23502' THEN 'not_null_violation'
            WHEN '42501' THEN 'insufficient_privilege'
            WHEN 'P0002' THEN 'no_data_found'
            ELSE v_state END;
    END;
    INSERT INTO test_results VALUES (p_code, p_action, p_expected,
        v_state || CASE WHEN v_msg <> '' THEN ': ' || v_msg ELSE '' END,
        v_state = p_expected);
END;
$$;

-- T01. Коректний запис студента (id 16) на курс DB-101 через процедуру
CALL pg_temp.expect('T01', 'CALL enroll_student(1, 16) — вільні місця є',
    'CALL edu.enroll_student(1, 16, NULL)', 'OK');

-- T02. Повторний запис того самого студента
CALL pg_temp.expect('T02', 'Повторний запис студента 16 на DB-101',
    'CALL edu.enroll_student(1, 16, NULL)', 'unique_violation');

-- T03. Запис на заповнений курс PY-101 (6 з 6)
CALL pg_temp.expect('T03', 'Запис на курс без вільних місць (PY-101)',
    'CALL edu.enroll_student(3, 17, NULL)', 'check_violation');

-- T04. Запис на курс-чернетку ML-301
CALL pg_temp.expect('T04', 'Запис на курс зі статусом draft',
    'CALL edu.enroll_student(6, 17, NULL)', 'check_violation');

-- T05. Запис викладача як студента
CALL pg_temp.expect('T05', 'Запис користувача з роллю teacher',
    'CALL edu.enroll_student(2, 2, NULL)', 'check_violation');

-- T06. Курс із датою завершення раніше початку
CALL pg_temp.expect('T06', 'end_date < start_date',
    $q$INSERT INTO edu.courses (code, title, category_id, teacher_id, start_date, end_date)
       VALUES ('TST-001', 'Тест', 1, 2, '2026-12-01', '2026-11-01')$q$, 'check_violation');

-- T07. E-mail, що відрізняється лише регістром
CALL pg_temp.expect('T07', 'Дублікат e-mail ST01@ELEARN.TEST',
    $q$INSERT INTO edu.users (email, full_name, role_code)
       VALUES ('ST01@ELEARN.TEST', 'Дублікат', 'student')$q$, 'unique_violation');

-- T08. Видалення студента, що має записи і роботи
CALL pg_temp.expect('T08', 'DELETE студента з історією навчання',
    'DELETE FROM edu.users WHERE id = 6', 'restrict_violation');

-- T09. Бал більший за max_score завдання (10)
CALL pg_temp.expect('T09', 'Оцінка 11 при max_score = 10',
    'UPDATE edu.grades SET score = 11 WHERE submission_id = 1', 'check_violation');

-- T10. Оцінювання викладачем іншого курсу
CALL pg_temp.expect('T10', 'grade_submission від викладача іншого курсу (id 3)',
    $q$CALL edu.grade_submission(50, 3, 15, 'x', NULL)$q$, 'check_violation');

-- T11. Здача роботи з завдання іншого курсу
CALL pg_temp.expect('T11', 'Завдання WEB-201 від запису на DB-101',
    $q$INSERT INTO edu.submissions (assignment_id, enrollment_id, answer_text)
       VALUES (4, 1, 'чужий курс')$q$, 'check_violation');

-- T12. Перевищення ліміту спроб (завдання 3: max_attempts = 2)
CALL pg_temp.expect('T12a', 'Друга спроба завдання 3 (у межах ліміту)',
    $q$INSERT INTO edu.submissions (assignment_id, enrollment_id, answer_text)
       VALUES (3, 1, 'спроба 2')$q$, 'OK');
CALL pg_temp.expect('T12b', 'Третя спроба завдання 3 (ліміт 2)',
    $q$INSERT INTO edu.submissions (assignment_id, enrollment_id, answer_text)
       VALUES (3, 1, 'спроба 3')$q$, 'check_violation');

-- T13. Тригер автоматично позначає запізнення
INSERT INTO edu.submissions (assignment_id, enrollment_id, answer_text, submitted_at)
VALUES (3, 7, 'пізно', '2026-11-14 10:00+02');
INSERT INTO test_results
SELECT 'T13', 'Здача після due_at: is_late, attempt_no встановлює тригер', 'is_late = true, attempt 1',
       format('is_late = %s, attempt %s', is_late, attempt_no), is_late AND attempt_no = 1
FROM edu.submissions WHERE assignment_id = 3 AND enrollment_id = 7;

-- T14. Недопустимий перехід статусу archived -> published
CALL pg_temp.expect('T14', 'Курс ENG-120: archived -> published',
    $q$UPDATE edu.courses SET status = 'published' WHERE code = 'ENG-120'$q$, 'check_violation');

-- T15. Результат окремої транзакції з ROLLBACK (див. початок скрипту)
INSERT INTO test_results
SELECT 'T15', 'UPDATE оцінки та ROLLBACK',
       'у транзакції: бал -1, аудит +1; після: як до',
       format('до %s/%s; у транзакції %s/%s; після %s/%s',
              :'t15_b_score', :'t15_b_audit', :'t15_i_score', :'t15_i_audit', a.score, a.cnt),
       :'t15_i_score'::numeric = :'t15_b_score'::numeric - 1
       AND :'t15_i_audit'::int = :'t15_b_audit'::int + 1
       AND a.score = :'t15_b_score'::numeric AND a.cnt = :'t15_b_audit'::int
FROM (SELECT (SELECT score FROM edu.grades WHERE submission_id = 1) AS score,
             (SELECT count(*) FROM edu.audit_log) AS cnt) a;

-- T16. Текстовий матеріал без вмісту
CALL pg_temp.expect('T16', 'material_type = text, content IS NULL',
    $q$INSERT INTO edu.materials (module_id, title, material_type, position)
       VALUES (1, 'Порожній', 'text', 9)$q$, 'check_violation');

-- T17. Процедура завершення курсу фіксує підсумковий бал
CALL pg_temp.expect('T17', 'CALL complete_enrollment для активного запису 24',
    'CALL edu.complete_enrollment(24, NULL)', 'OK');
CALL pg_temp.expect('T17b', 'Повторне завершення запису 24',
    'CALL edu.complete_enrollment(24, NULL)', 'check_violation');

-- T18. Функція звіту для неіснуючого курсу
CALL pg_temp.expect('T18', 'fn_course_report(999)',
    'SELECT * FROM edu.fn_course_report(999)', 'no_data_found');

-- ---------------------------------------------------------------------
-- Перевірки прав доступу (виконуються від імені групових ролей)
-- ---------------------------------------------------------------------
GRANT INSERT ON test_results TO edu_analyst, edu_student, edu_teacher;

SET ROLE edu_analyst;
CALL pg_temp.expect('T19', 'Аналітик: SELECT з v_course_overview',
    'SELECT count(*) FROM edu.v_course_overview', 'OK');
CALL pg_temp.expect('T20', 'Аналітик: INSERT у courses',
    $q$INSERT INTO edu.courses (code, title, category_id, teacher_id, start_date, end_date)
       VALUES ('TST-002', 'Тест', 1, 2, '2026-12-01', '2026-12-02')$q$, 'insufficient_privilege');
RESET ROLE;

SET ROLE edu_student;
CALL pg_temp.expect('T21', 'Студент: здача роботи (INSERT submissions)',
    $q$INSERT INTO edu.submissions (assignment_id, enrollment_id, answer_text)
       VALUES (3, 8, 'відповідь студента')$q$, 'OK');
CALL pg_temp.expect('T22', 'Студент: читання журналу аудиту',
    'SELECT count(*) FROM edu.audit_log', 'insufficient_privilege');
CALL pg_temp.expect('T23', 'Студент: виставлення собі оцінки',
    $q$INSERT INTO edu.grades (submission_id, grader_id, score) VALUES (55, 2, 20)$q$,
    'insufficient_privilege');
RESET ROLE;

SET ROLE edu_teacher;
CALL pg_temp.expect('T24', 'Викладач: оцінювання роботи через процедуру',
    $q$CALL edu.grade_submission(51, 2, 17, 'Добре', NULL)$q$, 'OK');
CALL pg_temp.expect('T25', 'Викладач: видалення записів аудиту',
    'DELETE FROM edu.audit_log', 'insufficient_privilege');
CALL pg_temp.expect('T26', 'Викладач: зміна структури (ALTER TABLE)',
    'ALTER TABLE edu.users ADD COLUMN x int', 'insufficient_privilege');
RESET ROLE;

\pset footer off
SELECT code, action, expected, actual,
       CASE WHEN passed THEN 'PASS' ELSE 'FAIL' END AS result
FROM test_results ORDER BY code;

SELECT count(*) FILTER (WHERE passed) AS passed,
       count(*) FILTER (WHERE NOT passed) AS failed
FROM test_results;

ROLLBACK;
