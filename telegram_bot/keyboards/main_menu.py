import json
import random
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

from settings import TopSettings

from tops.day_top import DayTop
from tops.week_top import WeekTop
from tops.clans_top import ClansTop
from tops.coins_top import CoinsTop
from tops.rubles_top import RublesTop
from tops.week_rubles_top import WeekRublesTop

from schemas.users import UserSchema, UserStatus
from schemas.games import ALL_GAMES, GAME_NAMES

from modules.additional import reduce_number


def validate_rewards(top) -> bool:
    """Проверяет включен ли топ"""

    return top.REWARDS is not None and all(top.REWARDS.values())


def get_start_bonus_keyboard() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру со стартовым бонусом"""

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            text="💰 Получить бонус",
            callback_data=json.dumps({"event": "get_start_bonus"})
        )]
    ])


def get_main_menu_keyboard(user_data: UserSchema) -> ReplyKeyboardMarkup:
    """Возвращает клавиатуру главного меню"""

    buttons = []

    if user_data.status == UserStatus.ADMIN:
        buttons.append([KeyboardButton(text="🕶Админ")])

    buttons.append([
        KeyboardButton(text="Играть"),
        KeyboardButton(text="Как играть?")
    ])

    buttons.append([
        KeyboardButton(text="Перевести Другу")
    ])

    buttons.append([
        KeyboardButton(text="Настройки"),
        KeyboardButton(text="Сервисы")
    ])

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_game_selection_keyboard() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру выбора игры для получения чата"""

    MAX_ROW = 3  # Максимальное количество элементов в строке
    MAX_BUTTONS = 10  # Максимальное количество кнопок

    games = random.sample(ALL_GAMES, k=min(MAX_BUTTONS, len(ALL_GAMES)))
    buttons = []

    for index, game in enumerate(games):
        if index % MAX_ROW == 0:
            buttons.append([])
        
        buttons[-1].append(InlineKeyboardButton(
            text=GAME_NAMES[game],
            callback_data=json.dumps({
                "event": "get_link_game_chat",
                "game": game.value
            })
        ))

    return InlineKeyboardMarkup(inline_keyboard=buttons)

