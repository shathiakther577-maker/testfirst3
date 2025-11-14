from datetime import datetime
from pydantic import BaseModel, Field


class BonusSubscriptionSchema(BaseModel):
    """Схема бонуса за подписку"""

    __tablename__ = "bonus_subscriptions"

    id: int | None = None  # Идентификатор бонуса (автоинкремент)
    reward: int  # Награда за подписку
    created_at: datetime = Field(default_factory=datetime.now, description="YYYY-MM-DD hh:mm:ss")
    # Время создания бонуса
    is_active: bool = True  # Активен ли бонус


class BonusSubscriptionLogSchema(BaseModel):
    """Схема логов выдачи бонусов за подписку"""

    __tablename__ = "bonus_subscription_logs"

    user_id: int  # Идентификатор пользователя
    bonus_id: int  # Идентификатор бонуса
    reward: int  # Награда которую получил пользователь
    received_at: datetime = Field(default_factory=datetime.now, description="YYYY-MM-DD hh:mm:ss")
    # Время получения бонуса

