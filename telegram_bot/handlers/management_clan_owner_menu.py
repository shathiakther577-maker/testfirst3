import re
import asyncio
import json
from datetime import datetime
from redis.client import Redis
from psycopg2.extras import DictCursor
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from settings import ServicesCosts, ClanSettings

from schemas.users import UserSchema, UserMenu
from schemas.clans import ExtraOwnerClan, OwnerClanMenu, ClanSchema, \
    ClanJoinType, ClanRole

from services.clans import ClanService
from services.clans_telegram import get_clans_message_telegram, get_clan_members_message_telegram
from services.incomes import IncomesService
from services.security import SecurityService

from modules.additional import format_number, convert_number
from modules.databases.users import update_user_menu, update_user_extra_data, \
    take_coins, get_user_data
from modules.telegram.bot import send_message
from modules.telegram.users import get_user_id

from telegram_bot.template_messages import BACK_MAIN_MENU, COMMAND_NOT_FOUND, \
    CLAN_NAME_LENGTH, CLAN_TAG_LENGTH, PATTERN_BANNED_SYMBOLS, NOT_ENOUGH_COINS, \
    CLAN_NAME_OCCUPIED, CLAN_TAG_OCCUPIED, USER_NOT_FOUND, USER_HAVE_CLAN, \
    MAX_COUNT_MEMBERS_IN_CLAN, APPLICATION_ALREADY_SENT, APPLICATION_SENT
