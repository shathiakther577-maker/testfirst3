from psycopg2.extras import DictCursor

from schemas.users import UserSchema, UserMenu
from schemas.chats import ExtraMyChats
from schemas.promocodes import ExtraPromoCode

from services.clans import ClanService

from modules.databases.users import update_user_menu, update_user_extra_data
from modules.telegram.bot import send_message

from telegram_bot.template_messages import COMMAND_NOT_FOUND, BACK_MAIN_MENU
from telegram_bot.keyboards.main_menu import get_main_menu_keyboard
from telegram_bot.keyboards.services_menu import get_services_menu_keyboard
from telegram_bot.keyboards.my_chats_menu import get_my_chats_keyboard
from telegram_bot.keyboards.promocode_menu import get_promocode_menu_keyboard
from telegram_bot.keyboards.statistics_menu import get_statistics_menu_keyboard


async def handler_services_menu(
        *,
        user_id: int,
        user_data: UserSchema,
        message: str,
        psql_cursor: DictCursor
) -> None:
    """Обрабатывает сообщения в меню сервисов"""

    if message == "назад":
        response = BACK_MAIN_MENU
        keyboard = get_main_menu_keyboard(user_data)
        update_user_menu(user_id, UserMenu.MAIN, psql_cursor)

    elif message == "промокоды" and user_data.banned_promo is True:
        response = "Отказано в доступе"
        keyboard = get_services_menu_keyboard()

    elif message == "промокоды" and user_data.banned_promo is False:
        response = "Сервис управления промокодами"
        keyboard = get_promocode_menu_keyboard()

        update_user_menu(user_id, UserMenu.PROMOCODE, psql_cursor)
        update_user_extra_data(user_id, ExtraPromoCode(), psql_cursor)

    elif message == "кланы":
        response, keyboard = await ClanService.go_clan_menu(user_data, psql_cursor)

    elif message == "мои чаты":
        response = "Выберите чат для управления:"
        keyboard = get_my_chats_keyboard(user_id, psql_cursor)

        update_user_menu(user_id, UserMenu.MY_CHATS, psql_cursor)
        update_user_extra_data(user_id, ExtraMyChats(), psql_cursor)

    elif message == "статистика":
        response = "Здесь вы можете посмотреть статистику проекта White Coin"
        keyboard = get_statistics_menu_keyboard()
        update_user_menu(user_id, UserMenu.STATISTICS, psql_cursor)

    else:
        response = COMMAND_NOT_FOUND
        keyboard = get_services_menu_keyboard()

    await send_message(user_id, response, keyboard)

