-- =====================================================================
-- Скрипт 02: функції, процедури, тригери (бізнес-правила)
-- =====================================================================
SET search_path = edu, public;

-- ---------------------------------------------------------------------
-- T1. BEFORE INSERT/UPDATE courses: викладач курсу повинен мати роль
--     teacher (BR04) і бути активним
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION edu.trg_course_teacher_check()
RETURNS trigger LANGUAGE plpgsql
SECURITY DEFINER SET search_path = edu, pg_temp AS $$
DECLARE
    v_role   varchar(10);
    v_active boolean;
BEGIN
    SELECT role_code, is_active INTO v_role, v_active
    FROM edu.users WHERE id = NEW.teacher_id
    FOR SHARE;                       -- роль не зміниться до кінця транзакції
    IF v_role IS DISTINCT FROM 'teacher' THEN
        RAISE EXCEPTION 'Користувач % не є викладачем', NEW.teacher_id
            USING ERRCODE = 'check_violation',
                  HINT = 'teacher_id має посилатися на користувача з role_code = teacher';
    END IF;
    IF NOT v_active THEN
        RAISE EXCEPTION 'Викладач % неактивний', NEW.teacher_id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER courses_teacher_check
BEFORE INSERT OR UPDATE OF teacher_id ON edu.courses
FOR EACH ROW EXECUTE FUNCTION edu.trg_course_teacher_check();

-- ---------------------------------------------------------------------
-- T2. BEFORE UPDATE courses: дозволені переходи статусу (BR08)
--     draft -> published -> archived;  published -> draft лише без записів
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION edu.trg_course_status_transition()
RETURNS trigger LANGUAGE plpgsql
SECURITY DEFINER SET search_path = edu, pg_temp AS $$
BEGIN
    IF OLD.status = NEW.status THEN
        RETURN NEW;
    END IF;
    IF (OLD.status, NEW.status) IN (('draft', 'published'),
                                    ('published', 'archived')) THEN
        RETURN NEW;
    END IF;
    IF OLD.status = 'published' AND NEW.status = 'draft'
       AND NOT EXISTS (SELECT 1 FROM edu.enrollments e WHERE e.course_id = OLD.id) THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Недопустимий перехід статусу курсу: % -> %', OLD.status, NEW.status
        USING ERRCODE = 'check_violation';
END;
$$;

CREATE TRIGGER courses_status_transition
BEFORE UPDATE OF status ON edu.courses
FOR EACH ROW EXECUTE FUNCTION edu.trg_course_status_transition();

-- ---------------------------------------------------------------------
-- T3. BEFORE INSERT/UPDATE enrollments: записатися може лише активний
--     студент (BR05) на опублікований курс (BR06)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION edu.trg_enrollment_check()
RETURNS trigger LANGUAGE plpgsql
SECURITY DEFINER SET search_path = edu, pg_temp AS $$
DECLARE
    v_role   varchar(10);
    v_active boolean;
    v_status varchar(10);
BEGIN
    IF TG_OP = 'UPDATE' AND NEW.course_id = OLD.course_id
       AND NEW.student_id = OLD.student_id THEN
        RETURN NEW;                  -- змінюється лише статус/оцінка
    END IF;
    SELECT role_code, is_active INTO v_role, v_active
    FROM edu.users WHERE id = NEW.student_id FOR SHARE;
    IF v_role IS DISTINCT FROM 'student' OR NOT v_active THEN
        RAISE EXCEPTION 'Користувач % не є активним студентом', NEW.student_id
            USING ERRCODE = 'check_violation';
    END IF;
    SELECT status INTO v_status FROM edu.courses WHERE id = NEW.course_id;
    IF v_status IS DISTINCT FROM 'published' THEN
        RAISE EXCEPTION 'Курс % недоступний для запису (статус %)', NEW.course_id, v_status
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER enrollments_check
BEFORE INSERT OR UPDATE ON edu.enrollments
FOR EACH ROW EXECUTE FUNCTION edu.trg_enrollment_check();

