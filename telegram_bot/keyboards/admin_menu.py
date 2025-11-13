import json
from telegram import ReplyKeyboardMarkup, KeyboardButton


def get_admin_menu_keyboard() -> ReplyKeyboardMarkup:
    """Возвращает клавиатуру для меню администраторов"""

    buttons = [
        [
            KeyboardButton(text="Прибыль"),
            KeyboardButton(text="Статистика")
        ],
        [
            KeyboardButton(text="Актив")
        ],
        [
            KeyboardButton(text="Топ"),
            KeyboardButton(text="Пользователи")
        ],
        [
            KeyboardButton(text="Назад")
        ]
    ]

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

