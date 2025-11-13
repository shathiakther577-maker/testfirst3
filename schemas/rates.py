from datetime import datetime
from pydantic import BaseModel, Field

from schemas.users import UserStatus
from schemas.games import Games


class RatesSchema(BaseModel):
    """Схема ставки которая хранится в db"""

    __tablename__ = "rates"

    user_id: int  # Идентификатор пользователя
    chat_id: int  # Идентификатор чата
    game_id: int  # Идентификатор игры

    amount: int  # Сумма ставки
    rate_type: str  # Тип ставки
    game_mode: Games
    owner_income: int  # Прибыль владельцев за ставку

    created_at: datetime = Field(datetime.now(), description="YYYY-MM-DD hh:mm:ss")
    # Время создания ставки


class GameRateSchema(RatesSchema):

    user_full_name: str  # Полное имя пользователя который поставил ставку
    user_status: UserStatus
    clan_id: int | None # Идентификатор клана


class CalculateRateSchema(GameRateSchema):
    """Схема рассчитанной ставки"""

    is_winning: bool | None = None  # Показывает, выиграл ли пользователь
    winning_amount: int | None = None  # Сумма выигрыша
