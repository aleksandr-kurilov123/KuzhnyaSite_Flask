"""remove legacy global teams

Revision ID: e4a8b6c0d2f1
Revises: d1f3c7a22b90
Create Date: 2026-09-19
"""
from alembic import op


revision = 'e4a8b6c0d2f1'
down_revision = 'd1f3c7a22b90'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('ALTER TABLE users DROP CONSTRAINT IF EXISTS fk_users_team_id')
    op.execute('ALTER TABLE tournament_teams DROP CONSTRAINT IF EXISTS fk_tournament_team_legacy_team_id')
    op.execute('ALTER TABLE users DROP COLUMN IF EXISTS team_id')
    op.execute('ALTER TABLE tournament_teams DROP COLUMN IF EXISTS legacy_team_id')
    op.execute('DROP TABLE IF EXISTS teams')


def downgrade():
    raise RuntimeError(
        'The legacy global teams structure was intentionally removed and cannot be restored automatically.'
    )
