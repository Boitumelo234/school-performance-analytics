"""Raw diagnostic: what does pdfplumber actually see in the DBE PDF?"""

from pathlib import Path
import pdfplumber

PDF = Path("data/raw/school_performance_2023.pdf")


def main() -> None:
    with pdfplumber.open(PDF) as pdf:
        total = len(pdf.pages)
        print(f"Total pages: {total}")
        print()

        # Sample pages across the whole document
        sample_pages = [1, 3, 6, 7, 8, 11, 12, 20, 50, 80, 100, 120, 150]

        for page_num in sample_pages:
            if page_num > total:
                continue

            page = pdf.pages[page_num - 1]

            # How much text is on this page?
            text = page.extract_text() or ""
            tables = page.extract_tables()

            print(f"--- page {page_num} ---")
            print(f"  text length: {len(text)}")
            print(f"  tables found: {len(tables)}")

            if tables:
                first = tables[0]
                print(f"  first table: {len(first)} rows x {len(first[0]) if first else 0} cols")
                if first:
                    # Print first two rows, truncated
                    for i, row in enumerate(first[:2]):
                        cells = [str(c)[:20] if c else "" for c in row[:8]]
                        print(f"    row {i}: {cells}")

            if text:
                # Show first 200 chars of text so we know what kind of page it is
                print(f"  text preview: {text[:200]!r}")

            print()


if __name__ == "__main__":
    main()