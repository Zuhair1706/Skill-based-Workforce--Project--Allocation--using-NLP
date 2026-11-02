from app.optimizer import optimize_team


def test_optimizer_honors_team_and_skill_constraints():
    project = {
        "team_size_required": 2,
        "member_allocation_pct": 50,
        "duration_months": 2,
        "budget_lakh": 30,
        "min_lead_count": 1,
        "min_senior_plus_pct": 50,
        "max_lead_pct": 50,
        "max_junior_pct": 50,
        "max_relocation_pct": 50,
    }
    requirements = [
        {
            "required_skill": "Python",
            "importance_1_5": 5,
            "min_proficiency_1_5": 4,
            "min_experience_years": 3,
            "min_headcount": 1,
        }
    ]
    candidates = [
        {
            "employee_id": "E1",
            "seniority": "Lead",
            "availability_pct": 100,
            "performance_score": 4.5,
            "experience_years": 10,
            "monthly_salary_lakh": 10,
            "relocation_required": False,
            "skills": [
                {"skill": "Python", "proficiency_1_5": 5, "skill_experience_years": 6}
            ],
        },
        {
            "employee_id": "E2",
            "seniority": "Junior",
            "availability_pct": 100,
            "performance_score": 4,
            "experience_years": 2,
            "monthly_salary_lakh": 8,
            "relocation_required": False,
            "skills": [],
        },
    ]

    result = optimize_team(project, requirements, candidates)

    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert len(result.selected) == 2
    assert {member["employee_id"] for member in result.selected} == {"E1", "E2"}
    assert result.total_cost_lakh <= 30
