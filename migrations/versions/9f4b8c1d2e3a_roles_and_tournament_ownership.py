"""add roles, tournament ownership, and match scheduling

Revision ID: 9f4b8c1d2e3a
Revises: 7eb0adb432f5
Create Date: 2026-09-19
"""
from alembic import op
import sqlalchemy as sa


revision = '9f4b8c1d2e3a'
down_revision = '7eb0adb432f5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('role', sa.String(length=20), nullable=False, server_default='player'))

    with op.batch_alter_table('tournaments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('created_by_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_tournaments_created_by_id', 'users', ['created_by_id'], ['id'])

    with op.batch_alter_table('matches', schema=None) as batch_op:
        batch_op.add_column(sa.Column('scheduled_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('matches', schema=None) as batch_op:
        batch_op.drop_column('scheduled_at')

    with op.batch_alter_table('tournaments', schema=None) as batch_op:
        batch_op.drop_constraint('fk_tournaments_created_by_id', type_='foreignkey')
        batch_op.drop_column('created_by_id')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('role')