import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

# DATABASE_URL (e.g. managed Postgres on Render) wins; otherwise a local SQLite
# file. SQLITE_PATH lets a deployment point SQLite at a mounted persistent disk.
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL") or (
    "sqlite:///" + os.getenv("SQLITE_PATH", "./sql_app_v2.db")
)

# Render and Heroku hand out "postgres://" URLs, which SQLAlchemy 1.4+ rejects.
if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)


def name_the_driver(url):
    """Say which Postgres driver to use instead of letting SQLAlchemy choose.

    A bare "postgresql://" URL leaves the choice to SQLAlchemy, and which DBAPI it
    reaches for has changed between releases. requirements.txt deliberately uses
    version floors, so an unrelated rebuild once installed a newer SQLAlchemy that
    asked for psycopg 3 while only psycopg2 was present, and the deploy died with
    ModuleNotFoundError. Naming the driver makes the build reproducible: prefer
    psycopg 3 when it is installed, fall back to psycopg2, and never guess.
    """
    if not url.startswith("postgresql://"):
        return url  # sqlite, or a URL that already names its driver
    try:
        import psycopg  # noqa: F401  (psycopg 3)
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    except ImportError:
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)


SQLALCHEMY_DATABASE_URL = name_the_driver(SQLALCHEMY_DATABASE_URL)

if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    # Managed Postgres drops idle connections; pre-ping avoids stale-connection errors
    # after the service has been idle (free tiers spin down aggressively).
    engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
