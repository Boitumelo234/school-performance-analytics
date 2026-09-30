"""
Force-add the missing columns and indexes to school_performance.

Safe to run multiple times. Prints what it does.
Run from the project root:  python -m scripts.force_migrate
"""

from sqlalchemy import inspect, text

from app.database import engine


COLUMNS = [
    ("province_name", "VARCHAR(100) NULL"),
    ("school_id", "INT NULL"),
    ("source_year", "INT NULL"),
]

INDEXES = [
    "CREATE INDEX idx_year_province ON school_performance (exam_year, province_name)",
    "CREATE INDEX idx_school_id ON school_performance (school_id)",
    "CREATE INDEX idx_source_year ON school_performance (source_year)",
    "CREATE INDEX idx_year_district ON school_performance (exam_year, district_name)",
    "CREATE INDEX idx_year_quintile ON school_performance (exam_year, quintile)",
]


def main() -> None:
    insp = inspect(engine)
    have = {c["name"] for c in insp.get_columns("school_performance")}
    print("BEFORE:", sorted(have))

    with engine.begin() as conn:
        for name, ddl in COLUMNS:
            if name in have:
                print(f"  = {name} already exists")
                continue
            print(f"  + adding column {name}")
            conn.execute(text(f"ALTER TABLE school_performance ADD COLUMN {name} {ddl}"))

    # refresh column list
    insp = inspect(engine)
    have = {c["name"] for c in insp.get_columns("school_performance")}
    print("AFTER: ", sorted(have))

    print("Adding indexes (ignoring ones that already exist)...")
    existing_indexes = {i["name"] for i in insp.get_indexes("school_performance")}
    with engine.begin() as conn:
        for stmt in INDEXES:
            idx_name = stmt.split()[2]  # "CREATE INDEX <name> ..."
            if idx_name in existing_indexes:
                print(f"  = {idx_name} already exists")
                continue
            try:
                conn.execute(text(stmt))
                print(f"  + {idx_name}")
            except Exception as exc:
                print(f"  ! {idx_name} failed: {exc}")

    print("Done.")


if __name__ == "__main__":
    main()