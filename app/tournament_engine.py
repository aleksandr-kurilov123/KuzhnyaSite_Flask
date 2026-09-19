from datetime import datetime, timedelta

from . import db
from .models import Matches, Tournaments


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


def _next_match_time(tournament):
    if not tournament.auto_schedule:
        return None

    previous_scheduled = getattr(tournament, '_next_scheduled_at', None)
    if previous_scheduled:
        next_scheduled = previous_scheduled + timedelta(minutes=30)
        tournament._next_scheduled_at = next_scheduled
        return next_scheduled

    scheduled = [match.scheduled_at for match in tournament.matches if match.scheduled_at]
    scheduled.extend(
        match.scheduled_at for match in db.session.new
        if isinstance(match, Matches)
        and match.tournament_id == tournament.id
        and match.scheduled_at
    )

    if scheduled:
        next_scheduled = max(scheduled) + timedelta(minutes=30)
        tournament._next_scheduled_at = next_scheduled
        return next_scheduled

    next_scheduled = tournament.schedule_start_at or datetime.now()
    tournament._next_scheduled_at = next_scheduled
    return next_scheduled


def _new_match(tournament, round_number, team_a_id, team_b_id=None, bracket=None, bracket_slot=None):
    match = Matches(
        tournament_id=tournament.id,
        round_number=round_number,
        team_a_id=team_a_id,
        team_b_id=team_b_id,
        bracket=bracket,
        bracket_slot=bracket_slot,
        scheduled_at=_next_match_time(tournament),
    )
    if team_b_id is None:
        match.played = True
        match.winner_id = team_a_id
    return match


def _round_robin_pairs(team_ids):
    return [
        (team_ids[index], team_ids[other])
        for index in range(len(team_ids))
        for other in range(index + 1, len(team_ids))
    ]


def _elimination_pairs(team_ids):
    bracket_size = 1
    while bracket_size < len(team_ids):
        bracket_size *= 2
    seeded = list(team_ids) + [None] * (bracket_size - len(team_ids))
    return [(seeded[index], seeded[index + 1]) for index in range(0, bracket_size, 2)]


def _create_next_single_elimination_round(tournament):
    matches = [match for match in tournament.matches if match.bracket == 'single']
    if not matches:
        return False
    current_round = max(match.round_number for match in matches)
    current_matches = [match for match in matches if match.round_number == current_round]
    if not all(match.played for match in current_matches):
        return False
    winners = [match.winner_id for match in sorted(current_matches, key=lambda item: item.bracket_slot) if match.winner_id]
    if len(winners) <= 1:
        tournament.status = 'finished'
        return True
    for slot in range(0, len(winners), 2):
        db.session.add(_new_match(
            tournament,
            current_round + 1,
            winners[slot],
            winners[slot + 1] if slot + 1 < len(winners) else None,
            bracket='single',
            bracket_slot=slot // 2,
        ))
    return True


def _double_elimination_pairs(tournament):
    team_ids = [team.id for team in tournament.teams]
    losses = {team_id: 0 for team_id in team_ids}
    opponents = {team_id: set() for team_id in team_ids}
    for match in tournament.matches:
        if not match.played or not match.team_b_id:
            continue
        opponents[match.team_a_id].add(match.team_b_id)
        opponents[match.team_b_id].add(match.team_a_id)
        loser = match.team_b_id if match.winner_id == match.team_a_id else match.team_a_id
        if loser in losses:
            losses[loser] += 1

    active = [team_id for team_id in team_ids if losses[team_id] < 2]
    active.sort(key=lambda team_id: (losses[team_id], team_id))
    bye = None
    if len(active) % 2:
        bye = active.pop()

    pairs = []
    while active:
        team_a_id = active.pop(0)
        candidate_index = next((index for index, team_id in enumerate(active)
                                if team_id not in opponents[team_a_id]), None)
        if candidate_index is None:
            candidate_index = 0
        team_b_id = active.pop(candidate_index)
        pairs.append((team_a_id, team_b_id))
    if bye is not None:
        pairs.append((bye, None))
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
    elif tournament.format == 'round_robin':
        pairs = _round_robin_pairs([team.id for team in tournament.teams])
    elif tournament.format == 'double_elim':
        pairs = _double_elimination_pairs(tournament)
    else:
        pairs = _elimination_pairs([team.id for team in tournament.teams])

    # create matches
    for slot, (a_id, b_id) in enumerate(pairs):
        if a_id is None:
            a_id, b_id = b_id, None
        if a_id is not None:
            db.session.add(_new_match(
                tournament, 1, a_id, b_id,
                bracket='single' if tournament.format == 'single_elim' else tournament.format,
                bracket_slot=slot,
            ))

    if tournament.format == 'single_elim':
        db.session.flush()
        _create_next_single_elimination_round(tournament)

    db.session.commit()
    return {'message': 'Tournament started', 'pairs': pairs}, 200


def finish_tournament(tournament_id):
    tournament = Tournaments.query.get(tournament_id)
    if not tournament:
        return {'error': 'Tournament not found'}, 404
    if tournament.status == 'draft':
        return {'error': 'Tournament has not started'}, 400
    if tournament.status == 'finished':
        return {'error': 'Tournament is already finished'}, 400

    tournament.status = 'finished'
    db.session.add(tournament)
    db.session.commit()
    return {'message': 'Tournament finished'}, 200


def submit_match_result(match_id, score_a, score_b):
    from .models import Matches, Tournaments

    match = Matches.query.get(match_id)
    if not match:
        return {'error': 'Match not found'}, 404
    tournament = Tournaments.query.get(match.tournament_id)
    if tournament.status == 'finished':
        return {'error': 'Finished tournaments cannot be changed'}, 400
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

    # Generate the next round only after every match in the current round is complete.
    current_round = match.round_number
    round_matches = Matches.query.filter_by(tournament_id=tournament.id, round_number=current_round).all()
    if all(m.played for m in round_matches):
        if tournament.format == 'round_robin':
            if all(m.played for m in tournament.matches):
                tournament.status = 'finished'
                db.session.commit()
            return {'message': 'Result recorded'}, 200

        if tournament.format == 'single_elim':
            _create_next_single_elimination_round(tournament)
            db.session.commit()
            return {'message': 'Result recorded'}, 200

        max_rounds = tournament.rounds or max(1, (len(tournament.teams) - 1).bit_length())
        if tournament.current_round < max_rounds:
            tournament.current_round += 1
            db.session.add(tournament)
            if tournament.format == 'swiss':
                pairs = generate_swiss_pairings(tournament, round_number=tournament.current_round)
            elif tournament.format == 'double_elim':
                pairs = _double_elimination_pairs(tournament)
            else:
                pairs = []
            for slot, (a_id, b_id) in enumerate(pairs):
                db.session.add(_new_match(
                    tournament,
                    tournament.current_round,
                    a_id,
                    b_id,
                    bracket=tournament.format,
                    bracket_slot=slot,
                ))
            db.session.commit()
        else:
            tournament.status = 'finished'
            db.session.add(tournament)
            db.session.commit()

    return {'message': 'Result recorded'}, 200
