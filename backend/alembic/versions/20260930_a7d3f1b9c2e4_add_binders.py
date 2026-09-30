"""add binders and binder_placements

Revision ID: a7d3f1b9c2e4
Revises: f2a4b6c8d0e1
Create Date: 2026-09-30 19:40:00.000000

Introduces the multi-binder system.

This migration is ADDITIVE and NON-DESTRUCTIVE:

- Creates ``binders`` and ``binder_placements`` tables.
- For every existing profile, seeds exactly one default ``POKEDEX`` binder
  named "Pokédex Binder", copying the profile's existing
  ``binder_rows`` / ``binder_columns`` / ``binder_sort`` so the migrated
  binder is visually identical to what the user had before.
- It NEVER touches ``collection`` (``is_binder_card`` is preserved),
  ``cards``, ``pokemon_species``, ``sets``, ``app_metadata`` or the existing
  ``profiles.binder_*`` columns. Those columns are intentionally retained for
  backward compatibility and as the source for the seeded layout.

Downgrade drops the two new tables only; no user data is affected.
"""
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a7d3f1b9c2e4"
down_revision: Union[str, None] = "f2a4b6c8d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEFAULT_POKEDEX_BINDER_NAME = "Pokédex Binder"


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Create tables
    # ------------------------------------------------------------------
    op.create_table(
        "binders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("binder_type", sa.String(length=20), nullable=False),
        sa.Column("rows", sa.Integer(), nullable=False),
        sa.Column("columns", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.String(length=50), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_binders_profile_id"), "binders", ["profile_id"], unique=False)
    op.create_index(op.f("ix_binders_binder_type"), "binders", ["binder_type"], unique=False)
    op.create_index(op.f("ix_binders_is_default"), "binders", ["is_default"], unique=False)

    op.create_table(
        "binder_placements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("binder_id", sa.Integer(), nullable=False),
        sa.Column("card_id", sa.Integer(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("slot", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["binder_id"], ["binders.id"]),
        sa.ForeignKeyConstraint(["card_id"], ["cards.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("binder_id", "page", "slot", name="uq_placement_binder_page_slot"),
        sa.UniqueConstraint("binder_id", "card_id", name="uq_placement_binder_card"),
    )
    op.create_index(
        op.f("ix_binder_placements_binder_id"), "binder_placements", ["binder_id"], unique=False
    )
    op.create_index(
        op.f("ix_binder_placements_card_id"), "binder_placements", ["card_id"], unique=False
    )

    # ------------------------------------------------------------------
    # 2. Seed one default POKEDEX binder per existing profile
    # ------------------------------------------------------------------
    # Read each profile's existing binder layout and copy it verbatim so the
    # migrated binder matches what the user saw before. This only reads
    # ``profiles`` and only writes to the freshly created ``binders`` table.
    conn = op.get_bind()

    profiles = conn.execute(
        sa.text(
            "SELECT id, binder_rows, binder_columns, binder_sort FROM profiles"
        )
    ).fetchall()

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    insert_stmt = sa.text(
        "INSERT INTO binders "
        "(profile_id, name, binder_type, rows, columns, sort_order, is_default, created_at) "
        "VALUES (:profile_id, :name, :binder_type, :rows, :columns, :sort_order, :is_default, :created_at)"
    )

    for row in profiles:
        profile_id = row[0]
        rows = row[1] if row[1] is not None else 5
        columns = row[2] if row[2] is not None else 4
        sort_order = row[3] if row[3] is not None else "dex_number"

        conn.execute(
            insert_stmt,
            {
                "profile_id": profile_id,
                "name": DEFAULT_POKEDEX_BINDER_NAME,
                "binder_type": "POKEDEX",
                "rows": rows,
                "columns": columns,
                "sort_order": sort_order,
                "is_default": True,
                "created_at": now,
            },
        )


def downgrade() -> None:
    op.drop_index(op.f("ix_binder_placements_card_id"), table_name="binder_placements")
    op.drop_index(op.f("ix_binder_placements_binder_id"), table_name="binder_placements")
    op.drop_table("binder_placements")

    op.drop_index(op.f("ix_binders_is_default"), table_name="binders")
    op.drop_index(op.f("ix_binders_binder_type"), table_name="binders")
    op.drop_index(op.f("ix_binders_profile_id"), table_name="binders")
    op.drop_table("binders")
