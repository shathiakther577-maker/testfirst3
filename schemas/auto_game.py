from pydantic import BaseModel

from schemas.games import Games


class AutoGameSchema(BaseModel):
    """Схема авто игры"""

    __tablename__ = "auto_games"

    user_id: int  # Идентификатор пользователя
    chat_id: int  # Идентификатор чата

    amount: int  # Сумма ставки
    rate_type: str  # Тип ставки

    game_mode: Games
    number_games: int  # Количество оставшихся игр
