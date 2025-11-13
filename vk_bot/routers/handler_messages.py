import re
import json

from databases.redis import get_redis_cursor
from databases.postgresql import get_postgresql_connection

from schemas.users import UserStatus, UserMenu
from schemas.clans import ClanRole
from schemas.redis import RedisKeys

from services.clans import ClanService
from services.user_in_chat import UserChatService
from services.notify_banned_user import notify_banned_user

from modules.additional import strtobool
from modules.registration import first_greeting
from modules.databases.users import get_user_data, update_users_last_activity
from modules.databases.chats import get_chat_data

from vk_bot.handlers.main_menu import handler_main_menu
from vk_bot.handlers.admin_menu import handler_admin_menu
from vk_bot.handlers.mailing_menu import handler_mailing_menu
from vk_bot.handlers.settings_menu import handler_settings_menu
from vk_bot.handlers.services_menu import handler_services_menu
from vk_bot.handlers.my_chats_menu import handler_my_chats_menu
from vk_bot.handlers.promocode_menu import handler_promocode_menu
from vk_bot.handlers.statistics_menu import handler_statistics_menu
from vk_bot.handlers.create_clan_menu import handler_menu_create_clan
from vk_bot.handlers.change_name_menu import handler_change_name_menu
from vk_bot.handlers.bonus_repost_menu import handler_bonus_repost_menu
from vk_bot.handlers.transfer_coins_menu import handler_transfer_coins_menu
from vk_bot.handlers.management_clan_owner_menu import handler_management_clan_owner_menu
from vk_bot.handlers.management_clan_members_menu import handler_management_clan_members_menu
from vk_bot.handlers.processing_in_all_menus import processing_in_all_menus

from vk_bot.handlers.active_chat import handler_active_chat
from vk_bot.handlers.inactive_chat import handler_inactive_chat


