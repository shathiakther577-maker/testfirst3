from redis.client import Redis
from vk_api.keyboard import VkKeyboard

from schemas.redis import RedisKeys
from schemas.users import UserSchema

from modules.telegram.bot import send_message


# VK клавиатура удалена - будет создана Telegram версия при необходимости
banned_keyboard = None


async def notify_banned_user(user_data: UserSchema, redis_cursor: Redis):
    """Уведомляет пользователя о блокировке аккаунта"""

    user_id = user_data.user_id
    redis_key = f"{RedisKeys.NOTIFY_BANNED_USER.value}:{user_id}"

    if redis_cursor.get(redis_key) is None:
        await send_message(
            chat_id=user_id,
            message=f"❌ {user_data.telegram_name}, ты в бане, данная кнопка для тебя недоступна",
            keyboard=banned_keyboard
        )
        redis_cursor.setex(name=redis_key, value=1, time=10_800)
