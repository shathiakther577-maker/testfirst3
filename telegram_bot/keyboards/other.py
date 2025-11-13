import json
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton


empty_keyboard = ReplyKeyboardMarkup(keyboard=[[]], resize_keyboard=True)

back_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Назад")]],
    resize_keyboard=True
)

repeat_chat_subscription_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton(
        text="Повторить подписку",
        callback_data=json.dumps({"event": "repeat_chat_subscription"})
    )]
])


def get_disabled_sub_chat_notif_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    """Возвращает клавиатуру для отключение уведомление об окончании подписки на чат"""

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            text="Отключить оповещения",
            callback_data=json.dumps({
                "handler": "processing_menus",
                "event": "disabled_sub_chat_notif",
                "chat_id": chat_id
            })
        )]
    ])

