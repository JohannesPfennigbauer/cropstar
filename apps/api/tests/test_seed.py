import io
from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from cropstar_api.auth.provider import PasswordAuthProvider
from cropstar_api.cli import main
from cropstar_api.models import Farm, Field, Membership, Plot, Role
from cropstar_api.seed import DEMO_FARM_NAME, seed_demo


def counts(db: Session) -> tuple[int, int, int]:
    return (
        db.scalar(select(func.count(Farm.id))) or 0,
        db.scalar(select(func.count(Field.id))) or 0,
        db.scalar(select(func.count(Plot.id))) or 0,
    )


def test_seeding_twice_replaces_instead_of_duplicating(db: Session) -> None:
    auth = PasswordAuthProvider(timedelta(days=1))

    first = seed_demo(db, auth, "demo@example.at", "cropstar-demo")
    second = seed_demo(db, auth, "demo@example.at", "cropstar-demo")

    assert first.id == second.id
    assert counts(db) == (1, 2, 4)
    membership = db.scalar(select(Membership).where(Membership.farm_id == first.id))
    assert membership is not None
    assert membership.role is Role.ADMIN
    assert first.name == DEMO_FARM_NAME


def test_seeded_geometries_are_valid_and_match_the_declared_areas(db: Session) -> None:
    seed_demo(db, PasswordAuthProvider(timedelta(days=1)), "demo@example.at", "cropstar-demo")

    rows = db.execute(
        select(
            Plot.land_use_name,
            Plot.declared_area_ha,
            func.ST_IsValid(Plot.geometry),
            func.ST_Area(Plot.geometry) / 10_000,
        )
    ).all()

    assert len(rows) == 4
    for name, declared, valid, computed in rows:
        assert valid, name
        assert float(computed) == pytest.approx(float(declared), abs=0.001), name


def test_seed_command_refuses_outside_development(
    database_url: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CROPSTAR_DATABASE_URL", database_url)
    monkeypatch.setenv("CROPSTAR_ENVIRONMENT", "production")
    monkeypatch.setattr("sys.stdin", io.StringIO(""))

    with pytest.raises(SystemExit) as exit_info:
        main(["seed-demo"])

    assert exit_info.value.code == 1
    assert "CROPSTAR_ENVIRONMENT=development" in capsys.readouterr().err


def test_seed_command_in_development(
    database_url: str, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CROPSTAR_DATABASE_URL", database_url)
    monkeypatch.setenv("CROPSTAR_ENVIRONMENT", "development")

    with pytest.raises(SystemExit) as exit_info:
        main(["seed-demo", "--email", "demo@example.at"])

    assert exit_info.value.code == 0
    assert counts(db) == (1, 2, 4)
