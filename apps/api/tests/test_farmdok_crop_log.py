import uuid
from datetime import date
from decimal import Decimal

import pytest

from cropstar_api.farmdok.crop_log import read_crop_log
from cropstar_api.farmdok.crop_log_plan import (
    CropLogPlan,
    InvalidResolutionError,
    KnownInput,
    Problem,
    ProductChoice,
    Resolutions,
    YearPlot,
    plan,
)
from cropstar_api.farmdok.report import FarmdokError, ProblemCode
from cropstar_api.models import FarmInputKind, FarmInputUnit
from cropstar_api.operation_details import (
    FertilisationDetails,
    HarvestDetails,
    SowingDetails,
    TillageDetails,
)
from tests.farmdok_export import DEMO_ENTRIES, Entry, crop_log, field_list

TYPES = {"tillage", "mechanical_weed_control", "mulching", "sowing", "fertilisation", "harvest"}
RYE = YearPlot(uuid.uuid4(), 1, 1, "142")
FALLOW = YearPlot(uuid.uuid4(), 1, 2, "771")
SUNFLOWER = YearPlot(uuid.uuid4(), 2, 1, "307")
PLOTS = [RYE, FALLOW, SUNFLOWER]
MANURE = KnownInput(
    uuid.uuid4(), "Rindermist", FarmInputKind.FERTILISER, FarmInputUnit.CUBIC_METRE, False
)
RYE_SEED = KnownInput(uuid.uuid4(), "Winterroggen", FarmInputKind.SEED, None, False)


def plan_log(
    entries: tuple[Entry, ...] = DEMO_ENTRIES,
    inputs: list[KnownInput] | None = None,
    resolutions: Resolutions | None = None,
    activities: dict[str, str | None] | None = None,
    products: dict[str, uuid.UUID | None] | None = None,
) -> CropLogPlan:
    return plan(
        read_crop_log(crop_log(entries)),
        PLOTS,
        [MANURE, RYE_SEED] if inputs is None else inputs,
        TYPES,
        activities or {},
        products or {},
        resolutions or Resolutions(),
    )


def test_the_log_is_read_with_dates_field_lists_and_units() -> None:
    entries = (*DEMO_ENTRIES[:1], Entry("02.09.2024", "1, 2", "Winterroggen", "Scheibenegge"))
    log = read_crop_log(crop_log(entries))

    assert (log.harvest_year, log.farm_number, len(log.entries)) == (2025, "9999999", 2)
    manure, harrow = log.entries[0], log.entries[1]
    assert (manure.row, manure.performed_on, manure.field_numbers) == (7, date(2024, 8, 28), (1,))
    assert (manure.product, manure.amount, manure.unit) == ("Rindermist", Decimal(25), "m³/ha")
    assert (harrow.field_numbers, harrow.product, harrow.amount) == ((1, 2), None, None)


def test_a_field_list_is_not_a_log() -> None:
    with pytest.raises(FarmdokError) as error:
        read_crop_log(field_list())

    assert [p.code for p in error.value.problems] == [ProblemCode.NOT_A_CROP_LOG]


def test_every_entry_becomes_a_task_with_structured_details() -> None:
    result = plan_log(entries=(DEMO_ENTRIES[0], DEMO_ENTRIES[2], DEMO_ENTRIES[3], DEMO_ENTRIES[4]))

    assert result.unresolved == ()
    manure, sowing, harrowing, harvest = result.tasks
    assert (manure.title, manure.operation_type, manure.plot_ids) == (
        "Wirtschaftsdünger Mist",
        "fertilisation",
        (RYE.id,),
    )
    assert manure.details == FertilisationDetails(
        farm_input_id=MANURE.id, amount=25, unit="m3_per_ha"
    )
    assert sowing.details == SowingDetails(
        purpose="main_crop", farm_input_id=RYE_SEED.id, rate=140, unit="kg_per_ha"
    )
    assert harrowing.operation_type == "mechanical_weed_control"
    assert harvest.details == HarvestDetails(
        product="grain", yield_t_per_ha=5.432, note="Winterroggen"
    )
    assert harvest.performed_on == date(2025, 7, 20)


def test_multi_field_entries_need_a_matching_plot_on_every_field() -> None:
    # Field 1 has rye and fallow; the entry's crop is rye, so only the rye Plot matches.
    two_fields = Entry("02.09.2024", "1, 2", "Sonnenblumen", "Scheibenegge")
    rye_field = Entry("02.09.2024", "1", "Winterroggen", "Scheibenegge")

    result = plan_log(entries=(two_fields, rye_field))

    assert [(u.problem, u.key, u.context) for u in result.unresolved] == [
        (Problem.NO_MATCHING_PLOT, "7", ("1", "2"))
    ]
    assert [t.plot_ids for t in result.tasks] == [(RYE.id,)]
    assert result.tasks[0].details == TillageDetails(implement="disc_harrow")


def test_unknown_fields_and_crops_are_listed() -> None:
    entries = (
        Entry("02.09.2024", "9", "Winterroggen", "Scheibenegge"),
        Entry("02.09.2024", "1", "Sonstige Grünlandfläche", "Scheibenegge"),
    )

    result = plan_log(entries=entries)

    assert [(u.problem, u.key) for u in result.unresolved] == [
        (Problem.UNKNOWN_FIELD, "7"),
        (Problem.UNKNOWN_CROP, "8"),
    ]


