"""Постоянная клавиатура для чатов"""
from telegram import ReplyKeyboardMarkup, KeyboardButton


def get_chat_persistent_keyboard() -> ReplyKeyboardMarkup:
    """Возвращает постоянную клавиатуру для чатов с кнопками Начать и Обновить"""
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🎮 Начать"),
                KeyboardButton(text="🔄 Обновить")
            ]
        ],
        resize_keyboard=True,
        is_persistent=True  # Клавиатура всегда видна
    )
    
    return keyboard


