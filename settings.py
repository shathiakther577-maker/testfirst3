import os
from enum import Enum
from pathlib import Path
from datetime import date
from modules.additional import strtobool

from dotenv import load_dotenv
load_dotenv()


class Config:
    """Общие настройки бота"""

    MAX_WINNING =  12_000_000  # Максимальный выигрыш с одной ставки
    NOTIFICATION_WIN = 100_000 # Сумма выигрыша при котором отправляются логи в чат результатов игр
    NOTIFICATION_RATE = 30_000 # Сумма ставки при котором отправляются логи в чат ставок

    COURSE_RUBLES_COINS = 1_380  # Среднее количество коинов за рубль при покупке в магазине
    EXCHANGE_RUBLES_COINS = 0.75  # Курс обмена рублей на коины

    BOT_OWNERS_SHARES = {
        162606700: 0.4625,
        691678371: 0.4625,
        317548089: 0.075
    }
    # Доли владельцев проекта (дробное число от 0 до 1)

    MAX_NORMAL_VK_DELAY: int = 3
    # Количество секунд, если > бот при ставках отправляет сообщения "вк лагает"

    REWARD_START_BONUS: int = 5_000  # Сумма стартового бонуса
    GETTING_START_BONUS: bool = False  # Нужно ли выдавать стартовый бонус (клавиатура)

    DEVELOPER_ID = 317548089  # Id программиста проекта
    DEVELOPMENT_MODE = strtobool(os.getenv("DEVELOPMENT_MODE"))  # Режим разработки

    SERVER_URL = "https://white-coin.ru"  # url проекта
    ON_SERVER = strtobool(os.getenv("ON_SERVER"))  # Показывает что запущен на сервере

    PROJECT_ROOT = Path.cwd()  # Расположение проекта
    TEMP_FOLDER = os.path.join(PROJECT_ROOT.parent, "bot_temp")  # Расположение временных файлов
    BACKUPS_FOLDER = os.path.join(PROJECT_ROOT.parent, "backups")  # Расположения бэкапов базы данных


class TopSettings:
    """
        Настройки топов
        Настроить IGNORE в файле tops base.py
    """

    SWITCH_DAY_TOP: bool = True  # Топ дня
    SWITCH_WEEK_TOP: bool = True  # Топ недели

    SWITCH_CHATS_TOP: bool = True  # Топ чата
    SWITCH_CLANS_TOP: bool = True  # Топ кланов

    SWITCH_RUBLES_TOP: bool = True  # Топ на рубли
    SWITCH_WEEK_RUBLES_TOP: bool = True  # Топ недели на рубли

    SWITCH_COINS_TOP: bool = False  # Праздничный топ на коины
    DATETIME_COINS_TOP: date | None = None  # Время когда должен сработать топ

    # Указывает какие топы включены, а какие отключены


class PointsLimit:
    """
        Ограничение на действие в игровых очках
        all_win которое должен выиграть пользователь, чтобы получить доступ
    """

    TRANSFER_COINS = 150_000  # Переводы коинов
    ACTIVATE_PROMOCODE = 150_000  # Активация промо кода
    CREATE_PROMOCODE = 150_000  # Создание промо кода


class ServicesCosts:
    """Стоимость услуг"""

    CREATE_CLAN = 300_000  # Создание клана
    CHANGE_CLAN_TAG = 100_000  # Смены тега клана
    CHANGE_CLAN_NAME = 100_000  # Смены имени клана
    CHANGE_USER_NAME = 50_000  # Смены имени пользователя


class ClanSettings:
    """Настройки клана"""

    MAX_CLAN_TAG = 5  # Максимальная длина тега клана
    MAX_CLAN_NAME = 15  # Максимальная длина имени клана
    MAX_COUNT_MEMBERS = 25  # Максимальное количество участников в клане

    MAX_JOIN_BARRIER = 9_223_372_036_854_775_807
    # Максимальная значения порога входа в клан

    DELETE_APPLICATION_CLAN = 3_600  # 1 час
    # Количество секунд через которые нужно удалить заявку на вступление или принятия в клан


class PromoCodeSettings:
    """Настройки промокодов"""

    MAX_LEN_NAME = 255  # Максимальная длина названия

    MIN_REWARD = 1_000  # Минимальная награда за активацию
    MAX_REWARD = 10_000_000  # Максимальная награда за активацию

    MAX_QUANTITY = 5_000  # Максимальное количество активаций

    MAX_LIFE_IN_MINUTES = 21_600  # 15 дней
    # Максимальное время жизни промокода в минутах

    MAX_COUNT_PROMOCODE = 10
    # Максимальное количество промокодов которое может имени пользователь


class NotifyChats(str, Enum):
    """Идентификаторы чатов для отправки логов"""

    MAIN = int(os.getenv("CHAT_ID_MAIN", "0"))  # Прочие
    RATES = int(os.getenv("CHAT_ID_RATES", "0"))  # Ставки
    PROMOCODE = int(os.getenv("CHAT_ID_PROMOCODE", "0"))  # Промокоды
    TOP_REWARD = int(os.getenv("CHAT_ID_TOP_REWARD", "0"))  # Награды за топ
    CREATE_CLAN = int(os.getenv("CHAT_ID_CREATE_CLAN", "0"))  # Кланы
    TRANSFER_COINS = int(os.getenv("CHAT_ID_TRANSFER_COINS_LOG", "0"))  # Переводы коинов
    CHANGE_USER_NAME = int(os.getenv("CHAT_ID_CHANGE_USER_NAME_LOG", "0"))  # Смена имени пользователя
    RESET_USER_ACCOINT = int(os.getenv("CHAT_ID_RESET_USER_ACCOINT", "0"))  # Обнуление данных пользователя


