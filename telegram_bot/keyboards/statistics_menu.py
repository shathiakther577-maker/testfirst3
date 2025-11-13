import json
from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


def get_statistics_menu_keyboard() -> ReplyKeyboardMarkup:
    """Возвращает клавиатуру для меню статистики"""

    buttons = [
        [
            KeyboardButton(text="🔝 Топ"),
            KeyboardButton(text="♻ Переводы")
        ],
        [KeyboardButton(text="Назад")]
    ]

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

