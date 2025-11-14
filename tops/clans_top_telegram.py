"""Telegram-специфичная версия топа кланов"""
from typing import Optional
from psycopg2.extras import DictCursor
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
import json

from schemas.users import UserSchema
from modules.additional import format_number, reduce_number
from tops.clans_top import ClansTopService, ClansTop
from settings import TopSettings


def get_clans_top_message_telegram(
        user_data: UserSchema,
        psql_cursor: DictCursor,
        offset: int = 0,
        limit: int = ClansTop.MAPPING
) -> tuple[str, Optional[InlineKeyboardMarkup]]:
    """Возвращает сообщение и клавиатуру топа кланов для Telegram"""

    if TopSettings.SWITCH_CLANS_TOP is False:
        return "Топ временно не работает", None

    reward = ClansTop.REWARDS
    winners = ClansTopService.get_winners(psql_cursor, offset, limit)
    participants = ClansTopService.get_number_participants(psql_cursor)

    response = "🎁 Топ кланов\n"
    keyboard_buttons = []

    for position, winner in enumerate(winners, offset + 1):
        winner_name = f"[{winner['tag']}] {UserSchema.format_telegram_name(winner['owner_id'], winner['name'])}"
        winner_points = winner["points"]

        response += f"\n{position}) {winner_name} - {format_number(winner_points)} коинов"
        if ClansTopService.can_get_reward(winner_points, reward, position):
            response += f" (приз {reduce_number(reward[position])} WC)"

    if user_data.clan_id is not None:
        clan_position = ClansTopService.get_position(user_data.clan_id, psql_cursor)
        response += f"\n\nКлан в котором вы состоите находится на {clan_position} месте"

    back_page = offset != 0
    next_page = participants - offset - limit > 0 and 5 * limit > offset + limit

    if back_page or next_page:
        nav_row = []
        if back_page:
            nav_row.append(InlineKeyboardButton(
                text="◀️ Назад" if next_page else "◀️",
                callback_data=json.dumps({
                    "event": "get_top_clans_message",
                    "offset": offset - limit
                })
            ))
        if next_page:
            nav_row.append(InlineKeyboardButton(
                text="Вперед ▶️" if back_page else "▶️",
                callback_data=json.dumps({
                    "event": "get_top_clans_message",
                    "offset": offset + limit
                })
            ))
        if nav_row:
            keyboard_buttons.append(nav_row)

    # Кнопка "Кланы"
    keyboard_buttons.append([
        InlineKeyboardButton(
            text="Кланы",
            callback_data=json.dumps({"event": "go_clan_menu"})
        )
    ])

    keyboard = InlineKeyboardMarkup(keyboard_buttons) if keyboard_buttons else None

    return response, keyboard

