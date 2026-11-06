from decimal import Decimal

import pytest

from cropstar_api.models import FarmInputUnit
from cropstar_api.nutrients import Applied, Contents, applied, compatible
from cropstar_api.operation_details import FertilisationUnit

SLURRY = Contents(
    FarmInputUnit.CUBIC_METRE, Decimal("3.51"), Decimal("2.14"), Decimal("1.39"), Decimal("6.94")
)
# Calcium ammonium nitrate, 27 % N, declared per 100 kg.
CAN = Contents(FarmInputUnit.HUNDRED_KG, Decimal(27), Decimal(27), None, None)
COMPOST = Contents(FarmInputUnit.TONNE, Decimal("6.5"), Decimal("0.7"), Decimal("3.2"), None)


def test_slurry_by_volume() -> None:
    result = applied(Decimal(20), FertilisationUnit.M3_PER_HA, SLURRY)

    assert result == Applied(Decimal("70.2"), Decimal("42.8"), Decimal("27.8"), Decimal("138.8"))


def test_mineral_fertiliser_in_kg_per_hectare() -> None:
    result = applied(Decimal(150), FertilisationUnit.KG_PER_HA, CAN)

    assert result == Applied(Decimal("40.5"), Decimal("40.5"), None, None)


@pytest.mark.parametrize(
    ("amount", "unit", "n"),
    [
        (Decimal(15), FertilisationUnit.T_PER_HA, "97.5"),
        (Decimal(15000), FertilisationUnit.KG_PER_HA, "97.5"),
    ],
)
def test_mass_amounts_convert_to_the_inputs_unit(
    amount: Decimal, unit: FertilisationUnit, n: str
) -> None:
    result = applied(amount, unit, COMPOST)

    assert result is not None
    assert result.total_n == Decimal(n)


def test_litres_convert_to_cubic_metres() -> None:
    result = applied(Decimal(20000), FertilisationUnit.L_PER_HA, SLURRY)

    assert result is not None
    assert result.total_n == Decimal("70.2")


def test_unknown_contents_stay_unknown() -> None:
    result = applied(Decimal(10), FertilisationUnit.T_PER_HA, COMPOST)

    assert result is not None
    assert result.k2o is None


@pytest.mark.parametrize(
    ("unit", "contents"),
    [
        (FertilisationUnit.M3_PER_HA, COMPOST),
        (FertilisationUnit.T_PER_HA, SLURRY),
        (FertilisationUnit.L_PER_HA, CAN),
    ],
)
def test_volume_and_mass_do_not_mix(unit: FertilisationUnit, contents: Contents) -> None:
    assert not compatible(unit, contents.unit)
    assert applied(Decimal(10), unit, contents) is None
