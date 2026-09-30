"""
Transform raw extracted CSVs into a clean long-format table and load into MySQL.

Run from the project root:  python -m scripts.transform
"""

import re
from pathlib import Path

import pandas as pd
from sqlalchemy.dialects.mysql import insert as mysql_insert

from app.database import Base, SessionLocal, engine
from app.models import SchoolPerformance, School, District, Province

ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = ROOT / "data" / "processed"
BATCH_SIZE = 1000

ID_ALIASES = {
    "emis no": "emis_number", "emis number": "emis_number", "emis": "emis_number",
    "centre no": "centre_no", "centre number": "centre_no",
    "centre name": "centre_name", "school name": "centre_name",
    "quintile": "quintile",
    "district name": "district_name", "district": "district_name",
}
ID_COLS = ["emis_number", "centre_no", "centre_name", "district_name", "quintile"]
REQUIRED = ["emis_number", "centre_name", "district_name", "quintile"]


# ------------------------------------------------------ district → province
# Word-set lookup. Order doesn't matter: "Baard Frances" matches "Frances Baard".
PROVINCE_KEYWORDS = {
    "Eastern Cape": [
        "alfred nzo", "amathole", "buffalo city", "chris hani", "joe gqabi",
        "nelson mandela", "or tambo", "sarah baartman",
    ],
    "Free State": [
        "fezile dabi", "lejweleputswa", "mangaung", "thabo mofutsanyana", "xhariep",
    ],
    "Gauteng": [
        "ekurhuleni", "gauteng east", "gauteng north", "gauteng west",
        "johannesburg", "sedibeng", "tshwane",
    ],
    "KwaZulu-Natal": [
        "amajuba", "harry gwala", "ilembe", "king cetshwayo", "pinetown",
        "ugu", "umgungundlovu", "umkhanyakude", "umlazi", "umzinyathi",
        "uthukela", "zululand",
    ],
    "Limpopo": [
        "capricorn", "mopani", "sekhukhune", "vhembe", "waterberg",
        "mogalakwena",
    ],
    "Mpumalanga": [
        "bohlabela", "ehlanzeni", "gert sibande", "nkangala",
    ],
    "North West": [
        "bojanala", "kenneth kaunda", "ruth segomotsi mompati",
        "ngaka modiri molema", "mompati", "kaunda", "molema", "bojana",
    ],
    "Northern Cape": [
        "frances baard", "john taolo gaetsewe", "namakwa",
        "pixley ka seme", "zf mgcawu", "xhariep",
    ],
    "Western Cape": [
        "cape winelands", "central karoo", "eden", "garden route",
        "metro central", "metro east", "metro north", "metro south",
        "overberg", "west coast",
    ],
}

# Explicit aliases for garbled or word-swapped names captured from bad scrapes.
# Key = the exact string as it appears in the CSV, value = the province.
DISTRICT_ALIASES = {
    "Awstupelewjel": "North West",     # "Ruth Segomotsi Mompati" reversed badly
    "Oehtom": "North West",            # garbage
    "Peirahx": "Free State",           # "Xhariep" garbled
    "Awkaman": "Western Cape",         # garbage
    "Auqaman": "Western Cape",         # garbage
    "Vhe": "Limpopo",                  # "Vhembe" truncated
    "Mbe East": "Limpopo",             # "Vhembe East" truncated
    "Metro Eas": "Western Cape",       # "Metro East" truncated
    "Johannesbu": "Gauteng",           # "Johannesburg" truncated
    "Rg Central": "Gauteng",           # "Johannesburg Central" truncated
    "T": "Gauteng",                    # "Tshwane" truncated
    "Joe G": "Eastern Cape",           # "Joe Gqabi" truncated
    "Urhuleni South": "Gauteng",       # "Ekurhuleni South" typo
    "Mogalakwena": "Limpopo",          # Waterberg-area district
    "Metro Central": "Western Cape",
    "Metro East": "Western Cape",
    "Metro North": "Western Cape",
    "Metro South": "Western Cape",
    "Dr. R.S. Mompati": "North West",
    "Ngaka M. Molema": "North West",
    "Ngaka M. Molema District": "North West",
    "Dr. K. Kaunda": "North West",
}


def _words(text: str) -> frozenset:
    if not text:
        return frozenset()
    tokens = re.findall(r"[a-z]+", text.lower())
    noise = {"district", "metro", "metropolitan", "city", "central",
             "east", "west", "north", "south", "of", "the", "and", "or"}
    return frozenset(t for t in tokens if t not in noise and len(t) > 2)


