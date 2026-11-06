"""Planned and Actual Details: what an Operation is, one schema per Operation Type.

The same schema serves the plan and the record, so completing can start from the plan.
Every field is optional — a plan is often vague — but what is given must be plausible.
Amounts are always per hectare, never totals, so that history can later be attributed by
area share when Plots are split or merged. Pure: no database, no Farm.
"""

import enum
import uuid
from typing import Annotated, Any, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    TypeAdapter,
    field_validator,
    model_validator,
)

Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)]
PerHectare = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Percent = Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]


class TillageImplement(enum.StrEnum):
    PLOUGH = "plough"
    CULTIVATOR = "cultivator"
    DISC_HARROW = "disc_harrow"
    SUBSOILER = "subsoiler"
    SEEDBED_COMBINATION = "seedbed_combination"
    POWER_HARROW = "power_harrow"
    ROLLER = "roller"
    OTHER = "other"


class WeedControlImplement(enum.StrEnum):
    TINE_WEEDER = "tine_weeder"
    HOE = "hoe"
    FINGER_WEEDER = "finger_weeder"
    ROTARY_HOE = "rotary_hoe"
    OTHER = "other"


class MulchedMaterial(enum.StrEnum):
    COVER_CROP = "cover_crop"
    CROP_RESIDUES = "crop_residues"
    GRASSLAND = "grassland"
    OTHER = "other"


class SowingPurpose(enum.StrEnum):
    MAIN_CROP = "main_crop"
    COVER_CROP = "cover_crop"
    UNDERSOWN_CROP = "undersown_crop"


class SowingUnit(enum.StrEnum):
    KG_PER_HA = "kg_per_ha"
    SEEDS_PER_M2 = "seeds_per_m2"
    SEEDS_PER_HA = "seeds_per_ha"


class FertilisationUnit(enum.StrEnum):
    KG_PER_HA = "kg_per_ha"
    T_PER_HA = "t_per_ha"
    M3_PER_HA = "m3_per_ha"
    L_PER_HA = "l_per_ha"


class HarvestedProduct(enum.StrEnum):
    GRAIN = "grain"
    STRAW = "straw"
    WHOLE_CROP = "whole_crop"
    FORAGE = "forage"
    OTHER = "other"


class _Details(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Anything the structured fields do not cover.
    note: Note | None = None

    @field_validator("note")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        return value or None


class TillageDetails(_Details):
    type: Literal["tillage"] = "tillage"
    implement: TillageImplement | None = None
    depth_cm: Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)] | None = None


class MechanicalWeedControlDetails(_Details):
    type: Literal["mechanical_weed_control"] = "mechanical_weed_control"
    implement: WeedControlImplement | None = None


class MulchingDetails(_Details):
    type: Literal["mulching"] = "mulching"
    material: MulchedMaterial | None = None


class SowingDetails(_Details):
    type: Literal["sowing"] = "sowing"
    purpose: SowingPurpose | None = None
    # Seed from the Farm Inputs.
    farm_input_id: uuid.UUID | None = None
    rate: PerHectare | None = None
    unit: SowingUnit | None = None

    @model_validator(mode="after")
    def _rate_with_unit(self) -> Self:
        _amount_with_unit(self.rate, self.unit)
        return self


class FertilisationDetails(_Details):
    type: Literal["fertilisation"] = "fertilisation"
    # A fertiliser from the Farm Inputs; its contents turn the amount into nutrients.
    farm_input_id: uuid.UUID | None = None
    amount: PerHectare | None = None
    unit: FertilisationUnit | None = None

    @model_validator(mode="after")
    def _amount_with_unit(self) -> Self:
        _amount_with_unit(self.amount, self.unit)
        return self


class HarvestDetails(_Details):
    type: Literal["harvest"] = "harvest"
    product: HarvestedProduct | None = None
    # At harvest moisture.
    yield_t_per_ha: PerHectare | None = None
    moisture_percent: Percent | None = None
    # Of the dry matter.
    crude_protein_percent: Percent | None = None


OperationDetails = Annotated[
    TillageDetails
    | MechanicalWeedControlDetails
    | MulchingDetails
    | SowingDetails
    | FertilisationDetails
    | HarvestDetails,
    Field(discriminator="type"),
]

_ADAPTER: TypeAdapter[OperationDetails] = TypeAdapter(OperationDetails)


def to_stored(details: OperationDetails | None) -> dict[str, Any] | None:
    """The JSON kept in the database: only what was given."""
    return None if details is None else details.model_dump(mode="json", exclude_none=True)


def from_stored(value: dict[str, Any] | None) -> OperationDetails | None:
    return None if value is None else _ADAPTER.validate_python(value)


def _amount_with_unit(amount: float | None, unit: enum.StrEnum | None) -> None:
    if amount is not None and unit is None:
        raise ValueError("an amount needs its unit")
