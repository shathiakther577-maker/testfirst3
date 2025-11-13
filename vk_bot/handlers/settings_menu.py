from psycopg2.extras import DictCursor

from settings import ServicesCosts
from schemas.users import UserSchema, UserMenu
from services.access_tokens import ApiAccessTokensService

from modules.additional import format_number
from modules.databases.users import update_user_menu
from modules.vkontakte.bot import send_message

from vk_bot.template_messages import COMMAND_NOT_FOUND, BACK_MAIN_MENU, \
    NOT_ENOUGH_COINS
from vk_bot.keyboards.other import back_keyboard
from vk_bot.keyboards.main_menu import get_main_menu_keyboard
from vk_bot.keyboards.settings_menu import get_settings_menu_keyboard


async def handler_settings_menu(
        *,
        user_id: int,
        user_data: UserSchema,
        message: str,
        psql_cursor: DictCursor
) -> None:
    """Обрабатывает сообщения в меню настроек"""

    response = COMMAND_NOT_FOUND
    keyboard = None

    if message == "назад":
        response = BACK_MAIN_MENU
        keyboard = get_main_menu_keyboard(user_data)
        update_user_menu(user_id, UserMenu.MAIN, psql_cursor)

    elif message == "показывать баланс":

        if user_data.show_balance is True:
            response = "Ваш баланс будет скрыт и его никто не увидит"
        else:
            response = "Ваш баланс могут посмотреть все пользователи"

        user_data.show_balance = not user_data.show_balance
        psql_cursor.execute("""
            UPDATE users
            SET show_balance = %(flag)s
            WHERE user_id = %(user_id)s
        """, {
            "flag": user_data.show_balance,
            "user_id": user_id
        })

    elif message == "рассылка":

        if user_data.mailing is True:
            response = "❌ Вы отписались от рассылки"
        else:
            response = "✅ Вы подписались на рассылку"

        user_data.mailing = not user_data.mailing
        psql_cursor.execute("""
            UPDATE users
            SET mailing = %(flag)s
            WHERE user_id = %(user_id)s
        """, {
            "flag": user_data.mailing,
            "user_id": user_id
        })

    elif message == "получить ключ api":
        access_token = ApiAccessTokensService.get_or_create_access_token(
            user_id=user_id, psql_cursor=psql_cursor
        )
        response = ApiAccessTokensService.format_message(access_token)

    elif message == "обновить ключ api":
        access_token = ApiAccessTokensService.update_user_access_token(
            user_id=user_id, psql_cursor=psql_cursor
        )
        response = ApiAccessTokensService.format_message(access_token)

    elif message == "ник":
        service_cost = 0 if user_data.free_nick_change else ServicesCosts.CHANGE_USER_NAME
        format_services_cost = format_number(service_cost)

        if user_data.coins >= service_cost:
            response = f"""
                Введи новое имя:
                (не более 15-ти символов)
                Стоимость: {format_services_cost} коинов
            """
            keyboard = back_keyboard
            update_user_menu(user_id, UserMenu.CHANGE_USER_NAME, psql_cursor)

        else:
            response = f"""
                {NOT_ENOUGH_COINS}
                Стоимость смены имени - {format_services_cost} BC
            """

    elif message == "тег клана":

        if user_data.show_clan_tag is True:
            response = "Отображение тега клана перед ником выключено"
        else:
            response = "Отображение тега клана перед ником включено"

        user_data.show_clan_tag = not user_data.show_clan_tag
        psql_cursor.execute("""
            UPDATE users
            SET show_clan_tag = %(flag)s
            WHERE user_id = %(user_id)s
        """, {
            "flag": user_data.show_clan_tag,
            "user_id": user_id
        })

    if keyboard is None:
        keyboard = get_settings_menu_keyboard(user_data)

    await send_message(user_id, response, keyboard)
