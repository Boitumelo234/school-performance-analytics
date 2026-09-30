"""FastAPI entry point for the school performance analytics API."""

import csv
import io
import time
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.database import get_db, settings
from app.models import SchoolPerformance as SP
from app import schemas

app = FastAPI(
    title=settings.app_name,
    version=settings.api_version,
    description=(
        "Analytics API for DBE school-level matric performance data: "
        "pass-rate trends across schools, districts, provinces and poverty quintiles."
    ),
)


@app.middleware("http")
async def log_slow_requests(request: Request, call_next):
    """Adds an X-Process-Time-ms header and prints any request slower than 1 second."""
    start = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - start) * 1000
    response.headers["X-Process-Time-ms"] = f"{ms:.0f}"
    if ms > 1000:
        print(f"[slow] {request.url.path}?{request.url.query} took {ms:.0f} ms")
    return response


def weighted_rate():
    """Learner-weighted pass rate: total achieved / total wrote."""
    return 100.0 * func.sum(SP.achieved) / func.nullif(func.sum(SP.wrote), 0)


def r2(value) -> float:
    return round(float(value or 0), 2)


# ------------------------------------------------------------------- meta
@app.get("/", tags=["meta"], response_model=schemas.RootOut)
def root():
    return {
        "service": settings.app_name,
        "version": settings.api_version,
        "status": "ok",
        "docs": "/docs",
    }


@app.get("/health", tags=["meta"], response_model=schemas.HealthOut)
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"status": "ok", "database": "connected"}


@app.get("/api/v1/meta", tags=["meta"], response_model=schemas.MetaOut)
def get_meta(db: Session = Depends(get_db)):
    """Available years, districts, provinces and quintiles (used by dashboard filters)."""
    years = [y for (y,) in db.query(SP.exam_year).distinct().order_by(SP.exam_year)]
    districts = [
        d for (d,) in db.query(SP.district_name)
        .filter(SP.district_name.isnot(None)).distinct().order_by(SP.district_name)
    ]
    provinces = [
        p for (p,) in db.query(SP.province_name)
        .filter(SP.province_name.isnot(None)).distinct().order_by(SP.province_name)
    ]
    return {
        "years": years,
        "districts": districts,
        "provinces": provinces,
        "quintiles": [1, 2, 3, 4, 5],
    }


@app.get("/api/v1/data-coverage", tags=["meta"])
def data_coverage(db: Session = Depends(get_db)):
    """What years, reports and rows are actually in the database."""
    years = [y for (y,) in db.query(SP.exam_year).distinct().order_by(SP.exam_year)]
    sources = [
        int(s) for (s,) in db.query(SP.source_year)
        .filter(SP.source_year.isnot(None)).distinct().order_by(SP.source_year)
    ]
    total_rows = db.query(func.count(SP.id)).scalar() or 0
    total_schools = db.query(func.count(func.distinct(SP.emis_number))).scalar() or 0
    per_year = [
        {"exam_year": int(y), "rows": int(n)}
        for (y, n) in db.query(SP.exam_year, func.count(SP.id))
        .group_by(SP.exam_year).order_by(SP.exam_year)
    ]
    return {
        "exam_years": years,
        "source_reports": sources,
        "total_rows": int(total_rows),
        "total_schools": int(total_schools),
        "rows_per_year": per_year,
    }


