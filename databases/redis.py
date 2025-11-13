from redis.client import Redis
from settings import DatabaseRedisSettings, DatabaseRedisRatesSettings


def get_redis_cursor() -> Redis:
    """Подключение к redis"""

    return Redis(
        host=DatabaseRedisSettings.DB_HOST,
        port=DatabaseRedisSettings.DB_PORT,
        db=DatabaseRedisSettings.DB_NUMBER,
        decode_responses=True,  # Переводит данные из байт-кода
    )


def get_redis_rates_cursor() -> Redis:
    """Подключается к redis которая хранит сообщения о ставках пользователя"""

    return Redis(
        host=DatabaseRedisRatesSettings.DB_HOST,
        port=DatabaseRedisRatesSettings.DB_PORT,
        db=DatabaseRedisRatesSettings.DB_NUMBER,
        decode_responses=True,  # Переводит данные из байт-кода
    )