from telegram_bot.keyboards.other import back_keyboard
from telegram_bot.keyboards.main_menu import get_main_menu_keyboard
from telegram_bot.keyboards.clans_menu import get_clan_owner_keyboard, \
    get_keyboard_managing_members, get_clan_settings_keyboard, get_keyboard_delete_clan, \
    get_keyboard_change_clan_join_type


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
        psql_connection,
        redis_cursor: Redis
) -> None:
    """Обрабатывает сообщения владельца клана"""

    clan_id = owner_data.clan_id
    clan_data = ClanService.get_clan_data(clan_id, psql_cursor)
    
    # Проверяем что extra_data не None
    if owner_data.extra_data is None:
        extra_data = ExtraOwnerClan()
    else:
        extra_data = ExtraOwnerClan(**owner_data.extra_data)

    response = COMMAND_NOT_FOUND
    keyboard = get_clan_owner_keyboard()

    if extra_data.menu == OwnerClanMenu.MAIN:

        if message == "меню" or message == "Меню":
            response = BACK_MAIN_MENU
            reply_keyboard, _ = get_main_menu_keyboard(owner_data)
            keyboard = reply_keyboard
            update_user_menu(owner_id, UserMenu.MAIN, psql_cursor)

        elif message == "кланы" or message == "Кланы":
            response, keyboard = get_clans_message_telegram(psql_cursor)

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
            clan_id_info = payload.get("clan_id")
            response, _ = ClanService.get_clan_info_message(
                psql_cursor, clan_id=clan_id_info, user_data=owner_data
            )
            keyboard = get_clan_owner_keyboard()

        elif (
            payload is not None and
            payload.get("event") == "get_clan_members_message" and
            isinstance(payload.get("offset"), int)
        ):
            offset = payload.get("offset")
            response, keyboard = get_clan_members_message_telegram(
                psql_cursor, clan_id=clan_id, offset=offset
            )
            # Добавляем кнопку "Назад"
            if keyboard:
                buttons = keyboard.inline_keyboard.copy()
                buttons.append([InlineKeyboardButton(
                    text="Назад",
                    callback_data=json.dumps({"event": "clan_back"})
                )])
                keyboard = InlineKeyboardMarkup(buttons)
            else:
                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        text="Назад",
                        callback_data=json.dumps({"event": "clan_back"})
                    )
                ]])
            extra_data.menu = OwnerClanMenu.MANAGING_MEMBERS
            update_user_extra_data(owner_id, extra_data, psql_cursor)

        elif (
            payload is not None and
            payload.get("event") == "clan_back"
        ):
            response, keyboard = go_clan_main_menu(clan_data, owner_data, psql_cursor)

        elif message == "участники" or message == "Участники":
            response, keyboard = get_clan_members_message_telegram(
                psql_cursor, clan_id=clan_id
            )

            extra_data.menu = OwnerClanMenu.MANAGING_MEMBERS
            update_user_extra_data(owner_id, extra_data, psql_cursor)
            # Сразу показываем клавиатуру управления участниками
            keyboard = get_keyboard_managing_members()

        elif message == "беседа клана" or message == "Беседа клана":
            response = ClanService.get_link_clan_chat(
                clan_id=clan_id, psql_cursor=psql_cursor
            )
            keyboard = get_clan_owner_keyboard()

        elif message == "удалить клан" or message == "Удалить клан":
            response = "Вы точно хотите удалить клан?"
            keyboard = get_keyboard_delete_clan()

            extra_data.menu = OwnerClanMenu.DELETE_CLAN
            update_user_extra_data(owner_id, extra_data, psql_cursor)

        elif message == "настройки" or message == "Настройки":
            response, keyboard = go_clan_settings_menu(clan_data, owner_data, psql_cursor)

    elif extra_data.menu == OwnerClanMenu.MANAGING_MEMBERS:

        if message == "назад" or message == "Назад":
            response, keyboard = go_clan_main_menu(clan_data, owner_data, psql_cursor)

        elif message == "пригласить" or message == "Пригласить":
            response = "Введите @username или ID игрока для приглашения в клан"
            keyboard = back_keyboard

            extra_data.menu = OwnerClanMenu.INVITE_MEMBER
            update_user_extra_data(owner_id, extra_data, psql_cursor)

        elif message == "исключить" or message == "Исключить":
            response = "Введите @username или ID игрока для исключения из клана"
            keyboard = back_keyboard

            extra_data.menu = OwnerClanMenu.EXPEL_MEMBER
            update_user_extra_data(owner_id, extra_data, psql_cursor)

        else:
            response = COMMAND_NOT_FOUND
            keyboard = get_keyboard_managing_members()

    elif extra_data.menu == OwnerClanMenu.SETTINGS:

        if message == "назад" or message == "Назад":
            response, keyboard = go_clan_main_menu(clan_data, owner_data, psql_cursor)

        elif message == "название" or message == "Название":
            service_cost = format_number(ServicesCosts.CHANGE_CLAN_NAME)
            response = f"""
                Введи новое имя клана
                Стоимость смены - {service_cost} коинов
            """
            keyboard = back_keyboard

            extra_data.menu = OwnerClanMenu.CHANGE_CLAN_NAME
            update_user_extra_data(owner_id, extra_data, psql_cursor)

        elif message == "тег" or message == "Тег":
            service_cost = format_number(ServicesCosts.CHANGE_CLAN_TAG)
            response = f"""
                Введи новый тег клана
                Стоимость смены - {service_cost} коинов
            """
            keyboard = back_keyboard

            extra_data.menu = OwnerClanMenu.CHANGE_CLAN_TAG
            update_user_extra_data(owner_id, extra_data, psql_cursor)

        elif message == "тип входа" or message == "Тип входа":
            from schemas.clans import clan_join_type_translation
            response = """
                Выбери тип входа:

                Открытый - Свободный вход в клан
                Закрытый - Вход по заявке, которую должен одобрить лидер
                По приглашению - Вступление только по ссылке или приглашению лидера
            """
            keyboard = get_keyboard_change_clan_join_type()

            extra_data.menu = OwnerClanMenu.CHANGE_JOIN_TYPE
            update_user_extra_data(owner_id, extra_data, psql_cursor)

        elif message == "порог входа" or message == "Порог входа":
            response = "Укажите, от какого количества выигранных коинов люди смогут вступать в клан/подавать заявку"
            keyboard = back_keyboard

            extra_data.menu = OwnerClanMenu.CHANGE_JOIN_BARRIER
            update_user_extra_data(owner_id, extra_data, psql_cursor)

        elif message == "ссылка на беседу" or message == "Ссылка на беседу":
            response = "Укажи ссылку на беседу клана"
            keyboard = back_keyboard

            extra_data.menu = OwnerClanMenu.CHANGE_CHAT_LINK
            update_user_extra_data(owner_id, extra_data, psql_cursor)

        elif message == "уведомления о входе" or message == "Уведомления о входе":
            old_switch = clan_data.owner_notifications
            switch = ClanService.switch_owner_notifications(clan_id, old_switch, psql_cursor)

            if switch:
                response = "Вы включили уведомления о входе/выходе игроков из клана"
            else:
                response = "Вы выключили уведомления о входе/выходе игроков из клана"

            clan_data.owner_notifications = switch
            keyboard = get_clan_settings_keyboard(clan_data)

        else:
            response = COMMAND_NOT_FOUND
            keyboard = get_clan_settings_keyboard(clan_data)

    elif extra_data.menu == OwnerClanMenu.DELETE_CLAN:

        if message == "подтвердить удаление" or message == "Подтвердить удаление":
            # Удаляем клан
            member_ids = ClanService.get_members_id(clan_id, psql_cursor)
            ClanService.delete_clan(clan_id, member_ids, psql_cursor)
            
            # ВАЖНО: Коммитим изменения
            psql_connection.commit()
            
            # Отправляем уведомления всем участникам
            await asyncio.gather(*[
                asyncio.create_task(send_message(member_id, "😕 Ваш клан был распущен"))
                for member_id in member_ids if member_id != owner_id
            ])
            
            response = "Клан успешно удален"
            reply_keyboard, _ = get_main_menu_keyboard(owner_data)
            keyboard = reply_keyboard
            update_user_menu(owner_id, UserMenu.MAIN, psql_cursor)

        elif message == "отмена" or message == "Отмена":
            response, keyboard = go_clan_main_menu(clan_data, owner_data, psql_cursor)

        else:
            response = COMMAND_NOT_FOUND
            keyboard = get_keyboard_delete_clan()

    elif extra_data.menu == OwnerClanMenu.CHANGE_CLAN_NAME:

        if message == "назад" or message == "Назад":
            response, keyboard = go_clan_settings_menu(clan_data, owner_data, psql_cursor)

        else:
            # Проверяем баланс и меняем название
            if owner_data.coins < ServicesCosts.CHANGE_CLAN_NAME:
                response = NOT_ENOUGH_COINS
                keyboard = back_keyboard
            else:
                clan_name = original_message.strip()
                if len(clan_name) > CLAN_NAME_LENGTH:
                    response = f"Имя клана должно содержать не более {CLAN_NAME_LENGTH} символов"
                    keyboard = back_keyboard
                elif re.search(PATTERN_BANNED_SYMBOLS, clan_name):
                    response = "Имя клана содержит запрещенные символы"
                    keyboard = back_keyboard
                elif ClanService.check_clan_name_occupied(clan_name, psql_cursor):
                    response = CLAN_NAME_OCCUPIED
                    keyboard = back_keyboard
                else:
                    take_coins(owner_id, ServicesCosts.CHANGE_CLAN_NAME, psql_cursor)
                    ClanService.update_clan_name(clan_id, clan_name, psql_cursor)
                    clan_data = ClanService.get_clan_data(clan_id, psql_cursor)
                    response = f"Название клана изменено на {clan_name}"
                    _, keyboard = go_clan_settings_menu(clan_data, owner_data, psql_cursor)

    elif extra_data.menu == OwnerClanMenu.CHANGE_CLAN_TAG:

        if message == "назад" or message == "Назад":
            response, keyboard = go_clan_settings_menu(clan_data, owner_data, psql_cursor)

        else:
            # Проверяем баланс и меняем тег
            if owner_data.coins < ServicesCosts.CHANGE_CLAN_TAG:
                response = NOT_ENOUGH_COINS
                keyboard = back_keyboard
            else:
                clan_tag = original_message.strip()
                if len(clan_tag) > CLAN_TAG_LENGTH:
                    response = f"Тег клана должен содержать не более {CLAN_TAG_LENGTH} символов"
                    keyboard = back_keyboard
                elif re.search(PATTERN_BANNED_SYMBOLS, clan_tag):
                    response = "Тег клана содержит запрещенные символы"
                    keyboard = back_keyboard
                elif ClanService.check_clan_tag_occupied(clan_tag, psql_cursor):
                    response = CLAN_TAG_OCCUPIED
                    keyboard = back_keyboard
                else:
                    take_coins(owner_id, ServicesCosts.CHANGE_CLAN_TAG, psql_cursor)
                    ClanService.update_clan_tag(clan_id, clan_tag, psql_cursor)
                    clan_data = ClanService.get_clan_data(clan_id, psql_cursor)
                    response = f"Тег клана изменен на {clan_tag}"
                    _, keyboard = go_clan_settings_menu(clan_data, owner_data, psql_cursor)

    elif extra_data.menu == OwnerClanMenu.CHANGE_JOIN_TYPE:

        if message == "назад" or message == "Назад":
            response, keyboard = go_clan_settings_menu(clan_data, owner_data, psql_cursor)

        elif (
            payload is not None and
            payload.get("event") == OwnerClanMenu.CHANGE_JOIN_TYPE and
            payload.get("join_type") is not None
        ):
            from schemas.clans import ClanJoinType, clan_join_type_translation
            try:
                join_type = ClanJoinType(payload.get("join_type"))
                ClanService.update_clan_join_type(clan_id, join_type, psql_cursor)
                clan_data = ClanService.get_clan_data(clan_id, psql_cursor)
                
                if join_type == ClanJoinType.OPEN:
                    response = "Теперь в клан могут вступить все желающие, кто выиграл больше необходимого для вступления значения коинов"
                elif join_type == ClanJoinType.CLOSED:
                    response = "Теперь игрокам придется подать заявку для вступления в клан"
                elif join_type == ClanJoinType.INVITE:
                    response = "Теперь вступить в клан можно только по приглашению лидера"
                else:
                    response = f"Тип входа изменен на {clan_join_type_translation[join_type]}"
                
                _, keyboard = go_clan_settings_menu(clan_data, owner_data, psql_cursor)
            except (ValueError, KeyError):
                response = COMMAND_NOT_FOUND
                keyboard = get_keyboard_change_clan_join_type()
        else:
            response = COMMAND_NOT_FOUND
            keyboard = get_keyboard_change_clan_join_type()

    elif extra_data.menu == OwnerClanMenu.CHANGE_JOIN_BARRIER:

        if message == "назад" or message == "Назад":
            response, keyboard = go_clan_settings_menu(clan_data, owner_data, psql_cursor)

        else:
            try:
                barrier = convert_number(message)
                if barrier < 0:
                    response = "Порог входа не может быть отрицательным"
                    keyboard = back_keyboard
                else:
                    ClanService.update_clan_join_barrier(clan_id, barrier, psql_cursor)
                    clan_data = ClanService.get_clan_data(clan_id, psql_cursor)
                    response = f"Порог входа изменен на {format_number(barrier)}"
                    _, keyboard = go_clan_settings_menu(clan_data, owner_data, psql_cursor)
            except ValueError:
                response = "Введите корректное число"
                keyboard = back_keyboard

    elif extra_data.menu == OwnerClanMenu.INVITE_MEMBER:

        if message == "назад" or message == "Назад":
            response, keyboard = go_clan_management_menu(owner_id, psql_cursor)

        else:
            # Обработка приглашения участника
            # Поддерживаем формат @username или числовой ID
            user_id = None
            try:
                # Если это числовой ID
                if message.strip().isdigit():
                    user_id = int(message.strip())
                else:
                    # Если это username (с @ или без)
                    user_id = await get_user_id(message)
            except (ValueError, TypeError):
                pass
            
            if user_id is None:
                response = f"Пользователь не найден. Используйте формат @username или числовой ID (например: @loverufina или 959257591)"
                keyboard = back_keyboard
            else:
                # Проверяем существует ли пользователь в БД
                target_user_data = get_user_data(user_id, psql_cursor)
                if target_user_data is None:
                    response = f"Пользователь с ID {user_id} не найден в базе данных. Попросите пользователя написать боту /start для регистрации."
                    keyboard = back_keyboard
                elif user_id == owner_id:
                    response = "Нельзя приглашать самого себя"
                    keyboard = back_keyboard
                elif target_user_data.clan_role != ClanRole.NOT:
                    response = USER_HAVE_CLAN
                    keyboard = back_keyboard
                elif not ClanService.is_have_free_place(clan_data.count_members):
                    response = MAX_COUNT_MEMBERS_IN_CLAN
                    keyboard = back_keyboard
                else:
                    # Отправляем приглашение
                    from schemas.redis import RedisKeys
                    redis_key = ClanService.create_redis_key_for_accent_user(
                        clan_id=clan_id, user_id=user_id
                    )
                    
                    if ClanService.redis_check_application_join_clan(redis_key, redis_cursor):
                        response = APPLICATION_ALREADY_SENT
                        keyboard = back_keyboard
                    else:
                        clan_position = ClanService.get_clan_position(clan_id, psql_cursor)
                        
                        from telegram_bot.keyboards.clans_menu import get_keyboard_answer_user_join_clan
                        invite_message = f"""🏆 Вас приглашают в клан [{clan_data.tag}] {clan_data.name}
🕶 Глава: {owner_data.full_name}
💳 Счет: {format_number(clan_data.points)}
🥇 Место в топе: {clan_position}"""
                        
                        try:
                            message_sent = await send_message(
                                user_id,
                                message=invite_message,
                                keyboard=get_keyboard_answer_user_join_clan(user_id, clan_id)
                            )
                            
                            if message_sent:
                                ClanService.redis_add_application_join_clan(redis_key, redis_cursor)
                                response = APPLICATION_SENT
                            else:
                                response = f"Не удалось отправить приглашение пользователю {user_id}. Возможно, пользователь заблокировал бота или не зарегистрирован. Попросите пользователя написать боту /start."
                        except Exception as e:
                            print(f"[CLAN ERROR] Failed to send invite to {user_id}: {e}", flush=True)
                            import traceback
                            traceback.print_exc()
                            response = f"Ошибка при отправке приглашения: {str(e)}"
                        
                        keyboard = get_keyboard_managing_members()
                        extra_data.menu = OwnerClanMenu.MANAGING_MEMBERS
                        update_user_extra_data(owner_id, extra_data, psql_cursor)

    elif extra_data.menu == OwnerClanMenu.EXPEL_MEMBER:

        if message == "назад" or message == "Назад":
            response, keyboard = go_clan_management_menu(owner_id, psql_cursor)

        else:
            # Обработка исключения участника
            user_id = await get_user_id(message)
            if user_id is None:
                response = USER_NOT_FOUND
                keyboard = back_keyboard
            else:
                expel_result = await ClanService.expel_user_from_clan(
                    user_id, clan_id, owner_data, psql_cursor
                )
                response = expel_result
                keyboard = get_keyboard_managing_members()
                extra_data.menu = OwnerClanMenu.MANAGING_MEMBERS
                update_user_extra_data(owner_id, extra_data, psql_cursor)

    elif extra_data.menu == OwnerClanMenu.CHANGE_CHAT_LINK:

        if message == "назад" or message == "Назад":
            response, keyboard = go_clan_settings_menu(clan_data, owner_data, psql_cursor)

        else:
            # Проверяем что это похоже на ссылку (для Telegram можно использовать t.me или другие форматы)
            chat_link = original_message.strip()
            # Простая проверка на ссылку
            if chat_link.startswith("http://") or chat_link.startswith("https://") or chat_link.startswith("t.me/"):
                ClanService.change_chat_link(clan_id, chat_link, psql_cursor)
                clan_data = ClanService.get_clan_data(clan_id, psql_cursor)
                response = "Ссылка на беседу клана обновлена"
                _, keyboard = go_clan_settings_menu(clan_data, owner_data, psql_cursor)
            else:
                response = "Это не похоже на ссылку. Введите корректную ссылку (например, t.me/... или https://...)"
                keyboard = back_keyboard

    await send_message(owner_id, response, keyboard)
