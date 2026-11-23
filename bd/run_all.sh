#!/usr/bin/env bash
# Повне розгортання БД elearn_db (Git Bash). Потрібні змінні PGPASSWORD та API_DB_PASSWORD (див. .env)
set -e
cd "$(dirname "$0")"
[ -f .env ] && set -a && . ./.env && set +a
PSQL="${PSQL:-psql}"
export PGCLIENTENCODING=UTF8
export PGOPTIONS="-c client_min_messages=warning"   # без інформаційних NOTICE (напр. «схеми edu не існує»)
DB="${DB:-elearn_db}"
"$PSQL" -h "${PGHOST:-localhost}" -U "${PGUSER:-postgres}" -d postgres -q -c "DROP DATABASE IF EXISTS $DB WITH (FORCE)" -c "CREATE DATABASE $DB ENCODING 'UTF8' TEMPLATE template0"
for f in 01_schema 02_logic 03_views 04_seed; do
  "$PSQL" -h "${PGHOST:-localhost}" -U "${PGUSER:-postgres}" -d "$DB" -v ON_ERROR_STOP=1 -q -f sql/$f.sql > /dev/null
done
"$PSQL" -h "${PGHOST:-localhost}" -U "${PGUSER:-postgres}" -d "$DB" -v ON_ERROR_STOP=1 -q -v api_password="$API_DB_PASSWORD" -f sql/05_roles.sql
echo "OK: база $DB розгорнута"
