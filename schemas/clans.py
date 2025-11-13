from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field


class ClanRole(str, Enum):
    """Роли в клане"""

    NOT = "not"  # Не состоит в клане
    OWNER = "owner"  # Владелец
    MEMBER = "member"  # Участник


class ClanJoinType(str, Enum):
    """Тип входа в клан"""

    OPEN = "open"  # Открыт
    CLOSED = "closed"  # Закрыт
    INVITE = "invite"  # По приглашению


clan_join_type_translation = {
    ClanJoinType.OPEN: "открытый",
    ClanJoinType.CLOSED: "закрытый",
    ClanJoinType.INVITE: "по приглашению"
}  # Перевод типа входа в клан для отображения пользователям


class ClanTypeApplication(str, Enum):
    """Типы заявок на вступление в клан"""

    JOIN_CLAN = "join_clan"  # Вступление в клан
    USER_TO_CLAN = "application_user"
    # Пользователь отправил заявку в клан
    CLAN_TO_USER = "application_clan"
    # Клан отправил заявку в пользователю


class ClanSchema(BaseModel):
    """Схема клана"""

    __tablename__ = "clans"

    clan_id: int  # Идентификатор клана
    owner_id: int  # Идентификатор владельца клана

    tag: str  # Tег клана
    name: str  # Имя клана

    points: int = 0  # Очки клана сколько игроки заработали очков
    # не храниться в дб вычисляется при select
    count_members: int = 0  # Количество участников в клане
    # не храниться в дб вычисляется при select

    join_type: ClanJoinType = ClanJoinType.OPEN  # тип входа в клан
    join_barrier: int = 0  # Барьеры для входа в клан ->
    # (минимальное количество коинов которое должен выиграть пользователь для входа в клан)

    chat_link: str | None = None  # Ссылка на беседу клана
    invitation_link: str | None = None  # Ссылка приглашения в клан
    invitation_salt: int | None = None  # Соль в виде числа чтобы не подделать вход в клан

    owner_notifications: bool = True  # Флаг получения уведомлений владельца клана ->
    # (вошел/вышел/...)
    created_at: datetime = Field(datetime.now(), description="YYYY-MM-DD hh:mm:ss")
    # Время создания клана


class MiniClanSchema(BaseModel):
    """Схема с минимальными значениями клана"""

    clan_id: int  # Идентификатор клана
    owner_id: int  # Идентификатор владельца клана
    tag: str  # Tег клана
    name: str  # Имя клана
    points: int  # Очки клана


class MemberScheme(BaseModel):
    """Схема участника клана"""

    user_id: int  # Идентификатор пользователя
    full_name: str  # Полное имя пользователя
    points: int  # Очки принесенные в клан


class CreateClanMenu(str, Enum):
    """Дополнительные меню для создания клана"""

    MAIN = "main"  # Стартовое меню с выбором или создание клана
    SET_TAG = "set_tag"  # Установка тега клана
    SET_NAME = "set_name"  # Установка имени клана


class ExtraCreateClan(BaseModel):
    """Дополнительные данные для создания клана"""

    menu: CreateClanMenu = CreateClanMenu.MAIN
    clan_name: str | None = None  # Имя клана


class OwnerClanMenu(str, Enum):
    """Дополнительные меню для управления клана владельцем"""

    MAIN = "main"  # Главное меню взаимодействием с кланом
    SETTINGS = "settings"  # Меню настройки клана
    DELETE_CLAN = "delete_clan"  # Меню удаления клана

    MANAGING_MEMBERS = "managing_members"  # Меню управление членами клана
    INVITE_MEMBER = "invite_member"  # Меню приглашения пользователя
    EXPEL_MEMBER = "expel_member"  # Меню изгнания пользователя 

    CHANGE_CLAN_TAG = "change_tag"  # Меню смены тега клана
    CHANGE_CLAN_NAME = "change_name"  # Меню смены названия клана

    CHANGE_CHAT_LINK = "chat_link"  # Меню смены ссылки чата клана
    CHANGE_JOIN_TYPE = "join_type"  # Меню смены типа входа в клан
    CHANGE_JOIN_BARRIER = "join_barrier"  # Меню смены барьера в клан


class ExtraOwnerClan(BaseModel):
    """Дополнительные данные для владельца клана"""

    menu: OwnerClanMenu = OwnerClanMenu.MAIN
