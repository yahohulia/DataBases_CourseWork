"""
Скрипт 09: порівняння планів двох запитів до і після створення індексів.
Запуск: python sql/09_performance.py  (база elearn_perf, див. 09_perf_data.sql)

Для кожного стану: VACUUM ANALYZE, перший запуск і 5 повторних запусків
EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON); фіксуються вузли плану, фактичні рядки,
Execution Time (перший і медіана повторів) та shared buffers.
"""
import json
import os
import statistics
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parent.parent
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

conn = psycopg2.connect(host=os.environ.get("PGHOST", "localhost"), port=os.environ.get("PGPORT", "5432"),
                        user=os.environ.get("PGUSER", "postgres"), password=os.environ["PGPASSWORD"],
                        dbname="elearn_perf")
conn.autocommit = True
cur = conn.cursor()

QUERIES = {
    "P1": {
        "title": "Останні 10 робіт запису на курс (enrollment_id = 7777)",
        "sql": """SELECT id, assignment_id, attempt_no, submitted_at, status
                  FROM edu.submissions
                  WHERE enrollment_id = 7777
                  ORDER BY submitted_at DESC
                  LIMIT 10""",
        "index": "CREATE INDEX submissions_enrollment_time_idx "
                 "ON edu.submissions (enrollment_id, submitted_at DESC)",
        "index_name": "submissions_enrollment_time_idx",
    },
    "P2": {
        "title": "Кількість робіт і запізнень за тиждень 10–17.10.2026 по завданнях",
        "sql": """SELECT assignment_id, count(*) AS cnt,
                         count(*) FILTER (WHERE is_late) AS late
                  FROM edu.submissions
                  WHERE submitted_at >= '2026-10-10 00:00+03'
                    AND submitted_at <  '2026-10-17 00:00+03'
                  GROUP BY assignment_id
                  ORDER BY cnt DESC""",
        "index": "CREATE INDEX submissions_submitted_at_idx "
                 "ON edu.submissions (submitted_at) INCLUDE (assignment_id, is_late)",
        "index_name": "submissions_submitted_at_idx",
    },
}


def nodes(plan, depth=0, out=None):
    out = [] if out is None else out
    label = plan["Node Type"]
    if "Index Name" in plan:
        label += f" using {plan['Index Name']}"
    if "Relation Name" in plan and "Index Name" not in plan:
        label += f" on {plan['Relation Name']}"
    out.append(f"{'  ' * depth}{label} (rows={plan['Actual Rows']}, loops={plan['Actual Loops']})")
    for child in plan.get("Plans", []):
        nodes(child, depth + 1, out)
    return out


def measure(q):
    cur.execute("VACUUM ANALYZE edu.submissions")
    runs = []
    for _ in range(6):
        cur.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + q["sql"])
        runs.append(cur.fetchone()[0][0])
    first, rest = runs[0], runs[1:]
    times = [r["Execution Time"] for r in rest]
    top = rest[-1]["Plan"]
    cur.execute("EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF, SUMMARY OFF) " + q["sql"])
    text_plan = "\n".join(r[0] for r in cur.fetchall())
    return {
        "plan": nodes(top),
        "text_plan": text_plan,
        "first_ms": round(first["Execution Time"], 3),
        "median_ms": round(statistics.median(times), 3),
        "min_ms": round(min(times), 3),
        "max_ms": round(max(times), 3),
        "shared_hit": top.get("Shared Hit Blocks", 0),
        "shared_read": top.get("Shared Read Blocks", 0),
        "total_cost": top["Total Cost"],
        "rows": top["Actual Rows"],
    }


def table_size():
    cur.execute("SELECT count(*), pg_size_pretty(pg_relation_size('edu.submissions')) FROM edu.submissions")
    return cur.fetchone()


if __name__ == "__main__":
    for q in QUERIES.values():
        cur.execute(f"DROP INDEX IF EXISTS edu.{q['index_name']}")
    cur.execute("SHOW server_version")
    print(f"PostgreSQL {cur.fetchone()[0]}; submissions: {table_size()[0]} рядків, {table_size()[1]}")
    results = {}
    for code, q in QUERIES.items():
        before = measure(q)
        cur.execute(q["index"])
        cur.execute(f"SELECT pg_size_pretty(pg_relation_size('edu.{q['index_name']}'))")
        idx_size = cur.fetchone()[0]
        after = measure(q)
        results[code] = {"title": q["title"], "sql": q["sql"], "index": q["index"],
                         "index_size": idx_size, "before": before, "after": after}
        print(f"\n=== {code}. {q['title']} ===")
        print(f"Зміна: {q['index']}  (розмір індексу {idx_size})")
        for state in ("before", "after"):
            r = results[code][state]
            print(f"--- {'До' if state == 'before' else 'Після'}: перший {r['first_ms']} мс, "
                  f"медіана 5 повторів {r['median_ms']} мс (min {r['min_ms']}, max {r['max_ms']}), "
                  f"shared hit={r['shared_hit']} read={r['shared_read']}, cost={r['total_cost']}")
            print(r["text_plan"])

    # вплив індексів на вставлення: 2 000 нових робіт з індексами і без
    import time
    def insert_bench():
        cur.execute("BEGIN")
        t = time.perf_counter()
        cur.execute("""INSERT INTO edu.submissions (assignment_id, enrollment_id, answer_text, submitted_at)
                       SELECT a.id, e.id, 'bench', '2026-12-20 12:00+02'
                       FROM edu.enrollments e
                       JOIN edu.modules m ON m.course_id = e.course_id AND m.position = 3
                       JOIN edu.assignments a ON a.module_id = m.id
                       WHERE e.id <= 1000""")
        n = cur.rowcount
        dt = (time.perf_counter() - t) * 1000
        cur.execute("ROLLBACK")
        return n, round(dt, 1)
    insert_bench()  # прогрівання кешу
    with_idx = [insert_bench() for _ in range(5)]
    for q in QUERIES.values():
        cur.execute(f"DROP INDEX edu.{q['index_name']}")
    insert_bench()
    without_idx = [insert_bench() for _ in range(5)]
    for q in QUERIES.values():
        cur.execute(q["index"])
    results["insert"] = {"with": with_idx, "without": without_idx}
    print(f"\nВставлення {with_idx[0][0]} рядків (5 повторів після прогріву, ROLLBACK): з індексами {[x[1] for x in with_idx]} мс; "
          f"без нових індексів {[x[1] for x in without_idx]} мс")
    (ROOT / "protocols" / "09_performance.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
