from pydantic import BaseModel


class AccessTokensSchema(BaseModel):
    """Схема токенов доступа"""

    __tablename__ = "access_tokens"

    user_id: int  # Идентификатор пользователя
    token: str  # Токен доступа к api
    callback_url: str | None = None  # Ссылка куда будет отправляться callback данные
    callback_secret: str | None = None  # Ключ для валидации callback данных


class CallbackSchema(BaseModel):
    """Схема callback"""

    callback_url: str | None = None  # Ссылка куда будет отправляться callback данные
    callback_secret: str | None = None  # Ключ для валидации callback данных


class DropCallback(BaseModel):
    """Схема удаления callback"""

    response: str = "ok"  # Ответ удаления
