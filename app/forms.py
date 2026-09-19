from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, DateTimeField, IntegerField, BooleanField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Regexp, Optional

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()], render_kw={"placeholder": "Username / Email"})
    password = PasswordField('Password', validators=[DataRequired()], render_kw={"placeholder": "Password"})
    submit = SubmitField('Login')


class RegisterForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8),
        Regexp(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$', message="Password must contain at least one uppercase letter, one lowercase letter, one number, and one special character.")
    ])
    password_repeat = PasswordField('Repeat Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')


class ConnectForm(FlaskForm):
    riotid = StringField('Riot ID', validators=[DataRequired()], render_kw={"placeholder": "Riot ID"})
    select_role_1 = SelectField('Role 1', choices=[('top', 'Топ'), ('jgl', 'Лес'), ('mid', 'Мид'), ('sup', 'Саппорт'), ('bot', 'Бот')], validators=[DataRequired()])
    select_role_2 = SelectField('Role 2', choices=[('top', 'Топ'), ('jgl', 'Лес'), ('mid', 'Мид'), ('sup', 'Саппорт'), ('bot', 'Бот')], validators=[DataRequired()])
    select_region = SelectField('Region', choices=[('euw1', 'EUW'), ('ru', 'RU')], validators=[DataRequired()])
    submit = SubmitField('Connect')

class TournamentForm(FlaskForm):
    tournament_name = StringField('Tournament Name', validators=[DataRequired()])
    format = SelectField('Format', choices=[('swiss', 'Swiss'), ('round_robin', 'Round Robin'), ('single_elim', 'Single Elimination'), ('double_elim', 'Double Elimination')], validators=[DataRequired()], default='swiss')
    max_teams = IntegerField('Max Teams', validators=[Optional()])
    rounds = IntegerField('Rounds', validators=[Optional()])
    auto_schedule = BooleanField('Automatically schedule matches')
    schedule_start_at = DateTimeField('First match time', format='%Y-%m-%d %H:%M', validators=[Optional()])
    submit = SubmitField('Add Tournament', render_kw={"class": "sign"})

class GameForm(FlaskForm):
    game_name = StringField('Game Name', validators=[DataRequired()])
    game_time = DateTimeField('Game Time', format='%Y-%m-%d %H:%M', validators=[DataRequired()], render_kw={"id": "game_time"})
    tournament_id = SelectField('Tournament', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Add Game', render_kw={"class": "sign"})

class EditUserForm(FlaskForm):
    user_id = SelectField('User', coerce=int, validators=[DataRequired()])
    username = StringField('Username', validators=[Optional()])
    email = StringField('Email', validators=[Optional(), Email()], render_kw={"autocomplete": "false"})
    password = PasswordField('Password', validators=[Optional()])
    role = SelectField('Role', choices=[('player', 'Player'), ('moderator', 'Moderator'), ('admin', 'Admin')], validators=[DataRequired()])
    submit = SubmitField('Update User', render_kw={"class": "sign"})

class TeamForm(FlaskForm):
    team_name = StringField('Team Name', validators=[DataRequired()])
    captain_id = SelectField('Captain', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Add Team', render_kw={"class": "sign"})

class EditTeamForm(FlaskForm):
    team_name = SelectField('Team Name', coerce=int, validators=[DataRequired()])   
    new_team_name = StringField('New Team Name', validators=[Optional()])
    captain_id = SelectField('Captain', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Update Team', render_kw={"class": "sign"})

class JoinTeamForm(FlaskForm):
    team_id = SelectField('Team', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Join Team')

class ApplyToTournamentForm(FlaskForm):
    submit = SubmitField('Apply to Tournament')