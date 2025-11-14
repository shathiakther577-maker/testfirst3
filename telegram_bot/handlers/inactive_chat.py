from redis.client import Redis
from psycopg2.extras import DictCursor

from settings import NotifyChats

from games.base import BaseGameModel
from schemas.chats import ChatSchema, ChatType, CHAT_TYPES_NAME, CHAT_TYPE_COST
from schemas.users import UserSchema, UserStatus
from schemas.games import Games, ALL_GAMES_VALUES

from services.chats import ChatsService
from services.incomes import IncomesService
from services.notification import NotificationsService

from modules.databases.users import take_coins
from modules.telegram.chats import get_chat_owner_id
from modules.telegram.bot import send_message

from telegram_bot.template_messages import NOT_ENOUGH_COINS
from telegram_bot.keyboards.other import empty_keyboard
from telegram_bot.keyboards.unactive_chat import get_keyboard_select_game_mode, \
    get_keyboard_select_chat_type


async def handler_inactive_chat(
        *,
        user_id: int,
        user_data: UserSchema,
        chat_id: int,
        chat_data: ChatSchema | None,
        message: str,
        payload: dict | None,
        psql_cursor: DictCursor,
        redis_cursor: Redis
) -> None:
    """Обрабатывает сообщения не активированного чата"""

    response = None
    keyboard = None

    if chat_data is None:
        ChatsService.register_chat(chat_id, psql_cursor)
        response = """
            Привет!

            Для игры здесь выбери режим (одна из кнопок ниже) и активируй беседу.
            ⚠️ Выдайте боту права администратора в беседе, чтобы активировать беседу
        """
        keyboard = get_keyboard_select_game_mode()
        return await send_message(chat_id, response, keyboard)

    if chat_data.owner_id is None:
        owner_id = await get_chat_owner_id(chat_id)

        if owner_id is None:
            response = "⚠️ Выдайте боту права администратора в беседе, чтобы активировать беседу"
            return await send_message(chat_id, response)
        else:
            ChatsService.update_owner_id(chat_id, owner_id, psql_cursor)

    if (
        message in ["start", "/start", "начать", "help", "выбор"] or

        payload is not None and
        payload.get("event") == "update_select_game" or

        payload is None and
        message == "повторить подписку"
    ):
        response = "Выберите игру:"
        keyboard = get_keyboard_select_game_mode()

    elif (
        payload is not None and
        payload.get("event") == "select_game" and
        payload.get("game") in ALL_GAMES_VALUES
    ):
        game_mode = Games(payload.get("game"))
        ChatsService.update_game_mode(chat_id, game_mode, psql_cursor)

        response = "Теперь выбери тип беседы:"
        keyboard = get_keyboard_select_chat_type()

    elif (
        payload is not None and
        (
            payload.get("event") == "set_chat_type" and
            payload.get("chat_type") in CHAT_TYPES_NAME or

            payload.get("event") == "repeat_chat_subscription" and
            chat_data.type in CHAT_TYPES_NAME
        )
        and chat_data.game_mode is not None and
        (
            user_id == chat_data.owner_id or
            user_data.status == UserStatus.ADMIN
        )
    ):
        keyboard = None
        chat_type = ChatType(payload.get("chat_type") or chat_data.type)

        if user_data.coins >= CHAT_TYPE_COST[chat_type] or user_data.status == UserStatus.ADMIN:
            response = f"✅ Статус беседы повышен до {chat_type.value}"
            ChatsService.update_type(chat_id, chat_type, psql_cursor)
            ChatsService.update_life_datetime(chat_id, 1, psql_cursor)

            if user_data.status != UserStatus.ADMIN:
                cost = CHAT_TYPE_COST[chat_type]
                take_coins(user_id, cost, psql_cursor)
                IncomesService.records_additional_incomes(cost, redis_cursor)

            # Проверяем, что игра существует в GAMES_MODEL
            if chat_data.game_mode not in BaseGameModel.GAMES_MODEL:
                response = f"❌ Игра {chat_data.game_mode.value} не поддерживается"
                keyboard = get_keyboard_select_game_mode()
            else:
                game_model = BaseGameModel.GAMES_MODEL[chat_data.game_mode]
                game_result = game_model.create_game(chat_id, psql_cursor)
                keyboard = game_model.get_game_keyboard(game_result)

            await NotificationsService.send_notification(
                chat=NotifyChats.MAIN,
                message=f"{user_data.full_name} активировал беседу {chat_id} со статусом {chat_type.value}"
            )

        else:
            response = NOT_ENOUGH_COINS

    elif message == "!чат":
        response = f"Текущий чат: {chat_id}"

    elif (
        message in ["убрать клаву", "убрать клавиатуру"] and
        user_data.status == UserStatus.ADMIN
    ):
        response = "✅"
        keyboard = empty_keyboard

    # В оригинале VK всегда отправляется сообщение, даже если response is None
    # (тогда отправляется пустое сообщение с клавиатурой)
    # В Telegram отправляем только если есть response
    if response is not None:
        await send_message(chat_id, response, keyboard)
    else:
        # Логируем, если сообщение не обработано
        print(f"Unhandled message in inactive_chat: chat_id={chat_id}, user_id={user_id}, message={message}", flush=True)

