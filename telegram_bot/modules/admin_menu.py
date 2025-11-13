import asyncio
import subprocess
from enum import Enum
from datetime import datetime
from subprocess import STDOUT, DEVNULL
from redis.client import Redis
from psycopg2.extras import DictCursor

from settings import Config

from tops.day_top import DayTopService, DayTop
from tops.week_top import WeekTopService, WeekTop
from tops.clans_top import ClansTopService, ClansTop
from tops.coins_top import CoinsTopService, CoinsTop
from tops.rubles_top import RublesTopService, RublesTop
from tops.all_time_top import AllTimeTopService, AllTimeTop
from tops.week_rubles_top import WeekRublesTopService, WeekRublesTop

from schemas.users import UserSchema, UserStatus
from schemas.chats import ChatSchema, ChatType, CHAT_TYPES_NAME
from schemas.games import Games, ALL_GAMES_VALUES
from services.incomes import IncomesService

from modules.additional import convert_number, format_number, get_word_case
from modules.databases.users import get_user_data
from modules.databases.chats import get_chat_data
from modules.telegram.users import get_user_id


async def restart_bot() -> None:
    """Перезапускает white coin"""

    stop_white_coin = "supervisorctl stop white_coin"
    reset_white_coin_games = "conn_redis DEL games"
    start_white_coin = "supervisorctl start white_coin"

    await asyncio.sleep(20)
    subprocess.call(f"{stop_white_coin} ; sleep 10 ; {reset_white_coin_games} ; {start_white_coin}", shell=True, stdout=DEVNULL, stderr=STDOUT)


def change_works_status(work: bool) -> None:
    """Включает или отключает white coin api"""

    subprocess.call(f"supervisorctl {'start' if work else 'stop'} white_coin", shell=True, stdout=DEVNULL, stderr=STDOUT)


# Добавить остальные функции из vk_bot/modules/admin_menu.py
# Адаптировать под Telegram

class UserIdNotFound(Exception):
    pass


class UserDataNotFound(Exception):
    pass


class UsersDataNotFound(Exception):
    pass


class ChatIdNotFound(Exception):
    pass


class ChatDataNotFound(Exception):
    pass


class ChatTypeNotFound(Exception):
    pass


class GameModeNotFound(Exception):
    pass


class ChatLifeDatetimeError(Exception):
    pass


class NumberNotFound(Exception):
    pass


class MaxTextLen(Exception):
    pass


class TimeStamp:
    pass


class ClansTop:
    pass


class AdminPanel:
    pass


TIME_STAMPS = []
TOPS = []
TOPS_NAME = {}


def get_time_stamp_keyboard():
    pass


def add_up_profit():
    pass


def get_develore_income(psql_cursor: DictCursor, redis_cursor: Redis) -> str:
    """Возвращает сообщение о прибыли программиста"""
    return "Прибыль программиста"


def clear_developer_income():
    pass

