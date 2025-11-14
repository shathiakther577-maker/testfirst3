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
    chat_data = get_chat_data(chat_id, psql_cursor) if chat_id else None

    if extra_data.menu == MyChatsMenu.CHATS and chat_id is None:

        if message == "назад":
            response = BACK_SERVICES_MENU
            keyboard = get_services_menu_keyboard()

            update_user_menu(owner_id, UserMenu.SERVICES, psql_cursor)
            update_user_extra_data(owner_id, None, psql_cursor)

        elif (
            is_payload and
            payload.get("event") == "get_my_chats_message" and
            isinstance(payload.get("offset"), int)
        ):
            response = "Выберите чат для управления:"
            keyboard = get_my_chats_keyboard(owner_id, psql_cursor, payload["offset"])

        elif (
            is_payload and
            payload.get("event") == "select_chat" and
            isinstance(payload.get("chat_id"), int)
        ):

            chat_id = payload["chat_id"]
            chat_data = get_chat_data(chat_id, psql_cursor)

            if chat_data and chat_data.owner_id == owner_id:
                response = "Доступные команды управления чатом"
                keyboard = get_management_chat_keyboard(chat_data)

                extra_data.chat_id = chat_id
                update_user_extra_data(owner_id, extra_data, psql_cursor)

            else:
                response = "Вы не являетесь владельцем этого чата"
                keyboard = get_my_chats_keyboard(owner_id, psql_cursor)

        else:
            response = "Выберите чат для управления:"
            keyboard = get_my_chats_keyboard(owner_id, psql_cursor)

    elif (
        extra_data.menu == MyChatsMenu.CHATS and
        chat_id is not None and
        chat_data and chat_data.owner_id == owner_id
    ):

        if message == "назад":
            response = "Выберите чат для управления:"
            keyboard = get_my_chats_keyboard(owner_id, psql_cursor)
            update_user_extra_data(owner_id, ExtraMyChats(), psql_cursor)

        elif message == "инфо" or (is_payload and payload.get("event") == "get_chat_info"):

            chat_name = chat_data.name if chat_data.name else str(chat_id)
            chat_type = chat_data.type.value if chat_data.type else "Не выбран"
            chat_owner_income = INCOME_CHAT_TYPE[chat_type] if chat_data.type else "-"
            game_mode = chat_data.game_mode.name if chat_data.game_mode else "Не выбран"
            life_datetime = chat_data.life_datetime.strftime("%Y-%m-%d %H:%M:%S")

            response = f"""
                📊 Информация о чате {chat_name}:

                💎 Тип: {chat_type} ({chat_owner_income}%)
                🌐 Режим: {game_mode}
                ⌛ Активен до: {life_datetime}
            """

        elif (
            (
                message == "продлить подписку" or
                (is_payload and payload.get("event") == "prolong_subscription")
            ) and
            chat_data.is_activated and chat_data.life_datetime > datetime.now()
        ):
            response = "Выберите срок продления или напишите свой, минимальный срок продления 1 сутки"
            keyboard = get_prolong_period_keyboard()

            extra_data.menu = MyChatsMenu.PROLONG
            update_user_extra_data(owner_id, extra_data, psql_cursor)

        elif (
            (
                message == "повторить подписку" or
                (is_payload and payload.get("event") == "repeat_subscription")
            ) and
            chat_data.is_activated is False and chat_data.life_datetime <= datetime.now()
        ):
            response = "Мы отправили вам сообщения в чат для повторения прошлой подписки"
            keyboard = get_management_chat_keyboard(chat_data)
            await send_message(chat_id, REPEAT_CHAT_SUBSCRIPTION, repeat_chat_subscription_keyboard)

        elif (
            message == "подписка чата недоступна" or
            (is_payload and payload.get("event") == "subscription_not_available")
        ):
            response = "Продление или повторное подписки в чате недоступны. Пожалуйста, обратитесь в службу поддержки."
            keyboard = get_management_chat_keyboard(chat_data)

        else:
            response = COMMAND_NOT_FOUND
            keyboard = get_management_chat_keyboard(chat_data)

    elif (
        extra_data.menu == MyChatsMenu.PROLONG and
        chat_data and chat_data.owner_id == owner_id
    ):
        days_period = payload.get("days") if is_payload else convert_number(message)
        days_sub_left = ChatsService.get_days_subscription_left(chat_id, psql_cursor)

        if message == "назад":
            response = "Доступные команды управления чатом"
            keyboard = get_management_chat_keyboard(chat_data)

            extra_data.menu = MyChatsMenu.CHATS
            update_user_extra_data(owner_id, extra_data, psql_cursor)

        elif days_period is None or not 1 <= days_period + days_sub_left <= 180:
            response = "Максимальный срок подписки чата может быть 180 дней"
            keyboard = get_prolong_period_keyboard()

        else:
            margin = get_margin_prolong_chat(days_period)
            chat_cost = CHAT_TYPE_COST[chat_data.type] if chat_data.type else 0

            days_word = get_word_case(days_period, ("день", "дня", "дней"))
            prolong_cost = round(((chat_cost / 30) + (chat_cost / 30) * margin) * days_period)
            format_prolong_cost = format_number(prolong_cost)

            response = f"Стоимость продления на {days_period} {days_word} составит {format_prolong_cost} WC, продолжаем ?"
            keyboard = get_prolong_confirm_keyboard()

            update_user_extra_data(owner_id, ExtraMyChats(
                menu=MyChatsMenu.PROLONG_CONFIRM, chat_id=chat_id,
                prolong_cost=prolong_cost, prolong_period=days_period
            ), psql_cursor)

    elif (
        extra_data.menu == MyChatsMenu.PROLONG_CONFIRM and
        chat_data and chat_data.owner_id == owner_id
    ):
        confirm = payload.get("confirm") if (is_payload and payload.get("event") == "prolong_confirm") else None

        if confirm is True:

            if owner_data.coins < extra_data.prolong_cost:
                response = NOT_ENOUGH_COINS

            elif chat_data.is_activated is False or chat_data.life_datetime <= datetime.now():
                response = "Нельзя продлить подписку в чате, так как она истекла. Сначала повторите подписку."

            else:
                prolong_period = extra_data.prolong_period
                ChatsService.prolong_life_datetime(chat_id, prolong_period, psql_cursor)

                prolong_cost = extra_data.prolong_cost
                take_coins(owner_id, prolong_cost, psql_cursor)
                IncomesService.records_additional_incomes(prolong_cost, redis_cursor)

                chat_name = chat_data.name if chat_data.name else str(chat_data.chat_id)
                days_word = get_word_case(prolong_period, ("день", "дня", "дней"))

                await NotificationsService.send_notification(
                    chat=NotifyChats.MAIN,
                    message=f"{owner_data.telegram_name} продлил беседу {chat_id} со статусом " \
                        f"{chat_data.type.value if chat_data.type else 'N/A'} на {prolong_period}д за {format_number(prolong_cost)}"
                )
                response = f"Вы успешно увеличили срок подписки в чате {chat_name} на {prolong_period} {days_word}"

            keyboard = get_management_chat_keyboard(chat_data)
            update_user_extra_data(owner_id, ExtraMyChats(chat_id=chat_id), psql_cursor)

        elif confirm is False:
            response = "Вы отменили продление подписки"
            keyboard = get_management_chat_keyboard(chat_data)
            update_user_extra_data(owner_id, ExtraMyChats(chat_id=chat_id), psql_cursor)

        else:
            days_period = extra_data.prolong_period
            days_word = get_word_case(days_period, ("день", "дня", "дней"))
            format_prolong_cost = format_number(extra_data.prolong_cost)

            response = f"Стоимость продления на {days_period} {days_word} составит {format_prolong_cost} WC, продолжаем ?"
            keyboard = get_prolong_confirm_keyboard()

    else:
        response = "Обновление данных до актуальных"
        keyboard = get_my_chats_keyboard(owner_id, psql_cursor)
        update_user_extra_data(owner_id, ExtraMyChats(), psql_cursor)

    await send_message(owner_id, response, keyboard)
