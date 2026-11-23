# База даних платформи дистанційного навчання (варіант 113)

**Тема:** Проєктування та реалізація бази даних інформаційної системи платформи дистанційного навчання
(курси, учасники, навчальні матеріали, завдання та результати виконання).

## Середовище

| Компонент | Версія |
|---|---|
| PostgreSQL (сервер, psql, pg_dump, pg_restore) | 18.3, Windows x64 |
| Python | 3.12 |
| FastAPI / Uvicorn / psycopg2-binary | 0.165 / 0.54 / 2.9 |
| Розширення PostgreSQL | не потрібні |

## Структура

```
sql/01_schema.sql         схема edu, 11 таблиць, ключі, обмеження, індекси
sql/02_logic.sql          7 тригерів, 3 функції, 3 процедури
sql/03_views.sql          3 представлення, 1 матеріалізоване, функція оновлення
sql/04_seed.sql           тестові дані (синтетичні)
sql/05_roles.sql          ролі edu_teacher, edu_student, edu_analyst, edu_api та права
sql/06_queries.sql        17 запитів SELECT і 5 операцій зміни (з ROLLBACK)
sql/07_tests.sql          28 перевірок (позитивні, негативні, права, відкат)
sql/08_concurrency.py     конкурентний доступ (два незалежні підключення)
sql/09_perf_data.sql      генерація 136 000 робіт у базі elearn_perf
sql/09_performance.py     EXPLAIN (ANALYZE, BUFFERS) до/після індексів
sql/10_backup_restore.sh  pg_dump -> pg_restore у elearn_restore + звірка
sql/11_selects.sql        93 SELECT-запити за темами + команди запуску на початку файлу
api/                      REST API (FastAPI) + Swagger UI, smoke_test.py
protocols/                фактичні результати запуску всіх скриптів
backup/                   результати звірки після pg_restore (дамп генерується скриптом)
run_all.sh                повне розгортання elearn_db
```

Усі команди нижче виконуються з папки `bd/`.

## Запуск

1. Створити файл `bd/.env` (не входить до комплекту — містить паролі;
   `PGCLIENTENCODING=UTF8` потрібен, щоб psql у Git Bash правильно показував кирилицю):
   ```
   PGHOST=localhost
   PGPORT=5432
   PGUSER=postgres
   PGPASSWORD=<пароль postgres>
   API_DB_PASSWORD=<пароль для ролі edu_api>
   PGCLIENTENCODING=UTF8
   ```
2. Розгорнути базу (Git Bash):
   ```bash
   PSQL="/c/Program Files/PostgreSQL/18/bin/psql" bash run_all.sh
   ```
   Очікуваний результат: `OK: база elearn_db розгорнута`.
   Вручну: `createdb elearn_db`, далі `psql -d elearn_db -f sql/01_schema.sql` … `04_seed.sql`,
   `psql -d elearn_db -v api_password=... -f sql/05_roles.sql`.
3. Запити й тести:
   ```bash
   psql -d elearn_db -f sql/06_queries.sql
   psql -d elearn_db -f sql/07_tests.sql      # очікується 28 passed, 0 failed
   python sql/08_concurrency.py
   bash sql/10_backup_restore.sh              # очікується «усі контрольні показники збігаються»
   ```
4. Дослідження продуктивності (окрема база):
   ```bash
   createdb elearn_perf
   for f in 01_schema 02_logic 03_views 09_perf_data; do psql -d elearn_perf -f sql/$f.sql; done
   python sql/09_performance.py
   ```
5. REST API:
   ```bash
   pip install -r api/requirements.txt
   python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
   ```
   Swagger UI: http://127.0.0.1:8000/docs, ReDoc: http://127.0.0.1:8000/redoc.
   Перевірка: `python api/smoke_test.py` (очікується 43 PASS, 0 FAIL).
