from datetime import datetime
from psycopg2.extras import DictCursor
from vk_api.keyboard import VkKeyboard, VkKeyboardColor

from schemas.chats import ChatSchema
from services.chats import ChatsService

from vk_bot.keyboards.pages import add_back_page, add_next_page


def get_my_chats_keyboard(
        owner_id: int,
        psql_cursor: DictCursor,
        offset: int = 0,
        limit: int = 6
) -> str:
    """Возвращает клавиатуру с выбором чата в меню мои чаты"""

    MAX_ROW = 3  # Максимальное количество элементов строке

    my_chats = ChatsService.get_my_chats(owner_id, psql_cursor, offset, limit)
    count_my_chats = len(my_chats)

    keyboard = VkKeyboard()

    for index, chat in enumerate(my_chats):

        if 0 < index < count_my_chats and index % MAX_ROW == 0:
            keyboard.add_line()

        chat_id = chat.chat_id
        chat_name = chat.name if chat.name else int(chat.chat_id - 2E9)

        keyboard.add_button(
            label=str(chat_name),
            color=VkKeyboardColor.POSITIVE if chat.is_activated else VkKeyboardColor.SECONDARY,
            payload={
                "event": "select_chat",
                "chat_id": chat_id
            }
        )

    back_page = offset != 0
    next_page = ChatsService.get_count_my_chats(owner_id, psql_cursor) - offset - limit > 0

    if count_my_chats > 0 and (back_page or next_page):
        keyboard.add_line()

    if back_page:
        add_back_page(
            keyboard=keyboard,
            full_test=next_page is False,
            payload={
                "event": "get_my_chats_message",
                "offset": offset - limit
            }
        )

    if next_page:
        add_next_page(
            keyboard=keyboard,
            full_test=offset == 0,
            payload={
                "event": "get_my_chats_message",
                "offset": offset + limit
            }
        )

    if count_my_chats:
        keyboard.add_line()

    keyboard.add_button(
        label="Назад",
        color=VkKeyboardColor.NEGATIVE
    )

    return keyboard.get_keyboard()


def get_management_chat_keyboard(chat_data: ChatSchema) -> str:
    """Возвращает клавиатуру для управление чатом в меню мои чаты """

    keyboard = VkKeyboard()
    current_datetime = datetime.now()

    keyboard.add_button(
        label="Инфо",
        color=VkKeyboardColor.POSITIVE,
        payload={"event": "get_chat_info"}
    )
    keyboard.add_line()

    if chat_data.is_activated is True and chat_data.life_datetime > current_datetime:
        keyboard.add_button(
            label="Продлить подписку",
            color=VkKeyboardColor.POSITIVE,
            payload={"event": "prolong_subscription"}
        )
    elif chat_data.is_activated is False and chat_data.life_datetime <= current_datetime:
        keyboard.add_button(
            label="Повторить подписку",
            color=VkKeyboardColor.POSITIVE,
            payload={"event": "repeat_subscription"}
        )
    else:
        keyboard.add_button(
            label="Подписка чата недоступна",
            color=VkKeyboardColor.SECONDARY,
            payload={"event": "subscription_not_available"}
        )
    keyboard.add_line()

    keyboard.add_button(label="Назад", color=VkKeyboardColor.NEGATIVE)

    return keyboard.get_keyboard()


def get_prolong_period_keyboard() -> str:
    """Возвращает клавиатуру для выбора периода продления подписки"""

    keyboard = VkKeyboard()

    keyboard.add_button(
        label="1Д",
        color=VkKeyboardColor.POSITIVE,
        payload={"event": "select_period", "days": 1}
    )
    keyboard.add_button(
        label="7Д",
        color=VkKeyboardColor.POSITIVE,
        payload={"event": "select_period", "days": 7}
    )
    keyboard.add_button(
        label="15Д",
        color=VkKeyboardColor.POSITIVE,
        payload={"event": "select_period", "days": 15}
    )
    keyboard.add_line()

    keyboard.add_button(
        label="30Д",
        color=VkKeyboardColor.POSITIVE,
        payload={"event": "select_period", "days": 30}
    )
    keyboard.add_button(
        label="60Д",
        color=VkKeyboardColor.POSITIVE,
        payload={"event": "select_period", "days": 60}
    )
    keyboard.add_button(
        label="150Д",
        color=VkKeyboardColor.POSITIVE,
        payload={"event": "select_period", "days": 150}
    )
    keyboard.add_line()

    keyboard.add_button(
        label="Назад",
        color=VkKeyboardColor.NEGATIVE
    )

    return keyboard.get_keyboard()


def get_prolong_confirm_keyboard() -> str:
    """Возвращает клавиатуру для подтверждения продления подписки чата"""

    keyboard = VkKeyboard(one_time=False, inline=False)

    keyboard.add_button(
        label="Да",
        color=VkKeyboardColor.POSITIVE,
        payload={
            "event": "prolong_confirm",
            "confirm": True
        }
    )
    keyboard.add_button(
        label="Нет",
        color=VkKeyboardColor.NEGATIVE,
        payload={
            "event": "prolong_confirm",
            "confirm": False
        }
    )

    return keyboard.get_keyboard()
