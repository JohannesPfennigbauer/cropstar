from decimal import Decimal

import pytest

from cropstar_api.farm_input_catalogue import catalogue, entry


def test_the_derivation_reproduces_the_worked_example_of_the_guidelines() -> None:
    # RSD Tab. 81: Jungvieh 1 bis 2 Jahre, Tiefstallmist. The guidelines print P₂O₅ as 1,56,
    # but their own inputs give 156,8 / 99,2 = 1,58.
    young_cattle = entry("rindertiefstallmist_jungvieh")

    assert young_cattle is not None
    assert (young_cattle.total_n, young_cattle.available_n) == (Decimal("3.02"), Decimal("1.38"))
    assert (young_cattle.p2o5, young_cattle.k2o) == (Decimal("1.58"), Decimal("6.03"))


def test_pig_slurry_matches_the_worked_example_within_its_rounding() -> None:
    # Tab. 81 divides by a herd and volume rounded to 34,8 and 38,6: 6,76 / 4,71 / 3,97 / 4,51.
    pigs = entry("schweinegulle_mast")

    assert pigs is not None
    for value, printed in [
        (pigs.total_n, "6.76"),
        (pigs.available_n, "4.71"),
        (pigs.p2o5, "3.97"),
        (pigs.k2o, "4.51"),
    ]:
        assert value is not None
        assert abs(value - Decimal(printed)) <= Decimal("0.02")


def test_every_entry_names_its_source_and_has_no_invented_values() -> None:
    for item in catalogue():
        assert "RSD, 8. Auflage" in item.source
        assert item.dry_matter_percent is None
        assert item.total_n is not None and item.available_n is not None
        assert item.available_n <= item.total_n


@pytest.mark.parametrize("code", ["rinderstallmist_milchkuh_6000", "rinderjauche_milchkuh_6000"])
def test_solid_and_liquid_manure_of_one_system_carry_no_p_and_k(code: str) -> None:
    # Tab. 70 gives one total per animal; how it splits between Mist and Jauche is unknown.
    item = entry(code)

    assert item is not None
    assert (item.p2o5, item.k2o) == (None, None)
