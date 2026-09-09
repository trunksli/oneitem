"""
Tests for app/migrations.py against a throwaway database in the OLD shape.

Regression cover for the outage of 2026-09-09: the migration ran every statement
in a single transaction, so one benign failure rolled back the ADD COLUMNs that
had already succeeded. On Postgres the aborted transaction also poisoned every
later statement. The API then returned 500 on any route selecting a full row,
because the ORM expected columns the database no longer had.

    venv/Scripts/python.exe test_migrations.py
"""
import os
import sys
import tempfile

from sqlalchemy import create_engine, inspect, text

from app.migrations import ADDED_COLUMNS, ensure_schema, verify_schema

failures = []


def check(label, condition, detail=""):
    if condition:
        print("  PASS  %s" % label)
    else:
        print("  FAIL  %s %s" % (label, detail))
        failures.append(label)


def build_old_schema(engine):
    """The schema as it existed before tone/preview_text, with legacy theme names."""
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE content_candidates (
                id VARCHAR(36) PRIMARY KEY,
                url VARCHAR,
                source_type VARCHAR(20),
                source_id VARCHAR,
                title VARCHAR,
                description TEXT,
                creator_name VARCHAR,
                creator_url VARCHAR,
                upload_date TIMESTAMP,
                discovered_date TIMESTAMP,
                thumbnail_url VARCHAR,
                status VARCHAR(20),
                theme VARCHAR(40)
            )"""))
        conn.execute(text("""
            CREATE TABLE hourly_ones (
                id VARCHAR(36) PRIMARY KEY,
                publish_time TIMESTAMP,
                theme VARCHAR(40),
                candidate_id VARCHAR(36),
                editorial_explanation TEXT,
                is_bandit_winner BOOLEAN
            )"""))
        conn.execute(text("""
            CREATE TABLE comments (
                id VARCHAR(36) PRIMARY KEY,
                user_id VARCHAR(36),
                content TEXT,
                created_at TIMESTAMP
            )"""))
        conn.execute(text(
            "INSERT INTO content_candidates (id, title, theme, status) "
            "VALUES ('c1', 'Old row', 'ENGINEERING', 'PENDING_REVIEW')"))
        conn.execute(text(
            "INSERT INTO content_candidates (id, title, theme, status) "
            "VALUES ('c2', 'Another', 'WEIRD_FOOD', 'PENDING_REVIEW')"))
        conn.execute(text(
            "INSERT INTO hourly_ones (id, publish_time, theme, candidate_id) "
            "VALUES ('h1', '2026-09-01 10:00:00', 'ODDBALL', 'c1')"))


def columns(engine, table):
    return {c["name"] for c in inspect(engine).get_columns(table)}


def main():
    handle, path = tempfile.mkstemp(suffix=".db")
    os.close(handle)
    engine = create_engine("sqlite:///" + path)

    try:
        build_old_schema(engine)

        print("\nbefore migration")
        check("starts without tone", "tone" not in columns(engine, "content_candidates"))
        check("starts without preview_text",
              "preview_text" not in columns(engine, "content_candidates"))
        check("verify_schema reports the gap", len(verify_schema(engine)) > 0)

        print("\nafter migration")
        ensure_schema(engine)
        check("schema reports complete", verify_schema(engine) == [],
              str(verify_schema(engine)))
        for table, column, _t in ADDED_COLUMNS:
            check("added %s.%s" % (table, column), column in columns(engine, table))

        print("\nlegacy theme values rewritten to labels")
        with engine.connect() as conn:
            themes = dict(conn.execute(text(
                "SELECT id, theme FROM content_candidates")).fetchall())
            hourly_theme = conn.execute(text(
                "SELECT theme FROM hourly_ones WHERE id = 'h1'")).scalar()
        check("ENGINEERING -> Engineering", themes.get("c1") == "Engineering", str(themes))
        check("WEIRD_FOOD -> Food", themes.get("c2") == "Food", str(themes))
        check("ODDBALL -> Oddities", hourly_theme == "Oddities", str(hourly_theme))

        print("\nidempotent")
        ensure_schema(engine)
        ensure_schema(engine)
        check("still complete after repeat runs", verify_schema(engine) == [])
        with engine.connect() as conn:
            again = conn.execute(text(
                "SELECT theme FROM content_candidates WHERE id = 'c1'")).scalar()
        check("values are not re-mangled", again == "Engineering", str(again))

        print("\nisolation: one bad statement must not undo the good ones")
        handle2, path2 = tempfile.mkstemp(suffix=".db")
        os.close(handle2)
        engine2 = create_engine("sqlite:///" + path2)
        build_old_schema(engine2)
        # hourly_ones is missing, so the statements touching it fail; the ones
        # touching content_candidates must still land.
        with engine2.begin() as conn:
            conn.execute(text("DROP TABLE hourly_ones"))
        ensure_schema(engine2)
        check("candidate columns added despite the missing table",
              {"tone", "preview_text"} <= columns(engine2, "content_candidates"))
        engine2.dispose()
        os.remove(path2)
    finally:
        engine.dispose()
        try:
            os.remove(path)
        except OSError:
            pass

    print("")
    if failures:
        print("%d FAILED: %s" % (len(failures), ", ".join(failures)))
        return 1
    print("All migration checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
