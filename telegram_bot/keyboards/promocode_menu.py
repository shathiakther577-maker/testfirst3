from telegram import ReplyKeyboardMarkup, KeyboardButton


def get_promocode_menu_keyboard() -> ReplyKeyboardMarkup:
    """Возвращает клавиатуру для меню промокодов"""

    buttons = [
        [KeyboardButton(text="Активировать промокод")],
        [KeyboardButton(text="Создать промокод")],
        [KeyboardButton(text="Информация о промокодах")],
        [KeyboardButton(text="Назад")]
    ]

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

