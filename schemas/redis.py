from enum import Enum
from typing import Any
from settings import Config


class RedisKeys(Enum):
    """Ключи, которые используются в redis"""

    QUIET_MODE = "quiet_mode"
    # Тихий режим если включен принимает сообщения только от администраторов
    # Хранится в redis при запуске запоминает состояние

    AUTO_GAMES_WORK = "auto_games_work"
    # Показывает включены или отключены авто игры
    # Хранится в redis при запуске запоминает состояние

    API_WORK = "api_work"
    # Работает ли api или нет (callback)

    DAY_ADDITIONAL_INCOMES = "day:additional_incomes"
    # Дополнительные доходы за день

    DAY_ADDITIONAL_EXPENSES = "day:additional_expenses"
    # Дополнительные расходы за день

    APPLICATION_JOIN_CLAN = "application_join_clan"
    # Хранит отправленные заявки на вступление или принятия в клан

    NOTIFY_BANNED_USER = "notify_banned_user"
    # Показывает отправлено ли пользователю сообщение о блокировке

    TRANSFERS_IN_CHAT = "transfers_in_chat" # :sender_id:recipient_id:amount
    # Хранит значения перевода отправителя и получателя в чате

    CAPTCHA_PROMOCODE = "captcha_promocode"  # :user_id
    # Хранит количество прохождения капчи в промокодах (1 часов)

    PROMOCODE_ATTEMPTS = "promocode_attempts"  # :user_id
    # Хранит количество попыток ввода промокода пользователем (1 часов)

    LAST_PROMOCODE_BAN = "last_promocode_ban"  # :user_id
    # Хранит сколько секунд был последний бан в промокодах (время бана * 4)

    BAN_ACTIVATION_PROMOCODE = "ban_activation_promocode" # :user_id
    # Пока существует данный ключ пользователь не может активировать промокод (ttl)

    CAPTCHA_BONUSREPOST = "captcha_bonusrepost"  # :user_id
    # Хранит количество прохождения капчи в получении бонуса за репост

    CAPTCHA_BAN_BONUSREPOST = "captcha_ban_bonusrepost"  # :user_id
    # Запрещает активировать пользователю бонус за репост на 10 минут


    def __getattribute__(self, __name: str) -> Any:

        if __name == "value":
            prefix = "dev_" if Config.DEVELOPMENT_MODE else ""
            redis_key = super().__getattribute__(__name)
            return f"{prefix}{redis_key}"

        return super().__getattribute__(__name)