async def handler_messages(event):
    """Перенаправляет данные для ответа пользователю"""

    message_data = event["object"]["message"]
    message_datetime = message_data.get("date") or 0

    reference = message_data.get("ref")

    payload = message_data.get("payload")
    payload = None if payload is None else json.loads(payload)

    fwd_messages = message_data.get("reply_message")
    fwd_messages = [fwd_messages] if fwd_messages else message_data["fwd_messages"]

    peer_id = message_data["peer_id"]
    user_id = message_data["from_id"]

    original_message = message_data["text"]
    message = original_message.lower()

    redis_cursor = get_redis_cursor()
    psql_connection, psql_cursor = get_postgresql_connection()

    try:
        user_data = get_user_data(user_id, psql_cursor)
        if user_data is None:
            await first_greeting(user_id, psql_cursor, redis_cursor)
            return

        if (
            strtobool(redis_cursor.get(RedisKeys.QUIET_MODE.value) or "0") and
            user_data.status != UserStatus.ADMIN
        ):
            return

        if user_data.banned is True:
            await notify_banned_user(user_data, redis_cursor)
            return

        if reference is not None and re.findall(r"^clan_[0-9]+_[0-9]+$", reference):
            await ClanService.reference_clan_join(reference, user_data, psql_cursor)
            return

        if 0 < peer_id < int(2E9):  # личное сообщение

            if (
                payload is not None and
                payload.get("handler", "") == "processing_menus"
            ):
                await processing_in_all_menus(
                    payload=payload,
                    puser_data=user_data,
                    psql_cursor=psql_cursor,
                    redis_cursor=redis_cursor
                )

            elif user_data.menu == UserMenu.MAIN:
                await handler_main_menu(
                    user_id=user_id, user_data=user_data,
                    message=message, fwd_messages=fwd_messages, payload=payload,
                    psql_cursor=psql_cursor, redis_cursor=redis_cursor
                )

            elif user_data.menu == UserMenu.TRANSFER_COINS:
                await handler_transfer_coins_menu(
                    user_id=user_id, user_data=user_data,
                    message=message, psql_cursor=psql_cursor
                )

            elif user_data.menu == UserMenu.SETTINGS:
                await handler_settings_menu(
                    user_id=user_id, user_data=user_data,
                    message=message, psql_cursor=psql_cursor
                )

            elif user_data.menu == UserMenu.CHANGE_USER_NAME:
                await handler_change_name_menu(
                    user_id=user_id, user_data=user_data,
                    message=message, original_message=original_message,
                    psql_cursor=psql_cursor, redis_cursor=redis_cursor
                )

            elif user_data.menu == UserMenu.SERVICES:
                await handler_services_menu(
                    user_id=user_id, user_data=user_data,
                    message=message, psql_cursor=psql_cursor
                )

            elif user_data.menu == UserMenu.CLANS and user_data.clan_role == ClanRole.NOT:
                await handler_menu_create_clan(
                    user_id=user_id, user_data=user_data,
                    message=message, original_message=original_message,
                    payload=payload, psql_cursor=psql_cursor,
                    redis_cursor=redis_cursor
                )

            elif user_data.menu == UserMenu.CLANS and user_data.clan_role == ClanRole.OWNER:
                await handler_management_clan_owner_menu(
                    owner_id=user_id, owner_data=user_data,
                    message=message, original_message=original_message,
                    payload=payload, psql_cursor=psql_cursor,
                    redis_cursor=redis_cursor
                )

            elif user_data.menu == UserMenu.CLANS and user_data.clan_role == ClanRole.MEMBER:
                await handler_management_clan_members_menu(
                    member_id=user_id, member_data=user_data,
                    message=message, payload=payload,
                    psql_cursor=psql_cursor
                )

            elif user_data.menu == UserMenu.MY_CHATS:
                await handler_my_chats_menu(
                    owner_id=user_id, owner_data=user_data,
                    message=message, payload=payload,
                    psql_cursor=psql_cursor, redis_cursor=redis_cursor
                )

            elif user_data.menu == UserMenu.PROMOCODE:
                await handler_promocode_menu(
                    user_id=user_id, user_data=user_data,
                    message=message, original_message=original_message,
                    payload=payload, psql_cursor=psql_cursor,
                    psql_connection=psql_connection, redis_cursor=redis_cursor
                )

            elif user_data.menu == UserMenu.STATISTICS:
                await handler_statistics_menu(
                    user_id=user_id, message=message,
                    payload=payload, psql_cursor=psql_cursor
                )

            elif user_data.menu == UserMenu.BONUS_REPOST:
                await handler_bonus_repost_menu(
                    user_id=user_id, user_data=user_data,
                    message=message, payload=payload,
                    psql_cursor=psql_cursor, psql_connection=psql_connection,
                    redis_cursor=redis_cursor
                )

            elif user_data.menu == UserMenu.ADMIN and user_data.status == UserStatus.ADMIN:
                await handler_admin_menu(
                    admin_id=user_id, admin_data=user_data,
                    message=message, original_message=original_message,
                    fwd_messages=fwd_messages, payload=payload,
                    psql_cursor=psql_cursor, redis_cursor=redis_cursor
                )

            elif user_data.menu == UserMenu.MAILING and user_data.status == UserStatus.ADMIN:
                await handler_mailing_menu(
                    admin_id=user_id, admin_data=user_data,
                    message=message, original_message=original_message,
                    psql_cursor=psql_cursor
                )

        elif peer_id > int(2E9):  # сообщение из чата

            chat_id = peer_id
            chat_data = get_chat_data(chat_id, psql_cursor)

            if chat_data is None or chat_data.is_activated is False:

                await handler_inactive_chat(
                    user_id=user_id, user_data=user_data,
                    chat_id=chat_id, chat_data=chat_data,
                    message=message, payload=payload,
                    psql_cursor=psql_cursor, redis_cursor=redis_cursor
                )

            else:
                user_chat_data = UserChatService.get_data(user_id, chat_id, psql_cursor)

                await handler_active_chat(
                    user_id=user_id, user_data=user_data,
                    chat_id=chat_id, chat_data=chat_data,
                    user_chat_data=user_chat_data,
                    message=message, original_message=original_message,
                    fwd_messages=fwd_messages, payload=payload,
                    psql_cursor=psql_cursor, psql_connection=psql_connection,
                    redis_cursor=redis_cursor
                )

    finally:
        update_users_last_activity(user_id, psql_cursor)

        psql_cursor.close()
        psql_connection.close()
        redis_cursor.close()
