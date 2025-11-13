from enum import Enum
from pydantic import BaseModel


class UserChatMenu(str, Enum):
    """Дополнительные меню в чате"""

    CHAT_NAME = "chat_name"  # Меняет имя чата
    AUTO_GAME = "auto_game"  # Установка значения авто игр
    CHANGE_GAME = "change_game"  # Меняет игровой режим
    CHANGE_TIMER = "change_timer"  # Меняет время игрового таймера
    ADD_HELPER = "add_helper"  # Добавляет помощника
    DEL_HELPER = "del_helper"  # Удаляет помощника


class UserChatSchema(BaseModel):
    """Схема хранения данных пользователя в чате"""

    __tablename__ = "user_in_chat"

    user_id: int  # Идентификатор пользователя
    chat_id: int  # Идентификатор чата

    menu: UserChatMenu | None = None
    current_rate: str | None = None  # Ставка игрока в текущий момент
    last_rate_amount: int | None = None  # Сумма последней ставки
