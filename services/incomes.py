from redis.client import Redis
from psycopg2.extras import DictCursor

from settings import Config

from schemas.users import UserStatus
from schemas.redis import RedisKeys
from schemas.bot_statistics import StatisticsSchema


class IncomesService:
    """Сервис по работе с доходами"""

    @staticmethod
    def records_additional_incomes(
            amount: int,
            redis_cursor: Redis
    ) -> None:
        """Записывает дополнительные доходы"""

        redis_cursor.incrby(RedisKeys.DAY_ADDITIONAL_INCOMES.value, amount)


    @staticmethod
    def get_additional_income(redis_cursor: Redis) -> int:
        """Возвращает дополнительные доходы"""

        return int(redis_cursor.get(RedisKeys.DAY_ADDITIONAL_INCOMES.value) or 0)


    @staticmethod
    def reset_additional_incomes(redis_cursor: Redis) -> None:
        """Сбрасывает дополнительные доходы"""

        redis_cursor.set(RedisKeys.DAY_ADDITIONAL_INCOMES.value, 0)


    @staticmethod
    def records_additional_expenses(
            amount: int,
            redis_cursor: Redis
    ) -> None:
        """Записывает дополнительные расходы"""

        redis_cursor.incrby(RedisKeys.DAY_ADDITIONAL_EXPENSES.value, amount)


    @staticmethod
    def get_additional_expenses(redis_cursor: Redis) -> int:
        """Возвращает дополнительные расходы"""

        return int(redis_cursor.get(RedisKeys.DAY_ADDITIONAL_EXPENSES.value) or 0)


    @staticmethod
    def reset_additional_expenses(redis_cursor: Redis) -> None:
        """Сбрасывает дополнительные расходы"""

        redis_cursor.set(RedisKeys.DAY_ADDITIONAL_EXPENSES.value, 0)


    @classmethod
    def get_day_statistics(cls, redis_cursor: Redis, psql_cursor: DictCursor) -> StatisticsSchema:
        """Возвращает статистику за день"""

        psql_cursor.execute("SELECT COUNT(user_id) as active FROM users WHERE day_rates > 0")
        user_activ = psql_cursor.fetchone()["active"]

        additional_income = cls.get_additional_income(redis_cursor)
        additional_expenses = cls.get_additional_expenses(redis_cursor)

        psql_cursor.execute("""
            SELECT COALESCE(SUM(day_win), 0) as day_win,
                   COALESCE(SUM(day_lost), 0) as day_lost
            FROM users
            WHERE status not in %(ignore_user_status)s
        """, {
            "ignore_user_status": (UserStatus.ADMIN, UserStatus.MARKET)
        })
        day_stats = psql_cursor.fetchone()

        coins_income = round(
            day_stats["day_lost"] + additional_income -
            day_stats["day_win"] - additional_expenses
        )
        rubles_income = round(coins_income / Config.COURSE_RUBLES_COINS)

        return StatisticsSchema(
            active=user_activ, coins_income=coins_income, rubles_income=rubles_income,
            additional_income=additional_income, additional_expenses=additional_expenses
        )
