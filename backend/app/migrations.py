"""
Idempotent schema fixes, run once at startup.

SQLAlchemy's create_all() creates missing tables but never alters existing ones,
and this project has a live Postgres database with real data. Everything here is
safe to run repeatedly, on both SQLite (local) and Postgres (deployed).

IMPORTANT: every statement runs in its OWN transaction.

Postgres aborts an entire transaction as soon as one statement in it fails --
every later statement then errors with "current transaction is aborted", and the
successful work rolls back too. An earlier version of this file ran the whole
migration in a single transaction and swallowed individual errors, so one benign
failure silently reverted the ADD COLUMNs. The API then served 500s on every
route that selected a full row, because the columns the ORM expected were gone.
SQLite hid the bug entirely, since it does not abort transactions that way.

Kept deliberately small rather than adopting Alembic: there is one deployment and
a handful of changes. Revisit if that stops being true.
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


def _run(engine, sql, label, params=None, optional=False):
    """Execute one statement in its own transaction.

    Isolation is the whole point: a failure here must not affect any other step.
    """
    try:
        with engine.begin() as conn:
            conn.execute(text(sql), params or {})
        print("migration: %s" % label)
        return True
    except Exception as e:
        if optional:
            print("migration: skipped %s (%s)" % (label, type(e).__name__))
        else:
            print("migration: FAILED %s -- %s" % (label, e))
        return False


def _table_names(engine):
    try:
        return set(inspect(engine).get_table_names())
    except Exception:
        return set()


def _columns(engine, table):
    try:
        return {c["name"]: str(c["type"]).upper() for c in inspect(engine).get_columns(table)}
    except Exception:
        return {}


def _add_missing_columns(engine):
    tables = _table_names(engine)
    for table, column, sql_type in ADDED_COLUMNS:
        if table not in tables:
            continue
        if column in _columns(engine, table):
            continue
        _run(engine,
             "ALTER TABLE %s ADD COLUMN %s %s" % (table, column, sql_type),
             "added %s.%s" % (table, column))


def _relax_theme_columns(engine, is_postgres):
    """Convert theme from a native enum to plain text.

    Only Postgres enforces the enum; SQLite already stores the label as text.
    """
    if not is_postgres:
        return
    tables = _table_names(engine)
    for table in ("content_candidates", "hourly_ones"):
        if table not in tables:
            continue
        current = _columns(engine, table).get("theme", "")
        if "CHAR" in current or "TEXT" in current:
            continue  # already plain text
        _run(engine,
             "ALTER TABLE %s ALTER COLUMN theme TYPE VARCHAR(40) USING theme::text" % table,
             "%s.theme is now free text" % table)

    # Picks can be scheduled before a theme is chosen. Harmless if already nullable,
    # and isolated so a failure cannot affect anything else.
    _run(engine,
         "ALTER TABLE hourly_ones ALTER COLUMN theme DROP NOT NULL",
         "hourly_ones.theme is nullable", optional=True)


def _normalize_theme_values(engine):
    """Rewrite legacy enum member names ('ENGINEERING') to labels ('Engineering')."""
    tables = _table_names(engine)
    for table in ("content_candidates", "hourly_ones"):
        if table not in tables:
            continue
        try:
            with engine.connect() as conn:
                rows = conn.execute(text(
                    "SELECT DISTINCT theme FROM %s WHERE theme IS NOT NULL" % table)).fetchall()
        except Exception as e:
            print("migration: could not read %s.theme values (%s)" % (table, e))
            continue

        for (value,) in rows:
            corrected = normalize_theme(value)
            if corrected != value:
                _run(engine,
                     "UPDATE %s SET theme = :new WHERE theme = :old" % table,
                     "%s.theme %r -> %r" % (table, value, corrected),
                     {"new": corrected, "old": value})


def verify_schema(engine):
    """Which expected columns are still missing. Empty list means the schema is current."""
    missing = []
    tables = _table_names(engine)
    for table, column, _type in ADDED_COLUMNS:
        if table in tables and column not in _columns(engine, table):
            missing.append("%s.%s" % (table, column))
    return missing


def ensure_schema(engine):
    """Bring an existing database up to the current shape. Safe to call every boot."""
    try:
        is_postgres = engine.dialect.name.startswith("postgres")
        _add_missing_columns(engine)
        _relax_theme_columns(engine, is_postgres)
        _normalize_theme_values(engine)

        missing = verify_schema(engine)
        if missing:
            # Loud, because the API will 500 on most routes in this state.
            print("migration: SCHEMA INCOMPLETE, still missing: %s" % ", ".join(missing))
        else:
            print("migration: schema is up to date")
        return missing
    except Exception:
        print("Schema migration failed (continuing):")
        traceback.print_exc()
        return ["<migration crashed>"]
