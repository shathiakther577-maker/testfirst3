from redis.client import Redis
from psycopg2.extras import DictCursor

from schemas.users import UserSchema, UserMenu
from schemas.clans import ClanRole, ClanTypeApplication
from services.clans import ClanService

from modules.databases.users import get_user_data
from modules.databases.chats import get_chat_data
from modules.vkontakte.bot import send_message

from vk_bot.template_messages import CLAN_GREETING, USER_NOT_FOUND, CLAN_NOT_FOUND, \
    YOU_HAVE_CLAN, USER_HAVE_CLAN, MAX_COUNT_MEMBERS_IN_CLAN, APPLICATION_EXPIRED, \
    DATA_OUTDATED
from vk_bot.keyboards.main_menu import get_game_selection_keyboard
from vk_bot.keyboards.clans_menu import get_clan_member_keyboard


async def processing_in_all_menus(
        *,
        payload: dict,
        puser_data: UserSchema,
        psql_cursor: DictCursor,
        redis_cursor: Redis
):
    """Обрабатывает команды которые должны работать независимо от меню"""

    event = payload.get("event")

    if (
        event == ClanTypeApplication.CLAN_TO_USER.value and
        isinstance(payload.get("confirm"), bool) and
        isinstance(payload.get("user_id"), int) and
        isinstance(payload.get("clan_id"), int)
    ):

        clan_id = payload.get("clan_id")
        clan_data = ClanService.get_clan_data(clan_id, psql_cursor)

        user_id = payload.get("user_id")
        user_data = get_user_data(user_id, psql_cursor)

        confirm = payload.get("confirm")
        redis_key = ClanService.create_redis_key_for_accent_user(
            clan_id=clan_id, user_id=user_id
        )

        if user_data is None:
            response = USER_NOT_FOUND

        elif user_data.clan_role != ClanRole.NOT:
            response = YOU_HAVE_CLAN

        elif clan_data is None:
            response = CLAN_NOT_FOUND

        elif not ClanService.redis_check_application_join_clan(
                redis_key, redis_cursor
        ):
            response = APPLICATION_EXPIRED

        elif confirm is True:
            response = CLAN_GREETING
            ClanService.join_clan(clan_id, user_id, psql_cursor)

            await ClanService.send_clan_owner_notification(
                clan_data=clan_data,
                message=f"⚠️ {user_data.vk_name} принял приглашение в клан",
                mandatory=True
            )

        elif confirm is False:
            response = "⚠️ Вы отказались от приглашения"

            await ClanService.send_clan_owner_notification(
                clan_data=clan_data,
                message=f"⚠️ {user_data.vk_name} отказался от приглашения в клан",
                mandatory=True
            )

        else:
            raise Exception(f"need an additional section in {event}")

        ClanService.redis_delete_application_join_clan(redis_key, redis_cursor)
        await send_message(user_id, response)

    if (
        event == ClanTypeApplication.USER_TO_CLAN.value and
        isinstance(payload.get("confirm"), bool) and
        isinstance(payload.get("user_id"), int) and
        isinstance(payload.get("clan_id"), int)
    ):

        clan_id = payload.get("clan_id")
        clan_data = ClanService.get_clan_data(clan_id, psql_cursor)

        user_id = payload.get("user_id")
        user_data = get_user_data(user_id, psql_cursor)

        confirm = payload.get("confirm")
        redis_key = ClanService.create_redis_key_for_accent_clan(
            clan_id=clan_id, user_id=user_id
        )

        if user_data is None:
            response = USER_NOT_FOUND

        elif clan_data is None:
            response = CLAN_NOT_FOUND

        elif clan_data.owner_id != puser_data.user_id:
            response = "❌ Вы не владелец данного клана"

        elif user_data.clan_role != ClanRole.NOT:
            response = USER_HAVE_CLAN

        elif not ClanService.is_have_free_place(clan_data.count_members):
            response = MAX_COUNT_MEMBERS_IN_CLAN

        elif not ClanService.redis_check_application_join_clan(
                redis_key, redis_cursor
        ):
            response = APPLICATION_EXPIRED

        elif confirm is True:
            response = "⚠️ Игрок принят в клан"
            ClanService.join_clan(clan_id, user_id, psql_cursor)

            clan_name = UserSchema.format_vk_name(clan_data.owner_id, clan_data.name)
            await send_message(
                peer_id=user_id,
                message=f"⚠️ Вы были приняты в клан {clan_name}",
                keyboard=get_clan_member_keyboard() if user_data.menu == UserMenu.CLANS else None
            )

        elif confirm is False:
            response = "⚠️ Заявка отклонена"

            clan_name = UserSchema.format_vk_name(clan_data.owner_id, clan_data.name)
            await send_message(
                peer_id=user_id,
                message=f"⚠️ Вас не приняли в клан {clan_name}"
            )

        else:
            raise Exception(f"need an additional section in {event}")

        ClanService.redis_delete_application_join_clan(redis_key, redis_cursor)
        await send_message(clan_data.owner_id, response)

    elif (
        event == "start_play_game"
    ):
        await send_message(
            peer_id=puser_data.user_id,
            message = "Нажмите кнопку \"Играть\" ещё раз чтобы увидеть другие игры",
            keyboard = get_game_selection_keyboard()
        )

    elif (
        event == "switch_mailing"
    ):
        psql_cursor.execute("""
            UPDATE users SET mailing = not mailing
            WHERE user_id = %s
        """, [puser_data.user_id]
        )
        await send_message(
            peer_id=puser_data.user_id,
            message="❌ Вы отписались от рассылки" if puser_data.mailing is True else "✅ Вы подписались на рассылку"
        )

    elif (
        event == "disabled_sub_chat_notif" and
        isinstance(payload.get("chat_id"), int)
    ):

        chat_id = payload["chat_id"]
        chat_data = get_chat_data(chat_id, psql_cursor)

        if chat_data is None:
            response = DATA_OUTDATED

        elif chat_data.owner_id != puser_data.user_id:
            response = "❌ Вы не являетесь владельцем этого чата"

        psql_cursor.execute("""
            UPDATE chats
            SET subscription_notif = FALSE
            WHERE chat_id = %s
        """, (chat_id,))

        response = "Оповещение об окончании подписки отключено"

        await send_message(puser_data.user_id, response)
