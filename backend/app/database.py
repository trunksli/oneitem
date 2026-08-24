from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

# For local development we can just use SQLite to avoid needing a full postgres setup right away,
# or if postgres is preferred, we can use the postgres URL.
# The implementation plan mentioned PostgreSQL, but for MVP speed, sqlite is much faster to bootstrap.
# Let's check what the user wants or just stick to postgres if they have it.
# Actually, I'll use sqlite for now as a fallback if DB_URL is not provided.
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sql_app_v2.db")

if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
