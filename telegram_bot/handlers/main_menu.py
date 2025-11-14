from redis.client import Redis
from psycopg2.extras import DictCursor

from settings import Config, PointsLimit

from schemas.users import UserSchema, UserStatus, UserMenu
from schemas.games import ALL_GAMES_VALUES
from schemas.redis import RedisKeys
from schemas.transfer_coins import ExtraTransferCoins

from services.clans import ClanService
from services.transfer_coins import TransferCoinsService

from tops.day_top import DayTopService
from tops.week_top import WeekTopService
from tops.month_top import MonthTopService
from tops.clans_top import ClansTopService
from tops.clans_top_telegram import get_clans_top_message_telegram
from tops.coins_top import CoinsTopService
from tops.rubles_top import RublesTopService
from tops.all_time_top import AllTimeTopService
from tops.week_rubles_top import WeekRublesTopService

from modules.additional import format_number
from modules.registration import get_start_bonus
from modules.databases.users import update_user_menu, update_user_extra_data
from modules.telegram.bot import send_message

from telegram_bot.template_messages import COMMAND_NOT_FOUND, ENTER_LINK_USER, BACK_SERVICES_MENU, \
    SOMETHING_WENT_WRONG
from telegram_bot.modules.main_menu import get_link_game_chat
from telegram_bot.keyboards.other import back_keyboard
from telegram_bot.keyboards.main_menu import get_main_menu_keyboard, get_game_selection_keyboard
from telegram_bot.keyboards.admin_menu import get_admin_menu_keyboard
from telegram_bot.keyboards.settings_menu import get_settings_menu_keyboard
from telegram_bot.keyboards.services_menu import get_services_menu_keyboard


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

    # Обработка команды /start и "меню"
    if message == "/start" or message == "start" or message == "меню" or message == "Меню":
        response = "Главное меню"
        reply_keyboard, inline_keyboard = get_main_menu_keyboard(user_data)
        update_user_menu(user_id, UserMenu.MAIN, psql_cursor)
        await send_message(user_id, response, reply_keyboard)
        if inline_keyboard:
            await send_message(user_id, "🏆 Топы:", inline_keyboard)
        return

    if (
        Config.GETTING_START_BONUS and
        is_payload and payload.get("event") == "get_start_bonus"
    ):
        response = await get_start_bonus(user_id, user_data, psql_cursor, redis_cursor)
        reply_keyboard, inline_keyboard = get_main_menu_keyboard(user_data)

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
        # Преобразуем строку в enum Games
        from schemas.games import Games
        game_str = payload.get("game")
        try:
            game_enum = Games(game_str)
            response = get_link_game_chat(game_enum)
        except (ValueError, TypeError):
            response = "Игра не найдена"
        reply_keyboard, inline_keyboard = get_main_menu_keyboard(user_data)
        keyboard = reply_keyboard

    elif message == "как играть?":
        response = """
            Тут можно ознакомиться с правилами игры
        """
        reply_keyboard, inline_keyboard = get_main_menu_keyboard(user_data)
        keyboard = reply_keyboard

    elif message == "перевести другу":
        # Переводы доступны всем без ограничений
        response = ENTER_LINK_USER
        keyboard = back_keyboard

        update_user_menu(user_id, UserMenu.TRANSFER_COINS, psql_cursor)
        update_user_extra_data(user_id, ExtraTransferCoins(), psql_cursor)

    elif message == "настройки":
        response = "Настройки профиля"
        keyboard = get_settings_menu_keyboard(user_data)
        update_user_menu(user_id, UserMenu.SETTINGS, psql_cursor)

    elif message == "сервисы":
        response = BACK_SERVICES_MENU
        keyboard = get_services_menu_keyboard()
        update_user_menu(user_id, UserMenu.SERVICES, psql_cursor)

    elif message == "профиль" or message == "Профиль":
        from modules.telegram.users import get_registration_date
        from modules.databases.users import get_user_data
        
        # Перезагружаем данные пользователя из БД для актуальной статистики
        current_user_data = get_user_data(user_id, psql_cursor)
        if current_user_data is None:
            current_user_data = user_data
        
        registration_date = await get_registration_date(user_id)
        response = f"""
👤 Профиль: {current_user_data.telegram_name}
📅 Дата регистрации: {registration_date}
💰 Баланс: {format_number(current_user_data.coins)} WC

🌐 Ставок: {format_number(current_user_data.all_rates)}
✅ Выиграно: {format_number(current_user_data.all_win)} WC
❌ Проиграно: {format_number(current_user_data.all_lost)} WC
💳 Прибыль: {format_number(current_user_data.all_win - current_user_data.all_lost)} WC
        """
        reply_keyboard, inline_keyboard = get_main_menu_keyboard(user_data)
        keyboard = reply_keyboard

    elif message == "топы" or message == "Топы":
        from telegram_bot.keyboards.tops_menu import get_tops_menu_keyboard
        response = "🏆 Выберите топ:"
        keyboard = get_tops_menu_keyboard()

    elif message == "топ дня" or message == "Топ дня":
        response, keyboard = DayTopService().get_message(
            user_data, psql_cursor, offset=0
        )

    elif message == "топ недели" or message == "Топ недели":
        response, keyboard = WeekTopService().get_message(
            user_data, psql_cursor, offset=0
        )

    elif message == "топ месяца" or message == "Топ месяца":
        response, keyboard = MonthTopService().get_message(user_data, psql_cursor, offset=0)

    elif message == "топ кланов" or message == "Топ кланов":
        response, keyboard = get_clans_top_message_telegram(
            user_data, psql_cursor, offset=0
        )

    elif message == "топ игроков":
        response, _ = AllTimeTopService().get_message(user_data, psql_cursor)
        reply_keyboard, inline_keyboard = get_main_menu_keyboard(user_data)
        keyboard = reply_keyboard

    elif is_payload and payload.get("event") == "get_top_day_message":
        response, keyboard = DayTopService().get_message(
            user_data, psql_cursor, payload.get("offset", 0),
        )

    elif is_payload and payload.get("event") == "get_top_week_message":
        from tops.week_top_telegram import get_week_top_message_telegram
        response, keyboard = get_week_top_message_telegram(
            user_data, psql_cursor, payload.get("offset", 0)
        )

    elif is_payload and payload.get("event") == "get_top_clans_message":
        response, keyboard = get_clans_top_message_telegram(
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
        reply_keyboard, inline_keyboard = get_main_menu_keyboard(user_data)
        keyboard = reply_keyboard

    else:
        response = COMMAND_NOT_FOUND
        reply_keyboard, inline_keyboard = get_main_menu_keyboard(user_data)
        keyboard = reply_keyboard

    await send_message(user_id, response, keyboard)

