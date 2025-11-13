from datetime import datetime
from pydantic import BaseModel, Field


class BonusPostSchema(BaseModel):
    """Схема бонуса за репост"""

    __tablename__ = "bonus_posts"

    post_id: int  # Идентификатор поста
    reward: int  # Награда за репост
    sub_reward: int  # Дополнительная награда за репост
    activations: int  # Количество активаций
    life_datetime: datetime = Field(datetime.now(), description="YYYY-MM-DD hh:mm:ss")
    # Время окончания поста
    on_wall: bool = False # Показывает что пост об окончании опубликован


class BonusRepostLogSchema(BaseModel):
    """Схема активированных постов"""

    __tablename__ = "bonus_repost_logs"

    post_id: int  # Идентификатор поста
    user_id: int  # Идентификатор пользователя
    reward: int  # Награда которую получил пользователь
    active_at: datetime = Field(datetime.now(), description="YYYY-MM-DD hh:mm:ss")
    # Время активации поста


class ExtraBonusRepost(BaseModel):
    """Дополнительные данные в получении бонуса за репост"""

    post_id: int  # Идентификатор поста за который хотят получить награду
    captcha_name: str  # Хранит правильный ответ капчи
