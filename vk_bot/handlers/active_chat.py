from redis.client import Redis
from psycopg2.extras import DictCursor
from psycopg2._psycopg import connection as Connection

from games.base import BaseGameModel
from games.rates import RatesService

from schemas.users import UserSchema, UserStatus
from schemas.chats import ChatSchema, ChatStatsPeriod, ALL_CHAT_STATS_PERIOD
from schemas.games import Games, ALL_GAMES_VALUES
from schemas.redis import RedisKeys
from schemas.user_in_chat import UserChatSchema, UserChatMenu

from tops.day_top import DayTopService
from tops.week_top import WeekTopService
from tops.chats_top import ChatsTopService
from tops.clans_top import ClansTopService
from tops.rubles_top import RublesTopService

from services.chats import ChatsService
from services.user_in_chat import UserChatService
from services.transfer_coins import TransferCoinsService

from modules.additional import convert_number
from modules.databases.chats import get_game_data
from modules.vkontakte.bot import send_message

from vk_bot.modules.active_chat import handler_change_chat_name, handler_change_game_mode, \
    handler_change_game_timer, handler_add_helper, handler_del_helper, get_user_balance_message, \
    handler_change_chat_owner, handler_article_notify
from vk_bot.keyboards.other import empty_keyboard
from vk_bot.keyboards.active_chat import get_keyboard_change_game_mode, get_chat_management_keyboard, \
    keyboard_repeat_bet, keyboard_cancel_event_menu


