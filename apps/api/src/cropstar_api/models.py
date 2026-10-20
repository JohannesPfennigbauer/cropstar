import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, ClassVar

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    MetaData,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Stable constraint names keep Alembic migrations reviewable and reversible.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map: ClassVar[dict[Any, Any]] = {datetime: DateTime(timezone=True)}


class User(Base):
    """A person who can sign in. Carries no credentials; those belong to an AuthProvider."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Stored normalised (trimmed, lower-case) so uniqueness is case-insensitive.
    email: Mapped[str] = mapped_column(String(320), unique=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    memberships: Mapped[list["Membership"]] = relationship(back_populates="user")


class PasswordCredential(Base):
    """The built-in AuthProvider's password for a User."""

    __tablename__ = "password_credentials"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    password_hash: Mapped[str] = mapped_column(String(255))
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Session(Base):
    """A signed-in browser. Only a hash of the cookie token is stored."""

    __tablename__ = "sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime]


class PasswordResetToken(Base):
    """A single-use, expiring permission to set a new password. Only a hash is stored."""

    __tablename__ = "password_reset_tokens"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime]
    used_at: Mapped[datetime | None]


class Farm(Base):
    """The agricultural holding that owns all farm data."""

    __tablename__ = "farms"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    memberships: Mapped[list["Membership"]] = relationship(back_populates="farm")


class Role(enum.StrEnum):
    ADMIN = "admin"
    WORKER = "worker"
    ADVISOR = "advisor"


class Membership(Base):
    """The link between one User and one Farm, carrying exactly one Role."""

    __tablename__ = "memberships"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("farms.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    role: Mapped[Role] = mapped_column(
        Enum(Role, name="role", values_callable=lambda roles: [r.value for r in roles])
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    farm: Mapped[Farm] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="memberships")


# Geometry is stored as AMA delivers it: MGI / Austria Lambert. The API converts to WGS84.
AMA_SRID = 31287


class Field(Base):
    """A Feldstück as declared to AMA for one Harvest Year."""

    __tablename__ = "fields"
    __table_args__ = (
        UniqueConstraint("farm_id", "harvest_year", "number"),
        Index("ix_fields_farm_id_harvest_year", "farm_id", "harvest_year"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"))
    harvest_year: Mapped[int] = mapped_column(SmallInteger)
    # The farmer's AMA field number; only unique within one Farm and Harvest Year.
    number: Mapped[int]
    name: Mapped[str | None] = mapped_column(String(200))
    land_use_code: Mapped[str] = mapped_column(String(10))
    land_use_name: Mapped[str] = mapped_column(String(200))
    declared_area_ha: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    geometry: Mapped[WKBElement] = mapped_column(
        Geometry("MULTIPOLYGON", srid=AMA_SRID, spatial_index=True)
    )

    plots: Mapped[list["Plot"]] = relationship(back_populates="field", cascade="all, delete")


class Plot(Base):
    """A Schlag as declared to AMA: part of a Field, one Land Use, one Harvest Year."""

    __tablename__ = "plots"
    __table_args__ = (UniqueConstraint("field_id", "number"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    field_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("fields.id", ondelete="CASCADE"), index=True
    )
    number: Mapped[int]
    name: Mapped[str | None] = mapped_column(String(200))
    land_use_code: Mapped[str] = mapped_column(String(10))
    land_use_name: Mapped[str] = mapped_column(String(200))
    declared_area_ha: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    geometry: Mapped[WKBElement] = mapped_column(
        Geometry("MULTIPOLYGON", srid=AMA_SRID, spatial_index=True)
    )

    field: Mapped[Field] = relationship(back_populates="plots")
