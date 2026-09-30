"""
Quick inspection of the raw extracted CSVs.

Prints shape, columns, first rows, and non-null counts so we can see
what the PDF extraction actually produced.

Usage:
    python scripts/inspect_data.py 2023
    python scripts/inspect_data.py        # inspects all years
"""

import sys
from pathlib import Path

import pandas as pd

PROCESSED_DIR = Path("data/processed")


def inspect(year: int | None = None) -> None:
    files = sorted(PROCESSED_DIR.glob("performance_*.csv"))
    if not files:
        print("No CSVs found in data/processed/")
        return

    for path in files:
        if year is not None and str(year) not in path.name:
            continue

        df = pd.read_csv(path, low_memory=False)

        print("=" * 80)
        print(f"FILE: {path.name}")
        print(f"SHAPE: {df.shape}")
        print(f"COLUMNS ({len(df.columns)}):")
        for col in df.columns:
            print(f"  - {col!r}")

        print()
        print("FIRST 15 ROWS:")
        print(df.head(15).to_string(max_colwidth=30))

        print()
        print("NON-NULL COUNTS PER COLUMN:")
        print(df.notna().sum().to_string())
        print()


if __name__ == "__main__":
    arg = int(sys.argv[1]) if len(sys.argv) > 1 else None
    inspect(arg)