import asyncio
import subprocess
from enum import Enum
from datetime import datetime
from subprocess import STDOUT, DEVNULL
from redis.client import Redis
from psycopg2.extras import DictCursor
import json
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

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


def get_develore_income(psql_cursor: DictCursor, redis_cursor: Redis) -> str:
    """Возвращает сообщение о прибыли программиста"""

    psql_cursor.execute("""
        SELECT datetime, developer_income as income
        FROM bot_statistics
        WHERE developer_income is not NULL
        ORDER BY datetime ASC
    """)
    psql_response = psql_cursor.fetchall()
    len_psql_response = len(psql_response)

    day_name = get_word_case(len_psql_response, ('день', 'дня', 'дней'))
    income_sum = sum([x['income'] for x in psql_response])

    response = "\n".join([f"{x['datetime']} = {format_number(x['income'])}" for x in psql_response])

    day_stats = IncomesService.get_day_statistics(redis_cursor, psql_cursor)
    dev_share = Config.BOT_OWNERS_SHARES.get(Config.DEVELOPER_ID)
    dev_income = format_number(round(day_stats.rubles_income * dev_share))
    response += f"\n{datetime.now().date()} = {dev_income} (НЕ УЧИТЫВАЕТСЯ)"

    response += f"\n\nИтого: {format_number(income_sum)} за {len_psql_response} {day_name}"

    return response


def clear_developer_income(psql_cursor: DictCursor) -> None:
    """Очищает значение прибыли программиста"""

    psql_cursor.execute("UPDATE bot_statistics SET developer_income = NULL")


def add_up_profit(up_profit: dict, day_profit: dict) -> dict:
    """Возвращает словарь прибавляет day_profit к up_profit"""

    return {
        "coins": int(up_profit["coins"] + day_profit["coins"]),
        "rubles": int(up_profit["rubles"] + day_profit["rubles"])
    }


class TimeStamp(Enum):
    """Временные отметки"""

    DAY = "day"
    WEEK = "week"
    ALL = "all"

TIME_STAMPS = [x.value for x in TimeStamp]


def get_time_stamp_keyboard(*, event: str) -> InlineKeyboardMarkup:
    """Возвращает клавиатуру с отметками времени"""

    buttons = [
        [
            InlineKeyboardButton(
                text="День",
                callback_data=json.dumps({"event": event, "time_stamp": TimeStamp.DAY.value})
            ),
            InlineKeyboardButton(
                text="Неделя",
                callback_data=json.dumps({"event": event, "time_stamp": TimeStamp.WEEK.value})
            )
        ],
        [
            InlineKeyboardButton(
                text="Все время",
                callback_data=json.dumps({"event": event, "time_stamp": TimeStamp.ALL.value})
            )
        ]
    ]

    return InlineKeyboardMarkup(inline_keyboard=buttons)


TOPS = {
    DayTop.NAME: DayTopService,
    WeekTop.NAME: WeekTopService,
    ClansTop.NAME: ClansTopService,
    CoinsTop.NAME: CoinsTopService,
    RublesTop.NAME: RublesTopService,
    AllTimeTop.NAME: AllTimeTopService,
    WeekRublesTop.NAME: WeekRublesTopService
}
TOPS_NAME = list(TOPS.keys())


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


class AdminPanel:

    @classmethod
    async def get_user_data(
            cls,
            user: str,
            psql_cursor: DictCursor
    ) -> UserSchema:
        """Возвращает данные пользователя для админ панели"""

        user_id = await get_user_id(user)
        if user_id is None:
            raise UserIdNotFound(f"❌ Не удалось получить user_id из {user}")

        user_data = get_user_data(user_id, psql_cursor)
        if user_data is None:
            raise UserDataNotFound(f"❌ {UserSchema.format_telegram_name(user_id, 'Пользователь')} не зарегистрирован")

        return user_data


    @classmethod
    async def get_users_data(
            cls,
            users: list[str],
            psql_cursor: DictCursor
    ) -> list[UserSchema]:
        """Возвращает данные пользователей для админ панели"""

        user_ids = [await get_user_id(x) for x in users]
        users_data = [i for i in [get_user_data(x, psql_cursor) for x in user_ids] if i is not None]

        if len(users_data) == 0:
            raise UsersDataNotFound(f"❌ Не удалось найти ни одного зарегистрированного пользователя")

        return users_data


    @classmethod
    def get_chat_data(
            cls,
            chat: str,
            psql_cursor: DictCursor
    ) -> ChatSchema:
        """Возвращает данные чата для админ панели"""

        if not chat.isdecimal():
            raise ChatIdNotFound(f"❌ Не удалось получить chat_id из {chat}")

        chat = int(chat)
        # В Telegram chat_id может быть положительным или отрицательным
        # Для совместимости с БД используем как есть
        chat_id = chat

        chat_data = get_chat_data(chat_id, psql_cursor)
        if chat_data is None:
            raise ChatDataNotFound(f"❌ Чат {chat} не зарегистрирован ")

        return chat_data


    @classmethod
    def get_chat_type(
            cls,
            new_type: str
    ) -> ChatType:
        """Возвращает тип чата для админ панели"""

        new_type = new_type.capitalize()

        if new_type not in CHAT_TYPES_NAME:
            raise ChatTypeNotFound(f"❌ Не существует типа чата: {new_type}")

        return ChatType(new_type)


    @classmethod
    def get_game_mode(
            cls,
            new_game_mode: str
    ) -> Games:
        """Возвращает игровой режим для админ панели"""

        if new_game_mode not in ALL_GAMES_VALUES:
            raise GameModeNotFound(f"❌ Игрового режима {new_game_mode} не существует")

        return Games(new_game_mode)


    @classmethod
    def get_life_datetime(
            cls,
            new_life: str
    ) -> datetime:
        """Возвращает новое время жизни чата для админ панели"""

        try:
            return datetime.strptime(new_life, "%Y-%m-%d %H:%M:%S")

        except:
            raise ChatLifeDatetimeError("❌ Время должно иметь вид 2030-12-30 23:59:59")


    @classmethod
    def get_number(cls, string: str) -> int:
        """Возвращает число для админ панели"""

        number = convert_number(string)
        if number is None:
            raise NumberNotFound(f"❌ Это {string} не похоже на число")

        return number


    @classmethod
    def update_user_status(
        cls,
        user_id: int,
        new_status: UserStatus,
        psql_cursor: DictCursor
    ) -> None:
        """Изменяет статус пользователя"""

        psql_cursor.execute("""
            UPDATE users
            SET status = %(status)s
            WHERE user_id = %(user_id)s
        """, {
            "status": new_status.value,
            "user_id": user_id
        })
