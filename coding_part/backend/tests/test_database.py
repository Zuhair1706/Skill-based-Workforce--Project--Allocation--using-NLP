from sqlalchemy import create_engine, func, insert, select

from app.database import allocations, metadata


def test_allocation_batch_can_store_multiple_team_members():
    engine = create_engine("sqlite://")
    metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(
            insert(allocations),
            [
                {
                    "allocation_id": "batch-1",
                    "project_id": "project-1",
                    "employee_id": employee_id,
                }
                for employee_id in ("employee-1", "employee-2")
            ],
        )
        count = connection.scalar(
            select(func.count()).select_from(allocations)
        )

    assert count == 2
