# School Performance Analytics — Project Proposal

**Author:** Boitumelo Matome
**Date started:** September 2026
**Status:** In development

---

## 1. Executive Summary

School Performance Analytics is a data engineering project that ingests
publicly available South African matric performance data published by the
Department of Basic Education (DBE) and turns it into actionable insight
through a REST API and interactive dashboard.

The project demonstrates a complete data pipeline: PDF extraction, data
cleaning, analytical enrichment, storage in a relational database, API
exposure, and visualization. It is built entirely in Python using
industry-standard tools (pandas, SQLAlchemy, FastAPI, Streamlit).

The goal is twofold:
1. Produce a genuinely useful dataset and interface for analysing
   South African school performance over time.
2. Demonstrate the full-stack data engineering skills required for
   junior-to-mid level data engineering and backend roles.

---

## 2. Problem Statement

The DBE publishes annual National Senior Certificate (NSC) School
Performance Reports as PDF documents. These reports contain detailed,
school-level data about how many learners wrote and passed the matric
examinations, broken down by province, district, and school.

**The problem:**
- The data is locked inside PDFs, making it nearly impossible to analyse
  at scale.
- The PDFs use rotated headers, multi-year column groupings, and
  inconsistent layouts across years.
- No free, queryable API exposes this data.
- NGOs, edtech companies, researchers, and journalists who want to
  analyse matric trends must either pay for expensive data services or
  manually re-enter numbers into spreadsheets.

**What this project does:**
- Automatically extracts school-level data from the DBE PDF reports.
- Cleans and normalizes the data into a queryable relational schema.
- Computes derived metrics that reveal trends the raw data hides.
- Exposes the data through a REST API and an interactive dashboard.

---

## 3. Target Audience

| Audience | What they need |
|---|---|
| Education NGOs | Identify districts with declining pass rates to target interventions |
| Edtech companies | Decide which subjects and regions to focus content on |
| Researchers | Query historical trends without manual data entry |
| Journalists | Quickly pull figures for investigative pieces |
| Policy analysts | Compare provinces and quintiles over time |
| Portfolio reviewers (hiring managers) | See evidence of production-quality data engineering |

---

## 4. Scope

### In scope

- Ingestion of DBE National Senior Certificate School Performance Reports
  (PDF format, 2023–2025).
- Extraction of school-level pass data: EMIS number, school name,
  province, district, quintile, and pass counts per year.
- Derived metrics: pass rate, year-over-year improvement, quintile
  performance gaps.
- Storage in a normalized MySQL schema.
- REST API built with FastAPI for programmatic access.
- Interactive Streamlit dashboard for visual exploration.

### Out of scope (for v1)

- Subject-level breakdowns (not available in the source PDFs used).
- Learner-level data (never in scope — POPIA compliance).
- Real-time data (reports are published annually).
- Mobile application.
- User authentication (read-only public data).

---

## 5. Data Governance & Compliance

This project is built with explicit data ethics constraints.

**Data source:** Only aggregated, school-level data from publicly
published DBE reports.

**What we do NOT process:**
- Learner names
- Exam numbers
- Individual learner results
- Any personally identifiable information

**Why this matters:** South Africa's Information Regulator has previously
taken legal action against the DBE over the publication of matric results.
While the courts ruled in favor of the DBE for exam-number-only publication,
this project avoids the entire controversy by design. We use only the
aggregated school-level data that is unambiguously in the public interest.

**POPIA alignment:** By avoiding all personal information, the project
operates outside the scope of POPIA's processing restrictions.

**No scraping:** All data is downloaded manually from the DBE website
and stored locally. No automated scraping of DBE servers is performed.

---

## 6. Technical Architecture

┌─────────────────┐
│ DBE PDFs │ Downloaded manually from education.gov.za
│ (data/raw/) │
└────────┬────────┘
│
▼
┌─────────────────┐
│ Ingestion │ pdfplumber + pandas
│ (scripts/ │ - Extracts tables
│ ingest_pdfs) │ - Fixes rotated headers
│ │ - Filters school-level tables
└────────┬────────┘
│
▼
┌─────────────────┐
│ Raw CSVs │ data/processed/performance_<year>.csv
└────────┬────────┘
│
▼
┌─────────────────┐
│ Transformation │ pandas + SQLAlchemy
│ (scripts/ │ - Normalizes columns
│ transform) │ - Computes derived metrics
│ │ - Loads to MySQL
└────────┬────────┘
│
▼
┌─────────────────┐
│ MySQL │ school_performance database
│ │ - schools (dimension)
│ │ - subject_performance (fact)
└────────┬────────┘
│
├──────────────────┐
▼ ▼
┌─────────────────┐ ┌─────────────────┐
│ FastAPI │ │ Streamlit │
│ app/main.py │ │ dashboard/ │
│ │ │ app.py │
└─────────────────┘ └─────────────────┘


---

