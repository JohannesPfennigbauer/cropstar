"""Invitations and AMA farm number

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invitations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("farm_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        # The role type already exists (memberships); reuse it.
        sa.Column("role", postgresql.ENUM(name="role", create_type=False), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_by_id", sa.Uuid(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["accepted_by_id"],
            ["users.id"],
            name=op.f("fk_invitations_accepted_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_invitations_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["farm_id"], ["farms.id"], name=op.f("fk_invitations_farm_id_farms"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invitations")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_invitations_token_hash")),
    )
    op.create_index(op.f("ix_invitations_farm_id"), "invitations", ["farm_id"], unique=False)
    op.add_column("farms", sa.Column("ama_farm_number", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("farms", "ama_farm_number")
    op.drop_index(op.f("ix_invitations_farm_id"), table_name="invitations")
    op.drop_table("invitations")
