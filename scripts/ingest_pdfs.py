"""
Ingestion script: extract school performance tables from DBE PDF reports.

The DBE publishes one PDF per year. Each PDF contains school-level tables
showing matric pass counts across multiple years.

This script:
1. Opens each PDF in data/raw/
2. Extracts tables via pdfplumber
3. Fixes rotated (mirrored) headers that DBE uses
4. Tracks the current province as we page through the document
5. Keeps only school-level tables (skips summaries and index pages)
6. Writes raw tables to data/processed/performance_<year>.csv

It does NOT clean the data. That is scripts/transform.py's job.

Run from the project root:  python -m scripts.ingest_pdfs
"""

import re
from pathlib import Path

import pandas as pd
import pdfplumber

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"

MIN_SCHOOL_PAGE = 11

PROVINCES = [
    "Eastern Cape", "Free State", "Gauteng", "KwaZulu-Natal", "Limpopo",
    "Mpumalanga", "North West", "Northern Cape", "Western Cape",
]
PROVINCE_KEYS = [p.lower().replace(" ", "") for p in PROVINCES]


def extract_year_from_filename(path: Path) -> int | None:
    match = re.search(r"(\d{4})", path.stem)
    return int(match.group(1)) if match else None


def detect_province(text: str) -> str | None:
    """Look for a province name in the page text (handles mirrored spelling)."""
    if not text:
        return None
    flat = text.lower().replace(" ", "").replace("\n", "")
    for name, key in zip(PROVINCES, PROVINCE_KEYS):
        if key in flat or key[::-1] in flat:
            return name
    return None


def _looks_mirrored(text: str) -> bool:
    clean = text.replace(" ", "")
    if not clean:
        return False
    if clean[0].islower() and clean[-1].isupper():
        return True
    words = text.split()
    if not words:
        return False
    mirrored_words = sum(1 for w in words if w and w[0].islower() and w[-1].isupper())
    return mirrored_words >= len(words) / 2


def fix_mirrored_header(cell) -> str:
    if cell is None:
        return ""
    text = str(cell).strip()
    if not text:
        return ""
    text = " ".join(text.split())
    if _looks_mirrored(text):
        text = text[::-1]
    return text


def _dedupe_columns(columns: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    result: list[str] = []
    for i, col in enumerate(columns, start=1):
        name = col if col else f"col_{i}"
        if name in seen:
            seen[name] += 1
            result.append(f"{name}_{seen[name]}")
        else:
            seen[name] = 1
            result.append(name)
    return result


def extract_tables(pdf_path: Path) -> list[pd.DataFrame]:
    frames: list[pd.DataFrame] = []
    skipped_tables = 0
    current_province: str | None = None

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        print(f"    Total pages: {total_pages}")

        for page_num, page in enumerate(pdf.pages, start=1):
            if page_num < MIN_SCHOOL_PAGE:
                continue
            if page_num % 20 == 0:
                print(f"    ... page {page_num}/{total_pages}")

            page_text = page.extract_text() or ""
            found_province = detect_province(page_text)
            if found_province:
                current_province = found_province

            tables = page.extract_tables()
            for table_index, table in enumerate(tables):
                if not table or len(table) < 5:
                    continue

                header_row_idx = 0
                if len(table) >= 2:
                    non_empty_row0 = sum(1 for c in table[0] if c and str(c).strip())
                    if non_empty_row0 < 3:
                        header_row_idx = 1

                header = table[header_row_idx]
                rows = table[header_row_idx + 1 :]

                non_empty = [c for c in header if c and str(c).strip()]
                if len(non_empty) < 3:
                    continue

                header = [fix_mirrored_header(c) for c in header]
                header = _dedupe_columns(header)

                if not any("emis" in h.lower() for h in header):
                    skipped_tables += 1
                    continue

                normalized_rows = []
                for row in rows:
                    if len(row) < len(header):
                        row = list(row) + [None] * (len(header) - len(row))
                    elif len(row) > len(header):
                        row = list(row)[: len(header)]
                    normalized_rows.append(row)

                df = pd.DataFrame(normalized_rows, columns=header)
                df["_source_page"] = page_num
                df["_source_table"] = table_index
                df["_province_guess"] = current_province
                frames.append(df)

    print(f"    Skipped {skipped_tables} non-school tables")
    return frames


def process_pdf(pdf_path: Path) -> Path | None:
    year = extract_year_from_filename(pdf_path)
    if year is None:
        print(f"  [skip] Could not extract year from {pdf_path.name}")
        return None

    print(f"  Processing {pdf_path.name} (year={year}) ...")
    frames = extract_tables(pdf_path)

    if not frames:
        print(f"  [warn] No tables extracted from {pdf_path.name}")
        return None

    combined = pd.concat(frames, ignore_index=True)
    combined["exam_year"] = year

    output_path = PROCESSED_DIR / f"performance_{year}.csv"
    combined.to_csv(output_path, index=False, encoding="utf-8")
    print(f"  [ok] {len(combined)} rows -> {output_path}")
    return output_path


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(RAW_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {RAW_DIR}. Download DBE reports and try again.")
        return
    print(f"Found {len(pdfs)} PDF(s) in {RAW_DIR}")
    for pdf_path in pdfs:
        process_pdf(pdf_path)


if __name__ == "__main__":
    main()