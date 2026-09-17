from flask import render_template, redirect, url_for, request, flash, session, jsonify, Blueprint, current_app, send_from_directory
from flask_login import login_user, login_required, logout_user, current_user
from . import db
from .forms import LoginForm, RegisterForm, ConnectForm, TournamentForm, GameForm, EditUserForm, TeamForm, EditTeamForm, JoinTeamForm, ApplyToTournamentForm
from .models import Users, RiotAccountInfoUser, Tournaments, Games, Teams, Matches
from .services import *
from .utils import admin_required
import random
from werkzeug.security import generate_password_hash
from datetime import datetime
from traits import generate_team_api, possible_emblems, generate_prioritize_full_traits_api, traits


routes = Blueprint('routes', __name__)

@routes.before_request
def before_request():
    with current_app.app_context():
        if current_user.is_authenticated:
            db.session.add(current_user)
            db.session.refresh(current_user)
            refresh_riot_account_info(current_user)

@routes.route("/")
@routes.route("/home")
def home():
    return render_template("index.html")

@routes.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("routes.home"))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = get_user_by_email_or_username(form.username.data)
        if user and user.check_password(form.password.data):
            login_user(user)
            session["username"] = user.username 
            return redirect(url_for("routes.home"))
        else:
            flash("Неверный логин или пароль")
            return redirect(url_for("routes.login"))
    return render_template("login.html", form=form)

@routes.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("routes.home"))
    
    form = RegisterForm()
    if form.validate_on_submit():
        return register_user(form)
    return render_template("register.html", form=form)

@routes.route("/logout")
def logout():
    logout_user()
    session.pop("username", None)
    return redirect(url_for("routes.home"))

@routes.route("/profile")
@login_required
def profile():
    user = current_user
    game_list = user.games
    refresh_riot_account_info(user)
    return render_template("profile.html", user=user, game_list=game_list)

@routes.route("/connect", methods=["GET", "POST"])
@login_required
def connect():
    form = ConnectForm()
    if form.validate_on_submit():
        return connect_riot_account(form)
    else:
        session["icon_number"] = str(random.randint(1, 28))
        return render_template("connect.html", form=form, number=session["icon_number"])

@routes.route("/tournaments")
def get_tournaments():
    tournaments = Tournaments.query.all()
    form = ApplyToTournamentForm()  # Create an instance of the form
    return render_template("tournaments.html", tournament_list=tournaments, form=form)

@routes.route("/tournaments/<int:id>")
def get_tournament_by_id(id):
    tournament = Tournaments.query.filter_by(id=id).first()
    if not tournament:
        flash("Tournament not found.")
        return redirect(url_for("routes.get_tournaments"))
    
    upcoming_games = Games.query.filter(Games.tournament_id == id, Games.game_time > datetime.now()).order_by(Games.game_time).all()
    form = ApplyToTournamentForm()  # Create an instance of the form
    return render_template("tournament_page.html", tournament=tournament, upcoming_games=upcoming_games, form=form)

@routes.route("/apply_to_tournament/<int:tournament_id>", methods=["POST"])
@login_required
def apply_to_tournament(tournament_id):
    if not current_user.team_id:
        flash("You need to join a team first.")
        return redirect(url_for("routes.profile"))
    
    team = Teams.query.get(current_user.team_id)
    if team.captain_id != current_user.id:
        flash("Only team captains can apply to tournaments.")
        return redirect(url_for("routes.get_tournament_by_id", id=tournament_id))
    
    tournament = Tournaments.query.get(tournament_id)
    if not tournament:
        flash("Tournament not found.")
        return redirect(url_for("routes.get_tournaments"))
    # Check if the team already applied
    if team in tournament.teams:
        flash("This team has already applied to the tournament.")
        return redirect(url_for("routes.get_tournament_by_id", id=tournament_id))

    # Add team to tournament participants
    tournament.teams.append(team)
    db.session.commit()

    flash("Successfully applied to the tournament.")
    return redirect(url_for("routes.get_tournament_by_id", id=tournament_id))


@routes.route("/tournaments/<int:tournament_id>/start", methods=["POST"])
@admin_required
def start_tournament_route(tournament_id):
    """
    """

    tournament = Tournaments.query.get(tournament_id)
    if not tournament:
        flash("Tournament not found.")
        return redirect(url_for("routes.get_tournaments"))
    result, status = start_tournament(tournament_id)
    if status != 200:
        flash(result.get('error', 'Unable to start tournament'))
    else:
        flash('Tournament started')
    return redirect(url_for("routes.get_tournament_by_id", id=tournament_id))


@routes.route("/tournaments/<int:tournament_id>/matches/<int:match_id>/result", methods=["POST"])
@admin_required
def record_match_result(tournament_id, match_id):
    # expects form fields 'score_a' and 'score_b'
    try:
        score_a = int(request.form.get('score_a'))
        score_b = int(request.form.get('score_b'))
    except Exception:
        flash('Invalid scores')
        return redirect(url_for('routes.get_tournament_by_id', id=tournament_id))

    result, status = submit_match_result(match_id, score_a, score_b)
    if status != 200:
        flash(result.get('error', 'Unable to record result'))
    else:
        flash('Result recorded')
    return redirect(url_for('routes.get_tournament_by_id', id=tournament_id))

