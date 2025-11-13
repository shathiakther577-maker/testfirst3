from psycopg2.extras import DictCursor

from schemas.users import UserMenu
from services.statistics import StatisticsService

from modules.databases.users import update_user_menu
from modules.vkontakte.bot import send_message

from vk_bot.template_messages import BACK_SERVICES_MENU, COMMAND_NOT_FOUND
from vk_bot.keyboards.services_menu import get_services_menu_keyboard
from vk_bot.keyboards.statistics_menu import get_statistics_menu_keyboard


async def handler_statistics_menu(
        *,
        user_id: int,
        message: str,
        payload: dict | None,
        psql_cursor: DictCursor
) -> None:
    """Обрабатывает сообщения в меню статистики"""

    keyboard = get_statistics_menu_keyboard()
    is_payload = payload is not None

    if message == "назад":
        response = BACK_SERVICES_MENU
        keyboard = get_services_menu_keyboard()
        update_user_menu(user_id, UserMenu.SERVICES, psql_cursor)

    elif is_payload and payload.get("event") == "get_bet_balance_message":
        response = StatisticsService.get_bet_balance_message(psql_cursor)

    elif is_payload and payload.get("event") == "get_transfers_statistics_message":
        response = StatisticsService.get_transfers_stats_message(psql_cursor)

    else:
        response = COMMAND_NOT_FOUND

    await send_message(user_id, response, keyboard)
