from datetime import datetime, timedelta
from psycopg2.extras import DictCursor

from schemas.users import UserSchema, UserStatus
from modules.additional import format_number, get_word_case


class StatisticsService:

    @staticmethod
    def get_best_users_balance(
            psql_cursor: DictCursor
    ) -> list[UserSchema | None]:
        """Возвращает пользователей отсортированных по балансу (включая мерчантов)"""

        psql_cursor.execute("""
            SELECT user_id, full_name, status, coins, show_balance
            FROM users
            WHERE status not in %(ignore_user_status)s AND
                  banned = FALSE
            ORDER BY coins DESC
            LIMIT 10
        """, {
            "ignore_user_status": (UserStatus.ADMIN,)  # Исключаем только админов, мерчанты учитываем
        })
        psql_response = psql_cursor.fetchall()

        users = []
        for user in psql_response:
            prefix = UserSchema.get_user_prefix(user["status"])
            user["full_name"] = f"{prefix}{user['full_name']}{prefix}"
            users.append(UserSchema(**user))

        return users


    @staticmethod
    def get_user_balance(
            psql_cursor: DictCursor
    ) -> int:
        """Возвращает баланс пользователей для статистики (включая мерчантов)"""

        psql_cursor.execute("""
            SELECT COALESCE(SUM(coins), 0) as balance
            FROM users
            WHERE status not in %(ignore_user_status)s AND
                  banned = FALSE
        """, {
            "ignore_user_status": (UserStatus.ADMIN,)  # Исключаем только админов, мерчанты учитываем
        })
        users_balance = psql_cursor.fetchone()["balance"]

        return int(users_balance)


    @classmethod
    def get_bet_balance_message(
            cls,
            psql_cursor: DictCursor
    ) -> str:
        """Возвращает сообщение о лучших балансов пользователей"""

        emoji_numbers = {
            1: "1️⃣", 2: "2️⃣", 3: "3️⃣",
            4: "4️⃣", 5: "5️⃣", 6: "6️⃣",
            7: "7️⃣", 8: "8️⃣", 9: "9️⃣",
            10: "🔟"
        }

        users = cls.get_best_users_balance(psql_cursor)
        response = [f"📊 Общий баланс WC - {format_number(cls.get_user_balance(psql_cursor))} WC\n"]

        for number, user in enumerate(users, 1):
            user_name = user.vk_name if user.show_balance else "Скрыл"
            format_coins = format_number(user.coins)
            response.append(f"{emoji_numbers[number]} {user_name} - {format_coins} WC")

        return "\n".join(response)


    @staticmethod
    def get_transfer_stats_for_period(
            end_time: datetime,  # До скольки искать
            start_time: datetime,  # Со скольки искать
            psql_cursor: DictCursor
    ) -> int:
        """Возвращает сумму переводов за определенный интервал"""

        psql_cursor.execute("""
            SELECT COALESCE(SUM(amount), 0) as amount
            FROM transfer_coins
            WHERE created_at >= %(start_time)s AND
                  created_at <= %(end_time)s
        """, {
            "start_time": start_time,
            "end_time": end_time
        })
        transfer_amount = psql_cursor.fetchone()["amount"]

        return int(transfer_amount)


    @staticmethod
    def calculate_percent_change(
            first_amount: int,
            last_amount: int
    ) -> int | float:
        """Возвращает насколько первое число меньше или больше второго в процентах"""

        if (
            first_amount != 0 and first_amount > last_amount or
            last_amount != 0 and last_amount > first_amount
        ):
            percent = 100 - min(first_amount, last_amount) / (max(first_amount, last_amount) / 100)
            percent = -percent if last_amount > first_amount else percent
        else:
            percent = 0

        return percent


    @classmethod
    def get_transfers_stats_message(
            cls,
            psql_cursor: DictCursor
    ) -> str:
        """Возвращает сообщение о статистике переводов"""

        now_time = datetime.now()
        hours_period = [4, 24, 48]
        response = ["♻ Переводы\n"]

        for hours in hours_period:
            first_interval = now_time - timedelta(hours=hours)
            last_interval = now_time - timedelta(hours=hours*2)

            first_amount = cls.get_transfer_stats_for_period(now_time, first_interval, psql_cursor)
            last_amount = cls.get_transfer_stats_for_period(first_interval, last_interval, psql_cursor)

            percent = cls.calculate_percent_change(first_amount, last_amount)
            emoji = "📈" if percent > 0 else "📉"
            str_hours = get_word_case(hours, ("час", "часа", "часов"))
            percent = int(percent)
            str_percent = f"{f'+{percent}' if percent > 0 else str(percent)}%"

            response.append(f"{emoji} За последние {hours} {str_hours} - {format_number(first_amount)} WC ({str_percent})")

        return "\n".join(response)
