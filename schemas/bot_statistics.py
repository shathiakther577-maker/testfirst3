from datetime import datetime, date
from pydantic import BaseModel, Field


class StatisticsSchema(BaseModel):
    active: int  # Количество активных игроков

    coins_income: int  # Доход в коинах
    rubles_income: int  # Доход в рублях

    additional_income: int  # Дополнительные доходы
    additional_expenses: int  # Дополнительные расходы


class BotStatisticsSchema(BaseModel):
    """Схема статистики бота за день"""

    __tablename__ = "bot_statistics"

    id: int  # Идентификатор записи
    active: int  # Количество активных пользователей

    coins_income: int  # Количество заработанных коинов
    rubles_income: int  # Количество заработанных рублей

    additional_income: int  # Дополнительная прибыль
    additional_expenses: int  # Дополнительные расходы

    developer_income: int  # Доход программиста в рублях

    datetime: date = Field(datetime.now().date(), description="YYYY-MM-DD")
    # Дата записи статистики