import re
import requests
from .models import Users
from flask_login import login_required, current_user
from flask import flash, redirect, url_for
from functools import wraps

def clean_input(input_string: str) -> str:
    # Удаляем невидимые символы Unicode, такие как ZERO WIDTH SPACE
    cleaned = re.sub(r'[\u200b\u200c\u200d\u2060\u2061]', '', input_string)
    # Убираем любые другие неотображаемые символы
    cleaned = ''.join(c for c in cleaned if c.isprintable())
    return cleaned.strip()

def is_admin_user(user):
    return user.is_admin or user.role == 'admin'


def can_manage_tournament(user, tournament):
    return is_admin_user(user) or (
        user.role == 'moderator' and tournament.created_by_id == user.id
    )


def staff_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not is_admin_user(current_user) and current_user.role != 'moderator':
            flash("You do not have permission to access this page.")
            return redirect(url_for("routes.home"))
        return f(*args, **kwargs)
    return decorated_function


admin_required = staff_required

def get_user_by_email_or_username(identifier: str):
    return Users.query.filter((Users.email == identifier) | (Users.username == identifier)).first()

# Функция для получения puuid аккаунта Riot
def get_account_puuid(name, tag, RIOT_API_KEY):
    url = f'https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{name}/{tag}?api_key={RIOT_API_KEY}'
    response = requests.get(url)
    return response.json()["puuid"]


# Функция для получения данных об аккаунте Лиги Легенд
def get_summoner_info_by_puuid(region, summoner_puuid, RIOT_API_KEY):
    url = f'https://{region}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{summoner_puuid}?api_key={RIOT_API_KEY}'
    response = requests.get(url)
    return response.json()


# Функция для получения данных о рейтинге пользователя в Лиге Легенд
def get_ranked_info(region, summoner_puuid, RIOT_API_KEY):
    url = f'https://{region}.api.riotgames.com/lol/league/v4/entries/by-puuid/{summoner_puuid}?api_key={RIOT_API_KEY}'
    response = requests.get(url)
    return response.json()