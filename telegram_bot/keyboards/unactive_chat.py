import json
import random
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

from schemas.chats import ChatType, INCOME_CHAT_TYPE, CHAT_TYPE_COST
from schemas.games import ALL_GAMES, GAME_NAMES
from modules.additional import reduce_number


def get_keyboard_select_game_mode() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру выбора игрового режима"""

    MAX_ROW = 3
    MAX_BUTTONS = 9

    games = random.sample(ALL_GAMES, k=min(MAX_BUTTONS, len(ALL_GAMES)))
    buttons = []

    for index, game in enumerate(games):
        if index % MAX_ROW == 0:
            buttons.append([])
        
        buttons[-1].append(InlineKeyboardButton(
            text=GAME_NAMES[game],
            callback_data=json.dumps({
                "event": "select_game",
                "game": game.value
            })
        ))

    if games:
        buttons.append([InlineKeyboardButton(
            text="Обновить список",
            callback_data=json.dumps({"event": "update_select_game"})
        )])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_keyboard_select_chat_type() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру для выбора типа беседы"""

    buttons = []

    for chat_type in ChatType:
        chat_type_name = chat_type.value
        chat_income = INCOME_CHAT_TYPE[chat_type]
        chat_cost = CHAT_TYPE_COST[chat_type]

        buttons.append([InlineKeyboardButton(
            text=f"{chat_type_name} {chat_income}% ({reduce_number(chat_cost)})",
            callback_data=json.dumps({
                "event": "set_chat_type",
                "chat_type": chat_type.value
            })
        )])

    buttons.append([InlineKeyboardButton(
        text="Назад к выбору режима",
        callback_data=json.dumps({"event": "update_select_game"})
    )])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