# ---------------------------------------------------------------- schools
@app.get("/api/v1/schools", tags=["schools"], response_model=schemas.PaginatedSchools)
def list_schools(
    search: Optional[str] = Query(None, description="Part of the school name"),
    district: Optional[str] = Query(None, description="Exact district name"),
    province: Optional[str] = Query(None, description="Exact province name"),
    quintile: Optional[int] = Query(None, ge=1, le=5),
    exam_year: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Paginated list of schools with optional filters."""
    query = db.query(SP)
    if search:
        query = query.filter(SP.centre_name.ilike(f"%{search}%"))
    if district:
        query = query.filter(SP.district_name == district)
    if province:
        query = query.filter(SP.province_name == province)
    if quintile:
        query = query.filter(SP.quintile == quintile)
    if exam_year:
        query = query.filter(SP.exam_year == exam_year)

    total = query.count()
    rows = (
        query.order_by(SP.centre_name, SP.exam_year)
        .offset((page - 1) * page_size).limit(page_size).all()
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "results": [
            {
                "emis_number": r.emis_number,
                "centre_name": r.centre_name,
                "district_name": r.district_name,
                "quintile": r.quintile,
                "exam_year": r.exam_year,
                "wrote": r.wrote,
                "achieved": r.achieved,
                "pass_rate": r.pass_rate,
            }
            for r in rows
        ],
    }


@app.get("/api/v1/schools/{emis_number}", tags=["schools"], response_model=schemas.SchoolDetail)
def get_school(emis_number: str, db: Session = Depends(get_db)):
    """All years of performance data for one school."""
    rows = (
        db.query(SP).filter(SP.emis_number == emis_number)
        .order_by(SP.exam_year).all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"School {emis_number} not found")
    latest = rows[-1]
    return {
        "emis_number": latest.emis_number,
        "centre_name": latest.centre_name,
        "district_name": latest.district_name,
        "province_name": latest.province_name,
        "quintile": latest.quintile,
        "history": [
            {
                "exam_year": r.exam_year,
                "wrote": r.wrote,
                "achieved": r.achieved,
                "pass_rate": r.pass_rate,
            }
            for r in rows
        ],
    }


# -------------------------------------------------------------- analytics
@app.get("/api/v1/analytics/trends", tags=["analytics"], response_model=list[schemas.TrendPoint])
def get_trends(
    district: Optional[str] = Query(None, description="Exact district name"),
    province: Optional[str] = Query(None, description="Exact province name"),
    quintile: Optional[int] = Query(None, ge=1, le=5),
    db: Session = Depends(get_db),
):
    """Pass rate per year (simple average and learner-weighted)."""
    query = db.query(
        SP.exam_year,
        func.avg(SP.pass_rate).label("avg_pass_rate"),
        weighted_rate().label("weighted_pass_rate"),
        func.sum(SP.wrote).label("total_wrote"),
        func.sum(SP.achieved).label("total_achieved"),
        func.count(SP.id).label("school_count"),
    )
    if district:
        query = query.filter(SP.district_name == district)
    if province:
        query = query.filter(SP.province_name == province)
    if quintile:
        query = query.filter(SP.quintile == quintile)

    rows = query.group_by(SP.exam_year).order_by(SP.exam_year).all()
    return [
        {
            "exam_year": r.exam_year,
            "avg_pass_rate": r2(r.avg_pass_rate),
            "weighted_pass_rate": r2(r.weighted_pass_rate),
            "total_wrote": int(r.total_wrote or 0),
            "total_achieved": int(r.total_achieved or 0),
            "school_count": int(r.school_count or 0),
        }
        for r in rows
    ]


@app.get("/api/v1/analytics/quintile-gaps", tags=["analytics"], response_model=list[schemas.QuintileGap])
def get_quintile_gaps(
    exam_year: Optional[int] = Query(None),
    district: Optional[str] = Query(None),
    province: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Pass rate by poverty quintile (1 = poorest)."""
    query = db.query(
        SP.quintile,
        func.avg(SP.pass_rate).label("avg_pass_rate"),
        weighted_rate().label("weighted_pass_rate"),
        func.count(SP.id).label("school_count"),
        func.sum(SP.wrote).label("total_wrote"),
    ).filter(SP.quintile.between(1, 5))
    if exam_year:
        query = query.filter(SP.exam_year == exam_year)
    if district:
        query = query.filter(SP.district_name == district)
    if province:
        query = query.filter(SP.province_name == province)

    rows = query.group_by(SP.quintile).order_by(SP.quintile).all()
    return [
        {
            "quintile": int(r.quintile),
            "avg_pass_rate": r2(r.avg_pass_rate),
            "weighted_pass_rate": r2(r.weighted_pass_rate),
            "school_count": int(r.school_count or 0),
            "total_wrote": int(r.total_wrote or 0),
        }
        for r in rows
    ]


@app.get("/api/v1/analytics/districts", tags=["analytics"], response_model=list[schemas.DistrictRow])
def get_district_ranking(
    exam_year: Optional[int] = Query(None, description="Defaults to the latest year"),
    quintile: Optional[int] = Query(None, ge=1, le=5),
    province: Optional[str] = Query(None, description="Restrict to one province"),
    min_schools: int = Query(3, ge=1),
    db: Session = Depends(get_db),
):
    """Districts ranked by learner-weighted pass rate for one year."""
    year = exam_year or db.query(func.max(SP.exam_year)).scalar()
    if year is None:
        return []
    query = (
        db.query(
            SP.district_name,
            func.max(SP.province_name).label("province_name"),
            func.avg(SP.pass_rate).label("avg_pass_rate"),
            weighted_rate().label("weighted_pass_rate"),
            func.count(SP.id).label("school_count"),
            func.sum(SP.wrote).label("total_wrote"),
        )
        .filter(SP.exam_year == year, SP.district_name.isnot(None))
    )
    if quintile:
        query = query.filter(SP.quintile == quintile)
    if province:
        query = query.filter(SP.province_name == province)
    rows = (
        query.group_by(SP.district_name)
        .having(func.count(SP.id) >= min_schools)
        .order_by(weighted_rate().desc())
        .all()
    )
    return [
        {
            "exam_year": year,
            "district_name": r.district_name,
            "province_name": r.province_name,
            "avg_pass_rate": r2(r.avg_pass_rate),
            "weighted_pass_rate": r2(r.weighted_pass_rate),
            "school_count": int(r.school_count),
            "total_wrote": int(r.total_wrote or 0),
        }
        for r in rows
    ]


@app.get("/api/v1/analytics/provinces", tags=["analytics"], response_model=list[schemas.ProvinceRow])
def get_province_ranking(
    exam_year: Optional[int] = Query(None, description="Defaults to the latest year"),
    quintile: Optional[int] = Query(None, ge=1, le=5),
    db: Session = Depends(get_db),
):
    """Provinces ranked by learner-weighted pass rate for one year."""
    year = exam_year or db.query(func.max(SP.exam_year)).scalar()
    if year is None:
        return []
    query = (
        db.query(
            SP.province_name,
            func.avg(SP.pass_rate).label("avg_pass_rate"),
            weighted_rate().label("weighted_pass_rate"),
            func.count(SP.id).label("school_count"),
            func.sum(SP.wrote).label("total_wrote"),
        )
        .filter(SP.exam_year == year, SP.province_name.isnot(None))
    )
    if quintile:
        query = query.filter(SP.quintile == quintile)
    rows = (
        query.group_by(SP.province_name)
        .order_by(weighted_rate().desc())
        .all()
    )
    return [
        {
            "exam_year": year,
            "province_name": r.province_name,
            "avg_pass_rate": r2(r.avg_pass_rate),
            "weighted_pass_rate": r2(r.weighted_pass_rate),
            "school_count": int(r.school_count),
            "total_wrote": int(r.total_wrote or 0),
        }
        for r in rows
    ]


@app.get("/api/v1/analytics/improving-schools", tags=["analytics"], response_model=list[schemas.ImprovingSchool])
def get_improving_schools(
    min_wrote: int = Query(30, ge=1, description="Minimum learners who wrote, per year"),
    district: Optional[str] = Query(None),
    province: Optional[str] = Query(None),
    quintile: Optional[int] = Query(None, ge=1, le=5),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Schools with the biggest pass-rate gain between their first and last year."""
    extra = ""
    params = {"min_wrote": min_wrote, "limit": limit}
    if district:
        extra += " AND sp.district_name = :district"
        params["district"] = district
    if province:
        extra += " AND sp.province_name = :province"
        params["province"] = province
    if quintile:
        extra += " AND sp.quintile = :quintile"
        params["quintile"] = quintile

    sql = text(f"""
        WITH eligible AS (
            SELECT sp.emis_number,
                   MIN(sp.exam_year) AS first_year,
                   MAX(sp.exam_year) AS last_year
            FROM school_performance sp
            WHERE sp.wrote >= :min_wrote AND sp.pass_rate IS NOT NULL {extra}
            GROUP BY sp.emis_number
            HAVING MIN(sp.exam_year) < MAX(sp.exam_year)
        )
        SELECT l.emis_number, l.centre_name, l.district_name, l.quintile,
               e.first_year, f.pass_rate AS first_pass_rate,
               e.last_year,  l.pass_rate AS last_pass_rate,
               (l.pass_rate - f.pass_rate) AS improvement
        FROM eligible e
        JOIN school_performance f ON f.emis_number = e.emis_number AND f.exam_year = e.first_year
        JOIN school_performance l ON l.emis_number = e.emis_number AND l.exam_year = e.last_year
        ORDER BY improvement DESC
        LIMIT :limit
    """)
    rows = db.execute(sql, params).all()
    return [
        {
            "emis_number": r.emis_number,
            "centre_name": r.centre_name,
            "district_name": r.district_name,
            "quintile": r.quintile,
            "first_year": r.first_year,
            "first_pass_rate": float(r.first_pass_rate),
            "last_year": r.last_year,
            "last_pass_rate": float(r.last_pass_rate),
            "improvement": r2(r.improvement),
        }
        for r in rows
    ]


# ----------------------------------------------------------------- export
@app.get("/api/v1/export/csv", tags=["export"])
def export_csv(
    district: Optional[str] = Query(None),
    province: Optional[str] = Query(None),
    quintile: Optional[int] = Query(None, ge=1, le=5),
    exam_year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Stream a CSV of the raw fact rows matching the given filters."""
    query = db.query(SP)
    if district:
        query = query.filter(SP.district_name == district)
    if province:
        query = query.filter(SP.province_name == province)
    if quintile:
        query = query.filter(SP.quintile == quintile)
    if exam_year:
        query = query.filter(SP.exam_year == exam_year)

    rows = query.order_by(SP.exam_year, SP.centre_name).all()

    def iter_csv():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "emis_number", "centre_no", "centre_name", "district_name",
            "province_name", "quintile", "exam_year", "source_year",
            "wrote", "achieved", "pass_rate",
        ])
        yield buf.getvalue()
        buf.seek(0); buf.truncate(0)
        for r in rows:
            writer.writerow([
                r.emis_number, r.centre_no or "", r.centre_name,
                r.district_name or "", r.province_name or "",
                r.quintile if r.quintile is not None else "",
                r.exam_year, r.source_year if r.source_year is not None else "",
                r.wrote, r.achieved,
                r.pass_rate if r.pass_rate is not None else "",
            ])
            yield buf.getvalue()
            buf.seek(0); buf.truncate(0)

    return StreamingResponse(
        iter_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=school_performance.csv"},
    )