"""Find which tables in the DBE PDF actually contain school-level data."""

from pathlib import Path

import pdfplumber

PDF_PATH = Path("data/raw/school_performance_2023.pdf")


def describe_table(table: list) -> str:
    """Return a short description of the first two rows of a table."""
    if not table:
        return "<empty>"
    header = [str(c)[:25] if c else "" for c in table[0]]
    first_row = (
        [str(c)[:25] if c else "" for c in table[1]] if len(table) > 1 else []
    )
    return f"HEADER: {header}\n         ROW1:   {first_row}"


def main() -> None:
    with pdfplumber.open(PDF_PATH) as pdf:
        print(f"Total pages: {len(pdf.pages)}")
        for page_num, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()
            for i, table in enumerate(tables):
                if not table or len(table) < 2:
                    continue
                print(f"\n--- page {page_num}, table {i} ({len(table)} rows) ---")
                print(describe_table(table))


if __name__ == "__main__":
    main()