class ProxySettings:
    """Настройки прокси"""

    HOST = os.getenv("PROXY_HOST")  # Хостинг
    PORT = os.getenv("PROXY_PORT")  # Порт
    USER = os.getenv("PROXY_USER")  # Пользователь
    PASS = os.getenv("PROXY_PASS")  # Пароль

    WORKS = Config.ON_SERVER
    # Прокси работает если выключен режим разработки
    LINK = f"http://{USER}:{PASS}@{HOST}:{PORT}"
    # Прокси через который проходят данные


class DatabasePsqlSettings:
    """Настройки базы данных postgresql"""

    DB_USER = os.getenv("PSQL_USER", "postgres")  # Пользователь базы данных
    DB_PASSWORD = os.getenv("PSQL_PASSWORD", "")  # Пароль от базы данных
    DB_HOST = os.getenv("PSQL_HOST", "localhost")  # Хостинг базы данных
    DB_PORT = os.getenv("PSQL_PORT", "5432")  # Порт базы данных
    DB_NAME = os.getenv("PSQL_DATABASE", "whitecoin")  # Имя базы данных


class DatabaseRedisSettings:
    """Настройки базы данных redis"""

    DB_NAME = os.getenv("REDIS_DATABASE", "redis")  # Имя базы данных
    DB_HOST = os.getenv("REDIS_HOST", "localhost")  # Хостинг базы данных
    DB_PORT = os.getenv("REDIS_PORT", "6379")  # Порт на котором работает база данных
    DB_NUMBER = int(os.getenv("REDIS_DB_NUMBER", "0"))  # Номер базы данных


class DatabaseRedisRatesSettings:
    """Настройки базы данных redis на localhost которая хранит сообщения ставок"""

    DB_NAME = "rate_messages"  # Имя базы данных
    DB_HOST = "localhost"  # Хостинг базы данных
    DB_PORT = 6379  # Порт на котором работает база данных
    DB_NUMBER = 0  # Номер базы данных


class VkBotSettings:
    """Настройки vk bot"""

    NAME = "White Coin"  # Имя группы
    API_VERSION = "5.131"  # Версия API для запросом к методам также callback, longpoll

    GROUP_ID = int(os.getenv("VK_GROUP_ID", "0"))  # Id группы
    GROUP_ACCESS_TOKEN = os.getenv("VK_GROUP_ACCESS_TOKEN", "")  # Токен доступа группы
    OWNER_ACCESS_TOKEN = os.getenv("VK_OWNER_ACCESS_TOKEN", "")  # Токен владельца проекта

    GROUP_CALLBACK_SECRET = os.getenv("VK_GROUP_CALLBACK_SECRET", "")
    # Секретный ключ callback для валидации приходящих от вк event-ов
    GROUP_CALLBACK_CONFIRM_RESPONSE = os.getenv("VK_GROUP_CALLBACK_CONFIRM_RESPONSE", "")
    # Строка, которую должен вернуть сервер

    MINI_APPS_TOKEN = os.getenv("VK_MINI_APPS_TOKEN", "")
    # Токен от приложения vk mini apps

    LINK = f"vk.me/club{GROUP_ID}"  # Ссылка на бота
    APPEAL_TO_BOT = f"club{GROUP_ID}"
    # Строка обращения к боту [кнопки/@public]


class TelegramBotSettings:
    """Настройки Telegram bot"""

    NAME = "White Coin"  # Имя бота
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8255662139:AAEmUeMzOJHt_xobxgsFCcAKR_O_7Zgeb6U")  # Токен бота от @BotFather
    BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "Whitecoingame_bot")  # Username бота (без @)
    
    # TODO: Укажите ID основного канала (например: -1001234567890)
    # Можно получить через @userinfobot или через get_chat API
    CHANNEL_ID = int(os.getenv("TELEGRAM_CHANNEL_ID", "0"))  # ID основного канала для бонусов
    SUBSCRIPTION_CHANNEL_ID = int(os.getenv("TELEGRAM_SUBSCRIPTION_CHANNEL_ID", "-1003306584831"))  # ID канала за подписку на который можно получать бонусы
    ADMIN_ID = int(os.getenv("TELEGRAM_ADMIN_ID", "6212101501"))  # ID администратора Telegram бота
    
    WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL", "")  # URL для webhook (опционально)
    WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")  # Секретный ключ для webhook


class FastApiSettings:
    """Настройки fast api"""

    ROOT_PREFIX="/dev_white_coin" if Config.DEVELOPMENT_MODE else "/white_coin"
    TITLE = TelegramBotSettings.NAME  # Название api
    VERSION = "0.2.0"  # Версия api
    DESCRIPTION = f"API для работы с {TelegramBotSettings.NAME}"  # Описание api




class Temp:

    # API_WORK = True  # Показывает включено или выключено api
    # QUIET_MODE = False  # Тихий режим если включен принимает сообщения только от администраторов
    # AUTO_GAMES_WORK = True  # Показывает включены или отключены авто игры

    GAMES = []  # Хранит все запущенные игры
    REGISTER_USERS = []  # Хранит пользователей которые регистрируются
    GET_START_BONUS = []  # Хранит пользователей которые получают стартовый бонус
    GET_BONUS_REPOST = []  # Хранит пользователей которые получают бонус за репост
