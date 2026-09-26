"""
Tests for database URL handling (app/database.py).

A deploy failed with "No module named 'psycopg'" because a bare postgresql:// URL
lets SQLAlchemy pick the driver, and its choice changed under a version floor.
These checks keep the driver explicit.

    venv/Scripts/python.exe test_database.py
"""
import sys

from app.database import name_the_driver

failures = []


def check(label, condition, detail=""):
    if condition:
        print("  PASS  %s" % label)
    else:
        print("  FAIL  %s %s" % (label, detail))
        failures.append(label)


def test_driver_is_named():
    print("Driver selection")
    named = name_the_driver("postgresql://user:pw@host:5432/one")
    check("a bare postgresql URL gets an explicit driver",
          named.startswith("postgresql+psycopg://") or named.startswith("postgresql+psycopg2://"), named)
    check("the rest of the URL is untouched", named.endswith("://user:pw@host:5432/one"), named)

    try:
        import psycopg  # noqa: F401
        expected = "postgresql+psycopg://"
    except ImportError:
        expected = "postgresql+psycopg2://"
    check("it names the driver that is actually installed", named.startswith(expected), named)


def test_leaves_other_urls_alone():
    print("Other URLs")
    for url in (
        "postgresql+psycopg2://user@host/one",   # already chosen by the operator
        "postgresql+psycopg://user@host/one",
        "sqlite:///./sql_app_v2.db",
        "sqlite:///:memory:",
    ):
        check("unchanged: %s" % url.split("://")[0], name_the_driver(url) == url, name_the_driver(url))


if __name__ == "__main__":
    test_driver_is_named()
    test_leaves_other_urls_alone()
    if failures:
        print("\n%d database check(s) FAILED: %s" % (len(failures), ", ".join(failures)))
        sys.exit(1)
    print("\nAll database checks passed.")