-- ---------------------------------------------------------------------
-- T4. BEFORE INSERT submissions: завдання і запис належать одному курсу,
--     запис активний, ліміт спроб, автоматичні attempt_no та is_late
--     (BR11, BR12, BR13)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION edu.trg_submission_before_insert()
RETURNS trigger LANGUAGE plpgsql
SECURITY DEFINER SET search_path = edu, pg_temp AS $$
DECLARE
    v_assign_course integer;
    v_enroll_course integer;
    v_enroll_status varchar(10);
    v_due           timestamptz;
    v_max_attempts  smallint;
    v_used          integer;
BEGIN
    SELECT m.course_id, a.due_at, a.max_attempts
      INTO v_assign_course, v_due, v_max_attempts
    FROM edu.assignments a JOIN edu.modules m ON m.id = a.module_id
    WHERE a.id = NEW.assignment_id;

    -- блокуємо запис студента: паралельні спроби рахуються послідовно
    SELECT course_id, status INTO v_enroll_course, v_enroll_status
    FROM edu.enrollments WHERE id = NEW.enrollment_id
    FOR UPDATE;

    IF v_assign_course IS NULL OR v_enroll_course IS NULL THEN
        RETURN NEW;                  -- відсутній об'єкт: спрацює FOREIGN KEY
    END IF;
    IF v_assign_course <> v_enroll_course THEN
        RAISE EXCEPTION 'Завдання % не належить курсу запису %',
            NEW.assignment_id, NEW.enrollment_id USING ERRCODE = 'check_violation';
    END IF;
    IF v_enroll_status <> 'active' THEN
        RAISE EXCEPTION 'Запис % не активний (статус %)', NEW.enrollment_id, v_enroll_status
            USING ERRCODE = 'check_violation';
    END IF;

    SELECT count(*) INTO v_used FROM edu.submissions
    WHERE assignment_id = NEW.assignment_id AND enrollment_id = NEW.enrollment_id;
    IF v_used >= v_max_attempts THEN
        RAISE EXCEPTION 'Вичерпано ліміт спроб (%) для завдання %',
            v_max_attempts, NEW.assignment_id USING ERRCODE = 'check_violation';
    END IF;

    NEW.attempt_no := v_used + 1;
    NEW.is_late    := NEW.submitted_at > v_due;
    NEW.status     := 'submitted';
    RETURN NEW;
END;
$$;

CREATE TRIGGER submissions_before_insert
BEFORE INSERT ON edu.submissions
FOR EACH ROW EXECUTE FUNCTION edu.trg_submission_before_insert();

-- ---------------------------------------------------------------------
-- T5. BEFORE INSERT/UPDATE grades: бал не перевищує max_score (BR07),
--     оцінює лише викладач цього курсу (BR09)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION edu.trg_grade_check()
RETURNS trigger LANGUAGE plpgsql
SECURITY DEFINER SET search_path = edu, pg_temp AS $$
DECLARE
    v_max     numeric(5,2);
    v_teacher integer;
BEGIN
    SELECT a.max_score, c.teacher_id INTO v_max, v_teacher
    FROM edu.submissions s
    JOIN edu.assignments a ON a.id = s.assignment_id
    JOIN edu.modules m     ON m.id = a.module_id
    JOIN edu.courses c     ON c.id = m.course_id
    WHERE s.id = NEW.submission_id;

    IF v_max IS NULL THEN
        RETURN NEW;                  -- FOREIGN KEY відхилить запис
    END IF;
    IF NEW.score > v_max THEN
        RAISE EXCEPTION 'Бал % перевищує максимальний %', NEW.score, v_max
            USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.grader_id <> v_teacher
       AND NOT EXISTS (SELECT 1 FROM edu.users
                       WHERE id = NEW.grader_id AND role_code = 'admin') THEN
        RAISE EXCEPTION 'Користувач % не є викладачем цього курсу', NEW.grader_id
            USING ERRCODE = 'check_violation';
    END IF;
    NEW.graded_at := now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER grades_check
BEFORE INSERT OR UPDATE ON edu.grades
FOR EACH ROW EXECUTE FUNCTION edu.trg_grade_check();

