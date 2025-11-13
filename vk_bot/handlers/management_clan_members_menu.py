from psycopg2.extras import DictCursor

from schemas.users import UserSchema, UserMenu
from services.clans import ClanService

from modules.databases.users import update_user_menu
from modules.vkontakte.bot import send_message

from vk_bot.template_messages import BACK_MAIN_MENU, COMMAND_NOT_FOUND
from vk_bot.keyboards.main_menu import get_main_menu_keyboard
from vk_bot.keyboards.clans_menu import get_clan_member_keyboard


async def handler_management_clan_members_menu(
        member_id: int,
        member_data: UserSchema,
        message: str,
        payload: dict | None,
        psql_cursor: DictCursor
) -> None:
    """Обрабатывает сообщения участников клана"""

    clan_id = member_data.clan_id

    if message == "меню":
        response = BACK_MAIN_MENU
        keyboard = get_main_menu_keyboard(member_data)
        update_user_menu(member_id, UserMenu.MAIN, psql_cursor)

    elif message == "кланы":
        response, keyboard = ClanService.get_clans_message(psql_cursor)

    elif (
        payload is not None and
        payload.get("event") == "get_clans_message" and
        isinstance(payload.get("offset"), int)
    ):
        offset = payload.get("offset")
        response, keyboard = ClanService.get_clans_message(
            psql_cursor, offset=offset
        )

    elif (
        payload is not None and
        payload.get("event") == "get_clan_info" and
        isinstance(payload.get("clan_id"), int)
    ):
        clan_id = payload.get("clan_id")
        response, _ = ClanService.get_clan_info_message(
            psql_cursor, clan_id=clan_id, user_data=member_data
        )
        keyboard = get_clan_member_keyboard()

    elif message == "участники":
        response, keyboard = ClanService.get_clan_members_message(
            psql_cursor, clan_id=clan_id
        )

    elif (
        payload is not None and
        payload.get("event") == "get_clan_members_message" and
        isinstance(payload.get("offset"), int)
    ):
        offset = payload.get("offset")
        response, keyboard = ClanService.get_clan_members_message(
            psql_cursor, clan_id=clan_id, offset=offset
        )

    elif message == "беседа клана":
        response = ClanService.get_link_clan_chat(
            clan_id=clan_id, psql_cursor=psql_cursor
        )
        keyboard = get_clan_member_keyboard()

    elif message == "покинуть клан":
        response = "Вы покинули клан"
        keyboard = get_main_menu_keyboard(member_data)

        update_user_menu(member_id, UserMenu.MAIN, psql_cursor)
        clan_service = ClanService
        clan_service.leave_clan([member_id], psql_cursor)

        clan_data = clan_service.get_clan_data(clan_id, psql_cursor)
        clan_owner_message = f"⚠️ {member_data.vk_name} покинул клан"
        await clan_service.send_clan_owner_notification(clan_data, clan_owner_message)

    else:
        response = COMMAND_NOT_FOUND
        keyboard = get_clan_member_keyboard()

    await send_message(member_id, response, keyboard)
