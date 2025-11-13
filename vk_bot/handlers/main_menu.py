from redis.client import Redis
from psycopg2.extras import DictCursor
from vk_api.keyboard import VkKeyboard

from settings import Config, PointsLimit

from schemas.users import UserSchema, UserStatus, UserMenu
from schemas.games import ALL_GAMES_VALUES
from schemas.redis import RedisKeys
from schemas.transfer_coins import ExtraTransferCoins

from services.clans import ClanService
from services.transfer_coins import TransferCoinsService

from tops.day_top import DayTopService
from tops.week_top import WeekTopService
from tops.clans_top import ClansTopService
from tops.coins_top import CoinsTopService
from tops.rubles_top import RublesTopService
from tops.all_time_top import AllTimeTopService
from tops.week_rubles_top import WeekRublesTopService

from modules.additional import format_number
from modules.registration import get_start_bonus
from modules.databases.users import update_user_menu, update_user_extra_data
from modules.vkontakte.bot import send_message

from vk_bot.template_messages import COMMAND_NOT_FOUND, ENTER_LINK_USER, BACK_SERVICES_MENU, \
    SOMETHING_WENT_WRONG
from vk_bot.modules.main_menu import get_link_game_chat
from vk_bot.keyboards.other import back_keyboard
from vk_bot.keyboards.main_menu import get_main_menu_keyboard, get_game_selection_keyboard
from vk_bot.keyboards.admin_menu import get_admin_menu_keyboard
from vk_bot.keyboards.settings_menu import get_settings_menu_keyboard
from vk_bot.keyboards.services_menu import get_services_menu_keyboard


async def handler_main_menu(
        *,
        user_id: int,
        user_data: UserSchema,
        message: str,
        payload: dict | None,
        fwd_messages: list | None,
        psql_cursor: DictCursor,
        redis_cursor: Redis
) -> None:
    """Обрабатывает сообщения в главном меню"""

    is_payload = payload is not None
    split_message = message.split(" ")
    len_split_message = len(split_message)

    if (
        Config.GETTING_START_BONUS and
        is_payload and payload.get("event") == "get_start_bonus"
    ):
        response = await get_start_bonus(user_id, user_data, psql_cursor, redis_cursor)
        keyboard = get_main_menu_keyboard(user_data)

    elif "админ" in message and user_data.status == UserStatus.ADMIN:
        response = "Админ панель"
        keyboard = get_admin_menu_keyboard()
        update_user_menu(user_id, UserMenu.ADMIN, psql_cursor)

    elif message == "играть":
        response = "Нажмите кнопку \"Играть\" ещё раз чтобы увидеть другие игры"
        keyboard = get_game_selection_keyboard()

    elif (
        is_payload and
        payload.get("event") == "get_link_game_chat" and
        payload.get("game") in ALL_GAMES_VALUES
    ):
        response = get_link_game_chat(payload.get("game"))
        keyboard = get_main_menu_keyboard(user_data)

    elif message == "как играть?":
        response = """
            Тут можно ознакомиться с правилами игры
        """
        keyboard = get_main_menu_keyboard(user_data)

    elif message == "перевести другу":
        if user_data.all_win >= PointsLimit.TRANSFER_COINS:
            response = ENTER_LINK_USER
            keyboard = back_keyboard

            update_user_menu(user_id, UserMenu.TRANSFER_COINS, psql_cursor)
            update_user_extra_data(user_id, ExtraTransferCoins(), psql_cursor)

        else:
            points_limit = format_number(PointsLimit.TRANSFER_COINS)
            response = f"""
                Переводить можно только по достижении {points_limit} очков в общем рейтинге игроков
                Твой счет: {format_number(user_data.all_win)}
            """
            keyboard = get_main_menu_keyboard(user_data)

    elif message == "настройки":
        response = "Настройки профиля"
        keyboard = get_settings_menu_keyboard(user_data)
        update_user_menu(user_id, UserMenu.SETTINGS, psql_cursor)

    elif message == "сервисы":
        response = BACK_SERVICES_MENU
        keyboard = get_services_menu_keyboard()
        update_user_menu(user_id, UserMenu.SERVICES, psql_cursor)

    elif message == "топ игроков":
        response, _ = AllTimeTopService().get_message(user_data, psql_cursor)
        keyboard = get_main_menu_keyboard(user_data)

    elif is_payload and payload.get("event") == "get_top_day_message":
        response, keyboard = DayTopService().get_message(
            user_data, psql_cursor, payload.get("offset", 0),
        )

    elif is_payload and payload.get("event") == "get_top_week_message":
        response, keyboard = WeekTopService().get_message(
            user_data, psql_cursor, payload.get("offset", 0)
        )

    elif is_payload and payload.get("event") == "get_top_clans_message":
        response, keyboard = ClansTopService().get_message(
            user_data, psql_cursor, payload.get("offset", 0)
        )

    elif is_payload and payload.get("event") == "go_clan_menu":
        response, keyboard = await ClanService.go_clan_menu(user_data, psql_cursor)

    elif is_payload and payload.get("event") == "get_top_coins_message":
        response, keyboard = CoinsTopService().get_message(
            user_data, psql_cursor, payload.get("offset", 0)
        )

    elif is_payload and payload.get("event") == "get_top_rubles_message":
        response, keyboard = RublesTopService().get_message(
            user_data, psql_cursor, payload.get("offset", 0)
        )

    elif is_payload and payload.get("event") == "get_top_week_rubles_message":
        response, keyboard = WeekRublesTopService().get_message(
            user_data, psql_cursor, payload.get("offset", 0)
        )

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
        keyboard = get_main_menu_keyboard(user_data)

    else:
        response = COMMAND_NOT_FOUND
        keyboard = get_main_menu_keyboard(user_data)

    await send_message(user_id, response, keyboard)
