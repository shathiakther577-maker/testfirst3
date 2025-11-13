from redis.client import Redis
from psycopg2.extras import DictCursor

from settings import Config, Temp

from schemas.users import UserSchema
from services.incomes import IncomesService
from services.security import SecurityService

from modules.additional import format_number, is_arabic_language
from modules.databases.users import register_user, update_free_nick_change, update_user_name
from modules.telegram.bot import send_message
from modules.telegram.users import get_user_name

from vk_bot.template_messages import SOMETHING_WENT_WRONG
from vk_bot.keyboards.main_menu import get_start_bonus_keyboard, get_main_menu_keyboard


async def first_greeting(
        user_id: int,
        psql_cursor: DictCursor,
        redis_cursor: Redis
) -> UserSchema | None:
    """Первое приветствие пользователя"""

    if user_id in Temp.REGISTER_USERS:
        return None
    Temp.REGISTER_USERS.append(user_id)

    try:
        _, _, full_name = await get_user_name(user_id)
        full_name = SecurityService.replace_banned_symbols(full_name)
        user_data = register_user(user_id, full_name, psql_cursor)

        await send_message(
            chat_id=user_id,
            message="🔥 Добро пожаловать в White Coin",
            keyboard=get_main_menu_keyboard(user_data)
        )

        if Config.GETTING_START_BONUS:
            await send_message(
                chat_id=user_id,
                message="Чтобы получить бонус нажмите на кнопку",
                keyboard=get_start_bonus_keyboard()
            )

        if is_arabic_language(full_name):
            update_user_name(user_id, "Empty", psql_cursor)
            update_free_nick_change(user_id, True, psql_cursor)
            await send_message(
                chat_id=user_id,
                message="⚠ Ваш никнейм был изменён, т.к содержит запрещённые символы, "
                        "вам доступна бесплатная смена никнейма!"
            )

        return user_data

    except:
        pass

    finally:
        Temp.REGISTER_USERS.remove(user_id)


async def get_start_bonus(
        user_id: int,
        user_data: UserSchema,
        psql_cursor: DictCursor,
        redis_cursor: Redis
) -> str:
    """Возвращает сообщение о выдаче бонуса"""

    if user_id in Temp.GET_START_BONUS:
        return "Выдача бонуса стоит в очереди"
    Temp.GET_START_BONUS.append(user_id)

    try:
        if user_data.start_bonus is False:
            psql_cursor.execute("""
                UPDATE users
                SET coins = coins + %(reward)s,
                    start_bonus = TRUE
                WHERE user_id = %(user_id)s
            """, {
                "reward": Config.REWARD_START_BONUS,
                "user_id": user_id
            })

            IncomesService.records_additional_expenses(
                amount=Config.REWARD_START_BONUS,
                redis_cursor=redis_cursor
            )

            response = f"✅ Вы получили {format_number(Config.REWARD_START_BONUS)} BC"

        else:
            response = "❌ Вы уже забрали эту награду"

        await send_message(chat_id=user_id, message=response)

    except:
        return SOMETHING_WENT_WRONG

    finally:
        Temp.GET_START_BONUS.remove(user_id)
