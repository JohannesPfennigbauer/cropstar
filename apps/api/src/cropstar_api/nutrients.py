"""Nutrients applied per hectare by a fertilisation, from its amount and the Farm Input.

Pure. The amount is per hectare in the unit of the details; the input's contents are kg per
its own unit. Mass amounts (kg/ha, t/ha) go with contents per t or per 100 kg, volume amounts
(m³/ha, l/ha) with contents per m³. Anything else would need a density nobody recorded, so
it is refused rather than guessed.
"""

from dataclasses import dataclass
from decimal import Decimal

from cropstar_api.models import FarmInputUnit
from cropstar_api.operation_details import FertilisationUnit

# How many of the input's units one unit of the amount is.
_FACTORS: dict[tuple[FertilisationUnit, FarmInputUnit], Decimal] = {
    (FertilisationUnit.KG_PER_HA, FarmInputUnit.TONNE): Decimal("0.001"),
    (FertilisationUnit.KG_PER_HA, FarmInputUnit.HUNDRED_KG): Decimal("0.01"),
    (FertilisationUnit.T_PER_HA, FarmInputUnit.TONNE): Decimal(1),
    (FertilisationUnit.T_PER_HA, FarmInputUnit.HUNDRED_KG): Decimal(10),
    (FertilisationUnit.M3_PER_HA, FarmInputUnit.CUBIC_METRE): Decimal(1),
    (FertilisationUnit.L_PER_HA, FarmInputUnit.CUBIC_METRE): Decimal("0.001"),
}
_KG = Decimal("0.1")


@dataclass(frozen=True)
class Contents:
    """kg per unit of a Farm Input; None where the input does not say."""

    unit: FarmInputUnit
    total_n: Decimal | None
    available_n: Decimal | None
    p2o5: Decimal | None
    k2o: Decimal | None


@dataclass(frozen=True)
class Applied:
    """kg per hectare, rounded to 0.1 kg; None where the contents are unknown."""

    total_n: Decimal | None
    available_n: Decimal | None
    p2o5: Decimal | None
    k2o: Decimal | None


def compatible(amount_unit: FertilisationUnit, input_unit: FarmInputUnit) -> bool:
    return (amount_unit, input_unit) in _FACTORS


def applied(amount: Decimal, amount_unit: FertilisationUnit, contents: Contents) -> Applied | None:
    """None when the units do not fit together."""
    factor = _FACTORS.get((amount_unit, contents.unit))
    if factor is None:
        return None
    quantity = amount * factor

    def per_ha(content: Decimal | None) -> Decimal | None:
        return None if content is None else (quantity * content).quantize(_KG)

    return Applied(
        total_n=per_ha(contents.total_n),
        available_n=per_ha(contents.available_n),
        p2o5=per_ha(contents.p2o5),
        k2o=per_ha(contents.k2o),
    )
