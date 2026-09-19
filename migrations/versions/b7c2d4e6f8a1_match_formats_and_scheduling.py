"""add tournament scheduling and bracket metadata

Revision ID: b7c2d4e6f8a1
Revises: 9f4b8c1d2e3a
Create Date: 2026-09-19
"""
from alembic import op
import sqlalchemy as sa


revision = 'b7c2d4e6f8a1'
down_revision = '9f4b8c1d2e3a'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('tournaments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('auto_schedule', sa.Boolean(), nullable=False, server_default=sa.text('false')))
        batch_op.add_column(sa.Column('schedule_start_at', sa.DateTime(), nullable=True))

    with op.batch_alter_table('matches', schema=None) as batch_op:
        batch_op.add_column(sa.Column('bracket', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('bracket_slot', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('matches', schema=None) as batch_op:
        batch_op.drop_column('bracket_slot')
        batch_op.drop_column('bracket')

    with op.batch_alter_table('tournaments', schema=None) as batch_op:
        batch_op.drop_column('schedule_start_at')
        batch_op.drop_column('auto_schedule')
