from flask import flash, redirect, url_for
from flask_login import current_user
from .models import Users, RiotAccountInfoUser, db, Tournaments, Games, Teams, Matches
from . import utils
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
        status='registration'
    )
    db.session.add(tournament)
    db.session.commit()
    return tournament


def generate_swiss_pairings(tournament, round_number=1):
    import random

    team_ids = [team.id for team in tournament.teams]
    if not team_ids:
        return []

    scores = {team_id: 0 for team_id in team_ids}
    opponents = {team_id: set() for team_id in team_ids}
    bye_recipients = set()

    for match in tournament.matches:
        if match.team_a_id not in scores:
            continue

        if match.team_b_id is None:
            if match.played and match.winner_id == match.team_a_id:
                scores[match.team_a_id] += 1
                bye_recipients.add(match.team_a_id)
            continue

        if match.team_b_id not in scores:
            continue
        opponents[match.team_a_id].add(match.team_b_id)
        opponents[match.team_b_id].add(match.team_a_id)
        if match.played and match.winner_id in scores:
            scores[match.winner_id] += 1

    if round_number == 1:
        random.shuffle(team_ids)
        team_ids.sort(key=lambda team_id: scores[team_id], reverse=True)
    else:
        team_ids.sort(key=lambda team_id: (-scores[team_id], team_id))

    bye_team_id = None
    if len(team_ids) % 2:
        eligible_byes = [team_id for team_id in team_ids if team_id not in bye_recipients]
        bye_candidates = eligible_byes or team_ids
        bye_team_id = min(bye_candidates, key=lambda team_id: (scores[team_id], team_id))
        team_ids.remove(bye_team_id)

    def pair_remaining(remaining, allow_rematches=False):
        if not remaining:
            return []

        first_team_id = remaining[0]
        candidates = remaining[1:]
        candidates.sort(key=lambda team_id: (
            team_id in opponents[first_team_id] if not allow_rematches else False,
            scores[team_id] != scores[first_team_id],
            abs(scores[team_id] - scores[first_team_id]),
            team_id,
        ))

        for candidate_id in candidates:
            if not allow_rematches and candidate_id in opponents[first_team_id]:
                continue
            next_remaining = [
                team_id for team_id in remaining
                if team_id not in (first_team_id, candidate_id)
            ]
            result = pair_remaining(next_remaining, allow_rematches)
            if result is not None:
                return [(first_team_id, candidate_id), *result]
        return None

    pairs = pair_remaining(team_ids)
    if pairs is None:
        pairs = pair_remaining(team_ids, allow_rematches=True)
    if pairs is None:
        raise ValueError("Unable to create Swiss pairings")
    if bye_team_id is not None:
        pairs.append((bye_team_id, None))
    return pairs


def start_tournament(tournament_id):
    tournament = Tournaments.query.get(tournament_id)
    if not tournament:
        return {'error': 'Tournament not found'}, 404
    if len(tournament.teams) < 2:
        return {'error': 'Not enough teams to start'}, 400
    tournament.status = 'active'
    tournament.current_round = 1
    db.session.add(tournament)
    pairs = []
    if tournament.format == 'swiss':
        pairs = generate_swiss_pairings(tournament, round_number=1)
    else:
        # fallback to simple random pairing
        import random
        tlist = list(tournament.teams)
        random.shuffle(tlist)
        i = 0
        while i < len(tlist):
            a = tlist[i]
            b = tlist[i+1] if i+1 < len(tlist) else None
            pairs.append((a.id, b.id if b else None))
            i += 2

    # create matches
    for a_id, b_id in pairs:
        match = Matches(tournament_id=tournament.id, round_number=1, team_a_id=a_id, team_b_id=b_id)
        if b_id is None:
            match.played = True
            match.winner_id = a_id
        db.session.add(match)

    db.session.commit()
    return {'message': 'Tournament started', 'pairs': pairs}, 200


def submit_match_result(match_id, score_a, score_b):
    match = Matches.query.get(match_id)
    if not match:
        return {'error': 'Match not found'}, 404
    match.score_a = score_a
    match.score_b = score_b
    if score_a is None or score_b is None:
        return {'error': 'Scores required'}, 400
    if score_a > score_b:
        match.winner_id = match.team_a_id
    elif score_b > score_a:
        match.winner_id = match.team_b_id
    else:
        match.winner_id = None
    match.played = True
    db.session.add(match)
    db.session.commit()

    # after submitting, check if all matches in the round are played and auto-create next round
    tournament = Tournaments.query.get(match.tournament_id)
    current_round = match.round_number
    round_matches = Matches.query.filter_by(tournament_id=tournament.id, round_number=current_round).all()
    if all(m.played for m in round_matches):
        # advance round if needed
        if tournament.rounds is None or tournament.current_round < tournament.rounds:
            tournament.current_round += 1
            db.session.add(tournament)
            # generate next round pairings
            if tournament.format == 'swiss':
                pairs = generate_swiss_pairings(tournament, round_number=tournament.current_round)
            else:
                pairs = []
            for a_id, b_id in pairs:
                new_match = Matches(tournament_id=tournament.id, round_number=tournament.current_round, team_a_id=a_id, team_b_id=b_id)
                if b_id is None:
                    new_match.played = True
                    new_match.winner_id = a_id
                db.session.add(new_match)
            db.session.commit()
        else:
            tournament.status = 'finished'
            db.session.add(tournament)
            db.session.commit()

    return {'message': 'Result recorded'}, 200

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
        db.session.commit()
        return user
    return None

def add_team(form):
    existing_team = Teams.query.filter_by(team_name=form.team_name.data).first()
    if existing_team:
        flash("A team with this name already exists.")
        return None

    team = Teams(
        team_name=form.team_name.data,
        captain_id=form.captain_id.data,
        join_token=str(uuid.uuid4())
    )
    
    db.session.add(team)
    db.session.commit()

    user = Users.query.get(form.captain_id.data)
    user.team_id = team.id
    db.session.commit()
    
    return team

def edit_team(form):
    team = Teams.query.get(form.team_name.data)
    if team:
        team.team_name = form.new_team_name.data
        team.captain_id = form.captain_id.data
        db.session.commit()
        return team
    return None

def generate_team_link(team_id, user_id):
    team = Teams.query.get(team_id)
    if not team or team.captain_id != user_id:
        return {"error": "You are not the captain of this team."}, 403
    link = url_for('routes.join_team_by_token_route', token=team.join_token, _external=True)
    return {"link": link}, 200

def join_team_by_token(token, user_id):
    team = Teams.query.filter_by(join_token=token).first()
    if not team:
        return {"error": "Team not found."}, 404
    if len(team.members) >= 5:
        return {"error": "Team is full."}, 403
    user = Users.query.get(user_id)
    user.team_id = team.id
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