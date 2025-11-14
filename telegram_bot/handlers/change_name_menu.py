from redis.client import Redis
from psycopg2.extras import DictCursor

from settings import ServicesCosts, NotifyChats
from schemas.users import UserSchema, UserMenu

from services.incomes import IncomesService
from services.security import SecurityService
from services.notification import NotificationsService

from modules.additional import format_number, is_arabic_language
from modules.databases.users import update_user_menu, get_user_data, \
    update_user_name, take_coins, update_free_nick_change
from modules.telegram.bot import send_message

from telegram_bot.template_messages import BACK_MAIN_MENU, PATTERN_BANNED_SYMBOLS, \
    NOT_ENOUGH_COINS
from telegram_bot.keyboards.other import back_keyboard
from telegram_bot.keyboards.main_menu import get_main_menu_keyboard


async def handler_change_name_menu(
        *,
        user_id: int,
        user_data: UserSchema,
        message: str,
        original_message: str,
        psql_cursor: DictCursor,
        redis_cursor: Redis
) -> None:
    """Обрабатывает сообщения в меню смены имени"""

    keyboard = back_keyboard
    new_user_name = str(original_message)
    banned_symbols = SecurityService.check_banned_symbols(new_user_name)

    if message == "назад":
        response = BACK_MAIN_MENU
        reply_keyboard, _ = get_main_menu_keyboard(user_data)
        keyboard = reply_keyboard
        update_user_menu(user_id, UserMenu.MAIN, psql_cursor)

    elif user_data.banned_nickname:
        response = "❌ Вам запрещено менять никнейм"

    elif len(new_user_name) <= 0 or len(new_user_name) > 15:
        response = "❌ Новое имя должно содержать не более 15-ти символов, попробуй еще раз:"

    elif is_arabic_language(new_user_name):
        response = "❌ Обнаружены запрещённые символы"

    elif len(banned_symbols) != 0:
        banned_symbols = ", ".join(banned_symbols)
        response = PATTERN_BANNED_SYMBOLS.format(banned_symbols)

    elif (
        user_data.coins <= ServicesCosts.CHANGE_USER_NAME and
        user_data.free_nick_change is False
    ):
        service_cost = format_number(ServicesCosts.CHANGE_USER_NAME)
        response = f"""
            {NOT_ENOUGH_COINS}
            Стоимость смены имени - {service_cost} коинов
        """

    else:
        update_user_name(user_id, new_user_name, psql_cursor)

        if user_data.free_nick_change is False:
            take_coins(user_id, ServicesCosts.CHANGE_USER_NAME, psql_cursor)
            IncomesService.records_additional_incomes(
                amount=ServicesCosts.CHANGE_USER_NAME,
                redis_cursor=redis_cursor
            )
        else:
            update_free_nick_change(user_id, False, psql_cursor)

        old_user_name = UserSchema.format_telegram_name(user_id, user_data.full_name)
        new_user_name_formatted = UserSchema.format_telegram_name(
            user_id, get_user_data(user_id, psql_cursor).full_name
        )

        await NotificationsService.send_notification(
            chat=NotifyChats.CHANGE_USER_NAME,
            message=f"✍ {old_user_name} сменил имя на {new_user_name_formatted}"
        )

        response = f"✅ Ваш ник изменен на {new_user_name_formatted}"
        reply_keyboard, _ = get_main_menu_keyboard(user_data)
        keyboard = reply_keyboard
        update_user_menu(user_id, UserMenu.MAIN, psql_cursor)

    await send_message(user_id, response, keyboard)

