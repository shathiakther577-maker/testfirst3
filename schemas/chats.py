from enum import Enum
from datetime import datetime

from pydantic import BaseModel, Field

from schemas.games import Games


class ChatType(str, Enum):
    """Типы бесед"""

    PREMIUM = "Premium"
    PREMIUM_PLUS = "Premium+"


CHAT_TYPES_NAME = [x.value for x in ChatType]
# Название типа чата


CHAT_TYPE_COST = {
    ChatType.PREMIUM: 300_000,
    ChatType.PREMIUM_PLUS: 800_000
}
# Стоимость типа чата


MARGIN_PROLONG_CHAT = {
    (60, 180): 0.05,
    (30, 59): 0.1,
    (15, 29): 0.2,
    (7, 14): 0.3,
    (1, 6): 0.5
}
# Наценка для продления чата


def get_margin_prolong_chat(days: int) -> float:
    """Возвращает процент наценки за продление подписки чата в виде дроби"""

    for range_days, margin in MARGIN_PROLONG_CHAT.items():
        if range_days[0] <= days <= range_days[1]:
            return margin

    raise ValueError("not found margin in get_margin_prolong_chat")


INCOME_CHAT_TYPE = {
    ChatType.PREMIUM: 0.5,
    ChatType.PREMIUM_PLUS: 1
}
# Сколько процентов нужно начислять за принятую ставку владельцу чата


class ChatSchema(BaseModel):
    """Схема чата """

    __tablename__ = "chats"

    chat_id: int  # Идентификатор чата
    owner_id: int | None  # Идентификатор владельца чата

    type: ChatType | None = None
    name: str | None = None  # Название беседы

    game_id: int | None = None  # Идентификатор игры
    game_mode: Games | None = None  # Игра которая установлена в чате
    new_game_mode: Games | None = None  # Новый игровой режим для автоматического переключения

    game_timer: int = 30  # Через сколько будет запущена игра
    article_notify: bool = True  # Отправляет сообщения с статьями в вк если if True
    subscription_notif: bool = True  # Отправляет оповещение об окончании подписки

    is_activated: bool = False  # Показывает оплачен ли чат
    life_datetime: datetime = Field(datetime.now(), description="YYYY-MM-DD hh:mm:ss")
    # Время когда закончится подписка на чат


EMPTY_CHAT_DATA = ChatSchema(
    chat_id=0,
    owner_id=0,
    name="empty"
)  # Пустые данные чата


class MyChatsMenu(Enum):
    """Дополнительные меню для продления подписки чатов"""

    CHATS = "chats"  # Выбор чата если chat_id is None иначе настройка чата
    PROLONG = "prolong"  # Выбор времени продления чата
    PROLONG_CONFIRM = "prolong_confirm"  # Подтверждение продления чата


class ExtraMyChats(BaseModel):
    """Дополнительные данные для продления подписки чатов"""

    menu: MyChatsMenu = MyChatsMenu.CHATS
    chat_id: int | None = None  # Идентификатор чата с которым проходят взаимодействия
    prolong_cost: int | None = None  # Сумма оплаты продления
    prolong_period: int | None = None  # Период продления чата хранится в днях


class ChatStatsPeriod(str, Enum):
    """Период получения статистики"""

    DAY = "day"
    WEEK = "week"
    ALL_TIME = "all_time"


CHAT_STATS_PAYLOAD = "get_chat_stats"
# payload для срабатывания сообщения
ALL_CHAT_STATS_PERIOD = [x.value for x in ChatStatsPeriod]
# Список всех периодов


class ChatStatsSchema(BaseModel):
    """Схема базовой статистики"""

    count_users: int  # Количество пользователей
    rates_amount: int  # Сумма всех ставок
    owner_incomes: int  # Прибыль владельца


class ChatStatsUserSchema(BaseModel):
    """Схема лучшего пользователя в чате"""

    user_id: int  # Идентификатор пользователя
    full_name: str  # Полное имя пользователя
    rates_amount: int  # Сумма ставок


class ChatHelperStatus(str, Enum):
    """Статусы помощников чата"""

    BASE = "base"  # Управление таймером и игровыми режимами


class ChatHelperSchema(BaseModel):
    """Схема помощника чата"""

    __tablename__ = "chat_helpers"

    user_id: int  # Идентификатор пользователя
    chat_id: int  # Идентификатор чата
    status: ChatHelperStatus = ChatHelperStatus.BASE
    created_at: datetime = Field(datetime.now(), description="YYYY-MM-DD hh:mm:ss")
    # Время добавления помощника
