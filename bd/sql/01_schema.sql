-- =====================================================================
-- Запуск: psql -d elearn_db -f 01_schema.sql
-- =====================================================================

DROP SCHEMA IF EXISTS edu CASCADE;
CREATE SCHEMA edu;
COMMENT ON SCHEMA edu IS 'Платформа дистанційного навчання (варіант 113)';

SET search_path = edu, public;

-- ---------------------------------------------------------------------
-- 1. Користувачі платформи (студенти, викладачі, адміністратори)
-- ---------------------------------------------------------------------
CREATE TABLE edu.users (
    id          integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email       varchar(120) NOT NULL,
    full_name   varchar(150) NOT NULL CHECK (btrim(full_name) <> ''),
    role_code   varchar(10)  NOT NULL
                CHECK (role_code IN ('student', 'teacher', 'admin')),
    is_active   boolean      NOT NULL DEFAULT true,
    created_at  timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT users_email_format_chk
        CHECK (email ~* '^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$')
);
-- BR01: e-mail унікальний без урахування регістру
CREATE UNIQUE INDEX users_email_uq ON edu.users (lower(email));
COMMENT ON TABLE edu.users IS 'Учасники платформи';

-- ---------------------------------------------------------------------
-- 2. Категорії курсів (ієрархічний довідник)
-- ---------------------------------------------------------------------
CREATE TABLE edu.categories (
    id         integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name       varchar(100) NOT NULL UNIQUE CHECK (btrim(name) <> ''),
    parent_id  integer REFERENCES edu.categories(id) ON DELETE RESTRICT,
    CONSTRAINT categories_not_self_parent_chk CHECK (parent_id <> id)
);
COMMENT ON TABLE edu.categories IS 'Ієрархія категорій курсів';

-- ---------------------------------------------------------------------
-- 3. Курси
-- ---------------------------------------------------------------------
CREATE TABLE edu.courses (
    id            integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code          varchar(20)  NOT NULL UNIQUE
                  CHECK (code ~ '^[A-Z]{2,6}-[0-9]{3}$'),
    title         varchar(200) NOT NULL CHECK (btrim(title) <> ''),
    description   text,
    category_id   integer NOT NULL
                  REFERENCES edu.categories(id) ON DELETE RESTRICT,
    teacher_id    integer NOT NULL
                  REFERENCES edu.users(id) ON DELETE RESTRICT,
    status        varchar(10) NOT NULL DEFAULT 'draft'
                  CHECK (status IN ('draft', 'published', 'archived')),
    start_date    date NOT NULL,
    end_date      date NOT NULL,
    max_students  integer NOT NULL DEFAULT 30
                  CHECK (max_students BETWEEN 1 AND 1000),
    created_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT courses_dates_chk CHECK (end_date >= start_date)
);
CREATE INDEX courses_teacher_idx  ON edu.courses (teacher_id);
CREATE INDEX courses_category_idx ON edu.courses (category_id);
COMMENT ON TABLE edu.courses IS 'Навчальні курси';

-- ---------------------------------------------------------------------
-- 4. Модулі курсу (упорядковані розділи)
-- ---------------------------------------------------------------------
CREATE TABLE edu.modules (
    id         integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    course_id  integer NOT NULL
               REFERENCES edu.courses(id) ON DELETE CASCADE,
    title      varchar(200) NOT NULL CHECK (btrim(title) <> ''),
    position   smallint NOT NULL CHECK (position > 0),
    CONSTRAINT modules_course_position_uq UNIQUE (course_id, position)
);
COMMENT ON TABLE edu.modules IS 'Модулі (розділи) курсу';

-- ---------------------------------------------------------------------
-- 5. Навчальні матеріали модуля
-- ---------------------------------------------------------------------
CREATE TABLE edu.materials (
    id             integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    module_id      integer NOT NULL
                   REFERENCES edu.modules(id) ON DELETE CASCADE,
    title          varchar(200) NOT NULL CHECK (btrim(title) <> ''),
    material_type  varchar(10) NOT NULL
                   CHECK (material_type IN ('video', 'pdf', 'link', 'text')),
    url            varchar(500),
    content        text,
    duration_min   smallint CHECK (duration_min > 0),
    position       smallint NOT NULL CHECK (position > 0),
    created_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT materials_module_position_uq UNIQUE (module_id, position),
    -- BR10: текстовий матеріал має вміст, інші типи — посилання
    CONSTRAINT materials_payload_chk CHECK (
        (material_type = 'text' AND content IS NOT NULL)
     OR (material_type <> 'text' AND url IS NOT NULL))
);
COMMENT ON TABLE edu.materials IS 'Навчальні матеріали модуля';

