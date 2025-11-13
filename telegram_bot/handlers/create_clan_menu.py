from redis.client import Redis
from psycopg2.extras import DictCursor

from settings import ServicesCosts, NotifyChats

from schemas.users import UserSchema, UserMenu
from schemas.clans import ExtraCreateClan, CreateClanMenu, ClanTypeApplication, \
    ExtraOwnerClan

from services.clans import ClanService
from services.incomes import IncomesService
from services.security import SecurityService
from services.notification import NotificationsService

from modules.additional import format_number
from modules.databases.users import update_user_menu, update_user_extra_data, \
    take_coins
from modules.telegram.bot import send_message

from telegram_bot.template_messages import BACK_SERVICES_MENU, COMMAND_NOT_FOUND, \
    PATTERN_BANNED_SYMBOLS, CLAN_NAME_LENGTH, CLAN_TAG_LENGTH, CLAN_NAME_OCCUPIED, \
    CLAN_TAG_OCCUPIED, CLAN_GREETING, NOT_ENOUGH_COINS
from telegram_bot.keyboards.other import back_keyboard
from telegram_bot.keyboards.main_menu import get_main_menu_keyboard
from telegram_bot.keyboards.clans_menu import get_create_clan_keyboard, \
    get_clan_owner_keyboard


async def handler_menu_create_clan(
        *,
        user_id: int,
        user_data: UserSchema,
        message: str,
        original_message: str,
        payload: dict | None,
        psql_cursor: DictCursor,
        redis_cursor: Redis
) -> None:
    """Обрабатывает сообщения в меню создания клана"""

    extra_data = ExtraCreateClan(**user_data.extra_data)

    if extra_data.menu == CreateClanMenu.MAIN:

        if message == "меню":
            response = BACK_SERVICES_MENU
            keyboard = get_main_menu_keyboard(user_data)
            update_user_menu(user_id, UserMenu.MAIN, psql_cursor)
            update_user_extra_data(user_id, None, psql_cursor)

        # Добавить остальную логику из vk_bot/handlers/create_clan_menu.py
        else:
            response = COMMAND_NOT_FOUND
            keyboard = get_create_clan_keyboard()

    # Добавить остальную логику
    else:
        response = COMMAND_NOT_FOUND
        keyboard = get_create_clan_keyboard()

    await send_message(user_id, response, keyboard)