def province_from_district(district_name: str | None) -> str | None:
    if not district_name:
        return None

    # explicit alias first
    if district_name.strip() in DISTRICT_ALIASES:
        return DISTRICT_ALIASES[district_name.strip()]

    # word-set fuzzy match
    words = _words(district_name)
    if not words:
        return None
    best_province = None
    best_score = 0
    for province, keywords in PROVINCE_KEYWORDS.items():
        for kw in keywords:
            kw_words = _words(kw)
            if not kw_words:
                continue
            overlap = len(words & kw_words)
            if overlap >= 1 and overlap >= len(kw_words):
                score = overlap / len(kw_words)
                if score > best_score:
                    best_score = score
                    best_province = province
    return best_province


def normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename = {}
    for col in df.columns:
        key = " ".join(str(col).lower().split())
        if key in ID_ALIASES:
            rename[col] = ID_ALIASES[key]
    df = df.rename(columns=rename)
    if df.columns.duplicated().any():
        df = df.loc[:, ~df.columns.duplicated()].copy()
    return df


def fix_district_name(value):
    if not isinstance(value, str) or not value.strip():
        return None
    text = " ".join(value.split())
    if "\n" in value or text.isupper():
        text = text[::-1]
    return text.title()


def to_number(series: pd.Series) -> pd.Series:
    cleaned = (
        series.astype(str)
        .str.replace("\u00a0", "", regex=False)
        .str.replace(" ", "", regex=False)
        .str.replace("%", "", regex=False)
        .str.replace(",", ".", regex=False)
    )
    return pd.to_numeric(cleaned, errors="coerce")


def find_year_blocks(columns: list) -> dict[int, list]:
    blocks = {}
    for i, col in enumerate(columns):
        if re.fullmatch(r"(19|20)\d{2}", str(col).strip()) and i + 3 < len(columns):
            blocks[int(str(col).strip())] = list(columns[i : i + 4])
    return blocks


def process_file(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, low_memory=False)
    df = normalise_columns(df)

    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        print(f"  [skip] {path.name}: missing columns {missing}")
        return pd.DataFrame()

    if "centre_no" not in df.columns:
        df["centre_no"] = None

    df["emis_number"] = df["emis_number"].astype(str).str.replace(r"\s", "", regex=True)
    df = df[df["emis_number"].str.fullmatch(r"\d+", na=False)].copy()
    df["district_name"] = df["district_name"].ffill().apply(fix_district_name)

    df["province_name"] = df["district_name"].apply(province_from_district)

    blocks = find_year_blocks(list(df.columns))
    if not blocks:
        print(f"  [skip] {path.name}: no year columns found")
        return pd.DataFrame()

    source_year = pd.to_numeric(df.get("exam_year"), errors="coerce").max()

    frames = []
    for year, (_, wrote_c, achieved_c, pct_c) in blocks.items():
        block = df[ID_COLS + ["province_name"]].copy()
        block["exam_year"] = year
        block["source_year"] = int(source_year) if pd.notna(source_year) else None
        block["wrote"] = to_number(df[wrote_c])
        block["achieved"] = to_number(df[achieved_c])
        block["pass_rate"] = to_number(df[pct_c])
        frames.append(block)

    out = pd.concat(frames, ignore_index=True)
    out = out[out["wrote"].notna() & (out["wrote"] > 0)]
    print(f"  {path.name}: years {sorted(blocks)} -> {len(out)} school-year rows")
    return out


