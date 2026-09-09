"""
Apply pending schema changes and report the result.

The API also runs this at startup, but running it directly gives visible output
and an exit code, which matters when the alternative is guessing from a 500.

    python migrate.py

Exits 0 when the schema is current, 1 when columns are still missing.
"""
import sys

from dotenv import load_dotenv
load_dotenv()

from app import database, models
from app.migrations import ensure_schema, verify_schema

if __name__ == "__main__":
    url = str(database.engine.url)
    # Never print credentials
    safe = url.split("@")[-1] if "@" in url else url
    print("Database: %s (%s)" % (database.engine.dialect.name, safe))

    print("\nCreating any missing tables...")
    models.Base.metadata.create_all(bind=database.engine)

    print("Applying schema migrations...")
    ensure_schema(database.engine)

    missing = verify_schema(database.engine)
    if missing:
        print("\nSTILL MISSING: %s" % ", ".join(missing))
        print("The API will return 500 on most routes until these exist.")
        sys.exit(1)

    print("\nSchema is up to date.")
    sys.exit(0)
