"""Land Use categories for AMA Schlagnutzungsart codes.

Codes are mapped to the Hierarchical Crop and Agriculture Taxonomy (HCAT) with the table
`ama_hcat.csv`, derived from fiboa's Austrian code list (https://fiboa.org/code/at/at.csv,
fiboa/cli, Apache-2.0). The category is the HCAT branch a code falls in.
"""

import csv
import enum
from functools import cache
from importlib.resources import files


class LandUseCategory(enum.StrEnum):
    CEREALS = "cereals"
    LEGUMES = "legumes"
    ROOT_CROPS = "root_crops"
    OILSEEDS = "oilseeds"
    FODDER = "fodder"
    VEGETABLES = "vegetables"
    FALLOW = "fallow"
    GRASSLAND = "grassland"
    PERMANENT = "permanent"
    OTHER = "other"


# Most specific prefix first; "3301" catches the remaining arable special crops.
_BY_HCAT_PREFIX: tuple[tuple[str, LandUseCategory], ...] = (
    ("330101", LandUseCategory.CEREALS),
    ("330102", LandUseCategory.LEGUMES),
    ("330116", LandUseCategory.LEGUMES),
    ("330103", LandUseCategory.ROOT_CROPS),
    ("330129", LandUseCategory.ROOT_CROPS),
    ("330106", LandUseCategory.OILSEEDS),
    ("330121", LandUseCategory.OILSEEDS),
    ("330109", LandUseCategory.FODDER),
    ("330111", LandUseCategory.FALLOW),
    ("3308", LandUseCategory.FALLOW),
    ("3301", LandUseCategory.VEGETABLES),
    ("3302", LandUseCategory.GRASSLAND),
    ("3303", LandUseCategory.PERMANENT),
    ("3305", LandUseCategory.PERMANENT),
)


@cache
def _hcat_by_ama_code() -> dict[str, str]:
    text = (files("cropstar_api.land_use") / "ama_hcat.csv").read_text("utf-8")
    return {row["ama_code"]: row["hcat_code"] for row in csv.DictReader(text.splitlines())}


def land_use_category(ama_code: str) -> LandUseCategory:
    """The category of an AMA Land Use code; unknown codes, landscape elements and
    protection areas are `OTHER`."""
    hcat = _hcat_by_ama_code().get(ama_code.strip())
    if hcat is None:
        return LandUseCategory.OTHER
    for prefix, category in _BY_HCAT_PREFIX:
        if hcat.startswith(prefix):
            return category
    return LandUseCategory.OTHER
