from datetime import datetime, timedelta
from redis.client import Redis
from psycopg2.extras import DictCursor
from psycopg2._psycopg import connection as Connection

from settings import Temp

from schemas.users import UserSchema, UserMenu
from schemas.redis import RedisKeys
from schemas.bonus_repost import ExtraBonusRepost

from services.incomes import IncomesService
from services.captcha import CaptchaService
from services.bonus_repost import BonusRepostService

from modules.additional import format_number
from modules.databases.users import update_user_menu, update_user_extra_data, \
    give_coins
from modules.vkontakte.bot import send_message, is_user_in_group
from modules.vkontakte.users import get_friends_amount, get_followers_amount, \
    get_registration_date

from vk_bot.template_messages import BACK_MAIN_MENU, DATA_OUTDATED, SOMETHING_WENT_WRONG
from vk_bot.keyboards.main_menu import get_main_menu_keyboard


def go_main_menu(
        user_data: UserSchema,
        psql_cursor: DictCursor
) -> tuple[str, str]:
    """Возвращает сообщение и клавиатуру для перехода в главное меню"""

    try:
        Temp.GET_BONUS_REPOST.remove(user_data.user_id)
    except:
        pass

    update_user_menu(user_data.user_id, UserMenu.MAIN, psql_cursor)
    update_user_extra_data(user_data.user_id, None, psql_cursor)

    return BACK_MAIN_MENU, get_main_menu_keyboard(user_data)


async def handler_bonus_repost_menu(
        *,
        user_id: int,
        user_data: UserSchema,
        message: str,
        payload: dict | None,
        psql_cursor: DictCursor,
        psql_connection: Connection,
        redis_cursor: Redis
) -> None:
    """Обрабатывает сообщения в меню получения бонуса за репост"""

    extra_data = ExtraBonusRepost(**user_data.extra_data)
    is_payload = payload is not None
    attachment = None

    attempts_captchas = CaptchaService.get_captcha_attempts(
        user_id, RedisKeys.CAPTCHA_BONUSREPOST, redis_cursor
    )

    if message == "назад":

        CaptchaService.set_captcha_attempts(
            user_id, RedisKeys.CAPTCHA_BONUSREPOST, attempts_captchas+1, redis_cursor
        )
        response, keyboard = go_main_menu(user_data, psql_cursor)

    elif is_payload and payload.get("captcha_name") == extra_data.captcha_name:

        post_id = extra_data.post_id
        bonus_post = BonusRepostService.get_bonus_post(post_id, psql_cursor)

        if bonus_post is None or bonus_post.activations <= 0:
            response = DATA_OUTDATED

        elif (
                bonus_post.activations > 0 and
                not BonusRepostService.user_active_post(user_id, post_id, psql_cursor) and
                (
                    await get_friends_amount(user_id) >= 25 or
                    await get_followers_amount(user_id) >= 30
                ) and
                datetime.today() >= await get_registration_date(user_id) + timedelta(days=180)
        ):

            reward = bonus_post.reward
            if await is_user_in_group(user_id):
                reward += bonus_post.sub_reward

            psql_connection.autocommit = False

            try:
                give_coins(user_id, reward, psql_cursor)
                BonusRepostService.decrement_activation(post_id, psql_cursor)
                BonusRepostService.insert_bonus_repost_logs(user_id, post_id, reward, psql_cursor)

                psql_cursor.execute("""
                    SELECT activations FROM bonus_posts
                    WHERE post_id = %(post_id)s
                """, {
                    "post_id": post_id
                })

                if (psql_cursor.fetchone())["activations"] < 0:
                    raise Exception()

                psql_connection.commit()

                response = f"✅ Вы получили {format_number(reward)} коинов за репост записи."
                IncomesService.records_additional_expenses(reward, redis_cursor)

            except:
                response = SOMETHING_WENT_WRONG
                psql_connection.rollback()

            finally:
                psql_connection.autocommit = True

        else:
            response = "😏 Бонус за репост был уже получен или ваш аккаунт не проходит проверку Анти-Фейк"

        _, keyboard = go_main_menu(user_data, psql_cursor)

    else:
        if attempts_captchas < 3:
            response = "Неправильная последовательность символов. Попробуйте еще раз"
            captcha_name, attachment = await CaptchaService.get_captcha()
            keyboard = CaptchaService.create_captcha_keyboard(captcha_name)

            CaptchaService.set_captcha_attempts(
                user_id, RedisKeys.CAPTCHA_BONUSREPOST, attempts_captchas+1, redis_cursor
            )

            extra_data.captcha_name = captcha_name
            update_user_extra_data(user_id, extra_data, psql_cursor)

        else:
            response = "Вы неверно решили капчу 3 раза"
            _, keyboard = go_main_menu(user_data, psql_cursor)

            CaptchaService.ban_service_access(
                user_id, RedisKeys.CAPTCHA_BAN_BONUSREPOST, redis_cursor
            )
            CaptchaService.del_captcha_attempts(
                user_id, RedisKeys.CAPTCHA_BONUSREPOST, redis_cursor
            )

    await send_message(user_id, response, keyboard, attachment)
