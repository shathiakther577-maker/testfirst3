import json
from telegram import InlineKeyboardButton


def add_back_page(
        buttons: list,
        offset: int,
        limit: int,
        count_items: int,
        event_prefix: str
) -> list:
    """Добавляет кнопку назад для пагинации"""

    if offset > 0:
        new_offset = max(0, offset - limit)
        if not buttons or len(buttons[-1]) > 0:
            buttons.append([])
        buttons[-1].append(InlineKeyboardButton(
            text="◀ Назад",
            callback_data=json.dumps({
                "event": f"{event_prefix}_page",
                "offset": new_offset
            })
        ))

    return buttons


def add_next_page(
        buttons: list,
        offset: int,
        limit: int,
        count_items: int,
        event_prefix: str
) -> list:
    """Добавляет кнопку вперед для пагинации"""

    if count_items >= limit:
        new_offset = offset + limit
        if not buttons or len(buttons[-1]) > 0:
            buttons.append([])
        buttons[-1].append(InlineKeyboardButton(
            text="Вперед ▶",
            callback_data=json.dumps({
                "event": f"{event_prefix}_page",
                "offset": new_offset
            })
        ))

    return buttons

