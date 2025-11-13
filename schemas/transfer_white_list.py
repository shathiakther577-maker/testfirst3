from pydantic import BaseModel


class TransferWhiteListSchema(BaseModel):
    """Схема белого списка переводов"""

    __tablename__ = "transfer_white_list"

    user_id: int  # Идентификатор пользователя
