"""Harvest Years of a Farm and their locks."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from cropstar_api.db import Db
from cropstar_api.farms import FarmMembership
from cropstar_api.models import Field, HarvestYearLock, Membership
from cropstar_api.policy import Action, Actor, decide
from cropstar_api.routes.farms import PersonOut

router = APIRouter(prefix="/farms/{farm_id}", tags=["harvest years"])

Year = Annotated[int, Path(ge=1990, le=2200)]


class LockOut(BaseModel):
    locked_by: PersonOut | None
    locked_at: datetime


class HarvestYearOut(BaseModel):
    year: int
    lock: LockOut | None


@router.get("/harvest-years", operation_id="listHarvestYears")
def list_harvest_years(membership: FarmMembership, db: Db) -> list[HarvestYearOut]:
    """Harvest Years the Farm has Fields in, most recent first, with their locks."""
    years = db.scalars(
        select(Field.harvest_year)
        .where(Field.farm_id == membership.farm_id)
        .distinct()
        .order_by(Field.harvest_year.desc())
    )
    locks = _locks(db, membership)
    return [HarvestYearOut(year=year, lock=_lock_out(locks.get(year))) for year in years]


@router.put("/harvest-years/{year}/lock", operation_id="lockHarvestYear")
def lock_harvest_year(year: Year, membership: FarmMembership, db: Db) -> HarvestYearOut:
    """Freezes everything referring to the Harvest Year. Locking it again keeps the first lock."""
    _require_admin(membership)
    _require_year(db, membership, year)
    lock = db.get(HarvestYearLock, (membership.farm_id, year))
    if lock is None:
        lock = HarvestYearLock(
            farm_id=membership.farm_id,
            harvest_year=year,
            locked_by_id=membership.user_id,
            locked_at=datetime.now(UTC),
        )
        db.add(lock)
        db.flush()
    return HarvestYearOut(year=year, lock=_lock_out(lock))


@router.delete("/harvest-years/{year}/lock", operation_id="unlockHarvestYear")
def unlock_harvest_year(year: Year, membership: FarmMembership, db: Db) -> HarvestYearOut:
    _require_admin(membership)
    _require_year(db, membership, year)
    lock = db.get(HarvestYearLock, (membership.farm_id, year))
    if lock is not None:
        db.delete(lock)
        db.flush()
    return HarvestYearOut(year=year, lock=None)


def _require_admin(membership: Membership) -> None:
    decision = decide(Actor(membership.user_id, membership.role), Action.LOCK_HARVEST_YEAR)
    if not decision:
        assert decision.denial is not None
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=decision.denial.value)


def _require_year(db: DbSession, membership: Membership, year: int) -> None:
    exists = db.scalar(
        select(Field.id)
        .where(Field.farm_id == membership.farm_id, Field.harvest_year == year)
        .limit(1)
    )
    if exists is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="harvest_year_not_found")


def _locks(db: DbSession, membership: Membership) -> dict[int, HarvestYearLock]:
    locks = db.scalars(select(HarvestYearLock).where(HarvestYearLock.farm_id == membership.farm_id))
    return {lock.harvest_year: lock for lock in locks}


def _lock_out(lock: HarvestYearLock | None) -> LockOut | None:
    if lock is None:
        return None
    by = lock.locked_by
    return LockOut(
        locked_by=PersonOut(id=by.id, email=by.email) if by else None,
        locked_at=lock.locked_at,
    )
