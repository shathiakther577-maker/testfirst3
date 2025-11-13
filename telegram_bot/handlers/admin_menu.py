import asyncio
import threading
from redis.client import Redis
from psycopg2.extras import DictCursor

from settings import Config
from games.base import BaseGameModel

from schemas.users import UserSchema, UserStatus, UserMenu
from schemas.chats import INCOME_CHAT_TYPE
from schemas.games import Games
from schemas.redis import RedisKeys

from services.incomes import IncomesService
from services.promocode import PromoCodeService
from services.bonus_repost import BonusRepostService
from services.notification import NotificationsService, NotifyChats
from services.transfer_coins import TransferCoinsService, TransferWhiteListService
from services.reset_user_data import ResetUserServices

from modules.additional import strtobool, format_number
from modules.databases.users import update_user_menu, update_user_extra_data, \
    get_user_data, set_coins, give_coins, take_coins, update_user_name, update_free_nick_change
from modules.databases.chats import get_game_data
from modules.telegram.bot import send_message
from modules.telegram.users import get_registration_date, get_user_friends, kick_user_from_chat

from telegram_bot.template_messages import BACK_MAIN_MENU, COMMAND_NOT_FOUND
from telegram_bot.modules.admin_menu import AdminPanel, UserIdNotFound, UserDataNotFound, \
    UsersDataNotFound, ChatIdNotFound, ChatTypeNotFound, ChatDataNotFound, GameModeNotFound, \
    ChatLifeDatetimeError, NumberNotFound, MaxTextLen, TimeStamp, ClansTop, restart_bot, \
    get_time_stamp_keyboard, add_up_profit, get_develore_income, clear_developer_income, \
    change_works_status, TIME_STAMPS, TOPS, TOPS_NAME
from telegram_bot.modules.active_chat import handler_change_game_mode
from telegram_bot.modules.mailing_menu import ExtraMailing, get_mailing_menu_keyboard
from telegram_bot.keyboards.main_menu import get_main_menu_keyboard
from telegram_bot.keyboards.admin_menu import get_admin_menu_keyboard


ADMIN_HELP_MESSAGE = """
    help - Показать список всех команд
    mailing - Перекидывает в меню рассылки

    СТАТИСТИКА
    • incames - Показывает доход проекта
    • stats|statistics - Показывает статистику проекта
    • active - Показывает статистику активности
    • luckys mode[day/week/all_time] - Показывает самых везучих игроков

    ПОЛЬЗОВАТЕЛИ
    • user user_id|link - Информация о пользователе
    • users user_id|link - Информация о нескольких пользователях
    • ban user_id|link - Заблокировать пользователя
    • unban user_id|link - Разблокировать пользователя
    • coins user_id|link amount - Выдать коины
    • take_coins user_id|link amount - Забрать коины
    • reset user_id|link - Обнулить данные пользователя

    ЧАТЫ
    • chat chat_id - Информация о чате
    • chat_type chat_id type - Изменить тип чата
    • chat_life chat_id days - Изменить срок жизни чата

    ИГРЫ
    • start_game game_id - Запустить игру

    ПРОЧЕЕ
    • restart_bot - Перезапустить бота
"""


async def handler_admin_menu(
    *,
    admin_id: int,
    admin_data: UserSchema,
    message: str,
    original_message: str,
    fwd_messages: list | None,
    payload: dict | None,
    psql_cursor: DictCursor,
    redis_cursor: Redis
) -> None:
    """Обрабатывает сообщения в админ панели"""

    keyboard = get_admin_menu_keyboard()
    split_message = message.split(" ")
    len_split_message = len(split_message)

    try:
        if message == "назад":
            response = BACK_MAIN_MENU
            keyboard = get_main_menu_keyboard(admin_data)
            update_user_menu(admin_id, UserMenu.MAIN, psql_cursor)

        elif message == "help":
            response = ADMIN_HELP_MESSAGE

        # Добавить остальную логику из vk_bot/handlers/admin_menu.py
        # Адаптировать под Telegram (убрать VK специфичные функции)
        else:
            response = COMMAND_NOT_FOUND

    except (
        UserIdNotFound, UserDataNotFound, UsersDataNotFound,
        ChatIdNotFound, ChatDataNotFound, ChatTypeNotFound,
        GameModeNotFound, ChatLifeDatetimeError, NumberNotFound,
        MaxTextLen
    ) as error_text:
        response = str(error_text)

    await send_message(admin_id, response, keyboard)

