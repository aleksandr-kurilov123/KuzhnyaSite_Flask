from flask_login import UserMixin
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from . import db
import uuid
# Association table for many-to-many relationship between users and games
user_games = db.Table('user_games',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id', name='fk_user_games_user_id'), primary_key=True),
    db.Column('game_id', db.Integer, db.ForeignKey('games.id', name='fk_user_games_game_id'), primary_key=True)
)

class TournamentTeamMember(db.Model):
    __tablename__ = 'tournament_team_members'

    id = db.Column(db.Integer, primary_key=True)
    tournament_team_id = db.Column(db.Integer, db.ForeignKey('tournament_teams.id', name='fk_tournament_team_members_team_id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', name='fk_tournament_team_members_user_id'), nullable=False)

    tournament_team = db.relationship('TournamentTeam', back_populates='members')
    user = db.relationship('Users', back_populates='tournament_team_memberships')

    __table_args__ = (
        db.UniqueConstraint('tournament_team_id', 'user_id', name='uq_tournament_team_member'),
    )


class TournamentTeam(db.Model):
    __tablename__ = 'tournament_teams'

    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey('tournaments.id', name='fk_tournament_team_tournament_id'), nullable=False)
    legacy_team_id = db.Column(db.Integer, db.ForeignKey('teams.id', name='fk_tournament_team_legacy_team_id'), nullable=True)
    team_name = db.Column(db.String(30), nullable=False)
    captain_id = db.Column(db.Integer, db.ForeignKey('users.id', name='fk_tournament_team_captain_id'), nullable=False)
    join_token = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    looking_for_members = db.Column(db.Boolean, nullable=False, default=False)

    tournament = db.relationship('Tournaments', back_populates='teams')
    legacy_team = db.relationship('Teams', foreign_keys=[legacy_team_id], backref='legacy_tournament_teams')
    captain = db.relationship('Users', foreign_keys=[captain_id], backref=db.backref('captained_tournament_teams', lazy='dynamic'))
    members = db.relationship('TournamentTeamMember', back_populates='tournament_team', cascade='all, delete-orphan')
    matches_as_a = db.relationship('Matches', foreign_keys='Matches.team_a_id', backref='team_a_tournament_team')
    matches_as_b = db.relationship('Matches', foreign_keys='Matches.team_b_id', backref='team_b_tournament_team')
    won_matches = db.relationship('Matches', foreign_keys='Matches.winner_id', backref='winner_tournament_team')

    __table_args__ = (
        db.UniqueConstraint('tournament_id', 'team_name', name='uq_tournament_team_name'),
    )


