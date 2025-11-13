from datetime import datetime
from redis.client import Redis
from psycopg2.extras import DictCursor

from schemas.users import UserSchema, UserMenu
from schemas.chats import ExtraMyChats, MyChatsMenu, CHAT_TYPE_COST, INCOME_CHAT_TYPE, \
    get_margin_prolong_chat

from services.chats import ChatsService
from services.incomes import IncomesService
from services.notification import NotificationsService, NotifyChats

from modules.additional import format_number, convert_number, get_word_case
from modules.databases.users import update_user_menu, update_user_extra_data, take_coins
from modules.databases.chats import get_chat_data
from modules.telegram.bot import send_message

from telegram_bot.template_messages import BACK_SERVICES_MENU, COMMAND_NOT_FOUND, NOT_ENOUGH_COINS, \
    REPEAT_CHAT_SUBSCRIPTION
from telegram_bot.keyboards.other import repeat_chat_subscription_keyboard
from telegram_bot.keyboards.services_menu import get_services_menu_keyboard
from telegram_bot.keyboards.my_chats_menu import get_my_chats_keyboard, get_management_chat_keyboard, \
    get_prolong_period_keyboard, get_prolong_confirm_keyboard


async def handler_my_chats_menu(
        *,
        owner_id: int,
        owner_data: UserSchema,
        message: str,
        payload: dict | None,
        psql_cursor: DictCursor,
        redis_cursor: Redis
) -> None:
    """Обрабатывает сообщения в меню мои чаты"""

    extra_data = ExtraMyChats(**owner_data.extra_data)

    keyboard = None
    is_payload = payload is not None

    chat_id = extra_data.chat_id
    chat_data = get_chat_data(chat_id, psql_cursor)

    if extra_data.menu == MyChatsMenu.CHATS and chat_id is None:

        if message == "назад":
            response = BACK_SERVICES_MENU
            keyboard = get_services_menu_keyboard()

            update_user_menu(owner_id, UserMenu.SERVICES, psql_cursor)
            update_user_extra_data(owner_id, None, psql_cursor)

        elif is_payload and payload.get("event") == "select_chat":
            chat_id = payload.get("chat_id")
            chat_data = get_chat_data(chat_id, psql_cursor)

            if chat_data is None:
                response = "Чат не найден"
                keyboard = get_my_chats_keyboard(owner_id, psql_cursor)
            else:
                response = "Управление чатом"
                keyboard = get_management_chat_keyboard(chat_data)
                extra_data.chat_id = chat_id
                extra_data.menu = MyChatsMenu.CHATS
                update_user_extra_data(owner_id, extra_data, psql_cursor)

        else:
            response = COMMAND_NOT_FOUND
            keyboard = get_my_chats_keyboard(owner_id, psql_cursor)

    # Добавить остальную логику из vk_bot/handlers/my_chats_menu.py
    else:
        response = COMMAND_NOT_FOUND
        keyboard = get_my_chats_keyboard(owner_id, psql_cursor)

    await send_message(owner_id, response, keyboard)

