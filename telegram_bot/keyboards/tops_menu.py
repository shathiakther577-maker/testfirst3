import json
from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

from settings import TopSettings
from tops.day_top import DayTop
from tops.week_top import WeekTop
from tops.clans_top import ClansTop
from tops.all_time_top import AllTimeTop
from modules.additional import reduce_number


def get_tops_menu_keyboard() -> ReplyKeyboardMarkup:
    """Возвращает клавиатуру меню топов"""

    buttons = [
        [KeyboardButton(text="Топ дня")],
        [KeyboardButton(text="Топ недели")],
        [KeyboardButton(text="Топ месяца")],
        [KeyboardButton(text="Топ кланов")],
        [KeyboardButton(text="Меню")]
    ]

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_tops_inline_keyboard() -> InlineKeyboardMarkup:
    """Возвращает inline клавиатуру с топами (для совместимости)"""

    buttons = []
    
    if TopSettings.SWITCH_DAY_TOP:
        label = (f"❄ Топ дня на {reduce_number(sum(DayTop.REWARDS.values()))} WC"
                if DayTop.REWARDS and TopSettings.SWITCH_DAY_TOP else
                "❄ Топ дня")
        buttons.append([InlineKeyboardButton(
            text=label,
            callback_data=json.dumps({"event": "get_top_day_message"})
        )])

    if TopSettings.SWITCH_WEEK_TOP:
        label = (f"🎄 Топ недели на {reduce_number(sum(WeekTop.REWARDS.values()))} WC"
                if WeekTop.REWARDS and TopSettings.SWITCH_WEEK_TOP else
                "🎄 Топ недели")
        buttons.append([InlineKeyboardButton(
            text=label,
            callback_data=json.dumps({"event": "get_top_week_message"})
        )])

    if TopSettings.SWITCH_CLANS_TOP:
        label = (f"🎁 Топ кланов на {reduce_number(sum(ClansTop.REWARDS.values()))} WC"
                if ClansTop.REWARDS and TopSettings.SWITCH_CLANS_TOP else
                "🎁 Топ кланов")
        buttons.append([InlineKeyboardButton(
            text=label,
            callback_data=json.dumps({"event": "get_top_clans_message"})
        )])

    buttons.append([InlineKeyboardButton(
        text="🏆 Топ всех времен",
        callback_data=json.dumps({"event": "get_top_all_time_message"})
    )])

    return InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None


