from vk_api.keyboard import VkKeyboard, VkKeyboardColor

from settings import ClanSettings

from schemas.users import UserSchema
from schemas.clans import ClanSchema, ClanRole, ClanJoinType, \
    OwnerClanMenu, ClanTypeApplication, clan_join_type_translation


def get_create_clan_keyboard() -> str:
    """Возвращает клавиатура для создания клана"""

    keyboard = VkKeyboard(one_time=False, inline=False)

    keyboard.add_button(
        label="Создать клан",
        color=VkKeyboardColor.POSITIVE,
        payload={"event": "create_clan"}
    )
    keyboard.add_line()

    keyboard.add_button(label="Меню", color=VkKeyboardColor.NEGATIVE)

    return keyboard.get_keyboard()


def get_clan_member_keyboard() -> str:
    """Возвращает клавиатуру для участников клана"""

    keyboard = VkKeyboard(one_time=False, inline=False)

    keyboard.add_button(label="Кланы", color=VkKeyboardColor.POSITIVE)
    keyboard.add_button(label="Участники", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()

    keyboard.add_button(label="Беседа клана", color=VkKeyboardColor.SECONDARY)
    keyboard.add_button(label="Покинуть клан", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()

    keyboard.add_button(label="Меню", color=VkKeyboardColor.NEGATIVE)

    return keyboard.get_keyboard()


def get_clan_owner_keyboard() -> str:
    """Возвращает клавиатуру для владельца клана"""

    keyboard = VkKeyboard(one_time=False, inline=False)

    keyboard.add_button(label="Кланы", color=VkKeyboardColor.POSITIVE)
    keyboard.add_button(label="Участники", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()

    keyboard.add_button(label="Беседа клана", color=VkKeyboardColor.SECONDARY)
    keyboard.add_button(label="Удалить клан", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()

    keyboard.add_button(label="Настройки", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()

    keyboard.add_button(label="Меню", color=VkKeyboardColor.NEGATIVE)

    return keyboard.get_keyboard()


def get_clan_menu_keyboard(user_data: UserSchema) -> str:
    """Возвращает клавиатуру кланов"""

    if user_data.clan_role == ClanRole.NOT:
        keyboard = get_create_clan_keyboard()

    if user_data.clan_role == ClanRole.MEMBER:
        keyboard = get_clan_member_keyboard()

    if user_data.clan_role == ClanRole.OWNER:
        keyboard = get_clan_owner_keyboard()

    return keyboard


def get_clan_settings_keyboard(clan_data: ClanSchema) -> str:
    """Возвращает клавиатуру для настройки клана"""

    keyboard = VkKeyboard(one_time=False, inline=False)

    keyboard.add_button(label="Название", color=VkKeyboardColor.POSITIVE)
    keyboard.add_button(label="Тег", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()

    keyboard.add_button(label="Тип входа", color=VkKeyboardColor.POSITIVE)
    keyboard.add_button(
        label="Порог входа",
        color=VkKeyboardColor.POSITIVE if clan_data.join_barrier > 0 else VkKeyboardColor.SECONDARY
    )
    keyboard.add_line()

    keyboard.add_button(
        label="Уведомления о входе",
        color=VkKeyboardColor.POSITIVE if clan_data.owner_notifications else VkKeyboardColor.SECONDARY
    )
    keyboard.add_button(
        label="Ссылка на беседу",
        color=VkKeyboardColor.POSITIVE if clan_data.chat_link is not None else VkKeyboardColor.SECONDARY
    )
    keyboard.add_line()

    keyboard.add_button(label="Назад", color=VkKeyboardColor.NEGATIVE)

    return keyboard.get_keyboard()


def get_keyboard_change_clan_join_type():
    """Возвращает клавиатуру для смены типа входа в клан"""

    keyboard = VkKeyboard(one_time=False, inline=False)
    translations = clan_join_type_translation
    payload_header = {
        "event": OwnerClanMenu.CHANGE_JOIN_TYPE.value
    }

    keyboard.add_button(
        label=translations[ClanJoinType.OPEN],
        color=VkKeyboardColor.POSITIVE,
        payload={
            **payload_header,
            "join_type": ClanJoinType.OPEN.value
        }
    )
    keyboard.add_button(
        label=translations[ClanJoinType.CLOSED],
        color=VkKeyboardColor.POSITIVE,
        payload={
            **payload_header,
            "join_type": ClanJoinType.CLOSED.value
        }
    )
    keyboard.add_line()

    keyboard.add_button(
        label=translations[ClanJoinType.INVITE],
        color=VkKeyboardColor.POSITIVE,
        payload={
            **payload_header,
            "join_type": ClanJoinType.INVITE.value
        }
    )
    keyboard.add_line()

    keyboard.add_button(
        label="Назад",
        color=VkKeyboardColor.NEGATIVE
    )

    return keyboard.get_keyboard()


def get_keyboard_managing_members() -> str:
    """Возвращает клавиатуру для управления участниками клана"""

    keyboard = VkKeyboard(one_time=False, inline=False)

    keyboard.add_button(label="Пригласить игрока", color=VkKeyboardColor.POSITIVE)
    keyboard.add_button(label="Исключить игрока", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()

    keyboard.add_button(label="Ссылка-приглашение", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()

    keyboard.add_button(label="Назад", color=VkKeyboardColor.NEGATIVE)

    return keyboard.get_keyboard()


def get_keyboard_delete_clan() -> str:
    """Возвращает клавиатуру для удаления клана """

    keyboard = VkKeyboard(one_time=False, inline=False)
    payload_header = {"event": "delete_clan"}

    keyboard.add_button(
        label="Да",
        color=VkKeyboardColor.POSITIVE,
        payload={
            **payload_header,
            "confirm": True
        }
    )
    keyboard.add_button(
        label="Нет",
        color=VkKeyboardColor.NEGATIVE,
        payload={
            **payload_header,
            "confirm": False
        }
    )

    return keyboard.get_keyboard()


def get_join_clan_keyboard(clan_id: int) -> str:
    """Возвращает клавиатуру для входа в клан"""

    keyboard = VkKeyboard(one_time=False, inline=True)

    keyboard.add_button(
        label="Вступить в клан",
        color=VkKeyboardColor.POSITIVE,
        payload={
            "event": ClanTypeApplication.JOIN_CLAN.value,
            "clan_id": clan_id
        }
    )

    return keyboard.get_keyboard()


def get_invite_clan_keyboard(clan_id: int) -> str:
    """Возвращает клавиатуру для отправки заявки на вступления в клан"""

    keyboard = VkKeyboard(one_time=False, inline=True)

    keyboard.add_button(
        label="Подать заявку",
        color=VkKeyboardColor.POSITIVE,
        payload={
            "event": ClanTypeApplication.USER_TO_CLAN.value,
            "clan_id": clan_id
        }
    )

    return keyboard.get_keyboard()


def get_clan_join_keyboard(
        user_data: UserSchema,
        clan_data: ClanSchema
) -> str | None:
    """Возвращает клавиатуру для вступления в клан"""

    if user_data.clan_role != ClanRole.NOT:
        return None

    elif clan_data.join_barrier > user_data.all_win:
        return None

    elif clan_data.count_members >= ClanSettings.MAX_COUNT_MEMBERS:
        return None

    elif clan_data.join_type == ClanJoinType.OPEN:
        return get_join_clan_keyboard(clan_data.clan_id)

    elif clan_data.join_type == ClanJoinType.CLOSED:
        return get_invite_clan_keyboard(clan_data.clan_id)

    elif clan_data.join_type == ClanJoinType.INVITE:
        return None

    return None


def get_keyboard_answer_owner_clan(
        user_id: int, clan_id: int
) -> str:
    """
        Возвращает клавиатуру для принятия или
        отклонения вступления пользователя
    """

    keyboard = VkKeyboard(one_time=False, inline=True)

    keyboard.add_button(
        label="Принять",
        color=VkKeyboardColor.POSITIVE,
        payload={
            "handler": "processing_menus",
            "event": ClanTypeApplication.USER_TO_CLAN.value,
            "confirm": True,
            "user_id": user_id,
            "clan_id": clan_id
        }
    )
    keyboard.add_button(
        label="Отклонить",
        color=VkKeyboardColor.NEGATIVE,
        payload={
            "handler": "processing_menus",
            "event": ClanTypeApplication.USER_TO_CLAN.value,
            "confirm": False,
            "user_id": user_id,
            "clan_id": clan_id
        }
    )

    return keyboard.get_keyboard()


def get_keyboard_answer_user_join_clan(
        user_id: int,
        clan_id: int
) -> str:
    """
        Возвращает клавиатуру для принятия или
        отклонения вступления в клан пользователем
    """

    payload_header = {
        "handler": "processing_menus",
        "event": ClanTypeApplication.CLAN_TO_USER.value
    }

    keyboard = VkKeyboard(one_time=False, inline=True)

    keyboard.add_button(
        label="Принять",
        color=VkKeyboardColor.POSITIVE,
        payload={
            **payload_header,
            "confirm": True,
            "user_id": user_id,
            "clan_id": clan_id
        }
    )
    keyboard.add_button(
        label="Отклонить",
        color=VkKeyboardColor.NEGATIVE,
        payload={
            **payload_header,
            "confirm": False,
            "user_id": user_id,
            "clan_id": clan_id
        }
    )

    return keyboard.get_keyboard()
