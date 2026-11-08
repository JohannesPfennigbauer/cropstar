"""A Farm's Task stages: the steps before a Task is done, as the board shows them."""

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import func, select, update

from cropstar_api import task_stages
from cropstar_api.db import Db
from cropstar_api.farms import FarmMembership
from cropstar_api.models import Task, TaskStage
from cropstar_api.policy import Action, Actor, decide

router = APIRouter(prefix="/farms/{farm_id}", tags=["tasks"])

StageName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
MAX_STAGES = 10


class TaskStageOut(BaseModel):
    id: uuid.UUID
    name: str
    # Tasks in this stage, whatever their Status.
    task_count: int


class TaskStageIn(BaseModel):
    # Null for a new stage.
    id: uuid.UUID | None = None
    name: StageName


class TaskStagesUpdate(BaseModel):
    """The whole list, in board order. Stages left out are removed; their Tasks move to the
    first stage."""

    stages: Annotated[list[TaskStageIn], Field(min_length=1, max_length=MAX_STAGES)]


@router.get("/task-stages", operation_id="listTaskStages")
def list_task_stages(membership: FarmMembership, db: Db) -> list[TaskStageOut]:
    return _out(db, membership.farm_id)


@router.put("/task-stages", operation_id="updateTaskStages")
def update_task_stages(
    body: TaskStagesUpdate, membership: FarmMembership, db: Db
) -> list[TaskStageOut]:
    decision = decide(Actor(membership.user_id, membership.role), Action.MANAGE_FARM)
    if not decision:
        assert decision.denial is not None
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=decision.denial.value)
    names = [stage.name.casefold() for stage in body.stages]
    if len(set(names)) != len(names):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="duplicate_stage_name")
    current = {stage.id: stage for stage in task_stages.stages(db, membership.farm_id)}
    sent = [stage.id for stage in body.stages if stage.id is not None]
    if set(sent) - current.keys() or len(set(sent)) != len(sent):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="stage_not_found")

    kept: list[TaskStage] = []
    for position, stage in enumerate(body.stages):
        if stage.id is None:
            created = TaskStage(farm_id=membership.farm_id, name=stage.name, position=position)
            db.add(created)
            kept.append(created)
        else:
            existing = current[stage.id]
            existing.name, existing.position = stage.name, position
            kept.append(existing)
    db.flush()
    removed = [stage_id for stage_id in current if stage_id not in sent]
    if removed:
        db.execute(update(Task).where(Task.stage_id.in_(removed)).values(stage_id=kept[0].id))
        for stage_id in removed:
            db.delete(current[stage_id])
    db.flush()
    return _out(db, membership.farm_id)


def _out(db: Db, farm_id: uuid.UUID) -> list[TaskStageOut]:
    counts = dict(
        db.execute(
            select(Task.stage_id, func.count(Task.id))
            .where(Task.farm_id == farm_id)
            .group_by(Task.stage_id)
        ).all()
    )
    return [
        TaskStageOut(id=stage.id, name=stage.name, task_count=counts.get(stage.id, 0))
        for stage in task_stages.stages(db, farm_id)
    ]
