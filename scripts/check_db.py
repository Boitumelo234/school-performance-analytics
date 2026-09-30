"""Quick DB status check. Run:  python -m scripts.check_db"""

from sqlalchemy import func

from app.database import SessionLocal
from app.models import SchoolPerformance as SP, School, District, Province


def main() -> None:
    db = SessionLocal()
    try:
        rows = db.query(func.count(SP.id)).scalar()
        years = [y for (y,) in db.query(SP.exam_year).distinct().order_by(SP.exam_year)]
        sources = [
            int(s) for (s,) in db.query(SP.source_year)
            .filter(SP.source_year.isnot(None)).distinct().order_by(SP.source_year)
        ]
        print(f"rows:            {rows}")
        print(f"exam years:      {years}")
        print(f"source reports:  {sources}")
        print(f"provinces:       {db.query(Province).count()}")
        print(f"districts:       {db.query(District).count()}")
        print(f"schools:         {db.query(School).count()}")
    finally:
        db.close()


if __name__ == "__main__":
    main()