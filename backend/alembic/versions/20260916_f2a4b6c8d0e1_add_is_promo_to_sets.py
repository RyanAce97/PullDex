"""add is_promo to sets

Revision ID: f2a4b6c8d0e1
Revises: e1f3a5c7d9b2
Create Date: 2026-09-16 21:15:00.000000

Adds an explicit ``is_promo`` boolean to the ``sets`` table.

Promotional status is EXPLICIT reference data sourced from the public
card-data catalogue (``sets/<id>.json`` → ``set.is_promo``, mirrored in
``manifest.json``). It is never inferred from the set name or series.

This migration is additive and non-destructive:
- It adds one column to ``sets`` with a server-side default of 0 (false), so
  every existing set row becomes ``is_promo = false``.
- It NEVER touches cards, collection, profiles, pokemon_species, or
  app_metadata — no user data is read or modified.
- The card-data updater / seeding path is responsible for subsequently
  setting the correct per-set value from the catalogue.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f2a4b6c8d0e1"
down_revision: Union[str, None] = "e1f3a5c7d9b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add the column with a server default so all existing rows become false.
    op.add_column(
        "sets",
        sa.Column(
            "is_promo",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_index(op.f("ix_sets_is_promo"), "sets", ["is_promo"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_sets_is_promo"), table_name="sets")
    op.drop_column("sets", "is_promo")
