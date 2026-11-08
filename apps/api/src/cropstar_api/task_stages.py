"""Task stages: the Farm's own steps before a Task is done."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from cropstar_api.models import DEFAULT_TASK_STAGES, TaskStage


def create_defaults(db: Session, farm_id: uuid.UUID) -> None:
    db.add_all(
        TaskStage(farm_id=farm_id, name=name, position=index)
        for index, name in enumerate(DEFAULT_TASK_STAGES)
    )


def stages(db: Session, farm_id: uuid.UUID) -> list[TaskStage]:
    return list(
        db.scalars(
            select(TaskStage).where(TaskStage.farm_id == farm_id).order_by(TaskStage.position)
        )
    )
