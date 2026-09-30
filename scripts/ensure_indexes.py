"""Ensure indexes exist. Run:  python -m scripts.ensure_indexes"""

from sqlalchemy import inspect, text
from app.database import engine

INDEXES = [
    "CREATE INDEX idx_year_district ON school_performance (exam_year, district_name)",
    "CREATE INDEX idx_year_quintile ON school_performance (exam_year, quintile)",
    "CREATE INDEX idx_year_province ON school_performance (exam_year, province_name)",
    "CREATE INDEX idx_emis ON school_performance (emis_number)",
    "CREATE INDEX idx_emis_year ON school_performance (emis_number, exam_year)",
    "CREATE INDEX idx_school_id ON school_performance (school_id)",
    "CREATE INDEX idx_source_year ON school_performance (source_year)",
    "CREATE INDEX idx_centre_name ON school_performance (centre_name)",
]


def main() -> None:
    insp = inspect(engine)
    existing = {i["name"] for i in insp.get_indexes("school_performance")}
    print(f"existing: {sorted(existing)}")
    with engine.begin() as conn:
        for stmt in INDEXES:
            name = stmt.split()[2]
            if name in existing:
                print(f"  = {name}")
                continue
            try:
                conn.execute(text(stmt))
                print(f"  + {name}")
            except Exception as exc:
                print(f"  ! {name}: {exc}")


if __name__ == "__main__":
    main()