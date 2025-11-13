import json
import random
from typing import Optional
from telegram import Bot, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.error import TelegramError
from telegram.constants import ParseMode

from settings import TelegramBotSettings


async def send_message(
        chat_id: int,
        message: str | None = None,
        keyboard: InlineKeyboardMarkup | ReplyKeyboardMarkup | None = None,
        photo: str | None = None,
        parse_mode: str = ParseMode.HTML,
        reply_to_message_id: int | None = None
) -> int | None:
    """Отправляет сообщения в Telegram"""

    if message is None and photo is None:
        return None

    try:
        bot = Bot(token=TelegramBotSettings.BOT_TOKEN)

        if photo:
            result = await bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=message,
                reply_markup=keyboard,
                parse_mode=parse_mode,
                reply_to_message_id=reply_to_message_id
            )
        else:
            # Разбиваем длинные сообщения на части
            if message and len(message) > 4096:
                # Отправляем первую часть
                last_space = message[:4096].rfind(" ")
                first_part = message[:last_space] if last_space > 0 else message[:4096]
                result = await bot.send_message(
                    chat_id=chat_id,
                    text=first_part,
                    reply_markup=keyboard,
                    parse_mode=parse_mode,
                    reply_to_message_id=reply_to_message_id
                )
                # Отправляем остальные части
                remaining = message[last_space:]
                if remaining:
                    await send_message(chat_id, remaining, None, None, parse_mode)
                return result.message_id
            else:
                result = await bot.send_message(
                    chat_id=chat_id,
                    text=message or "",
                    reply_markup=keyboard,
                    parse_mode=parse_mode,
                    reply_to_message_id=reply_to_message_id
                )

        return result.message_id

    except TelegramError as e:
        print(f"Telegram error: {e}")
        return None
    except Exception as e:
        print(f"Error sending message: {e}")
        return None


async def send_mailing_message(
        *,
        bot: Bot,
        chat_ids: list[int],
        message: str | None = None,
        keyboard: InlineKeyboardMarkup | ReplyKeyboardMarkup | None = None,
        photo: str | None = None
) -> None:
    """Отправляет массовые сообщения в Telegram"""

    for chat_id in chat_ids:
        try:
            await send_message(chat_id, message, keyboard, photo)
        except:
            pass


async def delete_message(chat_id: int, message_id: int) -> bool:
    """Удаляет отправленные сообщения"""

    try:
        bot = Bot(token=TelegramBotSettings.BOT_TOKEN)
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        return True
    except:
        return False


async def send_keyboard(chat_id: int, keyboard: InlineKeyboardMarkup | ReplyKeyboardMarkup) -> None:
    """Отправляет клавиатуру без сообщения"""

    try:
        bot = Bot(token=TelegramBotSettings.BOT_TOKEN)
        await bot.send_message(
            chat_id=chat_id,
            text="\u200B",  # Невидимый символ
            reply_markup=keyboard
        )
    except:
        pass


async def edit_message(
        chat_id: int,
        message_id: int,
        text: str,
        keyboard: InlineKeyboardMarkup | None = None,
        parse_mode: str = ParseMode.HTML
) -> bool:
    """Редактирует сообщение"""

    try:
        bot = Bot(token=TelegramBotSettings.BOT_TOKEN)
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=keyboard,
            parse_mode=parse_mode
        )
        return True
    except:
        return False


async def get_chat_member(chat_id: int, user_id: int):
    """Получает информацию о участнике чата"""

    try:
        bot = Bot(token=TelegramBotSettings.BOT_TOKEN)
        return await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
    except:
        return None


async def get_chat(chat_id: int):
    """Получает информацию о чате"""

    try:
        bot = Bot(token=TelegramBotSettings.BOT_TOKEN)
        return await bot.get_chat(chat_id=chat_id)
    except:
        return None

