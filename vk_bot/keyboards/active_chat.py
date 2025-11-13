import random
from vk_api.keyboard import VkKeyboard, VkKeyboardColor

from schemas.chats import ChatSchema
from schemas.games import ALL_GAMES
from schemas.chats import ChatStatsPeriod, CHAT_STATS_PAYLOAD


keyboard_repeat_bet = VkKeyboard(one_time=False, inline=True)
keyboard_repeat_bet.add_button(
    label="Повторить игру",
    color=VkKeyboardColor.POSITIVE,
    payload={"event": "accept_repeat_game"}
)
keyboard_repeat_bet.add_button(
    label="Авто Игра",
    color=VkKeyboardColor.POSITIVE,
    payload={"event": "auto_game"}
)
keyboard_repeat_bet = keyboard_repeat_bet.get_keyboard()


keyboard_game_bank = VkKeyboard(one_time=False, inline=True)
keyboard_game_bank.add_button(
    label="Последние игры",
    color=VkKeyboardColor.POSITIVE,
    payload={"event": "get_last_games"}
)
keyboard_game_bank.add_line()
keyboard_game_bank.add_button(
    label="Управление чатом",
    color=VkKeyboardColor.SECONDARY,
    payload={"event": "get_chat_help"}
)
keyboard_game_bank = keyboard_game_bank.get_keyboard()


def get_chat_management_keyboard(chat_data: ChatSchema) -> str:
    """Возвращает клавиатуру управления чатом"""

    keyboard = VkKeyboard(one_time=False, inline=True)
    keyboard.add_button(
    label="📊 Статистика",
    payload={
        "event": CHAT_STATS_PAYLOAD,
        "period": ChatStatsPeriod.DAY.value
    }
)
    keyboard.add_line()

    keyboard.add_button(
        label="🎮 Режимы",
        payload={"event": "change_game_mode"}
    )
    keyboard.add_button(
        label="⏳ Таймер",
        payload={"event": "change_game_timer"}
    )
    keyboard.add_line()

    keyboard.add_button(
        label="➕ Помощника",
        payload={"event": "add_chat_helper"}
    )
    keyboard.add_button(
        label="❌ Помощника",
        payload={"event": "del_chat_helper"}
    )
    keyboard.add_line()

    keyboard.add_button(
        label="👥 Список персонала",
        payload={"event": "show_personnel"}
    )
    keyboard.add_line()

    keyboard.add_button(
        label="✏ Ник беседы",
        payload={"event": "change_chat_name"}
    )
    keyboard.add_button(
        label="‼ Статья",
        color=VkKeyboardColor.POSITIVE if chat_data.article_notify else VkKeyboardColor.NEGATIVE,
        payload={"event": "article_notify"}
    )
    keyboard.add_line()


    return keyboard.get_keyboard()


keyboard_cancel_event_menu = VkKeyboard(one_time=False, inline=True)
keyboard_cancel_event_menu.add_button(
    label="Отменить",
    color=VkKeyboardColor.NEGATIVE,
    payload={"event": "cancel_event_menu"}
)
keyboard_cancel_event_menu = keyboard_cancel_event_menu.get_keyboard()
# Клавиатура для отмены действий в меню чата


def get_keyboard_change_game_mode() -> str:
    """Возвращает клавиатуру для выбора игрового режима"""

    MAX_ROW = 2  # Максимальное количество элементов строке
    MAX_BUTTONS = 8  # Максимальное количество кнопок (vk api 10)

    games = random.sample(ALL_GAMES, MAX_BUTTONS)
    keyboard = VkKeyboard(one_time=False, inline=True)

    for index, game in enumerate(games):

        if 0 < index < len(games) and index % MAX_ROW == 0:
            keyboard.add_line()

        keyboard.add_button(
            label=game.name,
            color=VkKeyboardColor.POSITIVE,
            payload={
                "event": "change_game_mode",
                "game_mode": game
            }
        )

    if len(games) > 0:
        keyboard.add_line()
        keyboard.add_button(
            label="🔄",
            color=VkKeyboardColor.PRIMARY,
            payload={"event": "change_game_mode"}
        )
        keyboard.add_line()

    keyboard.add_button(
        label="Отменить",
        color=VkKeyboardColor.NEGATIVE,
        payload={"event": "cancel_event_menu"}
    )

    return keyboard.get_keyboard()