async def handler_active_chat(
    user_id: int,
    user_data: UserSchema,
    chat_id: int,
    chat_data: ChatSchema,
    user_chat_data: UserChatSchema,
    message: str,
    original_message: str,
    fwd_messages: list | None,
    payload: dict | None,
    psql_cursor: DictCursor,
    psql_connection: Connection,
    redis_cursor: Redis,
):
    """Обрабатывает сообщения в активированном чате"""

    is_payload = payload is not None
    split_message = message.split(" ")
    len_split_message = len(split_message)
    split_original_message = original_message.split(" ")

    clear_chat_menu = True
    clear_current_rate = True

    game_data = get_game_data(chat_data.game_id, psql_cursor)
    game_model = BaseGameModel.GAMES_MODEL[chat_data.game_mode]
    game_result = game_model.format_game_result(game_data.game_result)

    response = None
    keyboard = game_model.get_game_keyboard(game_data.game_result)

    if is_payload and payload.get("event") == "get_game_bank":
        response, keyboard = game_model.get_game_bank_message(chat_data, game_data, psql_cursor)

    elif is_payload and payload.get("event") == "get_last_games":
        response = game_model.get_last_game_message(chat_id, psql_cursor)

    elif is_payload and payload.get("event") == "repeat_bet":
        response = "Выберите метод"
        keyboard = keyboard_repeat_bet

    elif is_payload and payload.get("event") == "get_user_balance":
        response = get_user_balance_message(user_data)

    elif (
        is_payload and
        payload.get("event") == "get_chat_help" or
        message in ["/help", "help"]
    ):
        response = "Команды владельцев частных бесед:"
        keyboard = get_chat_management_keyboard(chat_data)

    elif (
        is_payload and payload.get("event") == "get_chat_stats" and
        payload.get("period") in ALL_CHAT_STATS_PERIOD or
        message in ["/stats", "stats", "статистика"]
    ):
        if is_payload:
            period = ChatStatsPeriod(payload.get("period"))
        else:
            period = ChatStatsPeriod.DAY

        response = ChatsService.get_stats_message(chat_id, period, psql_cursor)
        keyboard = ChatsService.get_stats_keyboard()

    elif is_payload and payload.get("event") == "cancel_event_menu":
        response = "Действие отменено"

    elif is_payload and payload.get("event") == "change_chat_name":
        clear_chat_menu = False
        response = "Укажите новое имя чата"
        keyboard = keyboard_cancel_event_menu
        UserChatService.update_menu(user_id, chat_id, UserChatMenu.CHAT_NAME, psql_cursor)

    elif (
        message in ["/article_notify", "article_notify"] or
        is_payload and payload.get("event") == "article_notify"
    ):
        response = handler_article_notify(user_data, chat_data, psql_cursor)

    elif (
        split_original_message[0] in ["/name", "name"] and len_split_message >= 2 or
        user_chat_data.menu == UserChatMenu.CHAT_NAME
    ):
        if not user_chat_data.menu == UserChatMenu.CHAT_NAME:
            chat_name = original_message.replace("/", "", 1).replace("name", "", 1).strip()
        else:
            chat_name = original_message
        response = handler_change_chat_name(user_data, chat_data, chat_name, psql_cursor)

    elif message in ["/game", "game"]:
        response = f"""
            Смена игрового режима: /game режим или /help\n
            Доступные режимы: {", ".join(ALL_GAMES_VALUES)}
        """

    elif (
        is_payload and
        payload.get("event") == "change_game_mode" and
        len(payload) == 1
    ):
        clear_chat_menu = False
        response = "Выберите новый игровой режим"
        keyboard = get_keyboard_change_game_mode()
        UserChatService.update_menu(user_id, chat_id, UserChatMenu.CHANGE_GAME, psql_cursor)

    elif (
        (
            is_payload and
            payload.get("event") == "change_game_mode" and
            payload.get("game_mode") in ALL_GAMES_VALUES
        ) or (
            split_message[0] in ["/game", "game"] and
            len_split_message == 2 and
            split_message[1] in ALL_GAMES_VALUES
        )
    ):
        game_mode = Games(payload.get("game_mode") if is_payload else split_message[1])
        response, keyboard = handler_change_game_mode(user_data, chat_data, game_mode, psql_cursor)

    elif message in ["/timer", "timer"]:
        response = f"""
            Смена таймера игры: /timer время_в_секундах или /help
            Значение игрового таймера в данный момент: {chat_data.game_timer}
        """

    elif is_payload and payload.get("event") == "change_game_timer":
        clear_chat_menu = False
        response = "Укажите новое время игрового таймера в секундах"
        keyboard = keyboard_cancel_event_menu
        UserChatService.update_menu(user_id, chat_id, UserChatMenu.CHANGE_TIMER, psql_cursor)

    elif (
        split_message[0] in ["/timer", "timer"] and len_split_message == 2 or
        user_chat_data.menu == UserChatMenu.CHANGE_TIMER
    ):
        new_timer = message.replace("/", "", 1).replace("timer", "", 1).strip()
        response = handler_change_game_timer(user_data, chat_data, new_timer, psql_cursor)

    elif is_payload and payload.get("event") == "add_chat_helper":
        clear_chat_menu = False
        response = "Укажите какого пользователя добавить в помощники"
        keyboard = keyboard_cancel_event_menu
        UserChatService.update_menu(user_id, chat_id, UserChatMenu.ADD_HELPER, psql_cursor)

    elif (
        split_message[0] in ["/add_helper", "add_helper"] and len_split_message == 2 or
        user_chat_data.menu == UserChatMenu.ADD_HELPER
    ):
        if not user_chat_data.menu == UserChatMenu.ADD_HELPER:
            helper_link = split_message[1]
        else:
            helper_link = message
        response = await handler_add_helper(user_data, chat_data, helper_link, psql_cursor)

    elif is_payload and payload.get("event") == "del_chat_helper":
        clear_chat_menu = False
        response = "Укажите какого пользователя удалить из помощников"
        keyboard = keyboard_cancel_event_menu
        UserChatService.update_menu(user_id, chat_id, UserChatMenu.DEL_HELPER, psql_cursor)

    elif (
        split_message[0] in ["/del_helper", "del_helper"] and len_split_message == 2 or
        user_chat_data.menu == UserChatMenu.DEL_HELPER
    ):
        if not user_chat_data.menu == UserChatMenu.DEL_HELPER:
            helper_link = split_message[1]
        else:
            helper_link = message
        response = await handler_del_helper(user_data, chat_data, helper_link, psql_cursor)

    elif split_message[0] in ["/owner", "owner"] and len_split_message == 2:
        response = await handler_change_chat_owner(user_data, chat_data, split_message[1], psql_cursor)

    elif (
        is_payload and payload.get("event") == "show_personnel" or
        message in ["/helpers", "helpers"]
    ):
        response = ChatsService.get_helpers_message(chat_data, psql_cursor)

    elif (
        split_message[0] == "перевод" and
        (
            (
                len_split_message == 3
            ) or (
                len_split_message == 2 and
                fwd_messages is not None and
                len(fwd_messages) == 1
            )
        )
    ):
        response, keyboard = await TransferCoinsService.transfer_coins_in_message(
            sender_data=user_data, split_message=split_message, fwd_messages=fwd_messages,
            psql_cursor=psql_cursor, redis_cursor=redis_cursor
        )

    elif (
        is_payload and
        payload.get("event") == RedisKeys.TRANSFERS_IN_CHAT.value and
        payload.get("sender_id") == user_id
    ):
        response = TransferCoinsService.handler_transfer_coins_in_message(
            sender_id=user_id, payload=payload,
            psql_cursor=psql_cursor, redis_cursor=redis_cursor
        )

    elif message == "топ дня":
        response, _ = DayTopService.get_message(user_data, psql_cursor)

    elif message == "топ недели":
        response, _ = WeekTopService.get_message(user_data, psql_cursor)

    elif message in ["топ чатов", "топ бесед"]:
        response, _ = ChatsTopService.get_message(chat_data, psql_cursor)

    elif message == "топ кланов":
        response, _ = ClansTopService.get_message(user_data, psql_cursor)

    elif message == "топ монеток":
        response, _ = RublesTopService.get_message(user_data, psql_cursor)

    elif message == "!чат":
        response = f"Текущий чат: {int(chat_id - 2E9)}"

    elif (
        message in ["убрать клаву", "убрать клавиатуру"] and
        user_data.status == UserStatus.ADMIN
    ):
        response = "✅"
        keyboard = empty_keyboard

    elif (
        message in [
            "выдать клаву", "выдать клавиатуру",
            "вернуть клаву", "вернуть клавиатуру"
        ] and user_data.status == UserStatus.ADMIN
    ):
        response = "✅"
        keyboard = game_model.get_game_keyboard(game_data.game_result)

    elif response_current_rate := game_model.handler_current_rate(
        user_data, chat_data, game_result, user_chat_data,
        message, payload, psql_cursor
    ):
        clear_current_rate = False
        response, keyboard = response_current_rate

    elif user_chat_data.current_rate is not None:

        rates = user_chat_data.current_rate.split(" ")
        game_model.update_current_rate(chat_id, user_id, None, psql_cursor)
        clear_current_rate = False

        response = await RatesService.accept_bets(
            user_id=user_id, chat_id=chat_id, game_id=chat_data.game_id,
            amount=message, rates_type=rates, game_model=game_model,
            psql_cursor=psql_cursor, psql_connection=psql_connection,
            redis_cursor=redis_cursor
        )

    elif is_payload and payload.get("event") == "accept_repeat_game":

        response = await RatesService.accept_repeat_game(
            user_id=user_id, chat_id=chat_id, game_id=chat_data.game_id,
            game_model=game_model, psql_cursor=psql_cursor,  psql_connection=psql_connection,
            redis_cursor=redis_cursor
        )

    elif is_payload and payload.get("event") == "auto_game":
        clear_chat_menu = False
        UserChatService.update_menu(user_id, chat_id, UserChatMenu.AUTO_GAME, psql_cursor)
        response = "Введите количество игр, которые хотите повторить"

    elif (
        user_chat_data.menu == UserChatMenu.AUTO_GAME and
        convert_number(message) is not None
    ):
        response = await RatesService.accept_repeat_game(
            user_id=user_id, chat_id=chat_id, game_id=chat_data.game_id,
            game_model=game_model, psql_cursor=psql_cursor, psql_connection=psql_connection,
            redis_cursor=redis_cursor, number_games=convert_number(message)
        )

    if clear_chat_menu is True and user_chat_data.menu is not None:
        UserChatService.update_menu(user_id, chat_id, None, psql_cursor)

    if clear_current_rate is True and user_chat_data.current_rate is not None:
        game_model.update_current_rate(chat_id, user_id, None, psql_cursor)

    await send_message(chat_id, response, keyboard)
