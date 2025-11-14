import json
from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


def get_statistics_menu_keyboard() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру для меню статистики"""

    buttons = [
        [
            InlineKeyboardButton(
                text="🔝 Топ",
                callback_data=json.dumps({"event": "get_bet_balance_message"})
            ),
            InlineKeyboardButton(
                text="♻ Переводы",
                callback_data=json.dumps({"event": "get_transfers_statistics_message"})
            )
        ]
    ]

    return InlineKeyboardMarkup(inline_keyboard=buttons)

