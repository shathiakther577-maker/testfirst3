from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field


class PaymentsName(str, Enum):
    """Название платежный системы"""

    KEKSIK = "keksik"


PAYMENTS_NAMES = [x.value for x in PaymentsName]  # Название всех платежек


class PaymentSchema(BaseModel):
    """Схема пополнений"""

    __tablename__ = "payments"

    tx_id: int  # Идентификатор полученного платежа
    name: PaymentsName

    user_id: int  # Идентификатор пользователя
    rubles: float  # Количество полученных рублей
    coins: int  # Количество выданных коинов

    accepted_at: datetime = Field(datetime.now(), description="YYYY-MM-DD hh:mm:ss")
    # Время получения платежа
