# School Performance Analytics (South Africa)

> A data pipeline, analytics API, and dashboard for DBE school-level matric performance data.

**Status:** 🚧 In development

---

## The Problem

South Africa's national matric pass rate tells one story. The school-level data tells another.

A high pass rate doesn't mean a school is preparing learners for STEM study. What matters is **participation** (how many learners write gateway subjects like Mathematics and Physical Sciences) combined with **depth** (how many reach the 60%+ threshold that universities actually require for STEM programmes).

This project ingests the DBE's National Senior Certificate School Performance Reports, builds a normalized analytics layer, and surfaces the structural bottlenecks that raw pass rates hide.

**Core questions this project answers:**
- Which districts have the biggest gap between Maths participation and STEM-ready achievement?
- Which schools improved most in pushing learners beyond the minimum 30% threshold?
- Where is the Maths vs. Maths Literacy split creating the biggest pipeline loss?

---

## Data Governance & Compliance

This project uses **only aggregated, publicly available school-level data** from the Department of Basic Education's National Senior Certificate (NSC) School Performance Reports.

- No learner-level data is ingested, processed, or stored.
- No personally identifiable information is handled.
- No scraping of live job boards, exam portals, or third-party sites.

This aligns with POPIA principles by avoiding the processing of personal information entirely. The DBE's own published reports are the sole data source.

---

## Architecture

```
DBE PDFs
   │
   ▼
pdfplumber ingestion  →  data/processed/*.csv
   │
   ▼
Transformation layer  →  PostgreSQL
   │
   ▼
FastAPI               →  REST API
   │
   ▼
Streamlit + Plotly    →  Dashboard
```

---

## Stack

- **Python 3.12**
- **Ingestion:** pdfplumber, pandas
- **Storage:** PostgreSQL, SQLAlchemy
- **API:** FastAPI, pydantic, uvicorn
- **Dashboard:** Streamlit, Plotly
- **Orchestration:** (planned) GitHub Actions for scheduled ingestion

---

## Data Sources

Download the DBE School Performance Reports (PDF format) from the Department of Basic Education website and place them in `data/raw/`:

```
data/raw/
├── school_performance_2023.pdf
├── school_performance_2024.pdf
└── school_performance_2025.pdf
```

These files are **not committed** to this repository (see `.gitignore`). You must download them separately to run the pipeline.

---

## Running Locally

### Prerequisites
- Python 3.12
- PostgreSQL (local or hosted)
- Git

### Setup

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/school-performance-analytics.git
cd school-performance-analytics

# Create and activate virtual environment
python3.12 -m venv .venv
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Download DBE PDFs into data/raw/ (see Data Sources section)
```

### Run the pipeline (coming soon)

```bash
python scripts/ingest_pdfs.py
python scripts/transform.py
```

### Run the API (coming soon)

```bash
uvicorn app.main:app --reload
```

Open http://localhost:8000/docs for the auto-generated API documentation.

### Run the dashboard (coming soon)

```bash
streamlit run dashboard/app.py
```

---

## What I Learned

*(This section is updated as the project progresses. It documents the hardest parts, the pivots, and the mistakes — not just the successes.)*

- Setting up Python 3.12 alongside 3.14 on Windows required using the Python Install Manager (`py install 3.12`).
- The default pip SSL layer was crashing with an access violation on Windows; workaround was `--trusted-host pypi.org --trusted-host files.pythonhosted.org`.
- *(More to come.)*

---

## License

MIT

- DBE PDFs use rotated (mirrored) column headers — the text reads right-to-left,
  so `District Name` appears as `emaN tcirtsiD`. Fixed with a heuristic that
  detects lowercase-starting, uppercase-ending strings and reverses them.
- DBE layout puts the province name in row 0 and the real column headers in
  row 1. pdfplumber's `extract_tables()` defaults to using row 0 as the header,
  which returns single-column garbage. Fixed by detecting rows with fewer than
  3 non-empty cells and using the next row as the header instead.
- PowerShell buffers Python's stdout in ways that can make a running script
  look frozen. Fixed by running with `python -u` (unbuffered).
