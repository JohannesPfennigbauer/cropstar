import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, ClassVar

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import (
    CheckConstraint,
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
from sqlalchemy.dialects.postgresql import JSONB
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


class AreaSource(enum.StrEnum):
    """Where the geometry of a Field or Plot came from."""

    # The Farm's own area export from eAMA, uploaded by an Admin.
    EAMA_EXPORT = "eama_export"
    # Public INVEKOS open data (the demo Farm).
    INVEKOS_OPEN_DATA = "invekos_open_data"
    # Provisional: taken from another Harvest Year's areas, for a year without eAMA export.
    BORROWED = "borrowed"
    # Nothing to borrow from: the area is known, its geometry is not.
    NONE = "none"


class ImportKind(enum.StrEnum):
    FARMDOK_FIELD_LIST = "farmdok_field_list"
    FARMDOK_CROP_LOG = "farmdok_crop_log"


class FarmdokTermKind(enum.StrEnum):
    CROP = "crop"
    ACTIVITY = "activity"
    PRODUCT = "product"


class FarmdokAssignment(Base):
    """An Admin's answer to a farmdok crop, activity or product the import did not know,
    remembered for later imports."""

    __tablename__ = "farmdok_assignments"
    __table_args__ = (UniqueConstraint("farm_id", "kind", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"))
    kind: Mapped[FarmdokTermKind] = mapped_column(_pg_enum(FarmdokTermKind, "farmdok_term_kind"))
    # As farmdok names it.
    name: Mapped[str] = mapped_column(String(300))
    # Crops: the AMA Land Use code.
    land_use_code: Mapped[str | None] = mapped_column(String(10))
    # Activities: the Operation Type; null means "skip entries with this activity".
    operation_type: Mapped[str | None] = mapped_column(ForeignKey("operation_types.code"))
    # Products: the Farm Input; null means "import without a Farm Input".
    farm_input_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("farm_inputs.id", ondelete="CASCADE")
    )
    updated_at: Mapped[datetime]


class ImportBatch(Base):
    """One import from another system; undoing it removes everything it created."""

    __tablename__ = "import_batches"
    __table_args__ = (UniqueConstraint("farm_id", "harvest_year", "kind"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"))
    harvest_year: Mapped[int] = mapped_column(SmallInteger)
    kind: Mapped[ImportKind] = mapped_column(_pg_enum(ImportKind, "import_kind"))
    # The uploaded report's file name, for recognising it later; the file is not kept.
    source_name: Mapped[str] = mapped_column(String(300))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime]


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
        UniqueConstraint(
            "farm_id", "harvest_year", "number", deferrable=True, initially="DEFERRED"
        ),
        Index("ix_fields_farm_id_harvest_year", "farm_id", "harvest_year"),
        CheckConstraint(
            "(geometry IS NULL) = (geometry_source::text = 'none')", name="geometry_only_when_known"
        ),
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
    # Missing exactly when the source is "none".
    geometry: Mapped[WKBElement | None] = mapped_column(
        Geometry("MULTIPOLYGON", srid=AMA_SRID, spatial_index=True)
    )
    geometry_source: Mapped[AreaSource] = mapped_column(_pg_enum(AreaSource, "area_source"))
    # The Harvest Year borrowed geometry comes from.
    borrowed_from_year: Mapped[int | None] = mapped_column(SmallInteger)
    imported_at: Mapped[datetime]
    import_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("import_batches.id", ondelete="SET NULL"), index=True
    )

    plots: Mapped[list["Plot"]] = relationship(back_populates="field", cascade="all, delete")


class Plot(Base):
    """A Schlag as declared to AMA: part of a Field, one Land Use, one Harvest Year."""

    __tablename__ = "plots"
    __table_args__ = (
        UniqueConstraint("field_id", "number", deferrable=True, initially="DEFERRED"),
        CheckConstraint(
            "(geometry IS NULL) = (geometry_source::text = 'none')", name="geometry_only_when_known"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    field_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("fields.id", ondelete="CASCADE"), index=True
    )
    number: Mapped[int]
    name: Mapped[str | None] = mapped_column(String(200))
    land_use_code: Mapped[str] = mapped_column(String(10))
    land_use_name: Mapped[str] = mapped_column(String(200))
    declared_area_ha: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    # Missing exactly when the source is "none".
    geometry: Mapped[WKBElement | None] = mapped_column(
        Geometry("MULTIPOLYGON", srid=AMA_SRID, spatial_index=True)
    )
    geometry_source: Mapped[AreaSource] = mapped_column(_pg_enum(AreaSource, "area_source"))
    # The Harvest Year borrowed geometry comes from.
    borrowed_from_year: Mapped[int | None] = mapped_column(SmallInteger)
    imported_at: Mapped[datetime]
    import_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("import_batches.id", ondelete="SET NULL"), index=True
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


class TaskStage(Base):
    """A step of the not-yet-done phase, e.g. Geplant, Offen, In Arbeit; named and ordered per
    Farm. Done and Discarded are not stages: they are what happened, with fixed meaning."""

    __tablename__ = "task_stages"
    __table_args__ = (Index("ix_task_stages_farm_id_position", "farm_id", "position"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(60))
    position: Mapped[int] = mapped_column(SmallInteger)


# A new Farm starts with these stages, in this order.
DEFAULT_TASK_STAGES = ("Geplant", "Offen", "In Arbeit")


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
    # Set when an import created the Task; undoing the import removes it.
    import_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("import_batches.id", ondelete="SET NULL"), index=True
    )
    # Where an Open Task stands on the board; kept while Done, so reopening returns there.
    stage_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("task_stages.id", ondelete="SET NULL"), index=True
    )
    # The template copied into each Operation's Planned Details; see `operation_details`.
    planned_details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

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
    planned_details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # What really happened; kept as a draft when a Done Operation is reopened.
    actual_details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # The day the work was done, which may be long before it was recorded.
    performed_on: Mapped[date | None]
    completed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    completed_at: Mapped[datetime | None]

    task: Mapped[Task] = relationship(back_populates="operations")
    plot: Mapped[Plot] = relationship()


class FarmInputKind(enum.StrEnum):
    FERTILISER = "fertiliser"
    SEED = "seed"
    OTHER = "other"


class FarmInputUnit(enum.StrEnum):
    """What a fertiliser's nutrient contents refer to."""

    TONNE = "t"
    CUBIC_METRE = "m3"
    # Per 100 kg, the contents read as percentages, as mineral fertilisers declare them.
    HUNDRED_KG = "100kg"


class ValueSource(enum.StrEnum):
    """Where a Farm Input's nutrient contents come from."""

    STANDARD_VALUE = "standard_value"
    LAB_ANALYSIS = "lab_analysis"
    MANUFACTURER = "manufacturer"


class FarmInput(Base):
    """A fertiliser, seed or other input a Farm uses; Operations refer to it."""

    __tablename__ = "farm_inputs"
    __table_args__ = (Index("ix_farm_inputs_farm_id_kind", "farm_id", "kind"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"))
    kind: Mapped[FarmInputKind] = mapped_column(_pg_enum(FarmInputKind, "farm_input_kind"))
    name: Mapped[str] = mapped_column(String(200))
    note: Mapped[str | None] = mapped_column(Text)

    # Fertilisers: contents per unit, in kg, except dry matter in percent.
    unit: Mapped[FarmInputUnit | None] = mapped_column(_pg_enum(FarmInputUnit, "farm_input_unit"))
    dry_matter_percent: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    total_n: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    # Plant-available N in the year of application (jahreswirksamer N).
    available_n: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    p2o5: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    k2o: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    value_source: Mapped[ValueSource | None] = mapped_column(_pg_enum(ValueSource, "value_source"))
    # The standard, lab or product sheet the values come from.
    source_reference: Mapped[str | None] = mapped_column(String(500))
    analysed_on: Mapped[date | None]
    # The catalogue entry the values were copied from, if any; the copy is independent.
    catalogue_entry: Mapped[str | None] = mapped_column(String(50))

    # Seed.
    land_use_code: Mapped[str | None] = mapped_column(String(10))
    land_use_name: Mapped[str | None] = mapped_column(String(200))
    variety: Mapped[str | None] = mapped_column(String(200))
    thousand_kernel_weight_g: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))

    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    # Archived inputs stay on past records but are no longer offered.
    archived_at: Mapped[datetime | None]
