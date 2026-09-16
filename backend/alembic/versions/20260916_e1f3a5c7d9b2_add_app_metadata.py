"""add app_metadata table for card-data version

Revision ID: e1f3a5c7d9b2
Revises: d9e2f4a6b8c1
Create Date: 2026-09-16 15:40:00.000000

Adds an isolated key/value ``app_metadata`` table used to persist the local
card-data catalogue version (independent of the application version).

This migration is additive and non-destructive:
- It creates a new table only.
- It NEVER touches cards, sets, collection, profiles, or pokemon_species.
- It seeds a single baseline row: card_data_version = '1', matching the
  card catalogue bundled with PullDex 0.3.1.

The seed uses INSERT OR IGNORE semantics (guarded) so re-running or applying
over a database that somehow already has the key does not overwrite an
existing value.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1f3a5c7d9b2'
down_revision: Union[str, None] = 'd9e2f4a6b8c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The card-data version that ships bundled with this application release.
BASELINE_CARD_DATA_VERSION = "1"


def upgrade() -> None:
    op.create_table(
        "app_metadata",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint("key"),
    )

    # Seed the baseline card-data version, but only if it is not already set.
    # (INSERT OR IGNORE is a no-op if the key already exists.)
    op.execute(
        "INSERT OR IGNORE INTO app_metadata (key, value) "
        f"VALUES ('card_data_version', '{BASELINE_CARD_DATA_VERSION}')"
    )


def downgrade() -> None:
    op.drop_table("app_metadata")
