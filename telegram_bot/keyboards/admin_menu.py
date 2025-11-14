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


def get_user_management_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    """Возвращает клавиатуру для управления пользователем"""

    buttons = [
        [
            KeyboardButton(text=f"💰 Выдать {user_id}"),
            KeyboardButton(text=f"📉 Забрать {user_id}")
        ],
        [
            KeyboardButton(text=f"⚙️ Установить {user_id}"),
            KeyboardButton(text=f"ℹ️ Инфо {user_id}")
        ],
        [
            KeyboardButton(text=f"🚫 Забанить {user_id}"),
            KeyboardButton(text=f"✅ Разбанить {user_id}")
        ],
        [
            KeyboardButton(text="Назад")
        ]
    ]

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

