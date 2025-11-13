import asyncio
import traceback
from typing import Optional
from redis.client import Redis
from psycopg2.extras import DictCursor

from settings import NotifyChats
from databases.postgresql import get_postgresql_connection

from schemas.users import UserSchema, EMPTY_USER_DATA
from schemas.redis import RedisKeys
from schemas.promocodes import PromoCodeSchema, CreatePromoCode

from services.notification import NotificationsService

from modules.additional import format_number
from modules.databases.users import take_coins, give_coins, get_user_data
from modules.telegram.bot import send_message


class PromoCodeService:

    @staticmethod
    def get_promocode(
            name: str,
            psql_cursor: DictCursor
    ) -> PromoCodeSchema | None:
        """Возвращает промокод по его названию"""

        psql_cursor.execute("""
            SELECT * FROM promocodes
            WHERE name = %(name)s
        """, {
            "name": name
        })
        psql_response = psql_cursor.fetchone()

        return PromoCodeSchema(**psql_response) if psql_response else None


    @staticmethod
    def format_promocode_message(
            promocode: PromoCodeSchema
    ) -> str:
        """Форматирует строку с данными промокода"""

        response = f"""
            💬 Название: {promocode.name}
            💰 Бонус: {format_number(promocode.reward)}
            📊 Осталось: {format_number(promocode.quantity)}
            🕒 Активен до: {promocode.life_datetime.strftime("%Y-%m-%d %H:%M:%S")}
        """

        return response


    @staticmethod
    def get_user_pormocodes(
            user_id: int,
            psql_cursor: DictCursor
    ) -> list[Optional[PromoCodeSchema]]:
        """Возвращает все промокоды пользователя"""

        psql_cursor.execute("""
            SELECT * FROM promocodes
            WHERE owner_id = %(user_id)s
        """, {
            "user_id": user_id
        })
        psql_response = psql_cursor.fetchall()
        promocodes = [PromoCodeSchema(**x) for x in psql_response]

        return promocodes


    @classmethod
    def get_message_user_promocodes(
            cls,
            user_id: int,
            psql_cursor: DictCursor
    ) -> str:
        """Возраяшет сообщение о промокодах пользователя"""

        promocodes = cls.get_user_pormocodes(user_id, psql_cursor)

        if len(promocodes) > 0:
            response = "👑 Активные промокоды:"

            for promocode in promocodes:
                response += f"\n{cls.format_promocode_message(promocode)}"

        else:
            response = "У вас нет активных промокодов"

        return response


    @staticmethod
    def get_count_user_promocode(user_id: int, psql_cursor: DictCursor):
        """Возвращает количество промокодов пользователя"""

        psql_cursor.execute("""
            SELECT COUNT(*) as count_promocodes
            FROM promocodes
            WHERE owner_id = %(user_id)s
        """, {
            "user_id": user_id
        })
        count_promocodes = psql_cursor.fetchone()["count_promocodes"]

        return count_promocodes


    @classmethod
    async def create_promocode(
        cls,
        user_data: UserSchema,
        promocode: CreatePromoCode,
        psql_cursor: DictCursor
    ) -> PromoCodeSchema:
        """Возвращает данные созданного промокода"""

        user_id = user_data.user_id

        reward = promocode.reward
        quantity = promocode.quantity

        psql_cursor.execute("""
            INSERT INTO promocodes (
                owner_id, name, reward, quantity, life_datetime
            )
            VALUES (
                %(owner_id)s, %(name)s, %(reward)s, %(quantity)s,
                NOW() + INTERVAL '%(life_in_minutes)s MINUTES'
            )
            RETURNING *
        """, {
            "owner_id": user_id,
            "name": promocode.name,
            "reward": reward,
            "quantity": quantity,
            "life_in_minutes": promocode.life_date
        })
        promocode_data = PromoCodeSchema(**psql_cursor.fetchone())
        take_coins(user_id, int(quantity * reward), psql_cursor)

        admin_message = f"""
            {user_data.vk_name} создал промокод\n
            {cls.format_promocode_message(promocode_data)}
        """
        await NotificationsService.send_notification(NotifyChats.PROMOCODE, admin_message)

        return promocode_data


    @staticmethod
    def delete_promocode(
            name: str,
            psql_cursor: DictCursor
    ) -> None:
        """Удаляет промокод и кто его активировал"""

        psql_cursor.execute("""
            DELETE FROM promocodes
            WHERE name = %(name)s
        """, {
            "name": name
        })

        psql_cursor.execute("""
            DELETE FROM activated_promocodes
            WHERE name = %(name)s
        """, {
            "name": name
        })


    @classmethod
    async def activated_promocode(
            cls,
            user_data: UserSchema,
            promocode: PromoCodeSchema,
            psql_cursor: DictCursor
    ) -> None:
        """Активирует промокод"""

        user_id = user_data.user_id

        promocode_name = promocode.name
        promocode_reward = promocode.reward

        give_coins(user_id, promocode_reward, psql_cursor)
        psql_cursor.execute("""
            UPDATE promocodes
            SET quantity = quantity - 1
            WHERE name = %(name)s
            RETURNING quantity
        """, {
            "name": promocode_name
        })
        quantity = psql_cursor.fetchone()["quantity"]

        if quantity < 0:
            raise Exception()

        cls.add_promocode_activation(user_id, promocode_name, psql_cursor)

        admin_message = f"""
            {user_data.vk_name} активировал промо {promocode_name} и получили {promocode_reward} BC
        """
        await NotificationsService.send_notification(NotifyChats.PROMOCODE, admin_message)

        if quantity == 0:
            cls.delete_promocode(promocode_name, psql_cursor)

            admin_message = f"""
                У промокода {promocode_name} закончились активации
            """
            await NotificationsService.send_notification(NotifyChats.PROMOCODE, admin_message)


    @staticmethod
    def add_promocode_activation(
            user_id: int,
            name: str,
            psql_cursor: DictCursor
    ) -> None:
        """Добавляет пользователя, который активировал промокод"""

        psql_cursor.execute("""
            INSERT INTO activated_promocodes (user_id, name)
            VALUES (%(user_id)s, %(name)s)
        """, {
            "user_id": user_id,
            "name": name
        })


    @staticmethod
    def check_activation(
            name: str,
            user_id: int,
            psql_cursor: DictCursor
    ) -> bool:
        """Проверяет активирован ли промокод пользователем"""

        psql_cursor.execute("""
            SELECT * FROM activated_promocodes
            WHERE name = %(name)s AND
                  user_id = %(user_id)s
        """, {
            "name": name,
            "user_id": user_id
        })
        psql_response = psql_cursor.fetchone()

        return bool(psql_response)


    @classmethod
    async def run_collector_expired_promocodes(cls):
        """
            Запускает сборщика просроченных промокодов
            Возвращает не активированную награду создателю промокода и удаляет промокод
        """

        while True:
            psql_connection, psql_cursor = get_postgresql_connection()

            try:
                psql_cursor.execute("""
                    SELECT EXTRACT(EPOCH FROM
                        COALESCE(
                            MIN(life_datetime),
                            NOW() + INTERVAL '30 SECONDS'
                        ) - NOW()
                    ) as seconds
                    FROM promocodes
                """)
                seconds = psql_cursor.fetchone()["seconds"]
                seconds = seconds if seconds > 0 else 0
                seconds = min(seconds, 30)

                await asyncio.sleep(seconds)

                psql_cursor.execute("""
                    SELECT * FROM promocodes
                    WHERE life_datetime < NOW()
                """)
                psql_response = psql_cursor.fetchall()
                promocodes = [PromoCodeSchema(**x) for x in psql_response]

                for promocode in promocodes:
                    promocode_name = promocode.name
                    cls.delete_promocode(promocode_name, psql_cursor)

                    if promocode.quantity == 0:
                        continue

                    owner_id = promocode.owner_id
                    refund_amount = int(promocode.quantity * promocode.reward)
                    give_coins(owner_id, refund_amount, psql_cursor)

                    owner_data = get_user_data(owner_id, psql_cursor) or EMPTY_USER_DATA
                    refund_amount = format_number(refund_amount)

                    await NotificationsService.send_notification(
                        chat=NotifyChats.PROMOCODE,
                        message=f"""
                            Промокод {promocode_name} истёк
                            {refund_amount} коинов были возвращены {owner_data.vk_name}
                        """
                    )
                    await send_message(
                        peer_id=owner_id,
                        message=f"Промокод {promocode_name} истек, {refund_amount} BC возвращены на баланс"
                    )

            except:
                traceback.print_exc()
                await asyncio.sleep(10)

            finally:
                psql_cursor.close()
                psql_connection.close()


    @staticmethod
    def get_activation_attempts(
            user_id: int,
            redis_cursor: Redis
    ) -> int:
        """Возвращает количество попыток активации промокодов у пользователя"""

        value = redis_cursor.get(f"{RedisKeys.PROMOCODE_ATTEMPTS.value}:{user_id}")
        return int(value) if value else 0


    @staticmethod
    def set_activation_attempts(
            user_id: int,
            value: int,
            redis_cursor: Redis
    ) -> None:
        """Записывает количество попыток ввода промокода у пользователя"""

        value = redis_cursor.set(
            name=f"{RedisKeys.PROMOCODE_ATTEMPTS.value}:{user_id}",
            value=value, ex=3_600
        )


    @staticmethod
    def del_activation_attempts(
            user_id: int,
            redis_cursor: Redis
    ) -> None:
        """Удаляет количество попыток ввода промокода у пользователя"""

        redis_cursor.delete(f"{RedisKeys.PROMOCODE_ATTEMPTS.value}:{user_id}")


    @staticmethod
    def ban_access(
            user_id: int,
            redis_cursor: Redis
    ) -> None:
        """Блокирует доступ к активации промокодов пользователю """

        last_redis_key = f"{RedisKeys.LAST_PROMOCODE_BAN.value}:{user_id}"
        last_ban_time = redis_cursor.get(last_redis_key)

        ban_times = {
            0: 600,  # 10 минут
            600: 3_600,  # 1 час
            3_600: 21_600,  # 6 часов
            21_600: 43_200,  # 12 часов
            43_200: 86_400,  # 24 часа
            86_400: 86_400,  # 24 часа
        }
        new_ban_time = ban_times[int(last_ban_time) if last_ban_time else 0]

        redis_cursor.set(f"{RedisKeys.BAN_ACTIVATION_PROMOCODE.value}:{user_id}", 1, ex=new_ban_time)
        redis_cursor.set(name=last_redis_key, value=new_ban_time, ex=new_ban_time * 4)


    @staticmethod
    def get_ttl_ban_access(
            user_id: int,
            redis_cursor: Redis
    ) -> int:
        """Возвращает количество секунд блокировки к доступу активации промо кодов у пользователя"""

        ttl = redis_cursor.ttl(f"{RedisKeys.BAN_ACTIVATION_PROMOCODE.value}:{user_id}")
        return int(ttl) if ttl > 0 else 1


    @staticmethod
    def is_access_activation(
            user_id: int,
            redis_cursor: Redis
    ) -> bool:
        """Возвращает есть ли у пользователя доступ на активацию промокодов"""

        value = redis_cursor.get(f"{RedisKeys.BAN_ACTIVATION_PROMOCODE.value}:{user_id}")
        return not bool(value)
