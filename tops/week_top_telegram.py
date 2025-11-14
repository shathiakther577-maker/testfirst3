"""Telegram-специфичная версия топа недели"""
from typing import Optional
from psycopg2.extras import DictCursor
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
import json

from schemas.users import UserSchema
from modules.additional import format_number, reduce_number
from tops.week_top import WeekTopService, WeekTop
from settings import TopSettings


def get_week_top_message_telegram(
        user_data: UserSchema,
        psql_cursor: DictCursor,
        offset: int = 0,
        limit: int = WeekTop.MAPPING
) -> tuple[str, Optional[InlineKeyboardMarkup]]:
    """Возвращает сообщение и клавиатуру о топе недели для Telegram"""

    if TopSettings.SWITCH_WEEK_TOP is False:
        return "Топ временно не работает", None

    reward = WeekTop.REWARDS
    winners = WeekTopService.get_winners(psql_cursor, offset, limit)
    participants = WeekTopService.get_number_participants(psql_cursor)

    response = "🔥 Топ игроков еженедельного рейтинга\n"
    keyboard_buttons = []

    for position, winner in enumerate(winners, offset + 1):
        winner_name = UserSchema.format_telegram_name(winner["user_id"], winner["full_name"])
        winner_points = winner["points"]

        response += f"\n{position}) {winner_name} выиграл {format_number(winner_points)} коинов"
        if WeekTopService.can_get_reward(winner_points, reward, position):
            response += f" (приз {reduce_number(reward[position])} WC)"

    user_position = WeekTopService.get_position(user_data, psql_cursor)
    if user_position > 0:
        response += f"\n\nТы находишься на {user_position} месте, выиграв {format_number(user_data.week_top_points)} коинов"
        if WeekTopService.can_get_reward(user_data.week_top_points, reward, user_position):
            response += f"\n💰 Возможный выигрыш: {reduce_number(reward[user_position])} WC"

    nav_row = []
    back_page = offset != 0
    next_page = participants - offset - limit > 0 and 5 * limit > offset + limit

    if back_page:
        nav_row.append(InlineKeyboardButton(
            text="◀️ Назад" if next_page else "◀️",
            callback_data=json.dumps({"event": "get_top_week_message", "offset": offset - limit})
        ))
    if next_page:
        nav_row.append(InlineKeyboardButton(
            text="Вперед ▶️" if back_page else "▶️",
            callback_data=json.dumps({"event": "get_top_week_message", "offset": offset + limit})
        ))
    if nav_row:
        keyboard_buttons.append(nav_row)

    keyboard = InlineKeyboardMarkup(keyboard_buttons) if keyboard_buttons else None

    return response, keyboard