-- ---------------------------------------------------------------------
-- T6. AFTER INSERT/UPDATE/DELETE grades: оновлення статусу роботи
--     та запис до журналу аудиту (BR14)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION edu.trg_grade_audit()
RETURNS trigger LANGUAGE plpgsql
SECURITY DEFINER SET search_path = edu, pg_temp AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        UPDATE edu.submissions SET status = 'submitted' WHERE id = OLD.submission_id;
        INSERT INTO edu.audit_log (table_name, record_id, action, old_data, changed_by)
        VALUES ('grades', OLD.id, TG_OP, to_jsonb(OLD), session_user);
        RETURN OLD;
    END IF;
    UPDATE edu.submissions SET status = 'graded'
    WHERE id = NEW.submission_id AND status <> 'graded';
    INSERT INTO edu.audit_log (table_name, record_id, action, old_data, new_data, changed_by)
    VALUES ('grades', NEW.id, TG_OP,
            CASE WHEN TG_OP = 'UPDATE' THEN to_jsonb(OLD) END,
            to_jsonb(NEW), session_user);
    RETURN NEW;
END;
$$;

CREATE TRIGGER grades_audit
AFTER INSERT OR UPDATE OR DELETE ON edu.grades
FOR EACH ROW EXECUTE FUNCTION edu.trg_grade_audit();

-- ---------------------------------------------------------------------
-- T7. AFTER UPDATE courses: аудит зміни статусу курсу
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION edu.trg_course_audit()
RETURNS trigger LANGUAGE plpgsql
SECURITY DEFINER SET search_path = edu, pg_temp AS $$
BEGIN
    INSERT INTO edu.audit_log (table_name, record_id, action, old_data, new_data, changed_by)
    VALUES ('courses', NEW.id, 'UPDATE',
            jsonb_build_object('status', OLD.status),
            jsonb_build_object('status', NEW.status), session_user);
    RETURN NEW;
END;
$$;

CREATE TRIGGER courses_status_audit
AFTER UPDATE OF status ON edu.courses
FOR EACH ROW WHEN (OLD.status IS DISTINCT FROM NEW.status)
EXECUTE FUNCTION edu.trg_course_audit();

-- =====================================================================
-- Функції
-- =====================================================================

-- F1. SQL-функція: відсоток переглянутих матеріалів курсу для запису
CREATE OR REPLACE FUNCTION edu.fn_course_progress(p_enrollment_id integer)
RETURNS numeric
LANGUAGE sql STABLE AS $$
    SELECT CASE WHEN count(mt.id) = 0 THEN 0
                ELSE round(100.0 * count(mp.material_id) / count(mt.id), 1) END
    FROM edu.enrollments e
    JOIN edu.modules   m  ON m.course_id = e.course_id
    JOIN edu.materials mt ON mt.module_id = m.id
    LEFT JOIN edu.material_progress mp
           ON mp.material_id = mt.id AND mp.enrollment_id = e.id
    WHERE e.id = p_enrollment_id;
$$;
COMMENT ON FUNCTION edu.fn_course_progress(integer)
    IS 'Відсоток переглянутих матеріалів курсу (0–100)';

-- F2. SQL-функція: підсумковий бал студента у курсі (0–100).
--     Береться найкраща оцінена спроба кожного завдання; незданi = 0.
CREATE OR REPLACE FUNCTION edu.fn_enrollment_score(p_enrollment_id integer)
RETURNS numeric
LANGUAGE sql STABLE AS $$
    WITH best AS (
        SELECT a.id, a.max_score,
               COALESCE(max(g.score), 0) AS best_score
        FROM edu.enrollments e
        JOIN edu.modules m     ON m.course_id = e.course_id
        JOIN edu.assignments a ON a.module_id = m.id
        LEFT JOIN edu.submissions s
               ON s.assignment_id = a.id AND s.enrollment_id = e.id
        LEFT JOIN edu.grades g ON g.submission_id = s.id
        WHERE e.id = p_enrollment_id
        GROUP BY a.id, a.max_score
    )
    SELECT CASE WHEN sum(max_score) IS NULL THEN NULL
                ELSE round(100 * sum(best_score) / sum(max_score), 2) END
    FROM best;
