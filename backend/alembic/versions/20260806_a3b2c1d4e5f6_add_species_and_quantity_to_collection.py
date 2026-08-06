"""add pokemon_species_id and quantity to collection

Revision ID: a3b2c1d4e5f6
Revises: 16f5cb78880c
Create Date: 2026-08-06 23:15:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3b2c1d4e5f6'
down_revision: Union[str, None] = '16f5cb78880c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add pokemon_species_id column (nullable FK to pokemon_species.id)
    with op.batch_alter_table('collection') as batch_op:
        batch_op.add_column(
            sa.Column('pokemon_species_id', sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column('quantity', sa.Integer(), nullable=False, server_default='1')
        )
        batch_op.create_index(
            'ix_collection_pokemon_species_id',
            ['pokemon_species_id'],
            unique=False,
        )
        batch_op.create_foreign_key(
            'fk_collection_pokemon_species_id',
            'pokemon_species',
            ['pokemon_species_id'],
            ['id'],
        )

    # Set quantity=1 for all existing rows (they already have card_id set)
    op.execute("UPDATE collection SET quantity = 1 WHERE quantity IS NULL")


def downgrade() -> None:
    with op.batch_alter_table('collection') as batch_op:
        batch_op.drop_constraint('fk_collection_pokemon_species_id', type_='foreignkey')
        batch_op.drop_index('ix_collection_pokemon_species_id')
        batch_op.drop_column('quantity')
        batch_op.drop_column('pokemon_species_id')