def finalise(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["achieved"] = df["achieved"].fillna(0)
    computed = df["achieved"] / df["wrote"] * 100

    bad = df["pass_rate"].isna() | ~df["pass_rate"].between(0, 100)
    df.loc[bad, "pass_rate"] = computed[bad]
    df["pass_rate"] = df["pass_rate"].round(2)

    df["wrote"] = df["wrote"].astype(int)
    df["achieved"] = df["achieved"].astype(int)
    df["exam_year"] = df["exam_year"].astype(int)
    df["source_year"] = pd.to_numeric(df["source_year"], errors="coerce")

    df["quintile"] = pd.to_numeric(df["quintile"], errors="coerce")
    df.loc[~df["quintile"].between(1, 5), "quintile"] = None

    df["centre_name"] = df["centre_name"].str.replace(r"\s+", " ", regex=True).str.strip()
    df["centre_no"] = (
        df["centre_no"].astype("string").str.strip()
        .str.replace(r"\.0$", "", regex=True)
    )
    df = df.dropna(subset=["emis_number", "centre_name", "exam_year"])

    unmatched = (
        df.loc[df["province_name"].isna(), "district_name"].dropna().value_counts()
    )
    if len(unmatched):
        print(f"  [warn] {len(unmatched)} unmatched districts:")
        for name, count in unmatched.head(30).items():
            print(f"           {name!r}  ({count} rows)")
    return df


def upsert_provinces(db, names):
    names = sorted({n for n in names if n})
    existing = {p.name: p.id for p in db.query(Province).all()}
    to_add = [Province(name=n) for n in names if n not in existing]
    if to_add:
        db.add_all(to_add)
        db.flush()
    return {p.name: p.id for p in db.query(Province).all()}


def upsert_districts(db, pairs):
    existing = {(d.name, d.province_id): d.id for d in db.query(District).all()}
    provinces = {p.name: p.id for p in db.query(Province).all()}
    to_add = []
    for name, prov in sorted(set(pairs)):
        if not name:
            continue
        prov_id = provinces.get(prov) if prov else None
        if (name, prov_id) not in existing:
            to_add.append(District(name=name, province_id=prov_id))
    if to_add:
        db.add_all(to_add)
        db.flush()
    return {(d.name, d.province_id): d.id for d in db.query(District).all()}


def upsert_schools(db, schools: pd.DataFrame):
    existing = {s.emis_number: s.id for s in db.query(School).all()}
    provinces = {p.name: p.id for p in db.query(Province).all()}
    districts = {(d.name, d.province_id): d.id for d in db.query(District).all()}

    latest = (
        schools.sort_values("exam_year").drop_duplicates("emis_number", keep="last")
    )

    to_add = []
    for _, row in latest.iterrows():
        if row["emis_number"] in existing:
            continue
        prov_id = provinces.get(row.get("province_name")) if row.get("province_name") else None
        dist_id = districts.get((row.get("district_name"), prov_id))
        to_add.append(School(
            emis_number=row["emis_number"],
            centre_no=row.get("centre_no"),
            centre_name=row["centre_name"],
            district_id=dist_id,
            quintile=int(row["quintile"]) if pd.notna(row.get("quintile")) else None,
        ))
    if to_add:
        db.add_all(to_add)
        db.flush()

    result = {s.emis_number: s.id for s in db.query(School).all()}
    for _, row in latest.iterrows():
        sid = result.get(row["emis_number"])
        if sid is None:
            continue
        prov_id = provinces.get(row.get("province_name")) if row.get("province_name") else None
        dist_id = districts.get((row.get("district_name"), prov_id))
        db.query(School).filter(School.id == sid).update({
            "centre_name": row["centre_name"],
            "centre_no": row.get("centre_no"),
            "district_id": dist_id,
            "quintile": int(row["quintile"]) if pd.notna(row.get("quintile")) else None,
        })
    db.flush()
    return result


def to_records(df, school_ids):
    cols = ID_COLS + ["province_name", "exam_year", "source_year",
                      "wrote", "achieved", "pass_rate"]
    obj = df[cols].astype(object).copy()
    obj["school_id"] = obj["emis_number"].map(school_ids)
    obj = obj.where(pd.notna(obj), None)
    return obj.to_dict(orient="records")


def upsert_performance(records, db):
    for start in range(0, len(records), BATCH_SIZE):
        chunk = records[start : start + BATCH_SIZE]
        stmt = mysql_insert(SchoolPerformance).values(chunk)
        stmt = stmt.on_duplicate_key_update(
            centre_no=stmt.inserted.centre_no,
            centre_name=stmt.inserted.centre_name,
            district_name=stmt.inserted.district_name,
            province_name=stmt.inserted.province_name,
            quintile=stmt.inserted.quintile,
            school_id=stmt.inserted.school_id,
            source_year=stmt.inserted.source_year,
            wrote=stmt.inserted.wrote,
            achieved=stmt.inserted.achieved,
            pass_rate=stmt.inserted.pass_rate,
        )
        db.execute(stmt)
    db.commit()
    return len(records)


def main() -> None:
    files = sorted(PROCESSED_DIR.glob("performance_*.csv"))
    if not files:
        print(f"No CSVs in {PROCESSED_DIR}.")
        return

    print(f"Found {len(files)} CSV file(s)")
    frames = []
    for p in files:
        out = process_file(p)
        if not out.empty:
            frames.append(out)

    if not frames:
        print("No usable data. Aborting.")
        return

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.sort_values("source_year", kind="stable")
    combined = combined.drop_duplicates(["emis_number", "exam_year"], keep="last")

    df = finalise(combined)
    print(f"Final rows to load: {len(df)}")
    print(f"Exam years: {sorted(int(y) for y in df['exam_year'].unique())}")
    print(f"Source reports: {sorted(int(s) for s in df['source_year'].dropna().unique())}")
    print(f"Provinces: {sorted(df['province_name'].dropna().unique())}")
    print(f"Districts: {df['district_name'].nunique()}")

    print("Ensuring tables exist...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        upsert_provinces(db, df["province_name"].dropna().unique().tolist())
        pairs = list(zip(df["district_name"], df["province_name"]))
        upsert_districts(db, pairs)
        school_ids = upsert_schools(db, df)
        db.commit()
        print(f"  provinces={db.query(Province).count()} "
              f"districts={db.query(District).count()} "
              f"schools={db.query(School).count()}")

        print(f"Loaded {upsert_performance(to_records(df, school_ids), db)} rows into MySQL.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()