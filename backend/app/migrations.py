"""
Idempotent schema fixes, run once at startup.

SQLAlchemy's create_all() creates missing tables but never alters existing ones,
and this project has a live Postgres database with real data. Everything here is
safe to run repeatedly and safe to run on both SQLite (local) and Postgres
(deployed).

Kept deliberately small and dependency-free rather than adopting Alembic: there
is one deployment and a handful of changes. Revisit if that stops being true.
"""
import traceback

from sqlalchemy import inspect, text

from .themes import normalize_theme

# Columns added after the initial schema: (table, column, SQL type)
ADDED_COLUMNS = [
    ("content_candidates", "tone", "VARCHAR(40)"),
    ("content_candidates", "preview_text", "TEXT"),
    ("comments", "display_name", "VARCHAR(40)"),
    ("hourly_ones", "views_at_feature", "BIGINT"),
    ("hourly_ones", "views_after_7d", "BIGINT"),
    ("hourly_ones", "outcome_checked_at", "TIMESTAMP"),
]


def _existing_columns(inspector, table):
    try:
        return {c["name"] for c in inspector.get_columns(table)}
    except Exception:
        return set()


def _add_missing_columns(conn, inspector):
    tables = set(inspector.get_table_names())
    for table, column, sql_type in ADDED_COLUMNS:
        if table not in tables:
            continue
        if column in _existing_columns(inspector, table):
            continue
        conn.execute(text("ALTER TABLE %s ADD COLUMN %s %s" % (table, column, sql_type)))
        print("migration: added %s.%s" % (table, column))


def _relax_theme_columns(conn, is_postgres, inspector):
    """Convert theme from a native enum to plain text.

    Only Postgres actually enforces the enum; SQLite stores the label as text
    already, so there is nothing to alter there.
    """
    if not is_postgres:
        return
    for table in ("content_candidates", "hourly_ones"):
        if table not in set(inspector.get_table_names()):
            continue
        column_types = {c["name"]: str(c["type"]).upper() for c in inspector.get_columns(table)}
        current = column_types.get("theme", "")
        if "CHAR" in current or "TEXT" in current:
            continue  # already plain text
        conn.execute(text(
            "ALTER TABLE %s ALTER COLUMN theme TYPE VARCHAR(40) USING theme::text" % table))
        print("migration: %s.theme is now free text" % table)

    # hourly_ones.theme was NOT NULL; picks can now be scheduled before a theme
    # is chosen, so relax it.
    try:
        conn.execute(text("ALTER TABLE hourly_ones ALTER COLUMN theme DROP NOT NULL"))
    except Exception:
        pass  # already nullable


def _normalize_theme_values(conn, inspector):
    """Rewrite legacy enum member names ('ENGINEERING') to labels ('Engineering')."""
    tables = set(inspector.get_table_names())
    for table in ("content_candidates", "hourly_ones"):
        if table not in tables:
            continue
        rows = conn.execute(text(
            "SELECT DISTINCT theme FROM %s WHERE theme IS NOT NULL" % table)).fetchall()
        for (value,) in rows:
            corrected = normalize_theme(value)
            if corrected != value:
                conn.execute(
                    text("UPDATE %s SET theme = :new WHERE theme = :old" % table),
                    {"new": corrected, "old": value})
                print("migration: %s.theme %r -> %r" % (table, value, corrected))


def ensure_schema(engine):
    """Bring an existing database up to the current shape. Safe to call every boot."""
    try:
        is_postgres = engine.dialect.name.startswith("postgres")
        inspector = inspect(engine)
        # begin() commits on success and rolls back on error, on 1.4 and 2.x alike
        with engine.begin() as conn:
            _add_missing_columns(conn, inspector)
            _relax_theme_columns(conn, is_postgres, inspector)
            _normalize_theme_values(conn, inspector)
    except Exception:
        # A failed migration must not stop the API from serving existing content.
        print("Schema migration failed (continuing):")
        traceback.print_exc()
