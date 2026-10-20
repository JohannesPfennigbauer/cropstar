import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, ClassVar

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    MetaData,
    Numeric,
    SmallInteger,
    String,
    Table,
    Text,
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

    # The database cascades deletes; the ORM must not try to blank the keys first.
    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )


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
    # Sensitive: shown to Admins only.
    ama_farm_number: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="farm", cascade="all, delete-orphan", passive_deletes=True
    )


class Role(enum.StrEnum):
    ADMIN = "admin"
    WORKER = "worker"
    ADVISOR = "advisor"


def _pg_enum(enum_type: type[enum.StrEnum], name: str) -> Enum:
    # Store the lower-case values, not the Python member names.
    return Enum(enum_type, name=name, values_callable=lambda members: [m.value for m in members])


class Membership(Base):
    """The link between one User and one Farm, carrying exactly one Role."""

    __tablename__ = "memberships"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("farms.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    role: Mapped[Role] = mapped_column(_pg_enum(Role, "role"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    farm: Mapped[Farm] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="memberships")


class Invitation(Base):
    """A single-use, expiring link to join a Farm in a Role. Only a hash of it is stored."""

    __tablename__ = "invitations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("farms.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    role: Mapped[Role] = mapped_column(_pg_enum(Role, "role"))
    # Where the link was emailed to, if it was; anyone holding the link may accept it.
    email: Mapped[str | None] = mapped_column(String(320))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime]
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]
    accepted_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    accepted_at: Mapped[datetime | None]


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


class HarvestYearLock(Base):
    """A closed season: while it exists, everything referring to the Harvest Year is read-only."""

    __tablename__ = "harvest_year_locks"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("farms.id", ondelete="CASCADE"), primary_key=True
    )
    harvest_year: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    locked_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    locked_at: Mapped[datetime]

    locked_by: Mapped[User | None] = relationship()


class TaskStatus(enum.StrEnum):
    OPEN = "open"
    DONE = "done"
    DISCARDED = "discarded"


class Priority(enum.StrEnum):
    NONE = "none"
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class OperationType(Base):
    """A kind of work the model and reports understand. The same list for every Farm."""

    __tablename__ = "operation_types"

    code: Mapped[str] = mapped_column(String(30), primary_key=True)
    position: Mapped[int] = mapped_column(SmallInteger)


task_fields = Table(
    "task_fields",
    Base.metadata,
    Column("task_id", ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
    Column("field_id", ForeignKey("fields.id", ondelete="CASCADE"), primary_key=True, index=True),
)

task_plots = Table(
    "task_plots",
    Base.metadata,
    Column("task_id", ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
    Column("plot_id", ForeignKey("plots.id", ondelete="CASCADE"), primary_key=True, index=True),
)


class Task(Base):
    """Any piece of work on a Farm that someone intends to do or has done."""

    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_farm_id_status", "farm_id", "status"),
        Index("ix_tasks_farm_id_harvest_year", "farm_id", "harvest_year"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    due_date: Mapped[date | None]
    priority: Mapped[Priority] = mapped_column(_pg_enum(Priority, "priority"))
    status: Mapped[TaskStatus] = mapped_column(_pg_enum(TaskStatus, "task_status"))
    # People references survive account deletion as NULL: shown as "former member".
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    completed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    completed_at: Mapped[datetime | None]
    # Derived from the Fields and Plots below: set exactly when the Task refers to areas.
    harvest_year: Mapped[int | None] = mapped_column(SmallInteger)
    # With an Operation Type the Task holds one Operation per Plot; fixed at creation.
    operation_type: Mapped[str | None] = mapped_column(ForeignKey("operation_types.code"))
    # The template copied into each Operation's Planned Details.
    planned_details: Mapped[str | None] = mapped_column(Text)

    fields: Mapped[list[Field]] = relationship(secondary=task_fields, order_by=Field.number)
    plots: Mapped[list[Plot]] = relationship(secondary=task_plots)
    operations: Mapped[list["Operation"]] = relationship(
        back_populates="task", cascade="all, delete-orphan", passive_deletes=True
    )


class Operation(Base):
    """The Plot-specific part of a Task that has an Operation Type."""

    __tablename__ = "operations"
    __table_args__ = (UniqueConstraint("task_id", "plot_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    plot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("plots.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[TaskStatus] = mapped_column(_pg_enum(TaskStatus, "task_status"))
    planned_details: Mapped[str | None] = mapped_column(Text)
    # What really happened; kept as a draft when a Done Operation is reopened.
    actual_details: Mapped[str | None] = mapped_column(Text)
    # The day the work was done, which may be long before it was recorded.
    performed_on: Mapped[date | None]
    completed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    completed_at: Mapped[datetime | None]

    task: Mapped[Task] = relationship(back_populates="operations")
    plot: Mapped[Plot] = relationship()
