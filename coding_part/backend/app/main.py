from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import bindparam, func, insert, select, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import CORS_ORIGINS, MAX_CANDIDATES
from app.database import (
    allocations,
    create_schema,
    employee_skills,
    employees,
    engine,
    project_requirements,
    projects,
)
from app.nlp import extractor, extract_skills, normalize_skill
from app.optimizer import optimize_team


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_schema()
    yield


app = FastAPI(
    title="Skill-based Workforce Allocation API",
    description="Extract project skills and optimize a team with constraint programming.",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class ExtractionRequest(BaseModel):
    description: str = Field(min_length=1, max_length=20000)


class OptimizeRequest(BaseModel):
    project_id: str = Field(min_length=1, max_length=32)
    description: str | None = Field(default=None, max_length=20000)
    time_limit_seconds: float = Field(default=20.0, ge=1, le=120)


def _json_row(row: Any) -> dict[str, Any]:
    return {key: value.isoformat() if hasattr(value, "isoformat") else value for key, value in dict(row).items()}


@app.get("/api/health")
def health() -> dict[str, Any]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "database": "connected",
            "skill_extractor": extractor.model_status,
            "transformer_error": extractor.model_error,
        }
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}") from exc


@app.get("/api/projects")
def list_projects(
    search: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
) -> list[dict[str, Any]]:
    statement = select(projects).order_by(projects.c.start_date, projects.c.project_id).limit(limit)
    if search:
        statement = statement.where(
            projects.c.project_name.ilike(f"%{search.strip()}%")
            | projects.c.domain.ilike(f"%{search.strip()}%")
        )
    try:
        with engine.connect() as connection:
            return [_json_row(row) for row in connection.execute(statement).mappings()]
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail=f"Could not load projects: {exc}") from exc


@app.get("/api/projects/{project_id}")
def get_project(project_id: str) -> dict[str, Any]:
    with engine.connect() as connection:
        project = connection.execute(
            select(projects).where(projects.c.project_id == project_id)
        ).mappings().first()
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found.")
        requirements = connection.execute(
            select(project_requirements)
            .where(project_requirements.c.project_id == project_id)
            .order_by(project_requirements.c.importance_1_5.desc())
        ).mappings().all()
    return {
        **_json_row(project),
        "requirements": [_json_row(row) for row in requirements],
    }


@app.post("/api/skills/extract")
def skills_from_description(request: ExtractionRequest) -> dict[str, Any]:
    return {
        "model": extractor.model_status,
        "skills": extract_skills(request.description),
    }