-- ---------------------------------------------------------------------
-- 6. Записи студентів на курси (зв'язок N:M users–courses)
-- ---------------------------------------------------------------------
CREATE TABLE edu.enrollments (
    id           integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    course_id    integer NOT NULL
                 REFERENCES edu.courses(id) ON DELETE RESTRICT,
    student_id   integer NOT NULL
                 REFERENCES edu.users(id) ON DELETE RESTRICT,
    enrolled_at  timestamptz NOT NULL DEFAULT now(),
    status       varchar(10) NOT NULL DEFAULT 'active'
                 CHECK (status IN ('active', 'completed', 'dropped')),
    final_score  numeric(5,2) CHECK (final_score BETWEEN 0 AND 100),
    completed_at timestamptz,
    -- BR03: один студент — один запис на курс
    CONSTRAINT enrollments_course_student_uq UNIQUE (course_id, student_id),
    CONSTRAINT enrollments_completed_chk CHECK (
        (status = 'completed') = (completed_at IS NOT NULL))
);
CREATE INDEX enrollments_student_idx ON edu.enrollments (student_id);
COMMENT ON TABLE edu.enrollments IS 'Участь студента у курсі';

-- ---------------------------------------------------------------------
-- 7. Завдання модуля
-- ---------------------------------------------------------------------
CREATE TABLE edu.assignments (
    id            integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    module_id     integer NOT NULL
                  REFERENCES edu.modules(id) ON DELETE RESTRICT,
    title         varchar(200) NOT NULL CHECK (btrim(title) <> ''),
    description   text,
    max_score     numeric(5,2) NOT NULL CHECK (max_score > 0 AND max_score <= 100),
    due_at        timestamptz NOT NULL,
    max_attempts  smallint NOT NULL DEFAULT 3 CHECK (max_attempts BETWEEN 1 AND 10),
    created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX assignments_module_idx ON edu.assignments (module_id);
COMMENT ON TABLE edu.assignments IS 'Завдання для самостійного виконання';

-- ---------------------------------------------------------------------
-- 8. Здані роботи (спроби виконання завдання)
-- ---------------------------------------------------------------------
CREATE TABLE edu.submissions (
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
);
COMMENT ON TABLE edu.submissions IS 'Спроби виконання завдань студентами';

-- ---------------------------------------------------------------------
-- 9. Оцінки зданих робіт (1:1 до submissions)
-- ---------------------------------------------------------------------
CREATE TABLE edu.grades (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    submission_id  bigint NOT NULL UNIQUE
                   REFERENCES edu.submissions(id) ON DELETE CASCADE,
    grader_id      integer NOT NULL
                   REFERENCES edu.users(id) ON DELETE RESTRICT,
    score          numeric(5,2) NOT NULL CHECK (score >= 0),
    feedback       text,
    graded_at      timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE edu.grades IS 'Результати перевірки робіт';

-- ---------------------------------------------------------------------
-- 10. Прогрес перегляду матеріалів (N:M enrollments–materials)
-- ---------------------------------------------------------------------
CREATE TABLE edu.material_progress (
    enrollment_id  integer NOT NULL
                   REFERENCES edu.enrollments(id) ON DELETE CASCADE,
    material_id    integer NOT NULL
                   REFERENCES edu.materials(id) ON DELETE CASCADE,
    first_viewed_at timestamptz NOT NULL DEFAULT now(),
    last_viewed_at  timestamptz NOT NULL DEFAULT now(),
    views_count     integer NOT NULL DEFAULT 1 CHECK (views_count > 0),
    PRIMARY KEY (enrollment_id, material_id),
    CONSTRAINT material_progress_time_chk
        CHECK (last_viewed_at >= first_viewed_at)
);
CREATE INDEX material_progress_material_idx ON edu.material_progress (material_id);
COMMENT ON TABLE edu.material_progress IS 'Факт перегляду матеріалу студентом';

-- ---------------------------------------------------------------------
-- 11. Журнал аудиту змін оцінок і статусів курсів
-- ---------------------------------------------------------------------
CREATE TABLE edu.audit_log (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    table_name  varchar(40) NOT NULL,
    record_id   bigint      NOT NULL,
    action      varchar(6)  NOT NULL CHECK (action IN ('INSERT', 'UPDATE', 'DELETE')),
    old_data    jsonb,
    new_data    jsonb,
    changed_by  text        NOT NULL DEFAULT current_user,
    changed_at  timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX audit_log_record_idx ON edu.audit_log (table_name, record_id);
COMMENT ON TABLE edu.audit_log IS 'Журнал аудиту (заповнюється тригерами)';
