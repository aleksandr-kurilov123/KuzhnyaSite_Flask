"""tournament specific teams

Revision ID: d1f3c7a22b90
Revises: b7c2d4e6f8a1
Create Date: 2026-09-19
"""
from alembic import op
import sqlalchemy as sa


revision = 'd1f3c7a22b90'
down_revision = 'b7c2d4e6f8a1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'tournament_teams',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tournament_id', sa.Integer(), nullable=False),
        sa.Column('team_name', sa.String(length=30), nullable=False),
        sa.Column('captain_id', sa.Integer(), nullable=False),
        sa.Column('join_token', sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(['captain_id'], ['users.id'], name='fk_tournament_team_captain_id'),
        sa.ForeignKeyConstraint(['tournament_id'], ['tournaments.id'], name='fk_tournament_team_tournament_id'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('join_token', name='uq_tournament_teams_join_token'),
        sa.UniqueConstraint('tournament_id', 'team_name', name='uq_tournament_team_name'),
    )

    op.create_table(
        'tournament_team_members',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tournament_team_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['tournament_team_id'], ['tournament_teams.id'], name='fk_tournament_team_members_team_id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_tournament_team_members_user_id'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tournament_team_id', 'user_id', name='uq_tournament_team_member'),
    )

    with op.batch_alter_table('matches', schema=None) as batch_op:
        batch_op.add_column(sa.Column('team_a_tournament_team_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('team_b_tournament_team_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('winner_tournament_team_id', sa.Integer(), nullable=True))

        batch_op.create_foreign_key('fk_matches_team_a_tournament_team', 'tournament_teams', ['team_a_tournament_team_id'], ['id'])
        batch_op.create_foreign_key('fk_matches_team_b_tournament_team', 'tournament_teams', ['team_b_tournament_team_id'], ['id'])
        batch_op.create_foreign_key('fk_matches_winner_tournament_team', 'tournament_teams', ['winner_tournament_team_id'], ['id'])

    with op.batch_alter_table('tournaments', schema=None) as batch_op:
        batch_op.drop_constraint('fk_tournament_teams_tournament_id', type_='foreignkey')

    op.execute('ALTER TABLE matches DROP CONSTRAINT IF EXISTS fk_matches_team_a_id')
    op.execute('ALTER TABLE matches DROP CONSTRAINT IF EXISTS fk_matches_team_b_id')
    op.execute('ALTER TABLE matches DROP CONSTRAINT IF EXISTS fk_matches_winner_id')

    with op.batch_alter_table('matches', schema=None) as batch_op:
        batch_op.drop_column('team_a_id')
        batch_op.drop_column('team_b_id')
        batch_op.drop_column('winner_id')

    with op.batch_alter_table('matches', schema=None) as batch_op:
        batch_op.alter_column('team_a_tournament_team_id', new_column_name='team_a_id')
        batch_op.alter_column('team_b_tournament_team_id', new_column_name='team_b_id')
        batch_op.alter_column('winner_tournament_team_id', new_column_name='winner_id')

    with op.batch_alter_table('matches', schema=None) as batch_op:
        batch_op.create_foreign_key('fk_matches_team_a_id', 'tournament_teams', ['team_a_id'], ['id'])
        batch_op.create_foreign_key('fk_matches_team_b_id', 'tournament_teams', ['team_b_id'], ['id'])
        batch_op.create_foreign_key('fk_matches_winner_id', 'tournament_teams', ['winner_id'], ['id'])


def downgrade():
    with op.batch_alter_table('matches', schema=None) as batch_op:
        batch_op.drop_constraint('fk_matches_winner_id', type_='foreignkey')
        batch_op.drop_constraint('fk_matches_team_b_id', type_='foreignkey')
        batch_op.drop_constraint('fk_matches_team_a_id', type_='foreignkey')

    with op.batch_alter_table('matches', schema=None) as batch_op:
        batch_op.add_column(sa.Column('team_a_legacy_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('team_b_legacy_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('winner_legacy_id', sa.Integer(), nullable=True))

    with op.batch_alter_table('matches', schema=None) as batch_op:
        batch_op.alter_column('team_a_id', new_column_name='team_a_legacy_id')
        batch_op.alter_column('team_b_id', new_column_name='team_b_legacy_id')
        batch_op.alter_column('winner_id', new_column_name='winner_legacy_id')

    with op.batch_alter_table('matches', schema=None) as batch_op:
        batch_op.add_column(sa.Column('team_a_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('team_b_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('winner_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_matches_team_a_id_legacy', 'teams', ['team_a_id'], ['id'])
        batch_op.create_foreign_key('fk_matches_team_b_id_legacy', 'teams', ['team_b_id'], ['id'])
        batch_op.create_foreign_key('fk_matches_winner_id_legacy', 'teams', ['winner_id'], ['id'])

    op.drop_table('tournament_team_members')
    op.drop_table('tournament_teams')
