from typing import Optional
from telegram import Bot
from telegram.constants import ChatMemberStatus
from settings import TelegramBotSettings


async def get_chat_owner_id(chat_id: int) -> int | None:
    """Возвращает идентификатор создателя чата"""

    try:
        bot = Bot(token=TelegramBotSettings.BOT_TOKEN)
        chat = await bot.get_chat(chat_id)
        
        # В Telegram создатель чата имеет статус OWNER или ADMINISTRATOR
        # Получаем список администраторов
        administrators = await bot.get_chat_administrators(chat_id)
        
        # Ищем создателя (обычно первый в списке или с правами creator)
        for admin in administrators:
            if admin.status == ChatMemberStatus.OWNER:
                return admin.user.id
        
        # Если не нашли OWNER, возвращаем первого администратора
        if administrators:
            return administrators[0].user.id
        
        return None
    except:
        return None


async def get_chat_info(chat_id: int) -> dict | None:
    """Возвращает информацию о чате"""

    try:
        bot = Bot(token=TelegramBotSettings.BOT_TOKEN)
        chat = await bot.get_chat(chat_id)
        return {
            "id": chat.id,
            "title": chat.title,
            "type": chat.type,
            "username": chat.username
        }
    except:
        return None

