from flask import render_template, redirect, url_for, request, flash, session, jsonify, Blueprint, current_app, send_from_directory
from flask_login import login_user, login_required, logout_user, current_user
from . import db
from .forms import LoginForm, RegisterForm, ConnectForm, TournamentForm, GameForm, EditUserForm, TeamForm, EditTeamForm, JoinTeamForm, ApplyToTournamentForm
from .models import Users, RiotAccountInfoUser, Tournaments, Games, Teams, Matches
from .services import *
from .utils import admin_required, can_manage_tournament, get_user_by_email_or_username, is_admin_user, staff_required
import random
from werkzeug.security import generate_password_hash
from datetime import datetime
from traits import generate_team_api, possible_emblems, generate_prioritize_full_traits_api, traits


routes = Blueprint('routes', __name__)

@routes.before_request
def before_request():
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


@routes.route("/tournaments/create", methods=["GET", "POST"])
@staff_required
def create_tournament():
    form = TournamentForm()
    if form.validate_on_submit():
        add_tournament(form)
        flash("Tournament created successfully.")
        return redirect(url_for("routes.get_tournaments"))
    return render_template("create_tournament.html", form=form)

@routes.route("/tournaments/<int:id>")
def get_tournament_by_id(id):
    tournament = Tournaments.query.filter_by(id=id).first()
    if not tournament:
        flash("Tournament not found.")
        return redirect(url_for("routes.get_tournaments"))
    
    upcoming_matches = Matches.query.filter(
        Matches.tournament_id == id,
        Matches.scheduled_at > datetime.now(),
        Matches.played.is_(False),
    ).order_by(Matches.scheduled_at).all()
    form = ApplyToTournamentForm()  # Create an instance of the form
    can_manage = current_user.is_authenticated and can_manage_tournament(current_user, tournament)
    return render_template("tournament_page.html", tournament=tournament, upcoming_matches=upcoming_matches, form=form, can_manage=can_manage)

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
    if tournament.status != 'draft':
        flash("This tournament is not accepting applications.")
        return redirect(url_for("routes.get_tournament_by_id", id=tournament_id))
    # Check if the team already applied
    if team in tournament.teams:
        flash("This team has already applied to the tournament.")
        return redirect(url_for("routes.get_tournament_by_id", id=tournament_id))
    if tournament.max_teams is not None and len(tournament.teams) >= tournament.max_teams:
        flash("This tournament is full.")
        return redirect(url_for("routes.get_tournament_by_id", id=tournament_id))

    # Add team to tournament participants
    tournament.teams.append(team)
    db.session.commit()

    flash("Successfully applied to the tournament.")
    return redirect(url_for("routes.get_tournament_by_id", id=tournament_id))


@routes.route("/tournaments/<int:tournament_id>/start", methods=["POST"])
@staff_required
def start_tournament_route(tournament_id):
    """
    """

    tournament = Tournaments.query.get(tournament_id)
    if not tournament:
        flash("Tournament not found.")
        return redirect(url_for("routes.get_tournaments"))
    if not can_manage_tournament(current_user, tournament):
        flash("You can only manage tournaments that you created.")
        return redirect(url_for("routes.get_tournament_by_id", id=tournament_id))
    if tournament.status != 'draft':
        flash("This tournament has already started or finished.")
        return redirect(url_for("routes.get_tournament_by_id", id=tournament_id))
    result, status = start_tournament(tournament_id)
    if status != 200:
        flash(result.get('error', 'Unable to start tournament'))
    else:
        flash('Tournament started')
    return redirect(url_for("routes.get_tournament_by_id", id=tournament_id))


@routes.route("/tournaments/<int:tournament_id>/matches/<int:match_id>/result", methods=["POST"])
@staff_required
def record_match_result(tournament_id, match_id):
    tournament = Tournaments.query.get(tournament_id)
    match = Matches.query.get(match_id)
    if not tournament or not match or match.tournament_id != tournament.id:
        flash('Match not found')
        return redirect(url_for('routes.get_tournaments'))
    if not can_manage_tournament(current_user, tournament):
        flash("You can only manage tournaments that you created.")
        return redirect(url_for("routes.get_tournament_by_id", id=tournament_id))
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


