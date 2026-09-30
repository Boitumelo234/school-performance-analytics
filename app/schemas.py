"""Pydantic response schemas for the API. Keeps /docs clean and typed."""

from typing import Optional
from pydantic import BaseModel, Field


class MetaOut(BaseModel):
    years: list[int]
    districts: list[str]
    provinces: list[str]
    quintiles: list[int] = [1, 2, 3, 4, 5]


class TrendPoint(BaseModel):
    exam_year: int
    avg_pass_rate: float
    weighted_pass_rate: float
    total_wrote: int
    total_achieved: int
    school_count: int


class QuintileGap(BaseModel):
    quintile: int
    avg_pass_rate: float
    weighted_pass_rate: float
    school_count: int
    total_wrote: int


class DistrictRow(BaseModel):
    exam_year: int
    district_name: str
    province_name: Optional[str] = None
    avg_pass_rate: float
    weighted_pass_rate: float
    school_count: int
    total_wrote: int


class ProvinceRow(BaseModel):
    exam_year: int
    province_name: str
    avg_pass_rate: float
    weighted_pass_rate: float
    school_count: int
    total_wrote: int


class ImprovingSchool(BaseModel):
    emis_number: str
    centre_name: str
    district_name: Optional[str] = None
    quintile: Optional[int] = None
    first_year: int
    first_pass_rate: float
    last_year: int
    last_pass_rate: float
    improvement: float


class SchoolSummary(BaseModel):
    emis_number: str
    centre_name: str
    district_name: Optional[str] = None
    quintile: Optional[int] = None
    exam_year: int
    wrote: int
    achieved: int
    pass_rate: Optional[float] = None


class SchoolHistoryPoint(BaseModel):
    exam_year: int
    wrote: int
    achieved: int
    pass_rate: Optional[float] = None


class SchoolDetail(BaseModel):
    emis_number: str
    centre_name: str
    district_name: Optional[str] = None
    province_name: Optional[str] = None
    quintile: Optional[int] = None
    history: list[SchoolHistoryPoint]


class PaginatedSchools(BaseModel):
    total: int
    page: int
    page_size: int
    results: list[SchoolSummary]


class RootOut(BaseModel):
    service: str
    version: str
    status: str
    docs: str


class HealthOut(BaseModel):
    status: str
    database: str