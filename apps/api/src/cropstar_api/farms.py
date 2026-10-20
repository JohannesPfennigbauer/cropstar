import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy import select

from cropstar_api.auth.dependencies import CurrentIdentity
from cropstar_api.db import Db
from cropstar_api.models import Membership


def farm_membership(
    farm_id: Annotated[uuid.UUID, Path()], identity: CurrentIdentity, db: Db
) -> Membership:
    """The caller's Membership of the Farm in the path. Non-members get 404, not 403, so
    they cannot learn which Farms exist."""
    membership = db.scalar(
        select(Membership).where(
            Membership.farm_id == farm_id, Membership.user_id == identity.user_id
        )
    )
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="farm_not_found")
    return membership


FarmMembership = Annotated[Membership, Depends(farm_membership)]
