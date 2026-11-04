from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from cropstar_api.operation_details import (
    FertilisationDetails,
    OperationDetails,
    from_stored,
    to_stored,
)

DETAILS: TypeAdapter[OperationDetails] = TypeAdapter(OperationDetails)


@pytest.mark.parametrize(
    "valid",
    [
        {"type": "tillage", "implement": "plough", "depth_cm": 25},
        {"type": "mechanical_weed_control", "implement": "tine_weeder"},
        {"type": "mulching", "material": "cover_crop"},
        {"type": "sowing", "purpose": "cover_crop", "rate": 80, "unit": "kg_per_ha"},
        {"type": "fertilisation", "amount": 20, "unit": "m3_per_ha", "note": "Rindergülle"},
        {
            "type": "harvest",
            "product": "grain",
            "yield_t_per_ha": 6.2,
            "moisture_percent": 14.5,
            "crude_protein_percent": 12.1,
        },
    ],
    ids=lambda d: d["type"],
)
def test_each_operation_type_has_its_own_details(valid: dict[str, Any]) -> None:
    details = DETAILS.validate_python(valid)

    assert to_stored(details) == valid


@pytest.mark.parametrize(
    "invalid",
    [
        {"type": "tillage", "depth_cm": -5},
        {"type": "mechanical_weed_control", "implement": "plough"},
        {"type": "mulching", "material": "concrete"},
        {"type": "sowing", "rate": 80},
        {"type": "fertilisation", "amount": -1, "unit": "kg_per_ha"},
        {"type": "harvest", "crude_protein_percent": 101},
    ],
    ids=[
        "negative depth",
        "implement of another type",
        "unknown material",
        "rate without unit",
        "negative amount",
        "protein above 100 %",
    ],
)
def test_implausible_details_are_refused(invalid: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        DETAILS.validate_python(invalid)


def test_fields_of_another_type_are_refused() -> None:
    with pytest.raises(ValidationError):
        DETAILS.validate_python({"type": "tillage", "amount": 20})


def test_everything_is_optional_and_blank_notes_are_dropped() -> None:
    details = DETAILS.validate_python({"type": "fertilisation", "note": "  "})

    assert to_stored(details) == {"type": "fertilisation"}


def test_stored_details_read_back_as_they_were() -> None:
    details = FertilisationDetails(amount=30, unit="kg_per_ha", note="KAS")

    assert from_stored(to_stored(details)) == details
    assert from_stored(None) is None
