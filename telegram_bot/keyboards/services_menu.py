from telegram import ReplyKeyboardMarkup, KeyboardButton


def get_services_menu_keyboard() -> ReplyKeyboardMarkup:
    """Возвращает клавиатуру для меню сервисов"""

    buttons = [
        [
            KeyboardButton(text="Промокоды"),
            KeyboardButton(text="Кланы")
        ],
        [
            KeyboardButton(text="Мои чаты"),
            KeyboardButton(text="Статистика")
        ],
        [KeyboardButton(text="Назад")]
    ]

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

