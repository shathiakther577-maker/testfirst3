from typing import Optional
from telegram import Bot
from settings import TelegramBotSettings


async def get_user_data(user_id: int) -> dict | None:
    """Возвращает данные пользователя по ID из Telegram"""

    try:
        bot = Bot(token=TelegramBotSettings.BOT_TOKEN)
        user = await bot.get_chat(user_id)
        return {
            "id": user.id,
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
            "username": user.username,
            "full_name": f"{user.first_name or ''} {user.last_name or ''}".strip()
        }
    except:
        return None


async def get_user_name(user_id: int) -> tuple[str, str, str]:
    """Возвращает (имя, фамилию, полное имя) пользователя в Telegram"""

    user_data = await get_user_data(user_id)
    if not user_data:
        return "", "", ""

    first_name = user_data.get("first_name", "")
    last_name = user_data.get("last_name", "")
    full_name = user_data.get("full_name", f"{first_name} {last_name}".strip())

    return first_name, last_name, full_name


def get_user_from_link(link: str | int) -> str:
    """Возвращает идентификатор или username пользователя из ссылки"""

    if isinstance(link, int):
        return str(link)

    # Убираем @ если есть
    link = link.replace("@", "").strip()
    
    # Если это числовой ID
    if link.isdigit():
        return link
    
    # Если это username
    return link


async def get_user_id(link: str) -> int | None:
    """Возвращает идентификатор пользователя по ссылке или username"""

    try:
        bot = Bot(token=TelegramBotSettings.BOT_TOKEN)
        
        # Если это числовой ID
        if link.isdigit():
            return int(link)
        
        # Если это username (без @)
        username = link.replace("@", "").strip()
        if username:
            user = await bot.get_chat(f"@{username}")
            return user.id
        
        return None
    except:
        return None


async def get_user_friends(user_id: int) -> list[int]:
    """Возвращает список друзей (в Telegram это не поддерживается напрямую)"""
    # В Telegram нет прямого API для получения друзей
    # Возвращаем пустой список
    return []


async def get_friends_amount(user_id: int) -> int:
    """Возвращает количество друзей (в Telegram не поддерживается)"""
    return 0


async def get_followers_amount(user_id: int) -> int:
    """Возвращает количество подписчиков (в Telegram не поддерживается напрямую)"""
    return 0


async def get_registration_date(user_id: int):
    """Возвращает дату регистрации (в Telegram не поддерживается напрямую)"""
    from datetime import datetime
    return datetime.today()


async def kick_user_from_chat(
        user_id: int,
        chat_id: int
) -> bool:
    """Исключает пользователя из чата"""

    try:
        bot = Bot(token=TelegramBotSettings.BOT_TOKEN)
        await bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
        await bot.unban_chat_member(chat_id=chat_id, user_id=user_id)
        return True
    except:
        return False


async def is_user_subscribed_to_channel(user_id: int, channel_id: int) -> bool:
    """Проверяет, подписан ли пользователь на канал"""
    
    try:
        bot = Bot(token=TelegramBotSettings.BOT_TOKEN)
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        # member.status может быть: 'member', 'administrator', 'creator', 'left', 'kicked', 'restricted'
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

