from telegram import ReplyKeyboardMarkup, KeyboardButton

from schemas.users import UserSchema


def get_settings_menu_keyboard(user_data: UserSchema) -> ReplyKeyboardMarkup:
    """Возвращает клавиатуру для меню настроек"""

    show_balance_text = "✅ Показывать баланс" if user_data.show_balance else "❌ Показывать баланс"
    mailing_text = "✅ Рассылка" if user_data.mailing else "❌ Рассылка"

    buttons = [
        [KeyboardButton(text=show_balance_text)],
        [KeyboardButton(text=mailing_text)],
        [
            KeyboardButton(text="Получить ключ api"),
            KeyboardButton(text="Обновить ключ api")
        ],
        [
            KeyboardButton(text="Сменить имя"),
            KeyboardButton(text="Описание")
        ],
        [KeyboardButton(text="Назад")]
    ]

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

