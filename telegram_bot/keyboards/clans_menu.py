import json
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

from schemas.clans import ClanSchema, ClanJoinType, ClanRole, OwnerClanMenu
from schemas.users import UserSchema, UserStatus
from settings import ClanSettings


def get_create_clan_keyboard() -> ReplyKeyboardMarkup:
    """Возвращает клавиатура для создания клана"""

    buttons = [
        [KeyboardButton(text="Создать клан")],
        [KeyboardButton(text="Топ кланов")],
        [KeyboardButton(text="Меню")]
    ]

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_clan_menu_keyboard(user_data: UserSchema) -> ReplyKeyboardMarkup:
    """Возвращает клавиатуру для меню клана в зависимости от роли пользователя"""
    
    if user_data.clan_role == ClanRole.OWNER:
        return get_clan_owner_keyboard()
    elif user_data.clan_role == ClanRole.MEMBER:
        return get_clan_member_keyboard()
    else:
        return get_create_clan_keyboard()


def get_clan_member_keyboard() -> ReplyKeyboardMarkup:
    """Возвращает клавиатуру для участников клана"""

    buttons = [
        [
            KeyboardButton(text="Кланы"),
            KeyboardButton(text="Участники")
        ],
        [
            KeyboardButton(text="Беседа клана"),
            KeyboardButton(text="Покинуть клан")
        ],
        [KeyboardButton(text="Меню")]
    ]

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_clan_owner_keyboard() -> ReplyKeyboardMarkup:
    """Возвращает клавиатуру для владельца клана"""

    buttons = [
        [
            KeyboardButton(text="Кланы"),
            KeyboardButton(text="Участники")
        ],
        [
            KeyboardButton(text="Беседа клана"),
            KeyboardButton(text="Удалить клан")
        ],
        [KeyboardButton(text="Настройки")],
        [KeyboardButton(text="Меню")]
    ]

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_clan_join_keyboard(user_data: UserSchema, clan_data: ClanSchema) -> InlineKeyboardMarkup | None:
    """Возвращает клавиатуру для вступления в клан"""

    if clan_data.join_type == ClanJoinType.CLOSED:
        return None

    buttons = []
    
    if clan_data.join_type == ClanJoinType.OPEN:
        buttons.append([InlineKeyboardButton(
            text="Вступить в клан",
            callback_data=json.dumps({
                "event": "join_clan",
                "clan_id": clan_data.clan_id
            })
        )])
    elif clan_data.join_type == ClanJoinType.REQUEST:
        buttons.append([InlineKeyboardButton(
            text="Подать заявку",
            callback_data=json.dumps({
                "event": "request_join_clan",
                "clan_id": clan_data.clan_id
            })
        )])

    return InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None


def get_clan_settings_keyboard(clan_data: ClanSchema) -> ReplyKeyboardMarkup:
    """Возвращает клавиатуру для настройки клана"""

    buttons = [
        [
            KeyboardButton(text="Название"),
            KeyboardButton(text="Тег")
        ],
        [
            KeyboardButton(text="Тип входа"),
            KeyboardButton(text="Порог входа")
        ],
        [
            KeyboardButton(text="Уведомления о входе"),
            KeyboardButton(text="Ссылка на беседу")
        ],
        [KeyboardButton(text="Назад")]
    ]

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_keyboard_change_clan_join_type():
    """Возвращает клавиатуру для смены типа входа в клан"""

    from schemas.clans import clan_join_type_translation

    buttons = [
        [KeyboardButton(text=clan_join_type_translation[ClanJoinType.OPEN])],
        [KeyboardButton(text=clan_join_type_translation[ClanJoinType.CLOSED])],
        [KeyboardButton(text=clan_join_type_translation[ClanJoinType.INVITE])],
        [KeyboardButton(text=clan_join_type_translation[ClanJoinType.REQUEST])],
        [KeyboardButton(text="Назад")]
    ]

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_keyboard_managing_members() -> ReplyKeyboardMarkup:
    """Возвращает клавиатуру для управления участниками"""

    buttons = [
        [KeyboardButton(text="Пригласить")],
        [KeyboardButton(text="Исключить")],
        [KeyboardButton(text="Назад")]
    ]

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_keyboard_delete_clan() -> ReplyKeyboardMarkup:
    """Возвращает клавиатуру для удаления клана"""

    buttons = [
        [KeyboardButton(text="Подтвердить удаление")],
        [KeyboardButton(text="Отмена")]
    ]

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_keyboard_answer_user_join_clan(user_id: int, clan_id: int) -> InlineKeyboardMarkup:
    """Возвращает клавиатуру для ответа на приглашение в клан"""
    
    from schemas.clans import ClanTypeApplication

    buttons = [
        [
            InlineKeyboardButton(
                text="Принять",
                callback_data=json.dumps({
                    "event": ClanTypeApplication.CLAN_TO_USER.value,
                    "confirm": True,
                    "user_id": user_id,
                    "clan_id": clan_id
                })
            ),
            InlineKeyboardButton(
                text="Отклонить",
                callback_data=json.dumps({
                    "event": ClanTypeApplication.CLAN_TO_USER.value,
                    "confirm": False,
                    "user_id": user_id,
                    "clan_id": clan_id
                })
            )
        ]
    ]

    return InlineKeyboardMarkup(inline_keyboard=buttons)
