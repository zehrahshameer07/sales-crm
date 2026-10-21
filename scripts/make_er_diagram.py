"""Generate the database diagrams from the real SQLAlchemy models, so they can never go out of date.

    python scripts/make_er_diagram.py

Writes into docs/:
  schema.dbml     paste into https://dbdiagram.io to edit/export the diagram (free tool)
  er-diagram.mmd  Mermaid source (GitHub draws it inside docs/ER_DIAGRAM.md)
  er-diagram.png  picture rendered with Graphviz (needs the `dot` program; skipped if missing)
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import sqlalchemy as sa  # noqa: E402

from app import models  # noqa: E402,F401
from app.database import Base  # noqa: E402

DOCS = ROOT / "docs"


def type_name(column) -> str:
    t = column.type
    if isinstance(t, sa.Enum):
        return t.name
    if isinstance(t, sa.Uuid):
        return "uuid"
    if isinstance(t, sa.String):
        return f"varchar({t.length})" if t.length else "text"
    if isinstance(t, sa.Boolean):
        return "boolean"
    if isinstance(t, sa.Integer):
        return "int"
    if isinstance(t, sa.Text):
        return "text"
    if isinstance(t, sa.Date) and not isinstance(t, sa.DateTime):
        return "date"
    return "timestamptz"


def notes(column) -> list[str]:
    out = []
    if column.primary_key:
        out.append("PK")
    if column.foreign_keys:
        out.append("FK")
    if column.unique or any(i.unique and column in i.columns.values() for i in column.table.indexes):
        out.append("UK")
    return out


def dbml() -> str:
    lines = []
    enums = {}
    for table in Base.metadata.sorted_tables:
        for col in table.columns:
            if isinstance(col.type, sa.Enum):
                enums[col.type.name] = col.type.enums
    for name, values in enums.items():
        lines.append(f"Enum {name} {{")
        lines += [f"  {v}" for v in values]
        lines.append("}\n")
    for table in Base.metadata.sorted_tables:
        lines.append(f"Table {table.name} {{")
        for col in table.columns:
            flags = []
            if col.primary_key:
                flags.append("pk")
            if not col.nullable and not col.primary_key:
                flags.append("not null")
            if col.unique or any(i.unique and col in i.columns.values() for i in table.indexes):
                flags.append("unique")
            lines.append(f"  {col.name} {type_name(col)}" + (f" [{', '.join(flags)}]" if flags else ""))
        lines.append("}\n")
    for table in Base.metadata.sorted_tables:
        for fk in table.foreign_keys:
            lines.append(f"Ref: {table.name}.{fk.parent.name} > {fk.column.table.name}.{fk.column.name}")
    return "\n".join(lines) + "\n"


def mermaid() -> str:
    lines = ["erDiagram"]
    for table in Base.metadata.sorted_tables:
        for fk in table.foreign_keys:
            lines.append(f"  {fk.column.table.name.upper()} ||--o{{ {table.name.upper()} : \"{fk.parent.name}\"")
    for table in Base.metadata.sorted_tables:
        lines.append(f"  {table.name.upper()} {{")
        for col in table.columns:
            tag = " ".join(notes(col))
            lines.append(f"    {type_name(col).replace('(', '_').replace(')', '')} {col.name}" + (f" {tag}" if tag else ""))
        lines.append("  }")
    return "\n".join(lines) + "\n"


def dot() -> str:
    out = ['digraph G {', '  rankdir=LR; bgcolor="white"; nodesep=0.5; ranksep=1.1;',
           '  node [shape=plaintext, fontname="Helvetica"]; edge [fontname="Helvetica", fontsize=9, color="#667085", arrowhead=crow, arrowtail=tee, dir=both];']
    for table in Base.metadata.sorted_tables:
        rows = [f'<TR><TD COLSPAN="3" BGCOLOR="#E8590C"><FONT COLOR="white"><B>{table.name}</B></FONT></TD></TR>']
        for col in table.columns:
            tag = ", ".join(notes(col))
            rows.append(f'<TR><TD ALIGN="LEFT" PORT="{col.name}">{col.name}</TD><TD ALIGN="LEFT"><FONT COLOR="#667085">{type_name(col)}</FONT></TD>'
                        f'<TD>{f"<FONT COLOR=\"#E8590C\"><B>{tag}</B></FONT>" if tag else ""}</TD></TR>')
        out.append(f'  {table.name} [label=<<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="5" COLOR="#D0D5DD">{"".join(rows)}</TABLE>>];')
    for table in Base.metadata.sorted_tables:
        for fk in table.foreign_keys:
            out.append(f'  {fk.column.table.name}:{fk.column.name} -> {table.name}:{fk.parent.name} [label="{fk.parent.name}"];')
    out.append("}")
    return "\n".join(out)


if __name__ == "__main__":
    DOCS.mkdir(exist_ok=True)
    (DOCS / "schema.dbml").write_text(dbml())
    (DOCS / "er-diagram.mmd").write_text(mermaid())
    print("wrote docs/schema.dbml and docs/er-diagram.mmd")
    if shutil.which("dot"):
        subprocess.run(["dot", "-Tpng", "-Gdpi=130", "-o", str(DOCS / "er-diagram.png")], input=dot().encode(), check=True)
        print("wrote docs/er-diagram.png")
    else:
        print("Graphviz `dot` not found: skipped the PNG (install Graphviz to create it).")
