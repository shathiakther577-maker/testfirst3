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
from modules.databases.users import update_user_menu, update_user_extra_data, get_user_data
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


def checking_activation_promocode(
        user_id: int,
        promocode_data: PromoCodeSchema | None,
        psql_cursor: DictCursor
) -> tuple[str | None, bool]:
    """Проверяет можно ли активировать промокод"""
    
    # Перезагружаем user_data из БД чтобы получить актуальное значение all_win
    user_data = get_user_data(user_id, psql_cursor)
    if user_data is None:
        return "Ошибка: не удалось загрузить данные пользователя", False

    if user_data.banned_promo:
        return "Отказано в доступе", False

    if promocode_data is None:
        return "Промокод не найден", False

    promocode_name = promocode_data.name

    if promocode_data.quantity <= 0:
        PromoCodeService.delete_promocode(promocode_name, psql_cursor)
        return "Промокод не найден", False

    if promocode_data.life_datetime <= datetime.now():
        PromoCodeService.delete_promocode(promocode_name, psql_cursor)
        return "Промокод не найден", False

    if promocode_data.owner_id == user_id:
        return "Вы не можете активировать свой промокод", False

    # Активация промокодов доступна всем без ограничений
    # if user_data.all_win < PointsLimit.ACTIVATE_PROMOCODE:
    #     points_limit = format_number(PointsLimit.ACTIVATE_PROMOCODE)
    #     return f"""
    #         Активировать промокод можно по достижении {points_limit} очков в общем рейтинге игроков
    #         Твой счет: {format_number(user_data.all_win)}
    #     """, False

    if PromoCodeService.check_activation(promocode_name, user_id, psql_cursor):
        return "Вы уже активировали этот промокод", False

    return None, True


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
    attachment = None

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

    elif extra_data.menu == PromoCodeMenu.BEFORE_ACTIVATE:

        promocode_name = SecurityService.replace_banned_symbols(original_message)
        promocode_data = PromoCodeService.get_promocode(promocode_name, psql_cursor)
        promocode_response, promocode_access = checking_activation_promocode(
            user_id, promocode_data, psql_cursor
        )
        attempts = PromoCodeService.get_activation_attempts(user_id, redis_cursor) + 1
        PromoCodeService.set_activation_attempts(user_id, attempts, redis_cursor)

        if attempts >= 10:
            response = LIMIT_ATTEMPTS
            _, keyboard = go_promocode_main_menu(user_id, psql_cursor)
            PromoCodeService.ban_access(user_id, redis_cursor)
            PromoCodeService.del_activation_attempts(user_id, redis_cursor)

        elif message == "назад":
            response, keyboard = go_promocode_main_menu(user_id, psql_cursor)

        elif promocode_access is True:
            response = "Решите капчу чтобы активировать промокод. " \
                       "Укажите правильную последовательность символов"

            captcha_name, attachment = await CaptchaService.get_captcha()
            keyboard = CaptchaService.create_captcha_keyboard(captcha_name)
            PromoCodeService.del_activation_attempts(user_id, redis_cursor)

            extra_data.menu = PromoCodeMenu.ACTIVATE
            extra_data.name = promocode_name
            extra_data.captcha_name = captcha_name
            update_user_extra_data(user_id, extra_data, psql_cursor)

        else:
            response = promocode_response
            keyboard = back_keyboard

    elif extra_data.menu == PromoCodeMenu.ACTIVATE:

        attempts = CaptchaService.get_captcha_attempts(
            user_id, RedisKeys.CAPTCHA_PROMOCODE, redis_cursor
        ) + 1
        CaptchaService.set_captcha_attempts(
            user_id, RedisKeys.CAPTCHA_PROMOCODE, attempts, redis_cursor
        )

        if attempts >= 3:
            response = LIMIT_ATTEMPTS
            _, keyboard = go_promocode_main_menu(user_id, psql_cursor)
            PromoCodeService.ban_access(user_id, redis_cursor)
            CaptchaService.del_captcha_attempts(user_id, RedisKeys.CAPTCHA_PROMOCODE, redis_cursor)

        elif message == "назад":
            response, keyboard = go_promocode_main_menu(user_id, psql_cursor)

        elif is_payload and payload.get("captcha_name") == extra_data.captcha_name:

            promocode_data = PromoCodeService.get_promocode(extra_data.name, psql_cursor)
            promocode_response, promocode_access = checking_activation_promocode(
                user_id, promocode_data, psql_cursor
            )
            
            # Перезагружаем user_data для активации промокода
            user_data = get_user_data(user_id, psql_cursor)
            if user_data is None:
                response = "Ошибка: не удалось загрузить данные пользователя"
                _, keyboard = go_promocode_main_menu(user_id, psql_cursor)
                await send_message(user_id, response, keyboard, attachment)
                return

            psql_connection.autocommit = False

            if promocode_access is True:
                try:

                    await PromoCodeService.activated_promocode(user_data, promocode_data, psql_cursor)
                    response = f"✅ Вы успешно активировали промокод {promocode_data.name} " \
                        f"и получили {format_number(promocode_data.reward)} WC"

                    psql_connection.commit()

                except:
                    response = SOMETHING_WENT_WRONG
                    psql_connection.rollback()

                finally:
                    psql_connection.autocommit = True

            else:
                response = promocode_response

            _, keyboard = go_promocode_main_menu(user_id, psql_cursor)
            CaptchaService.del_captcha_attempts(user_id, RedisKeys.CAPTCHA_PROMOCODE, redis_cursor)

        else:
            response = "Неправильная последовательность символов. Попробуйте еще раз"
            captcha_name, attachment = await CaptchaService.get_captcha()
            keyboard = CaptchaService.create_captcha_keyboard(captcha_name)

            extra_data.captcha_name = captcha_name
            update_user_extra_data(user_id, extra_data, psql_cursor)

    elif extra_data.menu == PromoCodeMenu.SET_NAME:

        keyboard = back_keyboard
        promocode_name = original_message
        banned_symbols = SecurityService.check_banned_symbols(promocode_name)

        if message == "назад":
            response, keyboard = go_promocode_main_menu(user_id, psql_cursor)

        elif len(banned_symbols) != 0:
            banned_symbols = ", ".join(banned_symbols)
            response = PATTERN_BANNED_SYMBOLS.format(banned_symbols)

        elif (
            len(promocode_name) <= 0 or
            len(promocode_name) > PromoCodeSettings.MAX_LEN_NAME
        ):
            max_len = format_number(PromoCodeSettings.MAX_LEN_NAME)
            response = f"❌ Максимальная длина названия промокода {max_len}"

        elif PromoCodeService.get_promocode(promocode_name, psql_cursor) is not None:
            response = "Данное название уже занято"

        elif (
            PromoCodeService.get_count_user_promocode(user_id, psql_cursor)
            >= PromoCodeSettings.MAX_COUNT_PROMOCODE
        ):
            response = "Вы достигли лимита создания промокодов"
            _, keyboard = go_promocode_main_menu(user_id, psql_cursor)

        else:
            response = "Введите время через которое промокод станет неактивным в минутах"

            extra_data.menu = PromoCodeMenu.SET_LIFE_DATE
            extra_data.name = promocode_name
            update_user_extra_data(user_id, extra_data, psql_cursor)

    elif extra_data.menu == PromoCodeMenu.SET_LIFE_DATE:

        keyboard = back_keyboard
        life_date = convert_number(original_message)

        if message == "назад":
            response = "Введите название промокода"

            extra_data.menu = PromoCodeMenu.SET_NAME
            extra_data.name = None
            update_user_extra_data(user_id, extra_data, psql_cursor)

        elif (
            life_date is None or
            life_date <= 0 or
            life_date > PromoCodeSettings.MAX_LIFE_IN_MINUTES
        ):
            max_life_date = format_number(PromoCodeSettings.MAX_LIFE_IN_MINUTES)
            response = f"❌ Максимальное время существования промокода {max_life_date}"

        else:
            response = "Введите количество активаций"

            extra_data.menu = PromoCodeMenu.SET_QUANTITY
            extra_data.life_date = life_date
            update_user_extra_data(user_id, extra_data, psql_cursor)

    elif extra_data.menu == PromoCodeMenu.SET_QUANTITY:

        keyboard = back_keyboard
        quantity = convert_number(original_message)

        if message == "назад":
            response = "Введите время через которое промокод станет неактивным в минутах"

            extra_data.menu = PromoCodeMenu.SET_LIFE_DATE
            extra_data.life_date = None
            update_user_extra_data(user_id, extra_data, psql_cursor)

        elif (
            quantity is None or
            quantity <= 0 or
            quantity > PromoCodeSettings.MAX_QUANTITY
        ):
            max_quantity = format_number(PromoCodeSettings.MAX_QUANTITY)
            response = f"❌ Максимальное количество активаций {max_quantity}"

        else:
            response = "Введите награду за активацию"

            extra_data.menu = PromoCodeMenu.SET_AMOUNT
            extra_data.quantity = quantity
            update_user_extra_data(user_id, extra_data, psql_cursor)

    elif extra_data.menu == PromoCodeMenu.SET_AMOUNT:

        keyboard = back_keyboard
        reward = convert_number(original_message)

        if message == "назад":
            response = "Введите количество активаций"

            extra_data.menu = PromoCodeMenu.SET_QUANTITY
            extra_data.quantity = None
            update_user_extra_data(user_id, extra_data, psql_cursor)

        elif (
            reward is None or
            reward < PromoCodeSettings.MIN_REWARD or
            reward > PromoCodeSettings.MAX_REWARD
        ):
            min_reward = format_number(PromoCodeSettings.MIN_REWARD)
            max_reward = format_number(PromoCodeSettings.MAX_REWARD)
            response = f"❌ Диапазон награды за активацию от {min_reward} до {max_reward}"

        else:
            # Перезагружаем user_data из БД чтобы получить актуальное значение all_win и coins
            user_data = get_user_data(user_id, psql_cursor)
            if user_data is None:
                response = "Ошибка: не удалось загрузить данные пользователя"
                keyboard = back_keyboard
            elif extra_data.quantity * reward > user_data.coins:
                response = NOT_ENOUGH_COINS
                keyboard = back_keyboard
            elif user_data.banned_promo:
                response = "Отказано в доступе"
                keyboard = back_keyboard
            # Создание промокодов доступно всем без ограничений
            # elif user_data.all_win < PointsLimit.CREATE_PROMOCODE:
            #     points_limit = format_number(PointsLimit.CREATE_PROMOCODE)
            #     response = f"""
            #         Создавать промокод можно по достижении {points_limit} очков в общем рейтинге игроков
            #         Твой счет: {format_number(user_data.all_win)}
            #     """
            #     keyboard = back_keyboard
            else:
                create_promocode = CreatePromoCode(**dict(extra_data), reward=reward)
                promocode_data = await PromoCodeService.create_promocode(
                    user_data, create_promocode, psql_cursor
                )
                response = f"""
                    👑 Промокод успешно создан\n
                    {PromoCodeService.format_promocode_message(promocode_data)}
                """
                _, keyboard = go_promocode_main_menu(user_id, psql_cursor)

    else:
        response = COMMAND_NOT_FOUND
        keyboard = get_promocode_menu_keyboard()

    await send_message(user_id, response, keyboard, attachment)

