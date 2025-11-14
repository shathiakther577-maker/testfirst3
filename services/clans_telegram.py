"""Telegram-специфичные методы для работы с кланами"""
from typing import Optional
from psycopg2.extras import DictCursor
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
import json

from schemas.users import UserSchema
from modules.additional import format_number
from services.clans import ClanService


def get_clans_message_telegram(
        psql_cursor: DictCursor,
        offset: int = 0
) -> tuple[str, Optional[InlineKeyboardMarkup]]:
    """Возвращает сообщение и клавиатуру о кланах для Telegram"""

    COUNT_ROW = 4  # Количество кнопок в строке
    COUNT_CLANS = 8  # Количество кланов которое нужны найти

    clans = ClanService.get_clans(psql_cursor, offset, COUNT_CLANS)
    total_count_clans = ClanService.get_total_clans_counts(psql_cursor)

    response = "Топ кланов:\n"
    keyboard_buttons = []

    start_enumerate = offset + 1
    stop_enumerate = offset + min(COUNT_CLANS, len(clans))

    row = []
    for number, clan in enumerate(clans, start_enumerate):
        clan_name = UserSchema.format_telegram_name(clan.owner_id, clan.name)
        clan_points = format_number(clan.points)

        response += f"\n{number}) [{clan.tag}] {clan_name} - {clan_points} очков"
        
        row.append(InlineKeyboardButton(
            text=str(number),
            callback_data=json.dumps({
                "event": "get_clan_info",
                "clan_id": clan.clan_id
            })
        ))
        
        if len(row) >= COUNT_ROW or number == stop_enumerate:
            keyboard_buttons.append(row)
            row = []

    back_page = offset != 0
    next_page = total_count_clans - offset - COUNT_CLANS > 0

    if back_page or next_page:
        nav_row = []
        if back_page:
            nav_row.append(InlineKeyboardButton(
                text="◀️ Назад" if next_page else "◀️",
                callback_data=json.dumps({
                    "event": "get_clans_message",
                    "offset": offset - COUNT_CLANS
                })
            ))
        if next_page:
            nav_row.append(InlineKeyboardButton(
                text="Вперед ▶️" if back_page else "▶️",
                callback_data=json.dumps({
                    "event": "get_clans_message",
                    "offset": offset + COUNT_CLANS
                })
            ))
        if nav_row:
            keyboard_buttons.append(nav_row)

    keyboard = InlineKeyboardMarkup(keyboard_buttons) if keyboard_buttons else None

    return response, keyboard


def get_clan_members_message_telegram(
        psql_cursor: DictCursor,
        *,
        clan_id: int,
        offset: int = 0
) -> tuple[str, Optional[InlineKeyboardMarkup]]:
    """Возвращает сообщение и клавиатуру об участниках клана для Telegram"""

    COUNT_MEMBERS = 5  # Количество участников которые нужно запросить

    count_members = ClanService.get_clan_data(clan_id, psql_cursor).count_members
    members = ClanService.get_clan_members(clan_id, psql_cursor, offset, COUNT_MEMBERS)

    response = "Участники клана:\n"
    keyboard_buttons = []

    for number, member in enumerate(members, offset+1):
        member_full_name = UserSchema.format_telegram_name(member.user_id, member.full_name)
        response += f"\n{number}. {member_full_name} - выиграл {format_number(member.points)} коинов"

    back_page = offset != 0
    next_page = count_members - offset - COUNT_MEMBERS > 0

    if back_page or next_page:
        nav_row = []
        if back_page:
            nav_row.append(InlineKeyboardButton(
                text="◀️ Назад" if next_page else "◀️",
                callback_data=json.dumps({
                    "event": "get_clan_members_message",
                    "offset": offset - COUNT_MEMBERS
                })
            ))
        if next_page:
            nav_row.append(InlineKeyboardButton(
                text="Вперед ▶️" if back_page else "▶️",
                callback_data=json.dumps({
                    "event": "get_clan_members_message",
                    "offset": offset + COUNT_MEMBERS
                })
            ))
        if nav_row:
            keyboard_buttons.append(nav_row)

    keyboard = InlineKeyboardMarkup(keyboard_buttons) if keyboard_buttons else None

    return response, keyboard

