import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from cropstar_api.models import Field, Membership, OperationType, Plot, Role, Task


class SqlTaskRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, farm_id: uuid.UUID, task_id: uuid.UUID) -> Task | None:
        return self._db.scalar(select(Task).where(Task.farm_id == farm_id, Task.id == task_id))

    def add(self, task: Task) -> None:
        self._db.add(task)
        self._db.flush()

    def delete(self, task: Task) -> None:
        self._db.delete(task)
        self._db.flush()

    def role_of(self, farm_id: uuid.UUID, user_id: uuid.UUID) -> Role | None:
        return self._db.scalar(
            select(Membership.role).where(
                Membership.farm_id == farm_id, Membership.user_id == user_id
            )
        )

    def fields(self, farm_id: uuid.UUID, ids: frozenset[uuid.UUID]) -> list[Field]:
        return list(
            self._db.scalars(select(Field).where(Field.farm_id == farm_id, Field.id.in_(ids)))
        )

    def plots(self, farm_id: uuid.UUID, ids: frozenset[uuid.UUID]) -> list[Plot]:
        return list(
            self._db.scalars(
                select(Plot)
                .join(Field, Plot.field_id == Field.id)
                .options(joinedload(Plot.field))
                .where(Field.farm_id == farm_id, Plot.id.in_(ids))
            )
        )

    def operation_type_exists(self, code: str) -> bool:
        return self._db.get(OperationType, code) is not None