def test_entries_get_plots_by_hand_or_are_skipped() -> None:
    entries = (
        Entry("02.09.2024", "9", "Winterroggen", "Scheibenegge"),
        Entry("02.09.2024", "1", "Sonstige Grünlandfläche", "Scheibenegge"),
    )
    resolutions = Resolutions(entries={7: [FALLOW.id, SUNFLOWER.id], 8: None})

    result = plan_log(entries=entries, resolutions=resolutions)

    assert result.unresolved == ()
    assert [t.plot_ids for t in result.tasks] == [(FALLOW.id, SUNFLOWER.id)]
    assert result.skipped_rows == (8,)


def test_unknown_activities_and_products_are_resolved_and_remembered_ones_apply() -> None:
    entries = (
        Entry("01.05.2025", "1", "Winterroggen", "Spatenrollegge"),
        Entry("02.05.2025", "1", "Winterroggen", "Wirtschaftsdünger Mist", "Kompost", 10.0, "t/ha"),
    )

    open_ = plan_log(entries=entries)
    by_hand = plan_log(
        entries=entries,
        resolutions=Resolutions(
            activities={"Spatenrollegge": "tillage"},
            products={"Kompost": ProductChoice(create=True)},
        ),
    )
    remembered = plan_log(
        entries=entries, activities={"Spatenrollegge": None}, products={"Kompost": None}
    )

    assert {(u.problem, u.key) for u in open_.unresolved} == {
        (Problem.UNKNOWN_ACTIVITY, "Spatenrollegge"),
        (Problem.UNKNOWN_PRODUCT, "Kompost"),
    }
    assert by_hand.unresolved == ()
    assert [(n.name, n.kind, n.unit) for n in by_hand.new_inputs] == [
        ("Kompost", FarmInputKind.FERTILISER, FarmInputUnit.TONNE)
    ]
    assert by_hand.tasks[1].new_input == "Kompost"
    # Remembered: the activity is skipped, the product imported without a Farm Input.
    assert remembered.skipped_rows == (7,)
    assert remembered.tasks[0].details == FertilisationDetails(
        amount=10, unit="t_per_ha", note="Kompost"
    )


def test_a_fertiliser_must_fit_the_amounts_unit() -> None:
    by_mass = KnownInput(
        uuid.uuid4(), "Rindermist", FarmInputKind.FERTILISER, FarmInputUnit.TONNE, False
    )

    result = plan_log(entries=(DEMO_ENTRIES[0],), inputs=[by_mass])

    assert [(u.problem, u.key) for u in result.unresolved] == [
        (Problem.UNIT_MISMATCH, "Rindermist")
    ]


def test_seed_is_created_with_the_land_use_of_its_name() -> None:
    soy = Entry(
        "01.05.2025",
        "2",
        "Sonnenblumen",
        "Aussaat Hauptkultur",
        "Sojabohne (Körner/m²)",
        60.0,
        "Kö/m²",
    )

    result = plan_log(
        entries=(soy,),
        inputs=[],
        resolutions=Resolutions(products={"Sojabohne (Körner/m²)": ProductChoice(create=True)}),
    )

    assert [(n.kind, n.land_use_code) for n in result.new_inputs] == [(FarmInputKind.SEED, "308")]
    assert result.tasks[0].details == SowingDetails(
        purpose="main_crop", rate=60, unit="seeds_per_m2"
    )


@pytest.mark.parametrize(
    "resolutions",
    [
        Resolutions(activities={"Hexen": "tillage"}),
        Resolutions(activities={"Striegeln": "spraying"}),
        Resolutions(products={"Kompost": ProductChoice()}),
        Resolutions(products={"Rindermist": ProductChoice(farm_input_id=uuid.uuid4())}),
        Resolutions(products={"Rindermist": ProductChoice(farm_input_id=RYE_SEED.id)}),
        Resolutions(entries={99: None}),
        Resolutions(entries={7: [uuid.uuid4()]}),
    ],
    ids=[
        "unknown activity",
        "unknown type",
        "unknown product",
        "unknown input",
        "seed for fertilisation",
        "unknown row",
        "unknown plot",
    ],
)
def test_invalid_resolutions_are_refused(resolutions: Resolutions) -> None:
    with pytest.raises(InvalidResolutionError):
        plan_log(resolutions=resolutions)


def test_an_entry_applies_to_every_plot_of_its_fields_with_that_crop() -> None:
    # farmdok logs per Field: two rye Plots on Field 1 and one on Field 2 all get the work.
    second_rye = YearPlot(uuid.uuid4(), 1, 3, "142")
    rye_on_two = YearPlot(uuid.uuid4(), 2, 2, "142")
    harrow = Entry("02.09.2024", "1, 2", "Winterroggen", "Scheibenegge")

    result = plan(
        read_crop_log(crop_log((harrow,))),
        [*PLOTS, second_rye, rye_on_two],
        [],
        TYPES,
        {},
        {},
        Resolutions(),
    )

    assert result.tasks[0].plot_ids == (RYE.id, second_rye.id, rye_on_two.id)


def test_crops_the_admin_assigned_before_find_their_plots() -> None:
    margin = YearPlot(uuid.uuid4(), 3, 1, "361")
    mulch = Entry("01.06.2025", "3", "Sonstige Grünlandfläche", "Schlägeln/Mulchen")

    result = plan(
        read_crop_log(crop_log((mulch,))),
        [*PLOTS, margin],
        [],
        TYPES,
        {},
        {},
        Resolutions(),
        {"Sonstige Grünlandfläche": "361"},
    )

    assert result.tasks[0].plot_ids == (margin.id,)
