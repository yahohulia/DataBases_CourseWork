"""Побудова ER-діаграми (фізична модель) з каталогу PostgreSQL -> docs/er_diagram.png"""
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle
import psycopg2

ROOT = Path(__file__).resolve().parent.parent
for line in (ROOT / "bd" / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())
conn = psycopg2.connect(host="localhost", user=os.environ["PGUSER"], password=os.environ["PGPASSWORD"],
                        dbname="elearn_db")
cur = conn.cursor()
cur.execute("""
SELECT c.table_name, c.column_name,
       CASE WHEN c.data_type = 'character varying' THEN 'varchar(' || c.character_maximum_length || ')'
            WHEN c.data_type = 'numeric' THEN 'numeric(' || c.numeric_precision || ',' || c.numeric_scale || ')'
            WHEN c.data_type = 'timestamp with time zone' THEN 'timestamptz'
            ELSE c.data_type END,
       c.is_nullable = 'NO',
       EXISTS (SELECT 1 FROM information_schema.key_column_usage k
               JOIN information_schema.table_constraints t ON t.constraint_name = k.constraint_name
               WHERE t.constraint_type = 'PRIMARY KEY' AND k.table_name = c.table_name
                 AND k.column_name = c.column_name AND k.table_schema = 'edu'),
       EXISTS (SELECT 1 FROM information_schema.key_column_usage k
               JOIN information_schema.table_constraints t ON t.constraint_name = k.constraint_name
               WHERE t.constraint_type = 'FOREIGN KEY' AND k.table_name = c.table_name
                 AND k.column_name = c.column_name AND k.table_schema = 'edu')
FROM information_schema.columns c
WHERE c.table_schema = 'edu'
  AND c.table_name IN (SELECT tablename FROM pg_tables WHERE schemaname = 'edu')
ORDER BY c.table_name, c.ordinal_position""")
tables: dict[str, list] = {}
for t, col, typ, nn, pk, fk in cur.fetchall():
    tables.setdefault(t, []).append((col, typ, nn, pk, fk))

POS = {  # x, y_top
    "categories": (0.2, 19.6), "users": (0.2, 15.0), "audit_log": (6.0, 7.4),
    "courses": (6.0, 19.6), "enrollments": (6.0, 12.4),
    "modules": (11.8, 19.6), "assignments": (11.8, 16.6), "submissions": (11.8, 10.2),
    "materials": (17.6, 19.6), "material_progress": (17.6, 14.4), "grades": (17.6, 7.4),
}
W, RH, HH = 5.0, 0.36, 0.5
fig, ax = plt.subplots(figsize=(24, 21))
ax.set_xlim(0, 23)
ax.set_ylim(2.1, 20.2)
ax.axis("off")
box = {}
for t, cols in tables.items():
    x, y = POS[t]
    h = HH + RH * len(cols)
    box[t] = (x, y - h, W, h)
    ax.add_patch(Rectangle((x, y - h), W, h, fc="white", ec="#1f3b63", lw=1.6, zorder=2))
    ax.add_patch(Rectangle((x, y - HH), W, HH, fc="#1f3b63", ec="#1f3b63", zorder=3))
    ax.text(x + W / 2, y - HH / 2, t, color="white", ha="center", va="center",
            fontsize=13, fontweight="bold", zorder=4)
    for i, (col, typ, nn, pk, fk) in enumerate(cols):
        yy = y - HH - RH * (i + 0.5)
        mark = "PK" if pk else ""
        mark = (mark + (",FK" if mark else "FK")) if fk else mark
        ax.text(x + 0.08, yy, mark, fontsize=9, color="#b03a2e", va="center", fontweight="bold", zorder=4)
        ax.text(x + 0.75, yy, col, fontsize=10.5, va="center", zorder=4,
                fontweight="bold" if pk else "normal", style="normal")
        ax.text(x + W - 0.08, yy, typ + ("" if nn else " ∅"), fontsize=9, va="center",
                ha="right", color="#555", zorder=4)


def anchor(t, side, frac=0.5):
    x, y, w, h = box[t]
    return {"l": (x, y + h * frac), "r": (x + w, y + h * frac),
            "t": (x + w * frac, y + h), "b": (x + w * frac, y)}[side]