def _eligible_candidates(project: dict[str, Any], requirements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    allocation_pct = float(project.get("member_allocation_pct") or 100)
    local_locations = [
        location.strip()
        for location in [project.get("location", ""), *(project.get("nearby_locations") or "").split("|")]
        if location.strip()
    ]
    skills = [str(req["required_skill"]).casefold() for req in requirements]
    base = """
        SELECT e.employee_id
        FROM employees e
        LEFT JOIN employee_skills s
          ON s.employee_id = e.employee_id AND LOWER(s.skill) IN :skills
        WHERE COALESCE(e.availability_pct, 0) >= :allocation
          AND (LOWER(e.location) IN :locations OR e.willing_to_relocate = 1)
        GROUP BY e.employee_id
        ORDER BY SUM(COALESCE(s.proficiency_1_5, 0) * 4
                     + COALESCE(s.skill_experience_years, 0)) DESC,
                 e.performance_score DESC
        LIMIT :candidate_limit
    """
    # Candidate IDs from skill matches are supplemented by seniority/location
    # strata so headcount and relocation constraints are not hidden by ranking.
    with engine.connect() as connection:
        ids = list(
            connection.execute(
                text(base).bindparams(
                    bindparam("skills", expanding=True),
                    bindparam("locations", expanding=True),
                ),
                {
                    "skills": skills or [""],
                    "locations": [location.casefold() for location in local_locations] or [""],
                    "allocation": allocation_pct,
                    "candidate_limit": MAX_CANDIDATES,
                },
            ).scalars()
        )
        for seniority_values in (("Lead",), ("Senior", "Lead", "Principal"), ("Junior",)):
            supplementary = connection.execute(
                select(employees.c.employee_id)
                .where(
                    employees.c.availability_pct >= allocation_pct,
                    func.lower(employees.c.seniority).in_(
                        [value.casefold() for value in seniority_values]
                    ),
                    (
                        func.lower(employees.c.location).in_(
                            [location.casefold() for location in local_locations]
                        )
                        | (employees.c.willing_to_relocate.is_(True))
                    ),
                )
                .order_by(employees.c.performance_score.desc())
                .limit(250)
            ).scalars()
            ids.extend(supplementary)
        unique_ids = list(dict.fromkeys(ids))
        if not unique_ids:
            return []
        profile_rows = connection.execute(
            select(employees).where(employees.c.employee_id.in_(unique_ids))
        ).mappings().all()
        skill_rows = connection.execute(
            select(employee_skills).where(employee_skills.c.employee_id.in_(unique_ids))
        ).mappings().all()

    skill_by_employee: dict[str, list[dict[str, Any]]] = {}
    for row in skill_rows:
        skill_by_employee.setdefault(row["employee_id"], []).append(dict(row))
    local = {location.casefold() for location in local_locations}
    result: list[dict[str, Any]] = []
    for row in profile_rows:
        candidate = dict(row)
        candidate["skills"] = skill_by_employee.get(candidate["employee_id"], [])
        candidate["relocation_required"] = str(candidate.get("location", "")).casefold() not in local
        result.append(candidate)
    return result


@app.post("/api/allocations/optimize")
def optimize_allocation(request: OptimizeRequest) -> dict[str, Any]:
    project_payload = get_project(request.project_id)
    requirements = list(project_payload.pop("requirements"))
    description = request.description or project_payload.get("project_description") or ""
    extracted = extract_skills(description)
    existing = {normalize_skill(req["required_skill"]) for req in requirements}
    for mention in extracted:
        key = normalize_skill(mention["skill"])
        if key and key not in existing:
            requirements.append(
                {
                    "project_id": request.project_id,
                    "required_skill": mention["skill"],
                    "importance_1_5": 1,
                    "min_proficiency_1_5": 1,
                    "min_experience_years": 0,
                    "min_headcount": 0,
                }
            )
            existing.add(key)
    try:
        candidates = _eligible_candidates(project_payload, requirements)
        result = optimize_team(
            project_payload,
            requirements,
            candidates,
            time_limit_seconds=request.time_limit_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail=f"Candidate query failed: {exc}") from exc

    allocation_id = str(uuid4())
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    records = [
        {
            "allocation_id": allocation_id,
            "project_id": request.project_id,
            "employee_id": member["employee_id"],
            "match_score": member["match_score"],
            "skill_coverage_pct": member["skill_coverage_pct"],
            "allocation_pct": float(project_payload.get("member_allocation_pct") or 100),
            "relocation_required": member["relocation_required"],
            "optimization_status": result.status,
            "created_at": now,
        }
        for member in result.selected
    ]
    try:
        with engine.begin() as connection:
            connection.execute(insert(allocations), records)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail=f"Could not save allocation: {exc}") from exc

    team = [
        {
            key: (value.isoformat() if hasattr(value, "isoformat") else value)
            for key, value in member.items()
            if key != "skills"
        }
        for member in result.selected
    ]
    return {
        "allocation_id": allocation_id,
        "project_id": request.project_id,
        "project_name": project_payload.get("project_name"),
        "status": result.status,
        "team": team,
        "summary": {
            "team_size": len(team),
            "total_cost_lakh": result.total_cost_lakh,
            "budget_lakh": float(project_payload.get("budget_lakh") or 0),
            "average_skill_coverage_pct": result.average_skill_coverage_pct,
            "relocated_count": sum(bool(member["relocation_required"]) for member in team),
            "lead_count": sum(str(member.get("seniority", "")).casefold() == "lead" for member in team),
            "senior_plus_count": sum(
                str(member.get("seniority", "")).casefold() in {"senior", "lead", "principal"}
                for member in team
            ),
        },
        "extracted_skills": extracted,
        "skill_extractor": extractor.model_status,
        "candidates_considered": len(candidates),
    }


@app.get("/api/projects/{project_id}/allocations/latest")
def latest_allocation(project_id: str) -> dict[str, Any]:
    with engine.connect() as connection:
        latest_id = connection.execute(
            select(allocations.c.allocation_id)
            .where(allocations.c.project_id == project_id)
            .order_by(allocations.c.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if latest_id is None:
            raise HTTPException(status_code=404, detail="No allocation exists for this project.")
        rows = connection.execute(
            select(allocations, employees)
            .join(employees, employees.c.employee_id == allocations.c.employee_id)
            .where(allocations.c.allocation_id == latest_id)
            .order_by(allocations.c.match_score.desc())
        ).mappings().all()
    return {"allocation_id": latest_id, "team": [_json_row(row) for row in rows]}


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Workforce allocation API", "docs": "/docs"}
