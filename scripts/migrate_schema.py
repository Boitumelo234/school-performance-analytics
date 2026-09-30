"""
Create the normalised tables (provinces, districts, schools) and add any
missing columns on school_performance.

Safe to run multiple times: uses CREATE TABLE IF NOT EXISTS and only
adds columns that are missing.
"""

from sqlalchemy import inspect, text

from app.database import Base, engine
from app import models  # noqa: F401  (import so Base sees the tables)


NEW_COLUMNS = {
    "school_performance": {
        "province_name": "VARCHAR(100) NULL",
        "school_id": "INT NULL",
        "source_year": "INT NULL",
    },
}


def existing_columns(table: str) -> set[str]:
    insp = inspect(engine)
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def add_missing_columns() -> None:
    with engine.begin() as conn:
        for table, cols in NEW_COLUMNS.items():
            have = existing_columns(table)
            if not have:
                continue
            for name, ddl in cols.items():
                if name not in have:
                    print(f"  + {table}.{name}")
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def add_indexes() -> None:
    with engine.begin() as conn:
        for stmt in [
            "CREATE INDEX idx_year_province ON school_performance (exam_year, province_name)",
            "CREATE INDEX idx_school_id ON school_performance (school_id)",
            "CREATE INDEX idx_source_year ON school_performance (source_year)",
        ]:
            try:
                conn.execute(text(stmt))
                print(f"  + {stmt}")
            except Exception as exc:
                print(f"  = index already exists or skipped ({exc.__class__.__name__})")


def main() -> None:
    print("Creating new tables...")
    Base.metadata.create_all(bind=engine)
    print("  done.")
    print("Adding missing columns...")
    add_missing_columns()
    print("Adding indexes...")
    add_indexes()
    print("Migration complete.")


if __name__ == "__main__":
    main()