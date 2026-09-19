from flask import flash, redirect, url_for
from flask_login import current_user
from .models import Users, RiotAccountInfoUser, db, Tournaments, Games, Matches, TournamentTeam, TournamentTeamMember
from datetime import datetime, timedelta
from . import utils
from . import tournament_engine
from .tournament_engine import (
    _create_next_single_elimination_round,
    _double_elimination_pairs,
    _elimination_pairs,
    _new_match,
    _next_match_time,
    _round_robin_pairs,
    generate_swiss_pairings,
    finish_tournament as engine_finish_tournament,
    start_tournament as engine_start_tournament,
    submit_match_result as engine_submit_match_result,
)
import os
import re
from werkzeug.security import generate_password_hash
import uuid
from .utils import get_summoner_info_by_puuid, get_ranked_info

# Load environment variables from .env file
riot_api_key = os.getenv('RIOT_API_KEY')

def register_user(form):
    email = form.email.data
    username = form.username.data
    password = form.password.data
    found_user = utils.get_user_by_email_or_username(email) or utils.get_user_by_email_or_username(username)
    if found_user:
        flash("Пользователь с таким ником/почтой уже зарегестрирован")
        return redirect(url_for("routes.register"))
    else:
        user = Users(username, email, password)
        db.session.add(user)
        db.session.commit()
        flash("Успешная регистрация")
        return redirect(url_for("routes.home"))


def connect_riot_account(form):
    riotid = utils.clean_input(form.riotid.data)
    role_1 = form.select_role_1.data
    role_2 = form.select_role_2.data
    region = form.select_region.data
    if RiotAccountInfoUser.query.filter_by(riot_id=riotid).first():
        flash("Этот Riot ID уже привязан к другому аккаунту")
        return redirect(url_for("routes.connect"))
    elif re.match(r'[^#]{3,16}#[^#]{3,5}', riotid):
        name, tag = riotid.split('#')
        puuid = utils.get_account_puuid(name, tag, riot_api_key)
        ranked_info = get_ranked_info(region, puuid, riot_api_key)
        solo_tier = solo_wins = solo_losses = None
        flex_tier = flex_wins = flex_losses = None
        for entry in ranked_info:
            if entry['queueType'] == 'RANKED_SOLO_5x5':        
                solo_tier = entry['tier'] if entry['tier'] else None
                solo_wins = entry['wins'] if entry['wins'] else None
                solo_losses = entry['losses'] if entry['losses'] else None
            elif entry['queueType'] == 'RANKED_FLEX_SR':
                flex_tier = entry['tier'] if entry['tier'] else None
                flex_wins = entry['wins'] if entry['wins'] else None
                flex_losses = entry['losses'] if entry['losses'] else None
        
        try:
            icon_id = str(utils.get_summoner_info_by_puuid(region, puuid, riot_api_key)['profileIconId'])
        except:
            flash("Выбран неправильный сервер")
            return redirect(url_for("routes.connect"))
        
        flash("Успешная регистрация")
        user = current_user
        riot_info = RiotAccountInfoUser(
            user_id=user.id,
            riot_id=riotid,
            riot_puuid=puuid,
            role_1=role_1,
            role_2=role_2,
            region=region,
            icon_id=icon_id,
            solo_tier=solo_tier,
            solo_wins=solo_wins,
            solo_losses=solo_losses,
            flex_tier=flex_tier,
            flex_wins=flex_wins,
            flex_losses=flex_losses
        )
        db.session.add(riot_info)
        db.session.commit()
        return redirect(url_for("routes.profile"))
    return redirect(url_for("routes.profile"))

def add_tournament(form):
    tournament = Tournaments(
        tournament_name=form.tournament_name.data,
        format=form.format.data if hasattr(form, 'format') else 'swiss',
        max_teams=form.max_teams.data if hasattr(form, 'max_teams') else None,
        rounds=form.rounds.data if hasattr(form, 'rounds') else None,
        status='draft',
        created_by_id=current_user.id,
        auto_schedule=form.auto_schedule.data,
        schedule_start_at=form.schedule_start_at.data
    )
    db.session.add(tournament)
    db.session.commit()
    return tournament


def generate_swiss_pairings(tournament, round_number=1):
    return tournament_engine.generate_swiss_pairings(tournament, round_number=round_number)


def _next_match_time(tournament):
    return tournament_engine._next_match_time(tournament)


