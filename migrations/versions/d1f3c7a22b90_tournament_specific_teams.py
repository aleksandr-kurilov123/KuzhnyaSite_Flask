"""tournament specific teams

Revision ID: d1f3c7a22b90
Revises: b7c2d4e6f8a1
Create Date: 2026-09-19
"""
from alembic import op
import sqlalchemy as sa
import uuid


revision = 'd1f3c7a22b90'
down_revision = 'b7c2d4e6f8a1'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    had_legacy_join_table = False

    # Before this migration, tournament_teams was the many-to-many join table.
    # Preserve those links temporarily while replacing it with a real entity.
    if 'tournament_teams' in inspector.get_table_names():
        columns = {column['name'] for column in inspector.get_columns('tournament_teams')}
        if 'id' not in columns and 'team_id' in columns:
            op.rename_table('tournament_teams', 'legacy_tournament_teams')
            had_legacy_join_table = True

    op.execute(
        'ALTER TABLE teams ADD COLUMN IF NOT EXISTS '
        'looking_for_members BOOLEAN NOT NULL DEFAULT FALSE'
    )

    op.create_table(
        'tournament_teams',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tournament_id', sa.Integer(), nullable=False),
        sa.Column('legacy_team_id', sa.Integer(), nullable=True),
        sa.Column('team_name', sa.String(length=30), nullable=False),
        sa.Column('captain_id', sa.Integer(), nullable=False),
        sa.Column('join_token', sa.String(length=36), nullable=False),
        sa.Column('looking_for_members', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.ForeignKeyConstraint(['legacy_team_id'], ['teams.id'], name='fk_tournament_team_legacy_team_id'),
        sa.ForeignKeyConstraint(['captain_id'], ['users.id'], name='fk_tournament_team_captain_id'),
        sa.ForeignKeyConstraint(['tournament_id'], ['tournaments.id'], name='fk_tournament_team_tournament_id'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('join_token', name='uq_tournament_teams_join_token'),
        sa.UniqueConstraint('tournament_id', 'team_name', name='uq_tournament_team_name'),
    )

    if had_legacy_join_table:
        legacy_rows = bind.execute(sa.text(
            'SELECT tournament_id, team_id FROM legacy_tournament_teams'
        )).mappings().all()
        inserted = []
        for row in legacy_rows:
            team = bind.execute(sa.text(
                'SELECT team_name, captain_id, looking_for_members '
                'FROM teams WHERE id = :team_id'
            ), {'team_id': row['team_id']}).mappings().first()
            if not team or team['captain_id'] is None:
                continue
            tournament_team_id = bind.execute(sa.text(
                'INSERT INTO tournament_teams '
                '(tournament_id, legacy_team_id, team_name, captain_id, join_token, looking_for_members) '
                'VALUES (:tournament_id, :legacy_team_id, :team_name, :captain_id, :join_token, :looking_for_members) '
                'RETURNING id'
            ), {
                'tournament_id': row['tournament_id'],
                'legacy_team_id': row['team_id'],
                'team_name': team['team_name'],
                'captain_id': team['captain_id'],
                'join_token': str(uuid.uuid4()),
                'looking_for_members': team['looking_for_members'] or False,
            }).scalar_one()
            inserted.append((row['team_id'], tournament_team_id))

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

        for legacy_team_id, tournament_team_id in inserted:
            bind.execute(sa.text(
                'INSERT INTO tournament_team_members (tournament_team_id, user_id) '
                'SELECT :tournament_team_id, id FROM users WHERE team_id = :legacy_team_id '
                'ON CONFLICT DO NOTHING'
            ), {
                'tournament_team_id': tournament_team_id,
                'legacy_team_id': legacy_team_id,
            })
    else:
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

    op.execute('ALTER TABLE matches DROP CONSTRAINT IF EXISTS fk_matches_team_a_id')
    op.execute('ALTER TABLE matches DROP CONSTRAINT IF EXISTS fk_matches_team_b_id')
    op.execute('ALTER TABLE matches DROP CONSTRAINT IF EXISTS fk_matches_winner_id')
    op.execute('ALTER TABLE matches ADD COLUMN team_a_new_id INTEGER')
    op.execute('ALTER TABLE matches ADD COLUMN team_b_new_id INTEGER')
    op.execute('ALTER TABLE matches ADD COLUMN winner_new_id INTEGER')
    op.execute('''
        UPDATE matches AS m SET team_a_new_id = tt.id
        FROM tournament_teams AS tt
        WHERE tt.tournament_id = m.tournament_id AND tt.legacy_team_id = m.team_a_id
    ''')
    op.execute('''
        UPDATE matches AS m SET team_b_new_id = tt.id
        FROM tournament_teams AS tt
        WHERE tt.tournament_id = m.tournament_id AND tt.legacy_team_id = m.team_b_id
    ''')
    op.execute('''
        UPDATE matches AS m SET winner_new_id = tt.id
        FROM tournament_teams AS tt
        WHERE tt.tournament_id = m.tournament_id AND tt.legacy_team_id = m.winner_id
    ''')
    op.execute('ALTER TABLE matches DROP COLUMN team_a_id')
    op.execute('ALTER TABLE matches DROP COLUMN team_b_id')
    op.execute('ALTER TABLE matches DROP COLUMN winner_id')
    op.execute('ALTER TABLE matches RENAME COLUMN team_a_new_id TO team_a_id')
    op.execute('ALTER TABLE matches RENAME COLUMN team_b_new_id TO team_b_id')
    op.execute('ALTER TABLE matches RENAME COLUMN winner_new_id TO winner_id')
    op.create_foreign_key('fk_matches_team_a_id', 'matches', 'tournament_teams', ['team_a_id'], ['id'])
    op.create_foreign_key('fk_matches_team_b_id', 'matches', 'tournament_teams', ['team_b_id'], ['id'])
    op.create_foreign_key('fk_matches_winner_id', 'matches', 'tournament_teams', ['winner_id'], ['id'])

    if had_legacy_join_table:
        op.drop_table('legacy_tournament_teams')


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
