from datetime import datetime, timedelta
from redis.client import Redis
from psycopg2.extras import DictCursor
from psycopg2._psycopg import connection as Connection
from telegram import ReplyKeyboardMarkup

from settings import Temp, TelegramBotSettings

from schemas.users import UserSchema, UserMenu
from schemas.redis import RedisKeys
from schemas.bonus_repost import ExtraBonusRepost

from services.incomes import IncomesService
from services.captcha import CaptchaService
from services.bonus_repost import BonusRepostService

from modules.additional import format_number
from modules.databases.users import update_user_menu, update_user_extra_data, \
    give_coins
from modules.telegram.bot import send_message
from modules.telegram.users import is_user_subscribed_to_channel

from telegram_bot.template_messages import BACK_MAIN_MENU, DATA_OUTDATED, SOMETHING_WENT_WRONG
from telegram_bot.keyboards.main_menu import get_main_menu_keyboard


def go_main_menu(
        user_data: UserSchema,
        psql_cursor: DictCursor
) -> tuple[str, ReplyKeyboardMarkup]:
    """Возвращает сообщение и клавиатуру для перехода в главное меню"""

    try:
        Temp.GET_BONUS_REPOST.remove(user_data.user_id)
    except:
        pass

    update_user_menu(user_data.user_id, UserMenu.MAIN, psql_cursor)
    update_user_extra_data(user_data.user_id, None, psql_cursor)

    reply_keyboard, _ = get_main_menu_keyboard(user_data)
    return BACK_MAIN_MENU, reply_keyboard


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
    """Обрабатывает сообщения в меню бонуса за подписку на канал"""

    extra_data = ExtraBonusRepost(**user_data.extra_data)
    is_payload = payload is not None

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
            reply_keyboard, _ = get_main_menu_keyboard(user_data)
            keyboard = reply_keyboard

        elif (
                bonus_post.activations > 0 and
                not BonusRepostService.user_active_post(user_id, post_id, psql_cursor)
        ):
            # TODO: Укажите ID канала в settings.py -> TelegramBotSettings.CHANNEL_ID
            # или в .env файле как TELEGRAM_CHANNEL_ID
            channel_id = TelegramBotSettings.CHANNEL_ID
            
            if channel_id == 0:
                response = "❌ Бонус за подписку временно недоступен (канал не настроен)"
                reply_keyboard, _ = get_main_menu_keyboard(user_data)
                keyboard = reply_keyboard
            else:
                # Проверяем подписку на канал вместо репоста
                is_subscribed = await is_user_subscribed_to_channel(user_id, channel_id)
                
                if is_subscribed:
                    reward = bonus_post.reward
                    # Дополнительная награда за подписку (аналог sub_reward из VK)
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

                        response = f"✅ Вы получили {format_number(reward)} коинов за подписку на канал."
                        IncomesService.records_additional_expenses(reward, redis_cursor)
                        reply_keyboard, _ = get_main_menu_keyboard(user_data)
                        keyboard = reply_keyboard

                    except:
                        response = SOMETHING_WENT_WRONG
                        psql_connection.rollback()
                        reply_keyboard, _ = get_main_menu_keyboard(user_data)
                        keyboard = reply_keyboard

                    finally:
                        psql_connection.autocommit = True
                else:
                    response = "❌ Вы не подписаны на основной канал. Подпишитесь и попробуйте снова."
                    reply_keyboard, _ = get_main_menu_keyboard(user_data)
                    keyboard = reply_keyboard

        else:
            response = "😏 Бонус за подписку был уже получен"
            reply_keyboard, _ = get_main_menu_keyboard(user_data)
            keyboard = reply_keyboard
        
        response, keyboard = go_main_menu(user_data, psql_cursor)

    else:
        if attempts_captchas < 3:
            response = "Неправильная последовательность символов. Попробуйте еще раз"
            reply_keyboard, _ = get_main_menu_keyboard(user_data)
            keyboard = reply_keyboard
        else:
            CaptchaService.ban_service_access(
                user_id, RedisKeys.CAPTCHA_BAN_BONUSREPOST, redis_cursor
            )
            CaptchaService.del_captcha_attempts(
                user_id, RedisKeys.CAPTCHA_BONUSREPOST, redis_cursor
            )
            response = "Вы превысили лимит попыток. Попробуйте позже."
            reply_keyboard, _ = get_main_menu_keyboard(user_data)
            keyboard = reply_keyboard

    await send_message(user_id, response, keyboard)
