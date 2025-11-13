import json
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

from schemas.chats import ChatSchema
from schemas.games import ALL_GAMES_VALUES, GAME_NAMES


def get_keyboard_change_game_mode() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру для смены игрового режима"""

    buttons = []
    for game in ALL_GAMES_VALUES:
        buttons.append([InlineKeyboardButton(
            text=GAME_NAMES[game],
            callback_data=json.dumps({
                "event": "change_game_mode",
                "game_mode": game.value
            })
        )])

    buttons.append([InlineKeyboardButton(
        text="Отмена",
        callback_data=json.dumps({"event": "cancel_event_menu"})
    )])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_chat_management_keyboard(chat_data: ChatSchema) -> InlineKeyboardMarkup:
    """Возвращает клавиатуру управления чатом"""

    buttons = [
        [InlineKeyboardButton(
            text="Изменить имя",
            callback_data=json.dumps({"event": "change_chat_name"})
        )],
        [InlineKeyboardButton(
            text="Изменить режим",
            callback_data=json.dumps({"event": "change_game_mode"})
        )],
        [InlineKeyboardButton(
            text="Изменить таймер",
            callback_data=json.dumps({"event": "change_game_timer"})
        )],
        [InlineKeyboardButton(
            text="Помощники",
            callback_data=json.dumps({"event": "show_personnel"})
        )],
        [InlineKeyboardButton(
            text="Статистика",
            callback_data=json.dumps({"event": "get_chat_stats", "period": "day"})
        )]
    ]

    return InlineKeyboardMarkup(inline_keyboard=buttons)


keyboard_repeat_bet = InlineKeyboardMarkup([
    [InlineKeyboardButton(
        text="Повторить ставку",
        callback_data=json.dumps({"event": "accept_repeat_game"})
    )],
    [InlineKeyboardButton(
        text="Авто игра",
        callback_data=json.dumps({"event": "auto_game"})
    )]
])


keyboard_cancel_event_menu = InlineKeyboardMarkup([
    [InlineKeyboardButton(
        text="Отмена",
        callback_data=json.dumps({"event": "cancel_event_menu"})
    )]
])

