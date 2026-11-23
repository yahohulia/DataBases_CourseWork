"""
Скрипт 08: сценарії конкурентного доступу з двома незалежними підключеннями.
Запуск:  python sql/08_concurrency.py   (параметри підключення беруться з .env)

Сценарій К1: два студенти одночасно записуються на останнє вільне місце курсу.
Сценарій К2: блокування рядка FOR UPDATE і тайм-аут lock_timeout у другому сеансі.
Протокол друкується у stdout (зберігається в protocols/08_concurrency_output.txt).
"""
import os
import threading
import time
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parent.parent
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

DSN = dict(host=os.environ.get("PGHOST", "localhost"), port=os.environ.get("PGPORT", "5432"),
           user=os.environ.get("PGUSER", "postgres"), password=os.environ["PGPASSWORD"],
           dbname=os.environ.get("DB", "elearn_db"))
T0 = time.perf_counter()


def log(session, text):
    print(f"[{time.perf_counter() - T0:6.2f} s] {session:<8} {text}", flush=True)


def connect(name):
    conn = psycopg2.connect(application_name=name, **DSN)
    conn.autocommit = False
    return conn


def waiting_sessions(monitor):
    with monitor.cursor() as cur:
        cur.execute("""SELECT application_name, wait_event_type, wait_event, state
                       FROM pg_stat_activity
                       WHERE application_name LIKE 'sess_%' AND wait_event_type = 'Lock'""")
        return cur.fetchall()


# ---------------------------------------------------------------------------
def scenario_last_seat():
    print("\n=== К1. Запис двох студентів на останнє місце курсу STAT-110 ===")
    setup = connect("setup")
    setup.autocommit = True
    cur = setup.cursor()
    cur.execute("SELECT count(*) FROM edu.enrollments WHERE course_id = 4 AND status <> 'dropped'")
    taken = cur.fetchone()[0]
    cur.execute("UPDATE edu.courses SET max_students = %s WHERE id = 4", (taken + 1,))
    log("setup", f"зайнято {taken} місць, max_students = {taken + 1} -> вільне 1 місце")

    a, b, monitor = connect("sess_A"), connect("sess_B"), connect("monitor")
    monitor.autocommit = True
    result = {}

    def session_b():
        cb = b.cursor()
        cb.execute("SET LOCAL lock_timeout = '30s'")
        log("sess_B", "BEGIN; CALL edu.enroll_student(4, 8)  -- студент id 8")
        try:
            cb.execute("CALL edu.enroll_student(4, 8, NULL)")
            result["B"] = f"OK, enrollment_id = {cb.fetchone()[0]}"
            b.commit()
        except psycopg2.Error as e:
            result["B"] = f"ERROR {e.pgcode}: {e.pgerror.splitlines()[0]}"
            b.rollback()
        log("sess_B", f"результат: {result['B']}")

    ca = a.cursor()
    log("sess_A", "BEGIN; CALL edu.enroll_student(4, 9)  -- студент id 9")
    ca.execute("CALL edu.enroll_student(4, 9, NULL)")
    log("sess_A", f"процедура виконана, enrollment_id = {ca.fetchone()[0]}; транзакція відкрита")
    tb = threading.Thread(target=session_b)
    tb.start()
    time.sleep(1.5)
    for row in waiting_sessions(monitor):
        log("monitor", f"{row[0]} очікує: wait_event_type={row[1]}, wait_event={row[2]}")
    time.sleep(1.0)
    a.commit()
    log("sess_A", "COMMIT")
    tb.join()

    cur.execute("SELECT count(*), max(c.max_students) FROM edu.enrollments e "
                "JOIN edu.courses c ON c.id = e.course_id "
                "WHERE e.course_id = 4 AND e.status <> 'dropped'")
    cnt, mx = cur.fetchone()
    log("check", f"записів на курс: {cnt}, ліміт: {mx} -> перевищення немає: {cnt <= mx}")
    # відновлення початкового стану
    cur.execute("DELETE FROM edu.enrollments WHERE course_id = 4 AND student_id IN (8, 9)")
    cur.execute("UPDATE edu.courses SET max_students = 15 WHERE id = 4")
    log("cleanup", "тестові записи видалено, max_students = 15")
    for c in (a, b, monitor, setup):
        c.close()


# ---------------------------------------------------------------------------
def scenario_lock_timeout():
    print("\n=== К2. SELECT ... FOR UPDATE і lock_timeout у другому сеансі ===")
    a, b = connect("sess_A"), connect("sess_B")
    ca, cb = a.cursor(), b.cursor()
    log("sess_A", "BEGIN; SELECT id, max_students FROM edu.courses WHERE id = 1 FOR UPDATE")
    ca.execute("SELECT id, max_students FROM edu.courses WHERE id = 1 FOR UPDATE")
    log("sess_A", f"рядок заблоковано: {ca.fetchone()}")
    cb.execute("SET LOCAL lock_timeout = '2s'")
    log("sess_B", "BEGIN; SET LOCAL lock_timeout = '2s'; UPDATE edu.courses SET max_students = max_students + 1 WHERE id = 1")
    t = time.perf_counter()
    try:
        cb.execute("UPDATE edu.courses SET max_students = max_students + 1 WHERE id = 1")
        log("sess_B", "UPDATE виконано (неочікувано)")
    except psycopg2.Error as e:
        log("sess_B", f"через {time.perf_counter() - t:.2f} с: ERROR {e.pgcode}: {e.pgerror.splitlines()[0]}")
    b.rollback()
    log("sess_B", "ROLLBACK")
    a.rollback()
    log("sess_A", "ROLLBACK -> блокування знято")
    # повтор після зняття блокування
    cb.execute("UPDATE edu.courses SET max_students = max_students + 1 WHERE id = 1 RETURNING max_students")
    log("sess_B", f"повторний UPDATE виконано без очікування, max_students = {cb.fetchone()[0]}")
    b.rollback()
    log("sess_B", "ROLLBACK -> початкові дані збережено")
    a.close(); b.close()


if __name__ == "__main__":
    with psycopg2.connect(**DSN) as c, c.cursor() as cur:
        cur.execute("SHOW server_version")
        v = cur.fetchone()[0]
        cur.execute("SHOW default_transaction_isolation")
        print(f"PostgreSQL {v}; рівень ізоляції за замовчуванням: {cur.fetchone()[0]}")
    scenario_last_seat()
    scenario_lock_timeout()