@routes.route("/tournaments/<int:tournament_id>/matches/<int:match_id>/reschedule", methods=["POST"])
@staff_required
def reschedule_match(tournament_id, match_id):
    tournament = Tournaments.query.get(tournament_id)
    match = Matches.query.get(match_id)
    if not tournament or not match or match.tournament_id != tournament.id:
        flash('Match not found')
        return redirect(url_for('routes.get_tournaments'))
    if not can_manage_tournament(current_user, tournament):
        flash("You can only manage tournaments that you created.")
        return redirect(url_for("routes.get_tournament_by_id", id=tournament_id))
    if match.played:
        flash('Played matches cannot be rescheduled.')
        return redirect(url_for('routes.get_tournament_by_id', id=tournament_id))
    try:
        match.scheduled_at = datetime.fromisoformat(request.form['scheduled_at'])
    except (KeyError, ValueError):
        flash('Invalid match date and time.')
        return redirect(url_for('routes.get_tournament_by_id', id=tournament_id))
    db.session.commit()
    flash('Match rescheduled.')
    return redirect(url_for('routes.get_tournament_by_id', id=tournament_id))

@routes.route("/admin", methods=["GET", "POST"])
@staff_required
def admin():
    tournament_form = TournamentForm()
    game_form = GameForm()
    edit_user_form = EditUserForm()
    edit_team_form = EditTeamForm()

    all_tournaments = Tournaments.query.all()
    visible_tournaments = all_tournaments if is_admin_user(current_user) else [
        tournament for tournament in all_tournaments if tournament.created_by_id == current_user.id
    ]
    users = Users.query.all() if is_admin_user(current_user) else []
    teams = Teams.query.all() if is_admin_user(current_user) else []
    game_form.tournament_id.choices = [(t.id, t.tournament_name) for t in visible_tournaments]
    edit_user_form.user_id.choices = [(u.id, u.username) for u in users]
    edit_team_form.team_name.choices = [(t.id, t.team_name) for t in teams]
    edit_team_form.captain_id.choices = [(u.id, u.username) for u in users]

    if tournament_form.validate_on_submit():
        add_tournament(tournament_form)
        flash("Tournament added successfully.")
        return redirect(url_for("routes.admin"))

    if game_form.validate_on_submit():
        tournament = Tournaments.query.get(game_form.tournament_id.data)
        if not tournament or not can_manage_tournament(current_user, tournament):
            flash("You can only add games to tournaments that you manage.")
            return redirect(url_for("routes.admin"))
        add_game(game_form)
        flash("Game added successfully.")
        return redirect(url_for("routes.admin"))

    if edit_user_form.validate_on_submit() and is_admin_user(current_user):
        user = edit_user(edit_user_form)
        if user:
            flash("User info updated successfully.")
        else:
            flash("User not found.")
        return redirect(url_for("routes.admin"))

    if edit_team_form.validate_on_submit() and is_admin_user(current_user):
        edit_team(edit_team_form)
        flash("Team updated successfully.")
        return redirect(url_for("routes.admin"))

    return render_template("admin.html", tournament_form=tournament_form, game_form=game_form, edit_user_form=edit_user_form, team_form=edit_team_form, users=users, tournaments=visible_tournaments, teams=teams)

@routes.route("/api/tournament/<int:id>")
def get_tournament_info(id):
    tournament = Tournaments.query.get(id)
    if not tournament:
        return jsonify({"error": "Tournament not found"}), 404

    upcoming_matches = Matches.query.filter(
        Matches.tournament_id == id,
        Matches.scheduled_at > datetime.now(),
        Matches.played.is_(False),
    ).order_by(Matches.scheduled_at).all()
    tournament = Tournaments.query.get(id)

    return jsonify({
        "upcoming_matches": [{
            "round": match.round_number,
            "team_a": match.team_a.team_name if match.team_a else "TBD",
            "team_b": match.team_b.team_name if match.team_b else "BYE",
            "scheduled_at": match.scheduled_at.strftime('%Y-%m-%d %H:%M'),
        } for match in upcoming_matches],
        "participants": [{"team_name": team.team_name, "team_id": team.id} for team in tournament.teams]
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