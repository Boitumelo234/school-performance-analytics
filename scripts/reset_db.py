"""Drop all app tables so transform can rebuild them from scratch.

Run from the project root:  python -m scripts.reset_db
"""

from sqlalchemy import text

from app.database import engine


TABLES = ["school_performance", "schools", "districts", "provinces"]


def main() -> None:
    with engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for name in TABLES:
            print(f"  - dropping {name} (if exists)")
            conn.execute(text(f"DROP TABLE IF EXISTS {name}"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
    print("done.")


if __name__ == "__main__":
    main()