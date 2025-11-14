from psycopg2.extras import DictCursor

from schemas.bonus_subscription import BonusSubscriptionSchema, BonusSubscriptionLogSchema
from modules.additional import format_number
from modules.databases.users import get_user_data, give_coins


class BonusSubscriptionService:

    @staticmethod
    def get_bonus(
            bonus_id: int,
            psql_cursor: DictCursor
    ) -> BonusSubscriptionSchema | None:
        """Возвращает данные о бонусе за подписку"""

        psql_cursor.execute("SELECT * FROM bonus_subscriptions WHERE id = %s", [bonus_id])
        psql_response = psql_cursor.fetchone()

        return BonusSubscriptionSchema(**psql_response) if psql_response else None

    @staticmethod
    def get_active_bonuses(
            psql_cursor: DictCursor
    ) -> list[BonusSubscriptionSchema]:
        """Возвращает активные бонусы за подписку"""

        psql_cursor.execute("""
            SELECT * FROM bonus_subscriptions
            WHERE is_active = TRUE
            ORDER BY created_at DESC
        """)
        bonus_subscriptions = [BonusSubscriptionSchema(**x) for x in psql_cursor.fetchall()]

        return bonus_subscriptions

    @staticmethod
    def create_bonus(
            reward: int,
            psql_cursor: DictCursor
    ) -> BonusSubscriptionSchema:
        """Создает бонус за подписку"""

        psql_cursor.execute("""
            INSERT INTO bonus_subscriptions (reward, is_active)
            VALUES (%(reward)s, TRUE)
            RETURNING *
        """, {"reward": reward})
        psql_response = psql_cursor.fetchone()

        return BonusSubscriptionSchema(**psql_response)

    @staticmethod
    def delete_bonus(
            bonus_id: int,
            psql_cursor: DictCursor
    ) -> None:
        """Удаляет бонус за подписку (деактивирует)"""

        psql_cursor.execute("""
            UPDATE bonus_subscriptions
            SET is_active = FALSE
            WHERE id = %s
        """, [bonus_id])

    @staticmethod
    def user_received_bonus(
            user_id: int,
            bonus_id: int,
            psql_cursor: DictCursor
    ) -> bool:
        """Проверяет, получил ли пользователь уже этот бонус"""

        psql_cursor.execute("""
            SELECT received_at FROM bonus_subscription_logs
            WHERE user_id = %(user_id)s AND bonus_id = %(bonus_id)s
        """, {
            "user_id": user_id,
            "bonus_id": bonus_id
        })

        return bool(psql_cursor.fetchone())

    @staticmethod
    def mark_bonus_received(
            user_id: int,
            bonus_id: int,
            reward: int,
            psql_cursor: DictCursor
    ) -> None:
        """Отмечает, что пользователь получил бонус"""

        psql_cursor.execute("""
            INSERT INTO bonus_subscription_logs (user_id, bonus_id, reward)
            VALUES (%(user_id)s, %(bonus_id)s, %(reward)s)
        """, {
            "user_id": user_id,
            "bonus_id": bonus_id,
            "reward": reward
        })

    @classmethod
    def format_bonus_message(
            cls,
            bonus: BonusSubscriptionSchema
    ) -> str:
        """Формирует сообщение о бонусе за подписку"""

        return f"""
            ID: {bonus.id}
            💰 Бонус: {format_number(bonus.reward)} White Coin
            🕒 Создан: {bonus.created_at}
            {'✅ Активен' if bonus.is_active else '❌ Неактивен'}
        """

    @classmethod
    def get_active_bonuses_response_message(
            cls,
            psql_cursor: DictCursor
    ) -> str:
        """Возвращает сообщение об активных бонусах за подписку"""

        bonuses = cls.get_active_bonuses(psql_cursor)

        if not bonuses:
            return "Нет активных бонусов за подписку"

        response = ["👑 Активные бонусы за подписку:\n"]
        for bonus in bonuses:
            response.append(cls.format_bonus_message(bonus))

        return "\n".join(response)

