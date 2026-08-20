"""add profiles table and profile_id to collection

Revision ID: b7c9d2e4f1a3
Revises: a3b2c1d4e5f6
Create Date: 2026-08-20 14:00:00.000000

This migration:
1. Creates the `profiles` table
2. Inserts a default 'Default' profile (is_active=True)
3. Adds `profile_id` column to `collection` (nullable initially)
4. Sets all existing collection entries to reference the default profile
5. Rebuilds collection table with profile_id as NOT NULL + FK + index
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'b7c9d2e4f1a3'
down_revision: Union[str, None] = 'a3b2c1d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create profiles table
    op.create_table(
        'profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False,
                  server_default=sa.text("(datetime('now'))")),
        sa.Column('binder_rows', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('binder_columns', sa.Integer(), nullable=False, server_default='4'),
        sa.Column('binder_sort', sqlmodel.sql.sqltypes.AutoString(length=50),
                  nullable=False, server_default='dex_number'),
        sa.PrimaryKeyConstraint('id'),
    )

    # 2. Insert default profile
    op.execute(
        "INSERT INTO profiles (name, is_active, binder_rows, binder_columns, binder_sort) "
        "VALUES ('Default', 1, 5, 4, 'dex_number')"
    )

    # 3. Add profile_id to collection and assign all existing rows to the default profile
    with op.batch_alter_table('collection') as batch_op:
        batch_op.add_column(
            sa.Column('profile_id', sa.Integer(), nullable=True)
        )

    # 4. Set all existing collection entries to reference the default profile
    op.execute(
        "UPDATE collection SET profile_id = (SELECT id FROM profiles WHERE is_active = 1)"
    )

    # 5. Rebuild collection with NOT NULL constraint, FK, and index on profile_id
    with op.batch_alter_table('collection') as batch_op:
        batch_op.alter_column('profile_id', nullable=False)
        batch_op.create_index(
            'ix_collection_profile_id',
            ['profile_id'],
            unique=False,
        )
        batch_op.create_foreign_key(
            'fk_collection_profile_id',
            'profiles',
            ['profile_id'],
            ['id'],
        )


def downgrade() -> None:
    with op.batch_alter_table('collection') as batch_op:
        batch_op.drop_constraint('fk_collection_profile_id', type_='foreignkey')
        batch_op.drop_index('ix_collection_profile_id')
        batch_op.drop_column('profile_id')

    op.drop_table('profiles')
