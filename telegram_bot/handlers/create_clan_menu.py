from redis.client import Redis
from psycopg2.extras import DictCursor

from settings import ServicesCosts, NotifyChats

from schemas.users import UserSchema, UserMenu
from schemas.clans import ExtraCreateClan, CreateClanMenu, ClanTypeApplication, \
    ExtraOwnerClan

from services.clans import ClanService
from services.clans_telegram import get_clans_message_telegram
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

    # Проверяем что extra_data не None
    if user_data.extra_data is None:
        extra_data = ExtraCreateClan()
    else:
        extra_data = ExtraCreateClan(**user_data.extra_data)

    if extra_data.menu == CreateClanMenu.MAIN:

        if message == "меню":
            response = BACK_SERVICES_MENU
            reply_keyboard, _ = get_main_menu_keyboard(user_data)
            keyboard = reply_keyboard
            update_user_menu(user_id, UserMenu.MAIN, psql_cursor)
            update_user_extra_data(user_id, None, psql_cursor)

        elif message == "создать клан" or message == "Создать клан":
            service_cost = format_number(ServicesCosts.CREATE_CLAN)
            response = f"""
                Введи название клана
                Стоимость создания клана - {service_cost} коинов
            """
            keyboard = back_keyboard

            extra_data.menu = CreateClanMenu.SET_NAME
            update_user_extra_data(user_id, extra_data, psql_cursor)

        elif message == "топ кланов" or message == "Топ кланов":
            response, keyboard = get_clans_message_telegram(psql_cursor)

        elif (
            payload is not None and
            payload.get("event") == "create_clan"
        ):
            service_cost = format_number(ServicesCosts.CREATE_CLAN)
            response = f"""
                Введи название клана
                Стоимость создания клана - {service_cost} коинов
            """
            keyboard = back_keyboard

            extra_data.menu = CreateClanMenu.SET_NAME
            update_user_extra_data(user_id, extra_data, psql_cursor)

        elif (
            payload is not None and
            payload.get("event") == "get_clans_message" and
            isinstance(payload.get("offset"), int)
        ):
            offset = payload.get("offset")
            response, keyboard = get_clans_message_telegram(
                psql_cursor, offset=offset
            )

        elif (
            payload is not None and
            payload.get("event") == "get_clan_info" and
            isinstance(payload.get("clan_id"), int)
        ):
            clan_id = payload.get("clan_id")
            response, keyboard = ClanService.get_clan_info_message(
                psql_cursor, clan_id=clan_id, user_data=user_data,
            )

        elif (
            payload is not None and
            payload.get("event") == "join_clan" and
            isinstance(payload.get("clan_id"), int)
        ):
            clan_id = payload.get("clan_id")
            response, keyboard = await ClanService.handler_clan_join(clan_id, user_data, psql_cursor)

        elif (
            payload is not None and
            payload.get("event") == ClanTypeApplication.USER_TO_CLAN and
            isinstance(payload.get("clan_id"), int)
        ):
            clan_id = payload.get("clan_id")
            response = await ClanService.handler_user_application(
                psql_cursor, redis_cursor, clan_id=clan_id, user_data=user_data
            )
            keyboard = get_create_clan_keyboard()

        else:
            response = COMMAND_NOT_FOUND
            keyboard = get_create_clan_keyboard()

    elif extra_data.menu == CreateClanMenu.SET_NAME:

        keyboard = back_keyboard
        clan_name = original_message
        banned_symbols = SecurityService.check_banned_symbols(clan_name)

        if message == "назад" or message == "Назад":
            # Отменяем создание клана и возвращаемся в главное меню кланов
            response = "Создание клана отменено"
            keyboard = get_create_clan_keyboard()
            extra_data.menu = CreateClanMenu.MAIN
            update_user_extra_data(user_id, extra_data, psql_cursor)

        elif not ClanService.check_length_clan_name(clan_name):
            response = CLAN_NAME_LENGTH

        elif len(banned_symbols) != 0:
            banned_symbols = ",".join(banned_symbols)
            response = PATTERN_BANNED_SYMBOLS.format(banned_symbols)

        elif not ClanService.is_name_available(clan_name, psql_cursor):
            response = CLAN_NAME_OCCUPIED

        else:
            service_cost = format_number(ServicesCosts.CREATE_CLAN)
            response = f"""
                Введи тег клана
                Это такая приставка в квадратных скобках, которая будет отображаться у игроков перед ником
                Максимальная длина: 5 символов

                Стоимость создания клана - {service_cost} коинов
            """

            extra_data.menu = CreateClanMenu.SET_TAG
            extra_data.clan_name = clan_name
            update_user_extra_data(user_id, extra_data, psql_cursor)

    elif extra_data.menu == CreateClanMenu.SET_TAG:

        keyboard = back_keyboard
        clan_tag = original_message
        banned_symbols = SecurityService.check_banned_symbols(clan_tag)

        if message == "назад" or message == "Назад":
            service_cost = format_number(ServicesCosts.CREATE_CLAN)
            response = f"""
                Введи название клана
                Стоимость создания клана - {service_cost} коинов
            """

            extra_data.menu = CreateClanMenu.SET_NAME
            extra_data.clan_name = None
            update_user_extra_data(user_id, extra_data, psql_cursor)

        elif not ClanService.check_length_clan_tag(clan_tag):
            response = CLAN_TAG_LENGTH

        elif len(banned_symbols) != 0:
            banned_symbols = ", ".join(banned_symbols)
            response = PATTERN_BANNED_SYMBOLS.format(banned_symbols)

        elif not ClanService.is_tag_available(clan_tag, psql_cursor):
            response = CLAN_TAG_OCCUPIED

        elif user_data.coins < ServicesCosts.CREATE_CLAN:
            service_cost = format_number(ServicesCosts.CREATE_CLAN)
            response = f"""
                {NOT_ENOUGH_COINS}
                Стоимость создания клана - {service_cost} коинов
            """

        else:
            clan_name = extra_data.clan_name
            clan_service = ClanService

            clan_data = clan_service.create_clan(user_id, clan_tag, clan_name, psql_cursor)
            update_user_extra_data(user_id, ExtraOwnerClan(), psql_cursor)
            await clan_service.update_invitation_link(clan_data.clan_id, psql_cursor)

            service_cost = ServicesCosts.CREATE_CLAN
            take_coins(user_id, service_cost, psql_cursor)
            IncomesService.records_additional_incomes(service_cost, redis_cursor)

            clan_name = UserSchema.format_telegram_name(user_id, clan_name)
            await NotificationsService.send_notification(
                chat=NotifyChats.CREATE_CLAN,
                message=f"🏰 {user_data.telegram_name} создал клан {clan_name}"
            )

            response = CLAN_GREETING
            keyboard = get_clan_owner_keyboard()

    await send_message(user_id, response, keyboard)
