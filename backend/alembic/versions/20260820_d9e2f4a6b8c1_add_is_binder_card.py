"""add is_binder_card to collection

Revision ID: d9e2f4a6b8c1
Revises: c8d1e3f5a7b9
Create Date: 2026-08-20 16:10:00.000000

Adds is_binder_card boolean to collection table.
For species where exactly one card-level entry exists, auto-selects it.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9e2f4a6b8c1'
down_revision: Union[str, None] = 'c8d1e3f5a7b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add the is_binder_card column
    with op.batch_alter_table('collection') as batch_op:
        batch_op.add_column(
            sa.Column('is_binder_card', sa.Boolean(), nullable=False, server_default='0')
        )

    # Auto-select binder card for species where exactly one card entry exists per profile.
    # Find (profile_id, species_id) combinations with exactly one card entry
    # and mark that entry as the binder card.
    op.execute("""
        UPDATE collection
        SET is_binder_card = 1
        WHERE id IN (
            SELECT c.id
            FROM collection c
            JOIN cards ON c.card_id = cards.id
            WHERE c.card_id IS NOT NULL
            AND (c.profile_id, cards.pokemon_species_id) IN (
                SELECT c2.profile_id, cards2.pokemon_species_id
                FROM collection c2
                JOIN cards cards2 ON c2.card_id = cards2.id
                WHERE c2.card_id IS NOT NULL
                GROUP BY c2.profile_id, cards2.pokemon_species_id
                HAVING COUNT(*) = 1
            )
        )
    """)


def downgrade() -> None:
    with op.batch_alter_table('collection') as batch_op:
        batch_op.drop_column('is_binder_card')