$$;
COMMENT ON FUNCTION edu.fn_enrollment_score(integer)
    IS 'Підсумковий бал (0–100) за найкращими оціненими спробами';

-- F3. PL/pgSQL-функція: звіт по курсу (набір рядків)
CREATE OR REPLACE FUNCTION edu.fn_course_report(p_course_id integer)
RETURNS TABLE (
    student_id     integer,
    full_name      varchar,
    status         varchar,
    progress_pct   numeric,
    score          numeric,
    submitted_cnt  bigint,
    late_cnt       bigint
)
LANGUAGE plpgsql STABLE AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM edu.courses WHERE id = p_course_id) THEN
        RAISE EXCEPTION 'Курс % не знайдено', p_course_id
            USING ERRCODE = 'no_data_found';
    END IF;
    RETURN QUERY
    SELECT u.id, u.full_name, e.status,
           edu.fn_course_progress(e.id),
           edu.fn_enrollment_score(e.id),
           count(s.id),
           count(s.id) FILTER (WHERE s.is_late)
    FROM edu.enrollments e
    JOIN edu.users u ON u.id = e.student_id
    LEFT JOIN edu.submissions s ON s.enrollment_id = e.id
    WHERE e.course_id = p_course_id
    GROUP BY u.id, u.full_name, e.status, e.id
    ORDER BY u.full_name;
END;
$$;

-- =====================================================================
-- Процедури
-- =====================================================================

-- P1. Запис студента на курс з контролем кількості місць (BR15).
--     Рядок курсу блокується FOR UPDATE: паралельні записи на останнє
--     місце виконуються послідовно.
CREATE OR REPLACE PROCEDURE edu.enroll_student(
    IN  p_course_id     integer,
    IN  p_student_id    integer,
    OUT p_enrollment_id integer
)
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = edu, pg_temp AS $$
DECLARE
    v_max    integer;
    v_taken  integer;
BEGIN
    SELECT max_students INTO v_max
    FROM edu.courses WHERE id = p_course_id
    FOR UPDATE;
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
    VALUES (p_course_id, p_student_id)
    RETURNING id INTO p_enrollment_id;
END;
$$;

-- P2. Оцінювання роботи (UPSERT оцінки; статус роботи змінює тригер T6)
CREATE OR REPLACE PROCEDURE edu.grade_submission(
    IN  p_submission_id bigint,
    IN  p_grader_id     integer,
    IN  p_score         numeric,
    IN  p_feedback      text,
    OUT p_grade_id      bigint
)
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM edu.submissions WHERE id = p_submission_id) THEN
        RAISE EXCEPTION 'Роботу % не знайдено', p_submission_id USING ERRCODE = 'no_data_found';
    END IF;
    INSERT INTO edu.grades (submission_id, grader_id, score, feedback)
    VALUES (p_submission_id, p_grader_id, p_score, p_feedback)
    ON CONFLICT (submission_id) DO UPDATE
       SET score = EXCLUDED.score,
           feedback = EXCLUDED.feedback,
           grader_id = EXCLUDED.grader_id
    RETURNING id INTO p_grade_id;
END;
$$;

-- P3. Завершення курсу студентом: фіксація підсумкового балу
CREATE OR REPLACE PROCEDURE edu.complete_enrollment(
    IN  p_enrollment_id integer,
    OUT p_final_score   numeric
)
LANGUAGE plpgsql AS $$
DECLARE
    v_status varchar(10);
BEGIN
    SELECT status INTO v_status FROM edu.enrollments
    WHERE id = p_enrollment_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Запис % не знайдено', p_enrollment_id USING ERRCODE = 'no_data_found';
    END IF;
    IF v_status <> 'active' THEN
        RAISE EXCEPTION 'Запис % вже має статус %', p_enrollment_id, v_status
            USING ERRCODE = 'check_violation';
    END IF;
    p_final_score := COALESCE(edu.fn_enrollment_score(p_enrollment_id), 0);
    UPDATE edu.enrollments
       SET status = 'completed', final_score = p_final_score, completed_at = now()
     WHERE id = p_enrollment_id;
END;
$$;
