from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import math
from typing import Any

from ortools.sat.python import cp_model

from app.nlp import normalize_skill


@dataclass(frozen=True)
class OptimizationResult:
    status: str
    selected: list[dict[str, Any]]
    total_cost_lakh: float
    average_skill_coverage_pct: float
    solver_objective: float


def _number(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    return float(value if isinstance(value, (int, float, Decimal)) else Decimal(str(value)))


def _is_senior(employee: dict[str, Any]) -> bool:
    return str(employee.get("seniority", "")).casefold() in {"senior", "lead", "principal"}


def _is_lead(employee: dict[str, Any]) -> bool:
    return str(employee.get("seniority", "")).casefold() == "lead"


def _is_junior(employee: dict[str, Any]) -> bool:
    return str(employee.get("seniority", "")).casefold() == "junior"


def _required_skills(requirements: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {normalize_skill(str(req["required_skill"])): req for req in requirements}


def _employee_match(
    employee: dict[str, Any],
    requirements: list[dict[str, Any]],
) -> tuple[float, float, dict[str, bool]]:
    skill_rows = employee.get("skills", [])
    skill_index = {
        normalize_skill(str(row["skill"])): row for row in skill_rows
    }
    total_weight = sum(max(1, int(req.get("importance_1_5") or 1)) for req in requirements)
    if total_weight == 0:
        return 0.0, 0.0, {}
    score = 0.0
    matched: dict[str, bool] = {}
    for requirement in requirements:
        key = normalize_skill(str(requirement["required_skill"]))
        row = skill_index.get(key)
        importance = max(1, int(requirement.get("importance_1_5") or 1))
        if row is None:
            matched[key] = False
            continue
        proficiency = _number(row.get("proficiency_1_5"))
        years = _number(row.get("skill_experience_years"))
        minimum_proficiency = _number(requirement.get("min_proficiency_1_5"))
        minimum_years = _number(requirement.get("min_experience_years"))
        qualified = proficiency >= minimum_proficiency and years >= minimum_years
        matched[key] = qualified
        experience_quality = min(years / max(minimum_years, 1.0), 1.0)
        proficiency_quality = min(proficiency / 5.0, 1.0)
        score += importance * (0.65 * proficiency_quality + 0.35 * experience_quality)
    return score / total_weight, sum(matched.values()) / max(1, len(requirements)) * 100, matched


def optimize_team(
    project: dict[str, Any],
    requirements: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    time_limit_seconds: float = 20.0,
) -> OptimizationResult:
    team_size = int(project["team_size_required"])
    if team_size < 1:
        raise ValueError("Project team_size_required must be at least 1.")
    if len(candidates) < team_size:
        raise ValueError(
            f"Only {len(candidates)} eligible candidates were found for a team of {team_size}."
        )

    allocation_pct = _number(project.get("member_allocation_pct"), 100.0)
    duration_months = _number(project.get("duration_months"), 1.0)
    scores: list[int] = []
    costs: list[int] = []
    coverage: list[float] = []
    qualified: list[dict[str, bool]] = []
    for candidate in candidates:
        skill_score, skill_coverage, matches = _employee_match(candidate, requirements)
        salary = _number(candidate.get("monthly_salary_lakh"))
        performance = _number(candidate.get("performance_score"))
        experience = _number(candidate.get("experience_years"))
        local_bonus = 5 if not candidate.get("relocation_required") else 0
        objective = (
            700 * skill_score
            + 35 * performance / 5
            + 10 * min(experience / 20, 1)
            + local_bonus
            - 2 * salary / 30
        )
        scores.append(round(objective * 100))
        costs.append(
            round(salary * duration_months * allocation_pct / 100 * 100)
        )
        coverage.append(skill_coverage)
        qualified.append(matches)

    model = cp_model.CpModel()
    chosen = [model.NewBoolVar(f"employee_{i}") for i in range(len(candidates))]
    model.Add(sum(chosen) == team_size)

    lead_count = sum(chosen[i] for i, emp in enumerate(candidates) if _is_lead(emp))
    senior_count = sum(chosen[i] for i, emp in enumerate(candidates) if _is_senior(emp))
    junior_count = sum(chosen[i] for i, emp in enumerate(candidates) if _is_junior(emp))
    relocation_count = sum(
        chosen[i] for i, emp in enumerate(candidates) if emp.get("relocation_required")
    )
    model.Add(lead_count >= int(project.get("min_lead_count") or 0))
    model.Add(lead_count <= math.floor(team_size * _number(project.get("max_lead_pct"), 100) / 100))
    model.Add(senior_count >= math.ceil(team_size * _number(project.get("min_senior_plus_pct")) / 100))
    model.Add(junior_count <= math.floor(team_size * _number(project.get("max_junior_pct"), 100) / 100))
    model.Add(relocation_count <= math.floor(team_size * _number(project.get("max_relocation_pct"), 100) / 100))

    requirement_keys = _required_skills(requirements)
    for key, requirement in requirement_keys.items():
        min_headcount = int(requirement.get("min_headcount") or 0)
        if min_headcount > 0:
            model.Add(
                sum(
                    chosen[i]
                    for i in range(len(candidates))
                    if qualified[i].get(key, False)
                )
                >= min_headcount
            )

    budget = _number(project.get("budget_lakh"))
    if budget > 0:
        model.Add(sum(costs[i] * chosen[i] for i in range(len(candidates))) <= round(budget * 100))

    model.Maximize(sum(scores[i] * chosen[i] for i in range(len(candidates))))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    solver.parameters.num_search_workers = 8
    status_code = solver.Solve(model)
    if status_code not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise ValueError(
            "No feasible team satisfies all project constraints. "
            "Check candidate availability, skill headcounts, budget, and seniority limits."
        )

    selected: list[dict[str, Any]] = []
    total_cost = 0.0
    total_coverage = 0.0
    for index, candidate in enumerate(candidates):
        if not solver.BooleanValue(chosen[index]):
            continue
        member_cost = costs[index] / 100
        total_cost += member_cost
        total_coverage += coverage[index]
        selected.append(
            {
                **candidate,
                "match_score": scores[index] / 100,
                "skill_coverage_pct": round(coverage[index], 2),
                "estimated_cost_lakh": round(member_cost, 2),
            }
        )
    selected.sort(key=lambda member: (-member["match_score"], member["employee_id"]))
    return OptimizationResult(
        status="OPTIMAL" if status_code == cp_model.OPTIMAL else "FEASIBLE",
        selected=selected,
        total_cost_lakh=round(total_cost, 2),
        average_skill_coverage_pct=round(total_coverage / len(selected), 2),
        solver_objective=solver.ObjectiveValue() / 100,
    )
