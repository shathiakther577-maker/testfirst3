import re
import asyncio
from datetime import datetime
from redis.client import Redis
from psycopg2.extras import DictCursor

from settings import ServicesCosts, ClanSettings

from schemas.users import UserSchema, UserMenu
from schemas.clans import ExtraOwnerClan, OwnerClanMenu, ClanSchema, \
    ClanJoinType, ClanRole

from services.clans import ClanService
from services.incomes import IncomesService
from services.security import SecurityService

from modules.additional import format_number, convert_number
from modules.databases.users import update_user_menu, update_user_extra_data, \
    take_coins, get_user_data
from modules.telegram.bot import send_message, send_keyboard
from modules.telegram.users import get_user_id

from telegram_bot.template_messages import BACK_MAIN_MENU, COMMAND_NOT_FOUND, \
    CLAN_NAME_LENGTH, CLAN_TAG_LENGTH, PATTERN_BANNED_SYMBOLS, NOT_ENOUGH_COINS, \
    CLAN_NAME_OCCUPIED, CLAN_TAG_OCCUPIED, USER_NOT_FOUND, USER_HAVE_CLAN, \
    MAX_COUNT_MEMBERS_IN_CLAN, APPLICATION_ALREADY_SENT, APPLICATION_SENT
from telegram_bot.keyboards.other import back_keyboard
from telegram_bot.keyboards.main_menu import get_main_menu_keyboard
from telegram_bot.keyboards.clans_menu import get_clan_owner_keyboard, \
    get_keyboard_managing_members, get_clan_settings_keyboard, get_keyboard_delete_clan, \
    get_keyboard_change_clan_join_type, get_keyboard_answer_user_join_clan


def go_clan_main_menu(
        clan_data: ClanSchema,
        owner_data: UserSchema,
        psql_cursor: DictCursor
) -> tuple[str, str]:
    """
        Отправляет пользователя в главное меню клана
        и возвращает сообщение и клавиатуру
    """

    response = ClanService.format_message_clan_info(clan_data, owner_data)
    keyboard = get_clan_owner_keyboard()

    update_user_extra_data(
        user_id=owner_data.user_id,
        extra_data=ExtraOwnerClan(),
        psql_cursor=psql_cursor
    )

    return response, keyboard


async def handler_management_clan_owner_menu(
        owner_id: int,
        owner_data: UserSchema,
        message: str,
        original_message: str,
        payload: dict | None,
        psql_cursor: DictCursor,
        redis_cursor: Redis
) -> None:
    """Обрабатывает сообщения владельца клана"""

    # Адаптировать логику из vk_bot/handlers/management_clan_owner_menu.py
    response = COMMAND_NOT_FOUND
    keyboard = get_clan_owner_keyboard()

    await send_message(owner_id, response, keyboard)