def _new_match(tournament, round_number, team_a_id, team_b_id=None, bracket=None, bracket_slot=None):
    return tournament_engine._new_match(tournament, round_number, team_a_id, team_b_id, bracket, bracket_slot)


def _round_robin_pairs(team_ids):
    return tournament_engine._round_robin_pairs(team_ids)


def _elimination_pairs(team_ids):
    return tournament_engine._elimination_pairs(team_ids)


def _create_next_single_elimination_round(tournament):
    return tournament_engine._create_next_single_elimination_round(tournament)


def _double_elimination_pairs(tournament):
    return tournament_engine._double_elimination_pairs(tournament)


def start_tournament(tournament_id):
    return engine_start_tournament(tournament_id)


def finish_tournament(tournament_id):
    return engine_finish_tournament(tournament_id)


def submit_match_result(match_id, score_a, score_b):
    return engine_submit_match_result(match_id, score_a, score_b)

def add_game(form):
    game = Games(
        game_name=form.game_name.data,
        game_time=form.game_time.data,
        tournament_id=form.tournament_id.data
    )
    db.session.add(game)
    db.session.commit()
    return game

def edit_user(form):
    user = Users.query.get(form.user_id.data)
    if user:
        if form.username.data:
            user.username = form.username.data
        if form.email.data:
            user.email = form.email.data
        if form.password.data:
            user.password_hash = generate_password_hash(form.password.data)
        user.role = form.role.data
        user.is_admin = user.role == 'admin'
        db.session.commit()
        return user
    return None

def add_team(form):
    existing_team = TournamentTeam.query.filter_by(
        tournament_id=form.tournament_id.data,
        team_name=form.team_name.data,
    ).first()
    if existing_team:
        flash("A team with this name already exists in this tournament.")
        return None

    team = TournamentTeam(
        team_name=form.team_name.data,
        tournament_id=form.tournament_id.data,
        captain_id=current_user.id,
        join_token=str(uuid.uuid4()),
        looking_for_members=form.looking_for_members.data
    )

    db.session.add(team)
    db.session.flush()
    db.session.add(TournamentTeamMember(tournament_team_id=team.id, user_id=current_user.id))
    db.session.commit()

    return team

def generate_team_link(team_id, user_id):
    team = TournamentTeam.query.get(team_id)
    if not team or team.captain_id != user_id:
        return {"error": "You are not the captain of this team."}, 403
    link = url_for('routes.join_team_by_token_route', token=team.join_token, _external=True)
    return {"link": link}, 200

def join_team_by_token(token, user_id):
    team = TournamentTeam.query.filter_by(join_token=token).first()
    if not team:
        return {"error": "Team not found."}, 404
    if len(team.members) >= 5:
        return {"error": "Team is full."}, 403
    if TournamentTeamMember.query.filter_by(tournament_team_id=team.id, user_id=user_id).first():
        return {"error": "You are already in this team."}, 400
    db.session.add(TournamentTeamMember(tournament_team_id=team.id, user_id=user_id))
    db.session.commit()
    return {"message": "Joined team successfully."}, 200

def refresh_riot_account_info(user):
    if user.riot_user:
        try:
            summoner_info = get_summoner_info_by_puuid(user.riot_user.region, user.riot_user.riot_puuid, riot_api_key)
            ranked_info = get_ranked_info(user.riot_user.region, user.riot_user.riot_puuid, riot_api_key)
            solo_tier = solo_wins = solo_losses = None
            flex_tier = flex_wins = flex_losses = None
            for entry in ranked_info:
                if entry['queueType'] == 'RANKED_SOLO_5x5':        
                    solo_tier = entry['tier'] if entry['tier'] else None
                    solo_wins = entry['wins'] if entry['wins'] else None
                    solo_losses = entry['losses'] if entry['losses'] else None
                elif entry['queueType'] == 'RANKED_FLEX_SR':
                    flex_tier = entry['tier'] if entry['tier'] else None
                    flex_wins = entry['wins'] if entry['wins'] else None
                    flex_losses = entry['losses'] if entry['losses'] else None
            
            user.riot_user.icon_id = summoner_info['profileIconId']
            user.riot_user.solo_tier = solo_tier
            user.riot_user.solo_wins = solo_wins
            user.riot_user.solo_losses = solo_losses
            user.riot_user.flex_tier = flex_tier
            user.riot_user.flex_wins = flex_wins
            user.riot_user.flex_losses = flex_losses 
            db.session.commit()
        except Exception as e:
            print(f"Error refreshing Riot account info: {e}")