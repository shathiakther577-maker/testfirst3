import json
from datetime import datetime
from psycopg2.extras import DictCursor
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

from schemas.chats import ChatSchema
from services.chats import ChatsService

from telegram_bot.keyboards.pages import add_back_page, add_next_page


def get_my_chats_keyboard(
        owner_id: int,
        psql_cursor: DictCursor,
        offset: int = 0,
        limit: int = 6
) -> InlineKeyboardMarkup:
    """Возвращает клавиатуру с выбором чата в меню мои чаты"""

    MAX_ROW = 3

    my_chats = ChatsService.get_my_chats(owner_id, psql_cursor, offset, limit)
    count_my_chats = len(my_chats)

    buttons = []

    for index, chat in enumerate(my_chats):
        if index % MAX_ROW == 0:
            buttons.append([])

        chat_id = chat.chat_id
        chat_name = chat.name if chat.name else str(chat_id)

        buttons[-1].append(InlineKeyboardButton(
            text=str(chat_name),
            callback_data=json.dumps({
                "event": "select_chat",
                "chat_id": chat_id
            })
        ))

    # Добавляем навигацию по страницам
    total_chats = ChatsService.get_count_my_chats(owner_id, psql_cursor)
    if total_chats > limit:
        buttons = add_back_page(buttons, offset, limit, total_chats, "my_chats")
        buttons = add_next_page(buttons, offset, limit, total_chats, "my_chats")

    buttons.append([InlineKeyboardButton(
        text="Назад",
        callback_data=json.dumps({"event": "back"})
    )])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_management_chat_keyboard(chat_data: ChatSchema) -> InlineKeyboardMarkup:
    """Возвращает клавиатуру для управление чатом в меню мои чаты"""

    buttons = []
    current_datetime = datetime.now()

    buttons.append([InlineKeyboardButton(
        text="Инфо",
        callback_data=json.dumps({"event": "get_chat_info"})
    )])

    if chat_data.is_activated is True and chat_data.life_datetime > current_datetime:
        buttons.append([InlineKeyboardButton(
            text="Продлить подписку",
            callback_data=json.dumps({"event": "prolong_subscription"})
        )])
    elif chat_data.is_activated is False and chat_data.life_datetime <= current_datetime:
        buttons.append([InlineKeyboardButton(
            text="Повторить подписку",
            callback_data=json.dumps({"event": "repeat_subscription"})
        )])
    else:
        buttons.append([InlineKeyboardButton(
            text="Подписка чата недоступна",
            callback_data=json.dumps({"event": "subscription_not_available"})
        )])

    buttons.append([InlineKeyboardButton(
        text="Назад",
        callback_data=json.dumps({"event": "back"})
    )])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_prolong_period_keyboard() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру для выбора периода продления подписки"""

    buttons = [
        [
            InlineKeyboardButton(
                text="1Д",
                callback_data=json.dumps({"event": "select_period", "days": 1})
            ),
            InlineKeyboardButton(
                text="7Д",
                callback_data=json.dumps({"event": "select_period", "days": 7})
            ),
            InlineKeyboardButton(
                text="30Д",
                callback_data=json.dumps({"event": "select_period", "days": 30})
            )
        ],
        [
            InlineKeyboardButton(
                text="60Д",
                callback_data=json.dumps({"event": "select_period", "days": 60})
            ),
            InlineKeyboardButton(
                text="90Д",
                callback_data=json.dumps({"event": "select_period", "days": 90})
            )
        ],
        [InlineKeyboardButton(
            text="Назад",
            callback_data=json.dumps({"event": "back"})
        )]
    ]

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_prolong_confirm_keyboard(chat_id: int, days: int, cost: int) -> InlineKeyboardMarkup:
    """Возвращает клавиатуру для подтверждения продления подписки"""

    buttons = [
        [InlineKeyboardButton(
            text="Подтвердить",
            callback_data=json.dumps({
                "event": "prolong_confirm",
                "chat_id": chat_id,
                "days": days,
                "cost": cost
            })
        )],
        [InlineKeyboardButton(
            text="Назад",
            callback_data=json.dumps({"event": "back"})
        )]
    ]

    return InlineKeyboardMarkup(inline_keyboard=buttons)