class Users(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(30), unique=True, nullable=False)
    email = db.Column(db.String(30), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    role = db.Column(db.String(20), nullable=False, default='player')
    riot_user = db.relationship("RiotAccountInfoUser", backref="user", uselist=False, cascade="all, delete-orphan")
    games = db.relationship('Games', secondary=user_games, backref=db.backref('participants', lazy='dynamic'))
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id', name='fk_users_team_id'))
    team = db.relationship('Teams', foreign_keys=[team_id], backref=db.backref('members', lazy=True))
    tournament_team_memberships = db.relationship('TournamentTeamMember', back_populates='user', cascade='all, delete-orphan')

    def __init__(self, username: str, email: str, password: str, is_admin: bool = False, role: str = 'player'):
        self.username = username
        self.email = email
        self.password_hash = generate_password_hash(password)
        self.is_admin = is_admin
        self.role = 'admin' if is_admin else role

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class RiotAccountInfoUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', name='fk_riot_account_info_user_id'), nullable=False)
    riot_id = db.Column(db.String(50), unique=True, nullable=False)
    riot_puuid = db.Column(db.String(78), unique=True, nullable=False)
    role_1 = db.Column(db.String(3))
    role_2 = db.Column(db.String(3))
    region = db.Column(db.String(4))
    icon_id = db.Column(db.Integer)
    solo_tier = db.Column(db.String(20))
    solo_wins = db.Column(db.Integer)
    solo_losses = db.Column(db.Integer)
    flex_tier=db.Column(db.String(20))
    flex_wins=db.Column(db.Integer)
    flex_losses=db.Column(db.Integer)


class Tournaments(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tournament_name = db.Column(db.String(30), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_by = db.relationship('Users', foreign_keys=[created_by_id], backref='created_tournaments')
    games = db.relationship('Games', backref='tournament', lazy=True, cascade="all, delete-orphan")
    # tournament-scoped teams participating in the tournament
    teams = db.relationship('TournamentTeam', back_populates='tournament', cascade='all, delete-orphan')
    # tournament configuration
    format = db.Column(db.String(20), nullable=False, default='swiss')
    status = db.Column(db.String(20), nullable=False, default='draft')
    max_teams = db.Column(db.Integer, nullable=True)
    rounds = db.Column(db.Integer, nullable=True)
    current_round = db.Column(db.Integer, nullable=False, default=0)
    auto_schedule = db.Column(db.Boolean, nullable=False, default=False)
    schedule_start_at = db.Column(db.DateTime, nullable=True)
    # matches for this tournament
    matches = db.relationship('Matches', backref='tournament', lazy=True, cascade="all, delete-orphan")

    def __init__(self, tournament_name: str, format='swiss', status='draft', max_teams=None, rounds=None, created_by_id=None, auto_schedule=False, schedule_start_at=None):
        self.tournament_name = tournament_name
        self.format = format
        self.status = status
        self.max_teams = max_teams
        self.rounds = rounds
        self.created_by_id = created_by_id
        self.auto_schedule = auto_schedule
        self.schedule_start_at = schedule_start_at

    def get_closest_match(self):
        now = datetime.now()
        upcoming_matches = [
            match for match in self.matches
            if not match.played and match.scheduled_at and match.scheduled_at > now
        ]
        return min(upcoming_matches, key=lambda match: match.scheduled_at, default=None)

    def standings(self):
        # compute simple standings based on match wins
        teams = list(self.teams)
        wins = {t.id: 0 for t in teams}
        losses = {t.id: 0 for t in teams}
        for m in self.matches:
            if m.played and m.winner_id:
                wins[m.winner_id] = wins.get(m.winner_id, 0) + 1
                if m.team_a_id and m.team_b_id:
                    loser = m.team_a_id if m.winner_id == m.team_b_id else m.team_b_id if m.winner_id == m.team_a_id else None
                    if loser:
                        losses[loser] = losses.get(loser, 0) + 1
        standings = sorted(teams, key=lambda t: (-wins.get(t.id, 0), t.id))
        return [{'team': t, 'wins': wins.get(t.id, 0), 'losses': losses.get(t.id, 0)} for t in standings]


class Games(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    game_name = db.Column(db.String(30), nullable=False)
    game_time = db.Column(db.DateTime, nullable=False)
    tournament_id = db.Column(db.Integer, db.ForeignKey('tournaments.id', name='fk_games_tournament_id'), nullable=False)

    def __init__(self, game_name: str, game_time: datetime, tournament_id: int):
        self.game_name = game_name
        self.game_time = game_time
        self.tournament_id = tournament_id

    def formatted_game_time(self):
        return self.game_time.strftime('%H:%M %d-%m-%Y')


class Teams(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_name = db.Column(db.String(30), unique=True, nullable=False)
    captain_id = db.Column(db.Integer, db.ForeignKey('users.id', name='fk_teams_captain_id'))
    captain = db.relationship('Users', foreign_keys=[captain_id], backref=db.backref('captain_of', uselist=False))
    join_token = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    looking_for_members = db.Column(db.Boolean, nullable=False, default=False)


class Matches(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey('tournaments.id', name='fk_matches_tournament_id'), nullable=False)
    round_number = db.Column(db.Integer, nullable=False, default=1)
    team_a_id = db.Column(db.Integer, db.ForeignKey('tournament_teams.id', name='fk_matches_team_a_id'), nullable=True)
    team_b_id = db.Column(db.Integer, db.ForeignKey('tournament_teams.id', name='fk_matches_team_b_id'), nullable=True)
    team_a = db.relationship('TournamentTeam', foreign_keys=[team_a_id])
    team_b = db.relationship('TournamentTeam', foreign_keys=[team_b_id])
    score_a = db.Column(db.Integer, nullable=True)
    score_b = db.Column(db.Integer, nullable=True)
    scheduled_at = db.Column(db.DateTime, nullable=True)
    bracket = db.Column(db.String(20), nullable=True)
    bracket_slot = db.Column(db.Integer, nullable=True)
    winner_id = db.Column(db.Integer, db.ForeignKey('tournament_teams.id', name='fk_matches_winner_id'), nullable=True)
    played = db.Column(db.Boolean, default=False)