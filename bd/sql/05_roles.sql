-- =====================================================================
-- Скрипт 05: ролі та права доступу
-- Запуск: psql -d elearn_db -v api_password='...' -f 05_roles.sql
-- Групові ролі NOLOGIN перевіряються через SET ROLE (див. 07_tests.sql).
-- =====================================================================
SET search_path = edu, public;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'edu_teacher') THEN
        CREATE ROLE edu_teacher NOLOGIN; END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'edu_student') THEN
        CREATE ROLE edu_student NOLOGIN; END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'edu_analyst') THEN
        CREATE ROLE edu_analyst NOLOGIN; END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'edu_api') THEN
        CREATE ROLE edu_api LOGIN; END IF;
END $$;

-- пароль сервісного користувача API передається змінною psql, не зберігається у скрипті
ALTER ROLE edu_api PASSWORD :'api_password';

-- скидання попередніх прав (повторний запуск)
REVOKE ALL ON ALL TABLES    IN SCHEMA edu FROM edu_teacher, edu_student, edu_analyst, edu_api;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA edu FROM edu_teacher, edu_student, edu_analyst, edu_api;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA edu FROM PUBLIC;
REVOKE ALL ON ALL PROCEDURES IN SCHEMA edu FROM PUBLIC;
REVOKE CREATE ON SCHEMA edu FROM PUBLIC;

GRANT USAGE ON SCHEMA edu TO edu_teacher, edu_student, edu_analyst, edu_api;

-- ---------- Аналітик: лише читання представлень і статистики ----------
GRANT SELECT ON edu.v_course_overview, edu.v_gradebook, edu.mv_course_stats,
                edu.courses, edu.categories
      TO edu_analyst;
GRANT EXECUTE ON FUNCTION edu.fn_course_report(integer),
                          edu.fn_course_progress(integer),
                          edu.fn_enrollment_score(integer),
                          edu.refresh_course_stats() TO edu_analyst;

-- ---------- Студент: перегляд курсів і матеріалів, здача робіт ----------
GRANT SELECT ON edu.courses, edu.categories, edu.modules, edu.materials,
                edu.assignments, edu.v_course_overview TO edu_student;
GRANT SELECT, INSERT ON edu.submissions TO edu_student;
GRANT SELECT, INSERT, UPDATE ON edu.material_progress TO edu_student;
GRANT SELECT ON edu.enrollments TO edu_student;
GRANT EXECUTE ON PROCEDURE edu.enroll_student(integer, integer) TO edu_student;
GRANT EXECUTE ON FUNCTION edu.fn_course_progress(integer),
                          edu.fn_enrollment_score(integer) TO edu_student;
-- запис на курс — лише через процедуру enroll_student (SECURITY DEFINER),
-- прямий INSERT у enrollments студенту не надано
GRANT SELECT (id, email, full_name, role_code, is_active) ON edu.users TO edu_student;

-- ---------- Викладач: керування вмістом своїх курсів, оцінювання ----------
GRANT SELECT, INSERT, UPDATE ON edu.courses TO edu_teacher;
GRANT SELECT, INSERT, UPDATE, DELETE ON edu.modules, edu.materials, edu.assignments TO edu_teacher;
GRANT SELECT ON edu.categories, edu.enrollments, edu.submissions,
                edu.material_progress, edu.users,
                edu.v_course_overview, edu.v_gradebook, edu.v_pending_reviews TO edu_teacher;
GRANT SELECT, INSERT, UPDATE ON edu.grades TO edu_teacher;
GRANT UPDATE (status) ON edu.submissions TO edu_teacher;
GRANT UPDATE (status, final_score, completed_at) ON edu.enrollments TO edu_teacher;
GRANT EXECUTE ON PROCEDURE edu.grade_submission(bigint, integer, numeric, text),
                           edu.complete_enrollment(integer) TO edu_teacher;
GRANT EXECUTE ON FUNCTION edu.fn_course_report(integer),
                          edu.fn_course_progress(integer),
                          edu.fn_enrollment_score(integer) TO edu_teacher;

-- Тригерні функції виконуються від імені того, хто змінює таблицю
GRANT EXECUTE ON FUNCTION edu.trg_course_teacher_check(), edu.trg_course_status_transition(),
                          edu.trg_enrollment_check(), edu.trg_submission_before_insert(),
                          edu.trg_grade_check(), edu.trg_grade_audit(), edu.trg_course_audit()
      TO edu_teacher, edu_student, edu_api;

-- ---------- Сервісний користувач REST API: CRUD без зміни структури ----------
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA edu TO edu_api;
REVOKE INSERT, UPDATE, DELETE ON edu.audit_log FROM edu_api;   -- журнал лише читається
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA edu TO edu_api;
GRANT EXECUTE ON ALL FUNCTIONS  IN SCHEMA edu TO edu_api;
GRANT EXECUTE ON ALL PROCEDURES IN SCHEMA edu TO edu_api;

-- Журнал аудиту змінюють лише тригери (SECURITY DEFINER); прямий доступ закрито
REVOKE ALL ON edu.audit_log FROM edu_teacher, edu_student, edu_analyst;