@routes.route("/admin", methods=["GET", "POST"])
@admin_required
def admin():
    tournament_form = TournamentForm()
    game_form = GameForm()
    edit_user_form = EditUserForm()
    edit_team_form = EditTeamForm()

    game_form.tournament_id.choices = [(t.id, t.tournament_name) for t in Tournaments.query.all()]
    edit_user_form.user_id.choices = [(u.id, u.username) for u in Users.query.all()]
    edit_team_form.team_name.choices = [(t.id, t.team_name) for t in Teams.query.all()]
    edit_team_form.captain_id.choices = [(u.id, u.username) for u in Users.query.all()]

    if tournament_form.validate_on_submit():
        add_tournament(tournament_form)
        flash("Tournament added successfully.")
        return redirect(url_for("routes.admin"))

    if game_form.validate_on_submit():
        add_game(game_form)
        flash("Game added successfully.")
        return redirect(url_for("routes.admin"))

    if edit_user_form.validate_on_submit():
        user = edit_user(edit_user_form)
        if user:
            flash("User info updated successfully.")
        else:
            flash("User not found.")
        return redirect(url_for("routes.admin"))

    if edit_team_form.validate_on_submit():
        edit_team(edit_team_form)
        flash("Team updated successfully.")
        return redirect(url_for("routes.admin"))

    users = Users.query.all()
    tournaments = Tournaments.query.all()
    teams = Teams.query.all()
    return render_template("admin.html", tournament_form=tournament_form, game_form=game_form, edit_user_form=edit_user_form, team_form=edit_team_form, users=users, tournaments=tournaments, teams=teams)

@routes.route("/api/tournament/<int:id>")
def get_tournament_info(id):
    tournament = Tournaments.query.get(id)
    if not tournament:
        return jsonify({"error": "Tournament not found"}), 404

    upcoming_games = Games.query.filter(Games.tournament_id == id, Games.game_time > datetime.now()).order_by(Games.game_time).all()
    participants = Users.query.join(Users.games).filter(Games.tournament_id == id).all()

    return jsonify({
        "upcoming_games": [{"game_name": game.game_name, "game_time": game.game_time.strftime('%Y-%m-%d %H:%M')} for game in upcoming_games],
        "participants": [{"username": user.username, "email": user.email} for user in participants]
    })

@routes.route("/tfttools")
def tfttools():
    emblems = possible_emblems
    vertical = list(traits.keys())
    return render_template("tfttools.html", emblems=emblems, vertical=vertical)

@routes.route("/teams")
def teams_overview():
    teams = Teams.query.all()
    return render_template("teams_overview.html", teams=teams)

@routes.route("/teams/<int:id>")
def team_detail(id):
    team = Teams.query.get(id)
    if not team:
        flash("Team not found.")
        return redirect(url_for("routes.teams_overview"))
    return render_template("team_detail.html", team=team)

@routes.route("/create_team", methods=["GET", "POST"])
@login_required
def create_team():
    if not current_user.riot_user:
        flash("You need to connect your Riot account first.")
        return redirect(url_for("routes.connect"))
    if current_user.team_id:
        flash("You are already in a team.")
        return redirect(url_for("routes.profile"))
    
    form = TeamForm()
    form.captain_id.choices = [(current_user.id, current_user.username)]
    if form.validate_on_submit():
        team = add_team(form)
        if team:
            flash("Team created successfully.")
            return redirect(url_for("routes.profile"))
    return render_template("create_team.html", form=form)

@routes.route("/join_team/<string:token>", methods=["GET", "POST"])
@login_required
def join_team_by_token_route(token):
    response, status_code = join_team_by_token(token, current_user.id)
    if status_code == 200:
        flash(response["message"])
    else:
        flash(response["error"])
    return redirect(url_for("routes.profile"))

@routes.route("/api/generate_team_link/<int:team_id>")
@login_required
def generate_team_link_api(team_id):
    response, status_code = generate_team_link(team_id, current_user.id)
    return jsonify(response), status_code

@routes.route("/riot/callback", methods=["POST"])
def riot_callback():
    data = request.get_json()
    print(f"Received callback data: {data}")
    return jsonify({"status": "success"}), 200

@routes.route("//riot.txt")
def riot_txt():
    return send_from_directory(current_app.static_folder, "riot.txt")

@routes.route('/favicon.ico') 
def favicon(): 
    return send_from_directory(os.path.join(current_app.static_folder, 'img'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

@routes.route("/api/generate_team", methods=["POST"])
def api_generate_team():
    return generate_team_api()

@routes.route("/api/generate_prioritize_full_traits", methods=["POST"])
def api_generate_prioritize_full_traits():
    return generate_prioritize_full_traits_api()