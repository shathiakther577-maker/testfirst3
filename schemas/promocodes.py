from enum import Enum
from datetime import datetime
from pydantic import BaseModel


class PromoCodeSchema(BaseModel):
    """Схема промокода"""

    __tablename__ = "promocodes"

    owner_id: int  # Идентификатор владельца промокода
    name: str  # Название промокода

    reward: int  # Награда за активацию промокода
    quantity: int  # Количество активаций

    life_datetime: datetime  # Время жизни промокода


class CreatePromoCode(BaseModel):
    """Данные для создания промокода"""

    name: str  # Название
    life_date: int  # Время жизни в минутах
    reward: int  # Награда за активацию
    quantity: int  # Количество активаций


class ActivatedPromoCode(BaseModel):
    """Схема активированного промокода"""

    __tablename__ = "activated_promocodes"

    name: str  # Название промокода
    user_id: int  # Идентификатор пользователя


class PromoCodeMenu(str, Enum):
    """Дополнительные меню для управления промокодами"""

    MAIN = "main"  # Главное меню

    BEFORE_ACTIVATE = "before_activate"  # Дополнительная логика перед меню активации
    ACTIVATE = "activate"  # Меню активации

    SET_NAME = "set_name"  # Устанавливает имя промокода при создании
    SET_LIFE_DATE = "set_life"  # Устанавливает время жизни промокода
    SET_QUANTITY = "set_quantity"  # Устанавливает количество активаций промокода при создании
    SET_AMOUNT = "set_amount"  # Устанавливает награду за активацию промокода при создании


class ExtraPromoCode(BaseModel):
    """Дополнительные данные для управления промокодами"""

    menu: PromoCodeMenu = PromoCodeMenu.MAIN
    name: str | None = None  # Хранит название промокода при создании и активации
    life_date: int | None = None  # Хранит время жизни промокода в минутах
    quantity: int | None = None  # Хранит количество активаций промокода при создании
    captcha_name: str | None = None  # Хранит правильный ответ капчи
