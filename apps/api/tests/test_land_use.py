import pytest

from cropstar_api.land_use import LandUseCategory, land_use_category


@pytest.mark.parametrize(
    ("code", "category"),
    [
        ("142", LandUseCategory.CEREALS),  # Winterroggen
        ("111", LandUseCategory.CEREALS),  # Sommergerste
        ("308", LandUseCategory.LEGUMES),  # Sojabohnen
        ("651", LandUseCategory.ROOT_CROPS),  # Zuckerrüben
        ("307", LandUseCategory.OILSEEDS),  # Sonnenblumen
        ("635", LandUseCategory.FODDER),  # Luzerne
        ("771", LandUseCategory.FALLOW),  # Grünbrache
        ("716", LandUseCategory.GRASSLAND),  # Mähwiese/-weide zwei Nutzungen
        ("361", LandUseCategory.OTHER),  # GLÖZ Rain / Böschung
        ("351", LandUseCategory.OTHER),  # LSE Hecke / Ufergehölz
    ],
)
def test_ama_codes_fall_into_their_category(code: str, category: LandUseCategory) -> None:
    assert land_use_category(code) is category


def test_unknown_codes_are_other() -> None:
    assert land_use_category("99999") is LandUseCategory.OTHER
