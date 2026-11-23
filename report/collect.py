"""Збирання фактичних даних із каталогу PostgreSQL для звіту -> report/data.json"""
import json
import os
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parent.parent
for line in (ROOT / "bd" / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())
conn = psycopg2.connect(host="localhost", user=os.environ["PGUSER"], password=os.environ["PGPASSWORD"],
                        dbname="elearn_db")
cur = conn.cursor()
out = {}


def clean_check(d):
    import re as _re
    d = d.replace("::character varying", "").replace("::text[]", "").replace("::text", "").replace("::numeric", "")
    m = _re.search(r"\(\(?(\w+)\)? = ANY \(+ARRAY\[(.*?)\]\)+", d)
    if m:
        return f"CHECK ({m.group(1)} IN ({m.group(2)}))"
    d = _re.sub(r"\((\w+)\)", lambda mm: mm.group(1), d)
    d = _re.sub(r"\(\((.*)\)\)$", lambda mm: "(" + mm.group(1) + ")", d)
    return d

cur.execute("""
SELECT c.relname, a.attnum, a.attname, format_type(a.atttypid, a.atttypmod), a.attnotnull,
       pg_get_expr(d.adbin, d.adrelid), a.attidentity
FROM pg_attribute a
JOIN pg_class c ON c.oid = a.attrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
WHERE n.nspname = 'edu' AND c.relkind = 'r' AND a.attnum > 0 AND NOT a.attisdropped
ORDER BY c.relname, a.attnum""")
cols = {}
for t, num, name, typ, nn, default, ident in cur.fetchall():
    typ = typ.replace("character varying", "varchar").replace("timestamp with time zone", "timestamptz")
    cols.setdefault(t, []).append({"name": name, "num": num, "type": typ, "not_null": nn,
                                   "default": default, "identity": ident, "cons": []})

cur.execute("""
SELECT c.relname, con.conname, con.contype, con.conkey, pg_get_constraintdef(con.oid),
       fc.relname, con.confdeltype
FROM pg_constraint con
JOIN pg_class c ON c.oid = con.conrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
LEFT JOIN pg_class fc ON fc.oid = con.confrelid
WHERE n.nspname = 'edu' AND con.contype IN ('p','f','u','c')
ORDER BY c.relname, con.conname""")
table_cons = {}
deltype = {"a": "NO ACTION", "r": "RESTRICT", "c": "CASCADE", "n": "SET NULL", "d": "SET DEFAULT"}
for t, name, typ, keys, definition, ftable, fdel in cur.fetchall():
    table_cons.setdefault(t, []).append({"name": name, "type": typ, "def": clean_check(definition) if typ == "c" else definition})
    if len(keys) == 1:
        col = next(c for c in cols[t] if c["num"] == keys[0])
        if typ == "p":
            col["cons"].append("PK")
        elif typ == "f":
            col["cons"].append(f"FK → {ftable}, ON DELETE {deltype[fdel]}")
        elif typ == "u":
            col["cons"].append("UNIQUE")
        elif typ == "c":
            col["cons"].append(clean_check(definition))
cur.execute("""SELECT tablename, indexname, indexdef FROM pg_indexes WHERE schemaname='edu'
               ORDER BY tablename, indexname""")
out["indexes"] = cur.fetchall()
cur.execute("""SELECT c.relname, obj_description(c.oid) FROM pg_class c
               JOIN pg_namespace n ON n.oid = c.relnamespace
               WHERE n.nspname = 'edu' AND c.relkind = 'r'""")
out["comments"] = dict(cur.fetchall())
cur.execute("""SELECT relname, n_live_tup FROM pg_stat_user_tables WHERE schemaname='edu'""")
cur.execute("""SELECT 'users', count(*) FROM edu.users UNION ALL SELECT 'categories', count(*) FROM edu.categories
  UNION ALL SELECT 'courses', count(*) FROM edu.courses UNION ALL SELECT 'modules', count(*) FROM edu.modules
  UNION ALL SELECT 'materials', count(*) FROM edu.materials UNION ALL SELECT 'enrollments', count(*) FROM edu.enrollments
  UNION ALL SELECT 'assignments', count(*) FROM edu.assignments UNION ALL SELECT 'submissions', count(*) FROM edu.submissions
  UNION ALL SELECT 'grades', count(*) FROM edu.grades UNION ALL SELECT 'material_progress', count(*) FROM edu.material_progress
  UNION ALL SELECT 'audit_log', count(*) FROM edu.audit_log""")
out["rows"] = dict(cur.fetchall())
cur.execute("""SELECT table_name, privilege_type, grantee FROM information_schema.role_table_grants
               WHERE table_schema='edu' AND grantee LIKE 'edu_%' ORDER BY 1,3,2""")
out["grants"] = cur.fetchall()
cur.execute("""SELECT t.tgname, c.relname, pg_get_triggerdef(t.oid) FROM pg_trigger t
               JOIN pg_class c ON c.oid = t.tgrelid JOIN pg_namespace n ON n.oid = c.relnamespace
               WHERE n.nspname='edu' AND NOT t.tgisinternal ORDER BY c.relname, t.tgname""")
out["triggers"] = cur.fetchall()
cur.execute("SHOW server_version")
out["version"] = cur.fetchone()[0]
out["columns"] = cols
out["constraints"] = table_cons
(ROOT / "report" / "data.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print({t: len(c) for t, c in cols.items()}, out["rows"])
