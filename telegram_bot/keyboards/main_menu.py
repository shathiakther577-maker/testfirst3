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


def get_main_menu_keyboard(user_data: UserSchema) -> tuple[ReplyKeyboardMarkup, InlineKeyboardMarkup | None]:
    """Возвращает клавиатуру главного меню"""
    
    # Основная клавиатура (ReplyKeyboardMarkup)
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
        KeyboardButton(text="Профиль"),
        KeyboardButton(text="Топы")
    ])

    buttons.append([
        KeyboardButton(text="Настройки"),
        KeyboardButton(text="Сервисы")
    ])

    reply_keyboard = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    
    # Inline клавиатура для топов (как в оригинале)
    inline_buttons = []
    
    if TopSettings.SWITCH_COINS_TOP or TopSettings.SWITCH_RUBLES_TOP:
        if TopSettings.SWITCH_COINS_TOP:
            label = (f"🎆 Топ в честь праздника на {reduce_number(sum(CoinsTop.REWARDS.values()))} WC"
                    if validate_rewards(CoinsTop) and TopSettings.SWITCH_COINS_TOP else
                    "🎆 Топ в честь праздника")
            inline_buttons.append([InlineKeyboardButton(
                text=label,
                callback_data=json.dumps({"event": "get_top_coins_message"})
            )])

        # Новогодний топ отключен
        # if TopSettings.SWITCH_RUBLES_TOP:
        #     label = (f"🎅 Новогодний топ на {reduce_number(sum(RublesTop.REWARDS.values()))} монеток"
        #             if validate_rewards(RublesTop) and TopSettings.SWITCH_RUBLES_TOP else
        #             "🔥 Розыгрыш монеток")
        #     inline_buttons.append([InlineKeyboardButton(
        #         text=label,
        #         callback_data=json.dumps({"event": "get_top_rubles_message"})
        #     )])

    if TopSettings.SWITCH_WEEK_TOP or TopSettings.SWITCH_WEEK_RUBLES_TOP:
        row = []
        if TopSettings.SWITCH_WEEK_TOP:
            label = (f"🎄 Топ недели на {reduce_number(sum(WeekTop.REWARDS.values()))} WC"
                    if validate_rewards(WeekTop) and TopSettings.SWITCH_WEEK_TOP else
                    "🎄 Топ недели")
            row.append(InlineKeyboardButton(
                text=label,
                callback_data=json.dumps({"event": "get_top_week_message"})
            ))

        if TopSettings.SWITCH_WEEK_RUBLES_TOP:
            label = (f"🎄 Топ недели на {reduce_number(sum(WeekRublesTop.REWARDS.values()))} монеток"
                    if validate_rewards(WeekRublesTop) and TopSettings.SWITCH_WEEK_RUBLES_TOP else
                    "🎄 Топ недели на монетоки")
            row.append(InlineKeyboardButton(
                text=label,
                callback_data=json.dumps({"event": "get_top_week_rubles_message"})
            ))
        if row:
            inline_buttons.append(row)

    if TopSettings.SWITCH_DAY_TOP or TopSettings.SWITCH_CLANS_TOP:
        row = []
        if TopSettings.SWITCH_DAY_TOP:
            label = (f"❄ Топ дня на {reduce_number(sum(DayTop.REWARDS.values()))} WC"
                    if validate_rewards(DayTop) and TopSettings.SWITCH_DAY_TOP else
                    "❄ Топ дня")
            row.append(InlineKeyboardButton(
                text=label,
                callback_data=json.dumps({"event": "get_top_day_message"})
            ))

        if TopSettings.SWITCH_CLANS_TOP:
            label = (f"🎁 Топ кланов на {reduce_number(sum(ClansTop.REWARDS.values()))} WC"
                    if validate_rewards(ClansTop) and TopSettings.SWITCH_CLANS_TOP else
                    "🎁 Топ кланов")
            row.append(InlineKeyboardButton(
                text=label,
                callback_data=json.dumps({"event": "get_top_clans_message"})
            ))
        if row:
            inline_buttons.append(row)

    inline_keyboard = InlineKeyboardMarkup(inline_keyboard=inline_buttons) if inline_buttons else None

    return reply_keyboard, inline_keyboard


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

