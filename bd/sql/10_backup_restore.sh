#!/usr/bin/env bash
# Скрипт 10: логічна резервна копія elearn_db і відновлення в окрему базу elearn_restore
# з перевіркою об'єктів, кількості рядків, контрольних сум і ключових запитів.
set -e
cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a
BIN="${PGBIN:-/c/Program Files/PostgreSQL/18/bin}"
export PGCLIENTENCODING=UTF8
H="-h ${PGHOST:-localhost} -U ${PGUSER:-postgres}"
mkdir -p backup

echo "== pg_dump $("$BIN/pg_dump" --version)"
"$BIN/pg_dump" $H -d elearn_db -Fc -f backup/elearn_db.dump
ls -l backup/elearn_db.dump | awk '{print "файл дампу:", $NF, $5, "байт"}'

"$BIN/psql" $H -d postgres -q -c "DROP DATABASE IF EXISTS elearn_restore" -c "CREATE DATABASE elearn_restore ENCODING 'UTF8' TEMPLATE template0"
echo "== pg_restore у порожню базу elearn_restore"
"$BIN/pg_restore" $H --exit-on-error -d elearn_restore backup/elearn_db.dump
echo "pg_restore завершено, код $?"

CHECK=$(cat <<'SQL'
SELECT 'tables' AS k, count(*)::text AS v FROM pg_tables WHERE schemaname = 'edu'
UNION ALL SELECT 'views', count(*)::text FROM pg_views WHERE schemaname = 'edu'
UNION ALL SELECT 'matviews', count(*)::text FROM pg_matviews WHERE schemaname = 'edu'
UNION ALL SELECT 'indexes', count(*)::text FROM pg_indexes WHERE schemaname = 'edu'
UNION ALL SELECT 'functions+procedures', count(*)::text FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname = 'edu'
UNION ALL SELECT 'triggers', count(*)::text FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'edu' AND NOT t.tgisinternal
UNION ALL SELECT 'constraints', count(*)::text FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace WHERE n.nspname = 'edu'
UNION ALL SELECT 'rows users', count(*)::text FROM edu.users
UNION ALL SELECT 'rows courses', count(*)::text FROM edu.courses
UNION ALL SELECT 'rows enrollments', count(*)::text FROM edu.enrollments
UNION ALL SELECT 'rows submissions', count(*)::text FROM edu.submissions
UNION ALL SELECT 'rows grades', count(*)::text FROM edu.grades
UNION ALL SELECT 'rows material_progress', count(*)::text FROM edu.material_progress
UNION ALL SELECT 'rows audit_log', count(*)::text FROM edu.audit_log
UNION ALL SELECT 'sum(grades.score)', sum(score)::text FROM edu.grades
UNION ALL SELECT 'md5(submissions)', md5(string_agg(id || ':' || attempt_no || ':' || is_late || ':' || submitted_at, ',' ORDER BY id)) FROM edu.submissions
UNION ALL SELECT 'fn_course_report(4) sum score', sum(score)::text FROM edu.fn_course_report(4)
UNION ALL SELECT 'mv_course_stats rows', count(*)::text FROM edu.mv_course_stats
UNION ALL SELECT 'grants edu_analyst', count(*)::text FROM information_schema.role_table_grants WHERE grantee = 'edu_analyst'
SQL
)
"$BIN/psql" $H -d elearn_db      -At -F '|' -c "$CHECK" | sed 's/\x0D$//' > backup/check_source.txt
"$BIN/psql" $H -d elearn_restore -At -F '|' -c "$CHECK" | sed 's/\x0D$//' > backup/check_restore.txt
echo "== Порівняння: показник | джерело | відновлена"
paste -d'|' backup/check_source.txt backup/check_restore.txt \
  | awk -F'|' '{ st = ($2 "" == $4 "") ? "збігається" : "ВІДРІЗНЯЄТЬСЯ"; printf "%-30s | %-34s | %-34s | %s\n", $1, $2, $4, st }'
if diff -q backup/check_source.txt backup/check_restore.txt > /dev/null; then
  echo "РЕЗУЛЬТАТ: усі контрольні показники збігаються"
else
  echo "РЕЗУЛЬТАТ: є розбіжності"; exit 1
fi

echo "== Перевірка обмежень у відновленій базі (очікується помилка unique_violation)"
"$BIN/psql" $H -d elearn_restore -c "INSERT INTO edu.users (email, full_name, role_code) VALUES ('ST01@elearn.test', 'X', 'student')" 2>&1 | head -2 || true