def rel(points, one="1", many="N", label=None):
    xs, ys = zip(*points)
    ax.plot(xs, ys, color="#34495e", lw=1.4, zorder=1)
    (x0, y0), (x1, y1) = points[0], points[1]
    (xa, ya), (xb, yb) = points[-1], points[-2]
    ax.text(x0 + (0.18 if x1 > x0 else -0.18 if x1 < x0 else 0.12),
            y0 + (0.18 if y1 > y0 else -0.22 if y1 < y0 else 0.15), one,
            fontsize=12, color="#c0392b", fontweight="bold", ha="center", zorder=5)
    ax.text(xa + (0.2 if xb > xa else -0.2 if xb < xa else 0.15),
            ya + (0.18 if yb > ya else -0.22 if yb < ya else 0.15), many,
            fontsize=12, color="#c0392b", fontweight="bold", ha="center", zorder=5)
    if label:
        mx, my = (points[len(points) // 2 - 1][0] + points[len(points) // 2][0]) / 2, \
                 (points[len(points) // 2 - 1][1] + points[len(points) // 2][1]) / 2
        ax.text(mx, my + 0.12, label, fontsize=9, color="#34495e", ha="center", style="italic",
                bbox=dict(fc="white", ec="none", pad=0.5), zorder=5)


def ortho(a, b, mid_x=None, mid_y=None):
    if mid_x is not None:
        return [a, (mid_x, a[1]), (mid_x, b[1]), b]
    return [a, (a[0], mid_y), (b[0], mid_y), b]


# categories self-reference (петля під таблицею)
cx, cy, cw, ch = box["categories"]
rel([(cx + cw * 0.25, cy), (cx + cw * 0.25, cy - 0.35), (cx + cw * 0.75, cy - 0.35),
     (cx + cw * 0.75, cy)], label="parent_id")
rel(ortho(anchor("categories", "r", 0.75), anchor("courses", "l", 0.45), mid_x=5.6), label="category_id")
rel(ortho(anchor("users", "r", 0.8), anchor("courses", "l", 0.2), mid_x=5.4), label="teacher_id")
rel(ortho(anchor("users", "r", 0.45), anchor("enrollments", "l", 0.6), mid_x=5.6), label="student_id")
rel([anchor("courses", "b", 0.5), anchor("enrollments", "t", 0.5)], label="course_id")
rel([anchor("courses", "r", 0.93), anchor("modules", "l", 0.84)], label="course_id")
rel([anchor("modules", "r", 0.84), anchor("materials", "l", 0.9244)], label="module_id")
rel([anchor("modules", "b", 0.5), anchor("assignments", "t", 0.5)], label="module_id")
a1, a2 = anchor("assignments", "b", 0.5), anchor("submissions", "t", 0.5)
rel([a1, a2])
ax.text(a1[0] + 0.1, a1[1] - 0.9, "assignment_id", fontsize=9, color="#34495e", style="italic", zorder=5)
rel(ortho(anchor("enrollments", "r", 0.5), anchor("submissions", "l", 0.6), mid_x=11.3), label="enrollment_id")
rel(ortho(anchor("enrollments", "r", 0.75), anchor("material_progress", "l", 0.4), mid_x=17.1),
    label="enrollment_id")
rel([anchor("materials", "b", 0.5), anchor("material_progress", "t", 0.5)], label="material_id")
rel(ortho(anchor("submissions", "r", 0.5), anchor("grades", "l", 0.6), mid_x=17.2), one="1", many="0..1",
    label="submission_id")
gx, gy, gw, gh = box["grades"]
ux, uy, uw, uh = box["users"]
rel([(ux + uw * 0.5, uy), (ux + uw * 0.5, 2.75), (gx + gw * 0.5, 2.75), (gx + gw * 0.5, gy)],
    label="grader_id")
ax.text(0.2, 2.2, "PK — первинний ключ, FK — зовнішній ключ, ∅ — допускається NULL; "
        "1 / N — кратність зв'язку. audit_log заповнюється тригерами (зв'язок логічний: table_name + record_id).",
        fontsize=11, color="#333")
out = ROOT / "docs" / "er_diagram.png"
fig.savefig(out, dpi=110, bbox_inches="tight")
from PIL import Image
Image.open(out).rotate(90, expand=True).save(ROOT / "docs" / "er_diagram_rotated.png")
print("saved", out)
