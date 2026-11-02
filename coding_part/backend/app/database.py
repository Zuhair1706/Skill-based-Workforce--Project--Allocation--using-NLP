from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
import csv
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    create_engine,
    inspect,
)
from sqlalchemy.engine import Engine
from sqlalchemy.schema import CreateTable

from app.config import DATABASE_URL, csv_path


metadata = MetaData()
employees = Table(
    "employees",
    metadata,
    Column("employee_id", String(32), primary_key=True),
    Column("employee_name", String(255)),
    Column("age", Integer),
    Column("gender", String(50)),
    Column("location", String(255), index=True),
    Column("department", String(255)),
    Column("job_role", String(255)),
    Column("employment_type", String(100)),
    Column("experience_years", Numeric(5, 1)),
    Column("seniority", String(100), index=True),
    Column("availability_pct", Numeric(5, 2), index=True),
    Column("current_allocation_pct", Numeric(5, 2)),
    Column("performance_score", Numeric(4, 2)),
    Column("monthly_salary_lakh", Numeric(10, 2)),
    Column("willing_to_relocate", Boolean),
)
employee_skills = Table(
    "employee_skills",
    metadata,
    Column("employee_id", String(32), primary_key=True, index=True),
    Column("skill", String(255), primary_key=True, index=True),
    Column("proficiency_1_5", Integer),
    Column("skill_experience_years", Numeric(5, 1)),
)
projects = Table(
    "projects",
    metadata,
    Column("project_id", String(32), primary_key=True),
    Column("project_name", String(255)),
    Column("domain", String(255)),
    Column("location", String(255)),
    Column("nearby_locations", Text),
    Column("start_date", Date),
    Column("duration_months", Integer),
    Column("team_size_required", Integer),
    Column("priority", String(50)),
    Column("budget_lakh", Numeric(12, 2)),
    Column("member_allocation_pct", Numeric(5, 2)),
    Column("max_relocation_pct", Numeric(5, 2)),
    Column("min_lead_count", Integer),
    Column("min_senior_plus_pct", Numeric(5, 2)),
    Column("max_lead_pct", Numeric(5, 2)),
    Column("max_junior_pct", Numeric(5, 2)),
    Column("project_description", Text),
    Column("oov_tech_mentions", Text),
    Column("domain_original", String(255)),
    Column("budget_lakh_original", Numeric(12, 2)),
)
project_requirements = Table(
    "project_requirements",
    metadata,
    Column("project_id", String(32), primary_key=True, index=True),
    Column("required_skill", String(255), primary_key=True),
    Column("importance_1_5", Integer),
    Column("min_proficiency_1_5", Integer),
    Column("min_experience_years", Numeric(5, 1)),
    Column("min_headcount", Integer),
)
skill_aliases = Table(
    "skill_aliases",
    metadata,
    Column("skill", String(255), primary_key=True),
    Column("alias", String(255), primary_key=True),
)
project_skill_annotations = Table(
    "project_skill_annotations",
    metadata,
    Column("annotation_id", Integer, primary_key=True, autoincrement=True),
    Column("project_id", String(32), index=True),
    Column("skill", String(255)),
    Column("surface_form", String(255)),
    Column("form_type", String(100)),
    Column("char_start", Integer),
    Column("char_end", Integer),
)
allocations = Table(
    "allocations",
    metadata,
    Column("allocation_id", String(36), primary_key=True),
    Column("project_id", String(32), index=True),
    Column("employee_id", String(32), primary_key=True, index=True),
    Column("match_score", Float),
    Column("skill_coverage_pct", Float),
    Column("allocation_pct", Float),
    Column("relocation_required", Boolean),
    Column("optimization_status", String(32)),
    Column("created_at", DateTime, index=True),
)

engine: Engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def create_schema() -> None:
    metadata.create_all(engine)
    primary_key = inspect(engine).get_pk_constraint("allocations").get(
        "constrained_columns", []
    )
    if primary_key == ["allocation_id", "employee_id"]:
        return

    if engine.dialect.name == "sqlite":
        migrated_allocations = allocations.to_metadata(
            MetaData(), name="allocations_migration"
        )
        columns = ", ".join(column.name for column in allocations.columns)
        with engine.begin() as connection:
            connection.execute(CreateTable(migrated_allocations))
            connection.exec_driver_sql(
                f"INSERT INTO allocations_migration ({columns}) "
                f"SELECT {columns} FROM allocations"
            )
            connection.exec_driver_sql("DROP TABLE allocations")
            allocations.create(connection)
            connection.exec_driver_sql(
                f"INSERT INTO allocations ({columns}) "
                f"SELECT {columns} FROM allocations_migration"
            )
            connection.exec_driver_sql("DROP TABLE allocations_migration")
        return

    if engine.dialect.name == "mysql":
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "ALTER TABLE allocations DROP PRIMARY KEY, "
                "ADD PRIMARY KEY (allocation_id, employee_id)"
            )
        return

    raise RuntimeError(
        f"Cannot migrate allocations primary key for {engine.dialect.name}."
    )


def _parse_value(value: str | None, column: Column[Any]) -> Any:
    if value is None or value.strip() == "":
        return None
    value = value.strip()
    if isinstance(column.type, Boolean):
        return value.casefold() in {"true", "1", "yes"}
    if isinstance(column.type, Integer):
        return int(value)
    if isinstance(column.type, (Numeric, Float)):
        try:
            return Decimal(value) if isinstance(column.type, Numeric) else float(value)
        except InvalidOperation as exc:
            raise ValueError(f"Invalid numeric value {value!r} for {column.name}") from exc
    if isinstance(column.type, Date):
        return date.fromisoformat(value)
    if isinstance(column.type, DateTime):
        return datetime.fromisoformat(value)
    return value


_SEED_FILES: tuple[tuple[Table, Path], ...] = (
    (employees, csv_path("workforce dataset", "employees_100k.csv")),
    (employee_skills, csv_path("workforce dataset", "employee_skills.csv")),
    (projects, csv_path("projects dataset", "projects_30_v2.csv")),
    (project_requirements, csv_path("projects dataset", "project_requirements_v2.csv")),
    (skill_aliases, csv_path("projects dataset", "skill_aliases.csv")),
    (
        project_skill_annotations,
        csv_path("projects dataset", "project_skill_annotations.csv"),
    ),
)


def seed_database(batch_size: int = 5000) -> dict[str, int]:
    """Load the checked-in CSV datasets into the configured SQL database."""
    create_schema()
    row_counts: dict[str, int] = {}
    with engine.begin() as connection:
        for table, source in _SEED_FILES:
            if not source.is_file():
                raise FileNotFoundError(f"Dataset CSV not found: {source}")
            connection.execute(table.delete())
            count = 0
            with source.open("r", encoding="utf-8-sig", newline="") as csv_file:
                reader = csv.DictReader(csv_file)
                batch: list[dict[str, Any]] = []
                for row in reader:
                    batch.append(
                        {
                            column.name: _parse_value(row.get(column.name), column)
                            for column in table.columns
                            if column.name in row
                        }
                    )
                    if len(batch) >= batch_size:
                        connection.execute(table.insert(), batch)
                        count += len(batch)
                        batch.clear()
                if batch:
                    connection.execute(table.insert(), batch)
                    count += len(batch)
            row_counts[table.name] = count
    return row_counts
