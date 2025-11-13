import time
import aiohttp
from enum import Enum
from pydantic import BaseModel
from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import json

from modules.telegram.bot import send_message, send_mailing_message


class MailingMenu(Enum):
    """Дополнительные меню для рассылки"""

    ATTACHMENT = "attachment"  # Меню выбора фото
    MESSAGE = "message"  # Меню написания текста


class ExtraMailing(BaseModel):
    """Дополнительные данные для меню рассылки"""

    menu: MailingMenu = MailingMenu.ATTACHMENT
    attachment: str | None = None  # хранит фото


def get_mailing_menu_keyboard() -> ReplyKeyboardMarkup:
    """Возвращает клавиатуру для меню рассылки"""

    buttons = [
        [KeyboardButton(text="Пропустить")],
        [KeyboardButton(text="Назад")]
    ]

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_mailing_keyboard() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру которая будет отправлена с текстом рассылки"""

    buttons = [
        [InlineKeyboardButton(
            text="Играть",
            callback_data=json.dumps({"event": "start_play_game"})
        )]
    ]

    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def start_mailing(
        message: str,
        attachment: str | None,
        keyboard: InlineKeyboardMarkup | None,
        psql_cursor
) -> None:
    """Запускает рассылку"""

    # Адаптировать логику из vk_bot/modules/mailing_menu.py
    # Использовать send_mailing_message из modules.telegram.bot
    pass

