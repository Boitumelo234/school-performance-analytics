"""
SQLAlchemy ORM models for the school performance analytics database.

Tables:
  provinces           - 9 SA provinces
  districts           - DBE districts, FK to provinces
  schools             - one row per school (EMIS is the natural key)
  school_performance  - facts: one row per school per exam year

Design notes:
- EMIS number is the natural key for schools. It is stable across years.
- The fact table keeps `emis_number` denormalised for fast filtering, AND
  a `school_id` FK for joins.
- `source_year` records which DBE report the row came from (e.g. the 2025
  report covers exam years 2023, 2024, 2025). When two reports overlap, the
  newest report's numbers win, and source_year records that.
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Province(Base):
    """One of the 9 South African provinces."""

    __tablename__ = "provinces"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True, index=True)

    districts = relationship("District", back_populates="province")

    def __repr__(self) -> str:
        return f"<Province {self.name}>"


class District(Base):
    """A DBE district, belonging to one province."""

    __tablename__ = "districts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(150), nullable=False, index=True)
    province_id = Column(Integer, ForeignKey("provinces.id"), nullable=True, index=True)

    province = relationship("Province", back_populates="districts")
    schools = relationship("School", back_populates="district")

    __table_args__ = (
        UniqueConstraint("name", "province_id", name="uq_district_province"),
    )

    def __repr__(self) -> str:
        return f"<District {self.name}>"


class School(Base):
    """A school. EMIS number is the natural key."""

    __tablename__ = "schools"

    id = Column(Integer, primary_key=True, autoincrement=True)
    emis_number = Column(String(20), nullable=False, unique=True, index=True)
    centre_no = Column(String(20), nullable=True)
    centre_name = Column(String(255), nullable=False, index=True)

    district_id = Column(Integer, ForeignKey("districts.id"), nullable=True, index=True)
    quintile = Column(Integer, nullable=True, index=True)

    district = relationship("District", back_populates="schools")
    performances = relationship("SchoolPerformance", back_populates="school")

    def __repr__(self) -> str:
        return f"<School {self.emis_number} {self.centre_name}>"


class SchoolPerformance(Base):
    """One row per school per exam year."""

    __tablename__ = "school_performance"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Denormalised identifiers (kept for speed and backwards compatibility)
    emis_number = Column(String(20), nullable=False, index=True)
    centre_no = Column(String(20), nullable=True)
    centre_name = Column(String(255), nullable=False, index=True)
    district_name = Column(String(150), nullable=True, index=True)
    province_name = Column(String(100), nullable=True, index=True)
    quintile = Column(Integer, nullable=True, index=True)

    # FK to the normalised school
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)

    exam_year = Column(Integer, nullable=False, index=True)
    source_year = Column(Integer, nullable=True, index=True)

    wrote = Column(Integer, nullable=False, default=0)
    achieved = Column(Integer, nullable=False, default=0)
    pass_rate = Column(Float, nullable=True)

    school = relationship("School", back_populates="performances")

    __table_args__ = (
        UniqueConstraint("emis_number", "exam_year", name="uq_school_year"),
        Index("idx_year_district", "exam_year", "district_name"),
        Index("idx_year_quintile", "exam_year", "quintile"),
        Index("idx_year_province", "exam_year", "province_name"),
    )

    def __repr__(self) -> str:
        return (
            f"<SchoolPerformance {self.emis_number} {self.exam_year} "
            f"{self.pass_rate}%>"
        )