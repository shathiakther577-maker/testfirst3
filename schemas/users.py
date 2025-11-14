from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field

from schemas.clans import ClanRole


class UserMenu(str, Enum):
    """Меню пользователей"""

    MAIN = "main"  # Главное меню
    ADMIN = "admin"  # Админ панель
    CLANS = "clans"  # Меню кланов
    MAILING = "mailing"  # Меню рассылки
    SETTINGS = "settings"  # Меню настроек
    SERVICES = "services"  # Меню сервисов
    MY_CHATS = "my_chats"  # Меню управления чатами
    PROMOCODE = "promocode"  # Меню промокодов
    STATISTICS = "statistics"  # Меню статистики
    BONUS_REPOST = "bonus_repost"  # Меню получения бонуса за репост
    TRANSFER_COINS = "transfer_coins"  # Меню перевода коинов
    CHANGE_USER_NAME = "change_user_name"  # Меню смены имени пользователя


class UserStatus(str, Enum):
    """Статусы пользователя"""

    USER = "user"  # Пользователь
    ADMIN = "admin"  # Администратор
    MARKET = "market"  # Магазины, которые принадлежат администратором

    HONEST = "honest"  # Честный пользователя "👑"
    SCAMMER = "scammer"  # Не честный пользователя "⛔"


class UserSchema(BaseModel):
    """Схема пользователя"""

    __tablename__ = "users"

    user_id: int  # Идентификатор пользователя
    full_name: str  # Полное имя пользователя

    menu: UserMenu = UserMenu.MAIN
    status: UserStatus = UserStatus.USER

    coins: int = 0  # Количество white coin на аккаунте
    rubles: int = 0  # Количество рублей (монетки) на аккаунте

    clan_id: int | None = None  # Идентификатор клана в котором находится пользователь
    clan_role: ClanRole = ClanRole.NOT
    show_clan_tag: bool = False  # Флаг указывать тег клана в имени
    clan_points: int = 0  # Очки принесенные в клан

    day_win: int = 0  # Количество выигранных коинов за день
    day_lost: int = 0  # Количество проигранных коинов за день
    day_rates: int = 0  # Сумма ставок за день

    week_win: int = 0  # Количество выигранных коинов за неделю
    week_lost: int = 0  # Количество проигранных коинов за неделю
    week_rates: int = 0 # Сумма ставок за неделю

    all_win: int = 0  # Количество выигранных коинов за все время
    all_lost: int = 0  # Количество проигранных коинов за все время
    all_rates: int = 0  # Общее сумма ставок
    rates_count: int = 0  # Общее количество ставок

    top_profit: int = 0  # Количество выигранных коинов во всех топах
    coins_purchased: int = 0  # Количество купленных coins

    all_top_points: int = 0  # Количество очков в топе за все время
    day_top_points: int = 0  # Количество очков в топе дня
    week_top_points: int = 0  # Количество очков в недели
    month_top_points: int = 0  # Количество очков в топе месяца
    coins_top_points: int = 0  # Количество очков в праздничном топе
    rubles_top_points: int = 0  # Количество очков в топе на рубли
    week_rubles_top_points: int = 0  # Количество очков в топе недели на рубли

    mailing: bool = True  # Флаг получения рассылки
    start_bonus: bool = False  # Флаг получения стартового бонуса
    show_balance: bool = True  # Флаг можно ли другим пользователям видеть баланс
    free_nick_change: bool = False  # Флаг показывает можно ли бесплатно сменить никнейм

    banned: bool = False  # Флаг заблокирован ли пользователь
    banned_promo: bool = False  # Флаг заблокирован ли сервис промокодов
    banned_transfer: bool = False  # Флаг заблокирован ли перевод коинов
    banned_nickname: bool = False  # Флаг заблокирована ли смена имени

    extra_data: dict | None = None  # Дополнительные данные пользователя (для меню, ...)
    description: str | None = None  # Описание игрока

    last_activity: datetime = Field(datetime.now(), description="YYYY-MM-DD hh:mm:ss")
    # Время последней активности в боте
    created_at: datetime = Field(datetime.now(), description="YYYY-MM-DD hh:mm:ss")
    # Время создания аккаунта


    @classmethod
    def format_telegram_name(cls, user_id: int, user_name: str) -> str:
        """Возвращает имя пользователя для Telegram"""

        return user_name


    @property
    def telegram_name(self) -> str:
        """Имя пользователя для Telegram"""

        return self.format_telegram_name(self.user_id, self.full_name)


    @property
    def vk_name(self) -> str:
        """Обратная совместимость - использует telegram_name"""

        return self.telegram_name


    @classmethod
    def get_user_prefix(cls, status: UserStatus | None) -> str:
        """Определяет какой статус у пользователя"""

        if status == UserStatus.ADMIN:
            return "👑"

        elif status == UserStatus.HONEST:
            return "👑"

        elif status == UserStatus.SCAMMER:
            return "⛔"

        return ""


    @property
    def user_prefix(self) -> str:
        """Возвращает префикс пользователя"""

        return self.get_user_prefix(self.status)


EMPTY_USER_DATA = UserSchema(
    user_id=0,
    full_name="empty",
)  # Пустые данные пользователя
