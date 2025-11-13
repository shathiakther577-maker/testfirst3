from abc import ABC, abstractmethod

from redis.client import Redis
from psycopg2.extras import DictCursor

from schemas.users import UserSchema, UserStatus


"""
    Описание создания топа

    Каждый топ должен находиться в отдельном файле
    В каждом файле должен быть класс "NameTop" и "NameTopServices"

    Все NameTop должны содержать обязательные атрибуты помеченные * в BaseTop
    При добавлении нового атрибута нужно описать его в BaseTop

    При написания сервиса для топа нужно наследовать его от BaseTopService
"""


class BaseTop:
    """
        *NAME: str - название топа на английском (нужно для админ панели)
        *MAPPING: int - Количество участников которое нужно отображать в топе
        *REWARDS: dict[int, int] | None - награда за топ в виде словаря[key=место, value=награда] или None
    """
    pass


class BaseTopService(ABC):

    IGNORE_STATUS = (UserStatus.ADMIN.value, UserStatus.MARKET.value)  # Статусы, которые не принимают участие в топе
    IGNORE_USER_IDS = (0, )  # Идентификаторы пользователей которые не принимают участие в топе
    IGNORE_CHATS_IDS = (0, )  # Идентификаторы чатов которые не принимают участие в топе
    IGNORE_CLANS_IDS = (0, )  # Идентификаторы кланов которые не принимают участие в топе


    @classmethod
    @abstractmethod
    def get_winners(cls, psql_cursor: DictCursor, offset: int, limit: int) -> list[dict | None]:
        """Возвращает победителей"""
        ...


    @classmethod
    def _get_user_prefix(cls, winners: list[dict | None]) -> list[dict | None]:
        """Добавляет prefix для отображения в топах"""

        for winner in winners:
            status = winner.get("status")
            prefix = UserSchema.get_user_prefix(UserStatus(status) if status else None)
            winner["full_name"] = f"{prefix}{winner['full_name']}{prefix}"

        return winners


    @classmethod
    @abstractmethod
    def get_position(cls, data, psql_cursor: DictCursor) -> int:
        """Возвращает место участника топа"""
        ...


    @classmethod
    @abstractmethod
    def get_number_participants(cls, psql_cursor: DictCursor) -> int:
        """Возвращает количество участников в топе"""
        ...


    @classmethod
    @abstractmethod
    def get_message(cls, data, psql_cursor: DictCursor, offset: int, limit: int) -> tuple[str, str | None]:
        """Возвращает сообщение и клавиатуру топа"""
        ...


    @classmethod
    @abstractmethod
    def reset_points(cls, psql_cursor: DictCursor) -> None:
        """Сбрасывает очки топа"""
        ...


    @classmethod
    @abstractmethod
    async def reward_winners(cls, redis_cursor: Redis, psql_cursor: DictCursor) -> None:
        """Награждает победителей топа"""
        ...


    @classmethod
    def can_get_reward(cls, points: int, reward: dict[int | int] | None, position: int) -> bool:
        """Проверяет может ли участник получить награду"""

        return (
            points > 0 and
            reward is not None and
            reward.get(position) is not None
        )
