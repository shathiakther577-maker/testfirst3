import random
from vk_api.keyboard import VkKeyboard, VkKeyboardColor

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


def get_start_bonus_keyboard() -> str:
    """Возвращает клавиатуру со стартовым бонусом"""

    keyboard = VkKeyboard(one_time=False, inline=True)
    keyboard.add_button(
        label="💰 Получить бонус",
        color=VkKeyboardColor.POSITIVE,
        payload={"event": "get_start_bonus"}
    )

    return keyboard.get_keyboard()


def get_main_menu_keyboard(user_data: UserSchema) -> str:
    """Возвращает клавиатуру главного меню"""

    keyboard = VkKeyboard(one_time=False, inline=False)

    if user_data.status == UserStatus.ADMIN:
        keyboard.add_button(label="🕶Админ", color=VkKeyboardColor.NEGATIVE)
        keyboard.add_line()

    keyboard.add_button(label="Играть", color=VkKeyboardColor.POSITIVE)
    keyboard.add_button(label="Как играть?", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()

    keyboard.add_button(label="Перевести Другу", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()

    keyboard.add_button(label="Настройки", color=VkKeyboardColor.SECONDARY)
    keyboard.add_button(label="Сервисы", color=VkKeyboardColor.SECONDARY)

    if TopSettings.SWITCH_COINS_TOP or TopSettings.SWITCH_RUBLES_TOP:
        keyboard.add_line()

    if TopSettings.SWITCH_COINS_TOP:
        keyboard.add_button(
            label=f"🎆 Топ в честь праздника на {reduce_number(sum(CoinsTop.REWARDS.values()))} BC"
                if validate_rewards(CoinsTop) and TopSettings.SWITCH_COINS_TOP else
            "🎆 Топ в честь праздника",
            color=VkKeyboardColor.NEGATIVE,
            payload={"event": "get_top_coins_message"}
        )

    if TopSettings.SWITCH_RUBLES_TOP:
        keyboard.add_button(
            label=f"🎅 Новогодний топ на {reduce_number(sum(RublesTop.REWARDS.values()))} монеток"
                if validate_rewards(RublesTop) and TopSettings.SWITCH_RUBLES_TOP else
            "🔥 Розыгрыш монеток",
            color=VkKeyboardColor.NEGATIVE,
            payload={"event": "get_top_rubles_message"}
        )

    if TopSettings.SWITCH_WEEK_TOP or TopSettings.SWITCH_WEEK_RUBLES_TOP:
        keyboard.add_line()

    if TopSettings.SWITCH_WEEK_TOP:
        keyboard.add_button(
            label=f"🎄 Топ недели на {reduce_number(sum(WeekTop.REWARDS.values()))} BC"
                if validate_rewards(WeekTop) and TopSettings.SWITCH_WEEK_TOP else
            "🎄 Топ недели",
            color=VkKeyboardColor.NEGATIVE,
            payload={"event": "get_top_week_message"}
        )

    if TopSettings.SWITCH_WEEK_RUBLES_TOP:
        keyboard.add_button(
            label=f"🎄 Топ недели на {reduce_number(sum(WeekRublesTop.REWARDS.values()))} монеток"
                if validate_rewards(WeekRublesTop) and TopSettings.SWITCH_WEEK_RUBLES_TOP else
            "🎄 Топ недели на монетоки",
            color=VkKeyboardColor.NEGATIVE,
            payload={"event": "get_top_week_rubles_message"}
        )

    if TopSettings.SWITCH_DAY_TOP or TopSettings.SWITCH_CLANS_TOP:
        keyboard.add_line()

    if TopSettings.SWITCH_DAY_TOP:
        keyboard.add_button(
            label=f"❄ Топ дня на {reduce_number(sum(DayTop.REWARDS.values()))} BC"
                if validate_rewards(DayTop) and TopSettings.SWITCH_DAY_TOP else
            "❄ Топ дня",
            color=VkKeyboardColor.NEGATIVE,
            payload={"event": "get_top_day_message"}
        )

    if TopSettings.SWITCH_CLANS_TOP:
        keyboard.add_button(
            label=f"🎁 Топ кланов на {reduce_number(sum(ClansTop.REWARDS.values()))} BC"
                if validate_rewards(ClansTop) and TopSettings.SWITCH_CLANS_TOP else
            "🎁 Топ кланов",
            color=VkKeyboardColor.NEGATIVE,
            payload={"event": "get_top_clans_message"}
        )

    return keyboard.get_keyboard()


def get_game_selection_keyboard() -> str:
    """Возвращает клавиатуру выбора игры для получения чата"""

    MAX_ROW = 3  # Максимальное количество элементов строке
    MAX_BUTTONS = 10  # Максимальное количество кнопок (vk api 10)

    games = (random.sample(ALL_GAMES, k=MAX_BUTTONS))
    keyboard = VkKeyboard(one_time=False, inline=True)

    for index, game in enumerate(games):

        if 0 < index < len(games) and index % MAX_ROW == 0:
            keyboard.add_line()

        keyboard.add_button(
            label=GAME_NAMES[game],
            color=VkKeyboardColor.POSITIVE,
            payload={
                "event": "get_link_game_chat",
                "game": game.value
            }
        )

    return keyboard.get_keyboard()


