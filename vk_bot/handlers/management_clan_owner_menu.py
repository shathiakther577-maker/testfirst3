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
from modules.vkontakte.bot import send_message, send_keyboard
from modules.vkontakte.users import get_user_id

from vk_bot.template_messages import BACK_MAIN_MENU, COMMAND_NOT_FOUND, \
    CLAN_NAME_LENGTH, CLAN_TAG_LENGTH, PATTERN_BANNED_SYMBOLS, NOT_ENOUGH_COINS, \
    CLAN_NAME_OCCUPIED, CLAN_TAG_OCCUPIED, USER_NOT_FOUND, USER_HAVE_CLAN, \
    MAX_COUNT_MEMBERS_IN_CLAN, APPLICATION_ALREADY_SENT, APPLICATION_SENT
from vk_bot.keyboards.other import back_keyboard
from vk_bot.keyboards.main_menu import get_main_menu_keyboard
from vk_bot.keyboards.clans_menu import get_clan_owner_keyboard, \
    get_keyboard_managing_members, get_clan_settings_keyboard, get_keyboard_delete_clan, \
    get_keyboard_change_clan_join_type, get_keyboard_answer_user_join_clan


def go_clan_main_menu(
        clan_data: ClanSchema,
        owner_data: UserSchema,
        psql_cursor: DictCursor
) -> tuple[str, str]:
    """
        Отправляет пользователя в главное мекю клана
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


def go_clan_management_menu(
        owner_id: int,
        psql_cursor: DictCursor
) -> tuple[str, str]:
    """
        Отправляет пользователя в меню управления участниками клана
        и возвращает сообщение и клавиатуру
    """

    response = "Управления участниками клана"
    keyboard = get_keyboard_managing_members()

    update_user_extra_data(
        user_id=owner_id,
        extra_data=ExtraOwnerClan(
            menu=OwnerClanMenu.MANAGING_MEMBERS
        ),
        psql_cursor=psql_cursor
    )

    return response, keyboard


def go_clan_settings_menu(
        clan_data: ClanSchema,
        owner_data: UserSchema,
        psql_cursor: DictCursor
) -> tuple[str, str]:
    """
        Отправляет пользователя в меню настроек клана
        и возвращает сообщение и клавиатуру
    """

    response = "Доступные настройки клана"
    keyboard = get_clan_settings_keyboard(clan_data)

    update_user_extra_data(
        user_id=owner_data.user_id,
        extra_data=ExtraOwnerClan(
            menu=OwnerClanMenu.SETTINGS
        ),
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
    """Обрабатывает сообщения участников клана"""

    clan_id = owner_data.clan_id
    clan_data = ClanService.get_clan_data(clan_id, psql_cursor)
    extra_data = ExtraOwnerClan(**owner_data.extra_data)

    if extra_data.menu == OwnerClanMenu.MAIN:

        if message == "меню":
            response = BACK_MAIN_MENU
            keyboard = get_main_menu_keyboard(owner_data)
            update_user_menu(owner_id, UserMenu.MAIN, psql_cursor)

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
                psql_cursor, clan_id=clan_id, user_data=owner_data
            )
            keyboard = get_clan_owner_keyboard()

        elif message == "участники":
            response, keyboard = ClanService.get_clan_members_message(
                psql_cursor, clan_id=clan_id
            )

            extra_data.menu = OwnerClanMenu.MANAGING_MEMBERS
            update_user_extra_data(owner_id, extra_data, psql_cursor)
            await send_keyboard(owner_id, get_keyboard_managing_members())

        elif message == "беседа клана":
            response = ClanService.get_link_clan_chat(
                clan_id=clan_id, psql_cursor=psql_cursor
            )
            keyboard = get_clan_owner_keyboard()

        elif message == "удалить клан":
            response = "Вы точно хотите удалить клан?"
            keyboard = get_keyboard_delete_clan()

            extra_data.menu = OwnerClanMenu.DELETE_CLAN
            update_user_extra_data(owner_id, extra_data, psql_cursor)

        elif message == "настройки":
            response, keyboard = go_clan_settings_menu(clan_data, owner_data, psql_cursor)

        else:
            response = COMMAND_NOT_FOUND
            keyboard = get_clan_owner_keyboard()

    elif extra_data.menu == OwnerClanMenu.MANAGING_MEMBERS:

        if message == "назад":
            response, keyboard = go_clan_main_menu(clan_data, owner_data, psql_cursor)

        elif message == "пригласить игрока":
            response = "Введите ссылку игрока для приглашения в клан"
            keyboard = back_keyboard

            extra_data.menu = OwnerClanMenu.INVITE_MEMBER
            update_user_extra_data(owner_id, extra_data, psql_cursor)

        elif message == "исключить игрока":
            response = "Введите ссылку игрока для исключения из клана"
            keyboard = back_keyboard

            extra_data.menu = OwnerClanMenu.EXPEL_MEMBER
            update_user_extra_data(owner_id, extra_data, psql_cursor)

        elif message == "ссылка-приглашение":
            response = f"""
                Одноразовая ссылка-приглашение в клан:
                {clan_data.invitation_link}
            """
            keyboard = get_keyboard_managing_members()

        elif (
            payload is not None and
            payload.get("event") == "get_clan_members_message" and
            isinstance(payload.get("offset"), int)
        ):
            offset = payload.get("offset")
            response, keyboard = ClanService.get_clan_members_message(
                psql_cursor, clan_id=clan_id, offset=offset
            )

        else:
            response = COMMAND_NOT_FOUND
            keyboard = get_keyboard_managing_members()

    elif extra_data.menu == OwnerClanMenu.INVITE_MEMBER:

        keyboard = back_keyboard
        user_id = await get_user_id(message)
        user_data = get_user_data(user_id, psql_cursor)
        redis_key = ClanService.create_redis_key_for_accent_user(
            clan_id=clan_id, user_id=user_id
        )

        if message == "назад":
            response, keyboard = go_clan_management_menu(owner_id, psql_cursor)

        elif user_id == owner_id:
            response = "Нельзя приглашать самого себя"

        elif user_data is None:
            response = USER_NOT_FOUND

        elif user_data.clan_role != ClanRole.NOT:
            response = USER_HAVE_CLAN

        elif not ClanService.is_have_free_place(clan_data.count_members):
            response = MAX_COUNT_MEMBERS_IN_CLAN

        elif ClanService.redis_check_application_join_clan(redis_key, redis_cursor):
            response = APPLICATION_ALREADY_SENT

        else:
            clan_position = ClanService.get_clan_position(clan_id, psql_cursor)

            await send_message(
                user_id,
                message=f"""
                    🏆 Вас приглашают в клан [{clan_data.tag}] {clan_data.name}
                    🕶 Глава: {owner_data.vk_name}
                    💳 Счет: {format_number(clan_data.points)}
                    🥇 Место в топе: {clan_position}
                """,
                keyboard=get_keyboard_answer_user_join_clan(user_id, clan_id)
            )
            ClanService.redis_add_application_join_clan(redis_key, redis_cursor)

            response = APPLICATION_SENT
            _, keyboard = go_clan_management_menu(owner_id, psql_cursor)

    elif extra_data.menu == OwnerClanMenu.EXPEL_MEMBER:

        keyboard = back_keyboard
        user_id = await get_user_id(message)
        user_data = get_user_data(user_id, psql_cursor)

        if message == "назад":
            response, keyboard = go_clan_management_menu(owner_id, psql_cursor)

        elif user_id == owner_id:
            response = "Нельзя исключить самого себя"

        elif user_data is None:
            response = USER_NOT_FOUND

        elif user_data.clan_id != clan_id:
            response = "Этот игрок не состоит в вашем клане"

        elif datetime.today().weekday() >= 3 and user_data.clan_points > 0:
            response = "Нельзя исключить игроков после среды"

        elif user_data.clan_points > 500_000:
            response = "Нельзя исключить участника, набившего больше 500к за неделю"

        else:
            ClanService.leave_clan([user_id], psql_cursor)
            await send_message(user_id, "❌ Вас исключили из клана")

            response = f"❌ {user_data.vk_name} исключен из клана"
            _, keyboard = go_clan_management_menu(owner_id, psql_cursor)

    elif extra_data.menu == OwnerClanMenu.DELETE_CLAN:

        if (
            payload is not None and
            payload.get("event") == "delete_clan" and
            payload.get("confirm") == True
        ):
            clan_service = ClanService
            member_ids = clan_service.get_members_id(clan_id, psql_cursor)
            clan_service.delete_clan(clan_id, member_ids, psql_cursor)

            await asyncio.gather(*[
                asyncio.create_task(send_message(member_id, "😕 Ваш клан был распущен"))
                for member_id in member_ids
            ])

            response = "Клан был удален"
            keyboard = get_main_menu_keyboard(owner_data)

        elif (
            payload is not None and
            payload.get("event") == "delete_clan" and
            payload.get("confirm") == False
        ):
            response, keyboard = go_clan_main_menu(clan_data, owner_data, psql_cursor)

        else:
            response = COMMAND_NOT_FOUND
            keyboard = get_keyboard_delete_clan()

    elif extra_data.menu == OwnerClanMenu.SETTINGS:

        if message == "назад":
            response, keyboard = go_clan_main_menu(clan_data, owner_data, psql_cursor)

        elif message == "название":
            service_cost = format_number(ServicesCosts.CHANGE_CLAN_NAME)
            response = f"""
                Введи новое имя клана
                Стоимость смены - {service_cost} коинов
            """
            keyboard = back_keyboard

            extra_data.menu = OwnerClanMenu.CHANGE_CLAN_NAME
            update_user_extra_data(owner_id, extra_data, psql_cursor)

        elif message == "тег":
            service_cost = format_number(ServicesCosts.CHANGE_CLAN_TAG)
            response = f"""
                Введи новый тег клана
                Стоимость смены - {service_cost} коинов
            """
            keyboard = back_keyboard

            extra_data.menu = OwnerClanMenu.CHANGE_CLAN_TAG
            update_user_extra_data(owner_id, extra_data, psql_cursor)

        elif message == "тип входа":
            response = """
                Выбери тип входа:

                Открытый - Свободный вход в клан
                Закрытый - Вход по заявке, которую должен одобрить лидер
                По приглашению - Вступление только по ссылке или приглашению лидера
            """
            keyboard = get_keyboard_change_clan_join_type()

            extra_data.menu = OwnerClanMenu.CHANGE_JOIN_TYPE
            update_user_extra_data(owner_id, extra_data, psql_cursor)

        elif message == "порог входа":
            response = "Укажите, от какого количества выигранных коинов люди смогут вступать в клан/подавать заявку"
            keyboard = back_keyboard

            extra_data.menu = OwnerClanMenu.CHANGE_JOIN_BARRIER
            update_user_extra_data(owner_id, extra_data, psql_cursor)

        elif message == "уведомления о входе":
            old_switch = clan_data.owner_notifications
            switch = ClanService.switch_owner_notifications(clan_id, old_switch, psql_cursor)

            if switch:
                response = "Вы включили уведомления о входе/выходе игроков из клана"
            else:
                response = "Вы выключили уведомления о входе/выходе игроков из клана"

            clan_data.owner_notifications = switch
            keyboard = get_clan_settings_keyboard(clan_data)

        elif message == "ссылка на беседу":
            response = "Укажи ссылку на беседу клана"
            keyboard = back_keyboard

            extra_data.menu = OwnerClanMenu.CHANGE_CHAT_LINK
            update_user_extra_data(owner_id, extra_data, psql_cursor)

        else:
            response = COMMAND_NOT_FOUND
            keyboard = get_clan_settings_keyboard(clan_data)

    elif extra_data.menu == OwnerClanMenu.CHANGE_CLAN_NAME:

        keyboard = back_keyboard
        clan_name = original_message
        banned_symbols = SecurityService().check_banned_symbols(clan_name)

        if message == "назад":
            response, keyboard = go_clan_settings_menu(clan_data, owner_data, psql_cursor)

        elif not ClanService.check_length_clan_name(clan_name):
            response = CLAN_NAME_LENGTH

        elif len(banned_symbols) != 0:
            banned_symbols = ", ".join(banned_symbols)
            response = PATTERN_BANNED_SYMBOLS.format(banned_symbols)

        elif not ClanService.is_name_available(clan_name, psql_cursor):
            response = CLAN_NAME_OCCUPIED

        elif owner_data.coins < ServicesCosts.CHANGE_CLAN_NAME:
            service_cost = format_number(ServicesCosts.CHANGE_CLAN_NAME)
            response = f"""
                {NOT_ENOUGH_COINS}
                Стоимость смены имени клана - {service_cost} коинов
            """

        else:
            ClanService.change_clan_name(clan_id, clan_name, psql_cursor)

            service_cost = ServicesCosts.CHANGE_CLAN_NAME
            take_coins(owner_id, service_cost, psql_cursor)
            IncomesService.records_additional_incomes(service_cost, redis_cursor)

            response = f"Название клана изменено на {clan_name}"
            _, keyboard = go_clan_settings_menu(clan_data, owner_data, psql_cursor)

    elif extra_data.menu == OwnerClanMenu.CHANGE_CLAN_TAG:

        keyboard = back_keyboard
        clan_tag = original_message
        banned_symbols = SecurityService.check_banned_symbols(clan_tag)

        if message == "назад":
            response, keyboard = go_clan_settings_menu(clan_data, owner_data, psql_cursor)

        elif not ClanService.check_length_clan_tag(clan_tag):
            response = CLAN_TAG_LENGTH

        elif len(banned_symbols) != 0:
            banned_symbols = ", ".join(banned_symbols)
            response = PATTERN_BANNED_SYMBOLS.format(banned_symbols)

        elif not ClanService.is_tag_available(clan_tag, psql_cursor):
            response = CLAN_TAG_OCCUPIED

        elif owner_data.coins < ServicesCosts.CHANGE_CLAN_TAG:
            service_cost = format_number(ServicesCosts.CHANGE_CLAN_TAG)
            response = f"""
                {NOT_ENOUGH_COINS}
                Стоимость смены тага клана - {service_cost} коинов
            """

        else:
            ClanService.change_clan_tag(clan_id, clan_tag, psql_cursor)

            service_cost = ServicesCosts.CHANGE_CLAN_TAG
            take_coins(owner_id, service_cost, psql_cursor)
            IncomesService.records_additional_incomes(service_cost, redis_cursor)

            response = f"Тег клана изменен на {clan_tag}"
            _, keyboard = go_clan_settings_menu(clan_data, owner_data, psql_cursor)

    elif extra_data.menu == OwnerClanMenu.CHANGE_JOIN_TYPE:

        if message == "назад":
            response, keyboard = go_clan_settings_menu(clan_data, owner_data, psql_cursor)

        elif (
            payload is not None and
            payload.get("event") == OwnerClanMenu.CHANGE_JOIN_TYPE and
            payload.get("join_type") in [x.value for x in ClanJoinType]
        ):
            join_type = ClanJoinType(payload.get("join_type"))
            ClanService.change_join_type(clan_id, join_type, psql_cursor)

            if join_type == ClanJoinType.OPEN:
                response = "Теперь в клан могут вступить все желающие, кто выиграл больше необходимого для вступления значения коинов"

            elif join_type == ClanJoinType.CLOSED:
                response = "Теперь игрокам придется подать заявку для вступления в клан"

            elif join_type == ClanJoinType.INVITE:
                response = "Теперь вступить в клан можно только по приглашению лидера"

            _, keyboard = go_clan_settings_menu(clan_data, owner_data, psql_cursor)

        else:
            response = COMMAND_NOT_FOUND
            keyboard = get_keyboard_change_clan_join_type()

    elif extra_data.menu == OwnerClanMenu.CHANGE_JOIN_BARRIER:

        join_barrier = convert_number(message)

        if message == "назад":
            response, keyboard = go_clan_settings_menu(clan_data, owner_data, psql_cursor)

        elif (
            isinstance(join_barrier, int) and
            0 <= join_barrier <= ClanSettings.MAX_JOIN_BARRIER
        ):
            ClanService.change_join_barrier(clan_id, join_barrier, psql_cursor)

            response = f"Теперь вступить в клан/подать заявку смогут только игроки, которые выиграли больше {format_number(join_barrier)} коинов"
            clan_data.join_barrier = join_barrier
            _, keyboard = go_clan_settings_menu(clan_data, owner_data, psql_cursor)

        else:
            max_value = format_number(ClanSettings.MAX_JOIN_BARRIER)
            response = f"""
                Новое значение барьера не подходит по условиям
                Диапазон барьера от 0 до {max_value}
            """
            keyboard = back_keyboard

    elif extra_data.menu == OwnerClanMenu.CHANGE_CHAT_LINK:

        if message == "назад":
            response, keyboard = go_clan_settings_menu(clan_data, owner_data, psql_cursor)

        elif re.fullmatch(r"(https\:\/\/)?vk\.me\/join\/[a-zA-Z0-9_=\/]*", original_message):
            ClanService.change_chat_link(clan_id, original_message, psql_cursor)

            response = "Ссылка на беседу клана обновлена"
            clan_data.chat_link = original_message
            _, keyboard = go_clan_settings_menu(clan_data, owner_data, psql_cursor)

        else:
            response = "Это не похоже на ссылку на беседу"
            keyboard = back_keyboard

    await send_message(owner_id, response, keyboard)