## 7. Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| Language | Python 3.12 | Core language |
| PDF extraction | pdfplumber | Table extraction from PDFs |
| Data manipulation | pandas | Cleaning, transformation |
| ORM | SQLAlchemy 2.0 | Database abstraction |
| Database | MySQL 8 | Data storage |
| DB driver | PyMySQL | MySQL connector |
| API framework | FastAPI | REST endpoints |
| API server | Uvicorn | ASGI server |
| Config | pydantic-settings | Environment configuration |
| Dashboard | Streamlit | Interactive UI |
| Charts | Plotly | Visualizations |
| Version control | Git + GitHub | Source control |

---

## 8. Deliverables

By project completion, the following will exist:

1. **Source code** — a public GitHub repository with clean structure,
   README, and setup instructions.
2. **Data pipeline** — reproducible scripts that go from PDF to loaded
   database with a single command each.
3. **REST API** — deployed and accessible, with auto-generated Swagger
   documentation at `/docs`.
4. **Interactive dashboard** — deployed and publicly viewable.
5. **Documentation** — this proposal, a README, and inline comments
   explaining design decisions.
6. **Analysis write-up** — a short narrative (500–1000 words) that
   describes what the data reveals about South African school performance
   and what engineering decisions were made along the way.

---

## 9. Milestones

| # | Milestone | Status |
|---|---|---|
| 1 | Environment setup (Python, venv, dependencies) | ✅ Complete |
| 2 | Project structure and configuration | ✅ Complete |
| 3 | PDF ingestion pipeline | 🔄 In progress |
| 4 | Data transformation and MySQL load | ⏳ Pending |
| 5 | FastAPI endpoints and testing | ⏳ Pending |
| 6 | Streamlit dashboard | ⏳ Pending |
| 7 | Deployment (API + dashboard) | ⏳ Pending |
| 8 | README and analysis write-up | ⏳ Pending |

---

## 10. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| DBE PDFs are scanned images, not text | High — breaks entire pipeline | Verified: DBE reports have a text layer. Fallback: OCR via Tesseract. |
| PDF layout changes between years | Medium — breaks column mapping | Column alias dictionary in `transform.py` maps variants to canonical names. |
| Rotated headers produce garbled column names | Medium — data unusable | Header mirror detection and correction implemented. |
| Extraction is slow on 156-page PDFs | Low — annoying, not blocking | Progress prints every 10 pages. Fallback: text-based extraction. |
| MySQL connection issues | Low — blocks loading | Configuration externalized to `.env`; connection testing built in. |
| Source data not actually useful for analysis | Medium — project has no story | Mitigation: analyze what the data supports, not what was hoped for. |

---

## 11. Success Criteria

The project is considered successful if:

1. It ingests at least 3 years of DBE PDF data without manual intervention.
2. It loads a normalized, queryable dataset into MySQL.
3. The API responds to at least 5 documented endpoints.
4. The dashboard displays at least 3 meaningful visualizations.
5. Both API and dashboard are publicly accessible via a URL.
6. The GitHub README enables a stranger to reproduce the setup in
   under 10 minutes.
7. A hiring manager reviewing the repo can identify at least 3
   non-trivial engineering decisions documented in the code or README.

---

## 12. What This Project Demonstrates

For portfolio purposes, this project provides evidence of:

- **Data ingestion from messy sources:** Parsing real-world government
  PDFs with layout quirks.
- **Data transformation:** Column normalization, derived metrics,
  handling of inconsistent schemas.
- **Database design:** A normalized schema with primary keys, foreign
  keys, unique constraints, and indexes.
- **API design:** Pagination, query validation, response models,
  auto-documentation.
- **Visualization:** Interactive filtering and drill-down.
- **DevOps basics:** Environment isolation, dependency pinning,
  configuration management, deployment.
- **Data ethics:** Explicit handling of POPIA considerations.

---

## 13. Future Work (post-v1)

Beyond the initial scope, the project could grow to include:

- Subject-level analysis if the DBE publishes subject-specific reports.
- Historical trend modelling (linear regression per district).
- Interactive map of South Africa with drill-down by province.
- Automated scheduled ingestion via GitHub Actions.
- Comparison of DBE data against WCED or other provincial datasets.
- Natural language querying ("which quintile 1 schools improved most
  in Limpopo from 2023 to 2025?").

---

## Appendix A: Glossary

- **DBE:** Department of Basic Education (South Africa)
- **NSC:** National Senior Certificate (the matric qualification)
- **EMIS:** Education Management Information System — the unique
  identifier for every school in South Africa
- **Quintile:** A poverty ranking from 1 (poorest) to 5 (wealthiest)
  assigned to every public school
- **POPIA:** Protection of Personal Information Act (South Africa's
  data protection law)
- **Pass rate:** The percentage of learners who wrote an exam and
  achieved a passing grade
- **Depth ratio:** A derived metric measuring the ratio of high
  achievers to minimum-threshold passers

---

*This document is a living proposal. It will be updated as the project
progresses and as the data reveals what is actually possible.*
