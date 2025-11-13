from datetime import datetime
from redis.client import Redis
from psycopg2.extras import DictCursor
from psycopg2._psycopg import connection as Connection

from settings import PointsLimit, PromoCodeSettings

from schemas.users import UserSchema, UserMenu
from schemas.redis import RedisKeys
from schemas.promocodes import PromoCodeSchema, CreatePromoCode, \
    ExtraPromoCode, PromoCodeMenu

from services.captcha import CaptchaService
from services.security import SecurityService
from services.promocode import PromoCodeService

from modules.additional import format_number, convert_number, format_seconds_to_text
from modules.databases.users import update_user_menu, update_user_extra_data
from modules.telegram.bot import send_message

from telegram_bot.template_messages import BACK_SERVICES_MENU, COMMAND_NOT_FOUND, \
    PATTERN_BANNED_SYMBOLS, NOT_ENOUGH_COINS, LIMIT_ATTEMPTS, SOMETHING_WENT_WRONG
from telegram_bot.keyboards.other import back_keyboard
from telegram_bot.keyboards.services_menu import get_services_menu_keyboard
from telegram_bot.keyboards.promocode_menu import get_promocode_menu_keyboard


def go_promocode_main_menu(
        user_id: int,
        psql_cursor: DictCursor
) -> tuple[str, str]:
    """Возвращает пользователя в главное меню внутри меню промокодов"""

    response = "Сервис управления промокодами"
    keyboard = get_promocode_menu_keyboard()
    update_user_extra_data(user_id, ExtraPromoCode(), psql_cursor)

    return response, keyboard


async def handler_promocode_menu(
        *,
        user_id: int,
        user_data: UserSchema,
        message: str,
        original_message: str,
        payload: dict | None,
        psql_cursor: DictCursor,
        psql_connection: Connection,
        redis_cursor: Redis
) -> None:
    """Обрабатывает сообщения в меню промокодов"""

    extra_data = ExtraPromoCode(**user_data.extra_data)
    is_payload = payload is not None

    if extra_data.menu == PromoCodeMenu.MAIN:

        if message == "назад":
            response = BACK_SERVICES_MENU
            keyboard = get_services_menu_keyboard()

            update_user_menu(user_id, UserMenu.SERVICES, psql_cursor)
            update_user_extra_data(user_id, None, psql_cursor)

        elif message == "активировать промокод":
            if PromoCodeService.is_access_activation(user_id, redis_cursor):
                response = "Введите название промокода"
                keyboard = back_keyboard

                extra_data.menu = PromoCodeMenu.BEFORE_ACTIVATE
                update_user_extra_data(user_id, extra_data, psql_cursor)
            else:
                seconds = PromoCodeService.get_ttl_ban_access(user_id, redis_cursor)
                response = f"Доступ к сервису ограничен на {format_seconds_to_text(seconds)}"
                keyboard = get_promocode_menu_keyboard()

        elif message == "создать промокод":
            response = "Введите название промокода"
            keyboard = back_keyboard

            extra_data.menu = PromoCodeMenu.SET_NAME
            update_user_extra_data(user_id, extra_data, psql_cursor)

        elif message == "информация о промокодах":
            response = PromoCodeService.get_message_user_promocodes(user_id, psql_cursor)
            keyboard = get_promocode_menu_keyboard()

        else:
            response = COMMAND_NOT_FOUND
            keyboard = get_promocode_menu_keyboard()

    # Добавить остальную логику из vk_bot/handlers/promocode_menu.py
    else:
        response = COMMAND_NOT_FOUND
        keyboard = get_promocode_menu_keyboard()

    await send_message(user_id, response, keyboard)

