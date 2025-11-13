from enum import Enum
from datetime import datetime

from pydantic import BaseModel, Field
from dataclasses import dataclass, field

from vk_bot.template_messages import SOMETHING_WENT_WRONG


class TransferCoinsType(Enum):
    """Типы переводов"""

    IN = "in"  # к пользователю
    OUT = "out"  # от пользователя
    ALL = "all"  # любой


class TransferCoinsSchema(BaseModel):
    """Схема перевода может"""

    __tablename__ = "transfer_coins"

    id: int  # Идентификатор перевода
    sender_id: int  # Идентификатор отправителя
    recipient_id: int  # Идентификатор получателя
    amount: int  # Сумма перевода
    created_at: datetime = Field(datetime.now(), description="YYYY-MM-DD hh:mm:ss")
    # Время перевода


class TransferCoinsError(str, Enum):
    """Типы ошибок в переводах"""

    NO = "no"

    INCORRECT_AMOUNT = "incorrect amount"
    SOMETHING_WENT_WRONG = "something went wrong"

    YOU_BANNED = "you banned"
    RECIPIENT_BANNED = "recipient banned"

    YOU_UNREGISTERED = "you unregistered"  # на всякий случай
    UNREGISTERED_RECIPIENT = "recipient is not registered"

    NOT_ENOUGH_COINS = "not enough coins"
    NOT_ENOUGH_POINTS = "not enough points"

    TRANSFERS_BANNED = "transfers banned"
    CANT_SEND_COINS_TO_ONESELF = "can't send coins to oneself"


translation_errors_transfer_coins = {
    TransferCoinsError.NO: "Ограничения не найдены",

    TransferCoinsError.INCORRECT_AMOUNT: "⚠ Сумма передана некорректно",
    TransferCoinsError.SOMETHING_WENT_WRONG: SOMETHING_WENT_WRONG,

    TransferCoinsError.YOU_BANNED: "⚠ Вы заблокированы в боте",
    TransferCoinsError.RECIPIENT_BANNED: "⚠ Аккаунт получателя заблокирован",

    TransferCoinsError.YOU_UNREGISTERED: "😒 Вы не зарегистрированы в боте",
    TransferCoinsError.UNREGISTERED_RECIPIENT: "😒 Получатель не зарегистрирован в боте",

    TransferCoinsError.NOT_ENOUGH_COINS: "😒 Недостаточно коинов",
    TransferCoinsError.NOT_ENOUGH_POINTS: "😒 Недостаточно очков в общем рейтинге игроков",

    TransferCoinsError.TRANSFERS_BANNED: "⚠ Вам запрещено переводить коины",
    TransferCoinsError.CANT_SEND_COINS_TO_ONESELF: "😒 Вы не можете сделать перевод самому себе"
}  # Перевод ошибок для пользователя


def get_transfer_coins_error_message(error: TransferCoinsError):
    """Возвращает сообщение ошибки перевода"""

    return translation_errors_transfer_coins[error]


@dataclass
class AccessTransferCoins:
    """Данные, которые возвращаются при проверке возможности перевода"""

    access: bool = field(default=False)
    error: TransferCoinsError = field(
        default=TransferCoinsError.SOMETHING_WENT_WRONG
    )


class MenuTransferCoins(str, Enum):
    """Дополнительные меню в переводе монет"""

    RECIPIENT = "recipient"  # Установка получателя
    AMOUNT = "amount"  # Установка суммы перевода


class ExtraTransferCoins(BaseModel):
    """Дополнительные данные в меню перевод монет"""

    menu: MenuTransferCoins = MenuTransferCoins.RECIPIENT
    recipient_id: int | None = None  # Идентификатор получателя
    recipient_name: str | None = None  # Имя получателя
