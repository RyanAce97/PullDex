"""add unique constraint on collection (profile_id, card_id)

Revision ID: c8d1e3f5a7b9
Revises: b7c9d2e4f1a3
Create Date: 2026-08-20 15:30:00.000000

Ensures that each card can only appear once per profile in the collection
table. This prevents import/merge operations from accidentally creating
duplicate rows.

Note: The constraint only applies where card_id IS NOT NULL (species-level
entries have card_id=NULL and are not constrained by this index).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8d1e3f5a7b9'
down_revision: Union[str, None] = 'b7c9d2e4f1a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create a unique index on (profile_id, card_id) WHERE card_id IS NOT NULL.
    # SQLite doesn't support partial unique indexes via batch_alter_table,
    # so we use a standard CREATE UNIQUE INDEX with a WHERE clause.
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_collection_profile_card "
        "ON collection (profile_id, card_id) WHERE card_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_collection_profile_card")
