import os
import time
import asyncio
import threading
import traceback
import subprocess
from subprocess import STDOUT, DEVNULL

from settings import Config
from redis.client import Redis
from datetime import datetime, timedelta
from psycopg2.extras import DictCursor

from settings import TopSettings, Config, DatabasePsqlSettings
from databases.redis import get_redis_cursor
from databases.postgresql import get_postgresql_connection

from tops.day_top import DayTopService
from tops.week_top import WeekTopService
from tops.chats_top import ChatsTopService
from tops.clans_top import ClansTopService
from tops.coins_top import CoinsTopService
from tops.rubles_top import RublesTopService
from tops.week_rubles_top import WeekRublesTopService

from schemas.bot_statistics import StatisticsSchema

from services.incomes import IncomesService
from services.promocode import PromoCodeService
from services.bonus_repost import BonusRepostService
from services.notification import NotificationsService, NotifyChats
from services.reset_user_data import ResetUserServices

from modules.additional import format_number, get_word_case
from modules.databases.users import get_user_data, update_users_last_activity
from modules.telegram.bot import send_message, send_keyboard

from vk_bot.template_messages import REPEAT_CHAT_SUBSCRIPTION
from vk_bot.keyboards.other import empty_keyboard, repeat_chat_subscription_keyboard, \
    get_disabled_sub_chat_notif_keyboard


class BackgroundWorkers:

    @staticmethod
    async def reset_subscribe_chats() -> None:
        """Обнуляет подписку на чаты"""

        while True:
            try:
                psql_connect, psql_cursor = get_postgresql_connection()

                psql_cursor.execute("""
                    SELECT chats.chat_id as chat_id
                    FROM chats JOIN users ON chats.owner_id = users.user_id
                    WHERE users.status != 'admin' AND
                          chats.is_activated = TRUE AND
                          chats.life_datetime <= NOW()
                """)
                chat_ids = [x["chat_id"] for x in psql_cursor.fetchall()]

                for chat_id in chat_ids:

                    psql_cursor.execute("""
                        UPDATE chats SET is_activated = FALSE
                        WHERE chat_id = %(user_id)s
                    """, {
                        "user_id": chat_id
                    })

                    await send_message(chat_id, REPEAT_CHAT_SUBSCRIPTION, repeat_chat_subscription_keyboard)
                    await send_keyboard(chat_id, empty_keyboard)

                psql_cursor.close()
                psql_connect.close()
                await asyncio.sleep(30)

            except:
                await asyncio.sleep(10)


    @classmethod
    async def reser_user_data(cls) -> None:
        """Обнуляет данные пользователя если не пользовался ботом 2 месяца"""

        while True:
            redis_cursor = get_redis_cursor()
            psql_connect, psql_cursor = get_postgresql_connection()

            try:
                psql_cursor.execute("""
                    SELECT EXTRACT(EPOCH FROM (
                        COALESCE(
                            (SELECT MIN(last_activity) FROM users) + INTERVAL '2 MONTH',
                            NOW() + INTERVAL '60 SECOND'
                        ) - NOW()
                    )) AS expectation_seconds
                """)
                expectation_seconds = psql_cursor.fetchone()["expectation_seconds"]
                expectation_seconds = expectation_seconds if expectation_seconds > 0 else 0
                expectation_seconds = min(expectation_seconds, 60)

                await asyncio.sleep(expectation_seconds)

                psql_cursor.execute("""
                    SELECT user_id
                    FROM users
                    WHERE NOW() > (last_activity + INTERVAL '2 MONTH') AND
                          user_id != 0
                """)
                user_ids = [x["user_id"] for x in psql_cursor.fetchall()]

                for user_id in user_ids:
                    reset_data = ResetUserServices.reset_data(user_id, psql_cursor)
                    IncomesService.records_additional_incomes(reset_data.total_amount, redis_cursor)
                    update_users_last_activity(user_id, psql_cursor)

                    prefix = "⚠" if reset_data.total_amount > 0 else ""
                    user_data = get_user_data(user_id, psql_cursor)
                    await NotificationsService.send_notification(
                        chat=NotifyChats.RESET_USER_ACCOINT,
                        message=f"""
                            {prefix} {user_data.vk_name} не пользовался ботом более 2-х месяцев\
                            {reset_data.reset_message}
                        """
                    )

            except:
                traceback.print_exc()
                await asyncio.sleep(10)

            finally:
                psql_cursor.close()
                psql_connect.close()
                redis_cursor.close()


    @staticmethod
    def create_database_backup() -> None:
        """Создает резервную копию базы данных"""

        today = datetime.now().strftime("%d-%m-%Y_%H:%M:%S")
        dump_file_name = f"{DatabasePsqlSettings.DB_NAME}_{today}.sql"
        dump_location = os.path.join(Config.BACKUPS_FOLDER, dump_file_name)

        subprocess.call(
            f"""
                PGPASSWORD="{DatabasePsqlSettings.DB_PASSWORD}" \\
                pg_dump \\
                -U {DatabasePsqlSettings.DB_USER} \\
                -h {DatabasePsqlSettings.DB_HOST} \\
                -d {DatabasePsqlSettings.DB_NAME} \\
                -f {dump_location}
            """,
            shell=True, stdout=DEVNULL, stderr=STDOUT
        )


    @staticmethod
    def remove_old_database_backup() -> None:
        """Удаляет старые резервные копии базы данных"""

        files = os.listdir(Config.BACKUPS_FOLDER)
        backups = [x for x in files if x.startswith(DatabasePsqlSettings.DB_NAME)]
        to_remove = []

        for backup_name in backups:
            try:
                created_at = datetime.strptime(
                    backup_name.replace(f"{DatabasePsqlSettings.DB_NAME}_", "").replace(".sql", ""),
                    "%d-%m-%Y_%H:%M:%S"
                )
                diff = datetime.now() - created_at
                # 7 дней с погрешностью в 1000 секунд
                if diff.total_seconds() >= 7 * 86400 - 1000:
                    to_remove.append(backup_name)
            except:
                traceback.print_exc()

        for backup_name in to_remove:
            os.remove(os.path.join(Config.BACKUPS_FOLDER, backup_name))


    @staticmethod
    async def inform_owners_incomes(stats: StatisticsSchema, *, period: str) -> None:
        """Информирует владельцев о доходе за period"""

        template_message = f"✅ За {period} бот принес {format_number(stats.coins_income)} коинов ({format_number(round(stats.rubles_income / 1000))})"

        for owner_id, share in Config.BOT_OWNERS_SHARES.items():
            coins_share = format_number(int(stats.coins_income * share))
            rubles_share = format_number(round(stats.rubles_income * share / 1000))
            await send_message(
                peer_id=owner_id,
                message=template_message + f"\n💳 Твоя доля: {coins_share} коинов ({rubles_share})"
            )


    @classmethod
    async def inform_owners_week_incomes(cls, psql_cursor: DictCursor) -> None:
        """Информирует владельцев о доходе за неделю"""

        psql_cursor.execute("""
            SELECT COALESCE(SUM(active), 0) as active,
                   COALESCE(SUM(coins_income), 0) as coins_income,
                   COALESCE(SUM(rubles_income), 0) as rubles_income,
                   COALESCE(SUM(additional_income), 0) as additional_income,
                   COALESCE(SUM(additional_expenses), 0) as additional_expenses
            FROM bot_statistics
            WHERE datetime >= DATE(NOW() - INTERVAL '7 days')
        """)
        stats = StatisticsSchema(**psql_cursor.fetchone())

        await cls.inform_owners_incomes(stats, period="неделю")


    @staticmethod
    def write_day_statistics(bot_statistics: StatisticsSchema, psql_cursor: DictCursor) -> None:
        """Записывает статистику за день"""

        statistics = bot_statistics.dict()

        statistics["developer_income"] = int(
            bot_statistics.rubles_income *
            Config.BOT_OWNERS_SHARES.get(Config.DEVELOPER_ID, 0)
        )

        psql_cursor.execute("""
            INSERT INTO bot_statistics (
                active, coins_income, rubles_income,
                additional_income, additional_expenses,
                developer_income, datetime
            )
            VALUES (
                %(active)s, %(coins_income)s, %(rubles_income)s,
                %(additional_income)s, %(additional_expenses)s,
                %(developer_income)s, DATE(NOW() - INTERVAL '1 days')
            )
        """, statistics)


    @staticmethod
    def reset_day_statistics(redis_cursor: Redis, psql_cursor: DictCursor) -> None:
        """Очищает статистику за день"""

        psql_cursor.execute("UPDATE users SET day_win = 0, day_lost = 0, day_rates = 0")

        IncomesService.reset_additional_incomes(redis_cursor)
        IncomesService.reset_additional_expenses(redis_cursor)


    @staticmethod
    def reset_week_statistics(psql_cursor: DictCursor) -> None:
        """Очищает статистику за неделю"""

        psql_cursor.execute("UPDATE users SET week_win = 0, week_lost = 0, week_rates = 0")


    @staticmethod
    async def send_notif_about_end_chat_sub(psql_cursor: DictCursor) -> None:
        """Отправляет уведомления об окончании подписки на чат"""

        psql_cursor.execute("""
            SELECT chats.chat_id,
                   chats.owner_id,
                   chats.name,
                   ROUND(EXTRACT(EPOCH FROM (chats.life_datetime - NOW())) / 86400) as days_left
            FROM chats JOIN users ON chats.owner_id = users.user_id
            WHERE chats.subscription_notif is True AND
                  ROUND(EXTRACT(EPOCH FROM (chats.life_datetime - NOW())) / 86400) IN (1, 7) AND
                  users.status != 'admin'
        """)
        chats = psql_cursor.fetchall()

        for chat in chats:

            chat_id = chat["chat_id"]
            chat_name = f"{chat['name']}" if chat["name"] else int(chat_id - 2E9)

            days_left = int(chat["days_left"])
            left_word = get_word_case(days_left, ("остался", "осталось", "осталось"))
            days_word = get_word_case(days_left, ("день", "дня", "дней"))

            message = f"Чат {chat_name} скоро истeчёт, до истечения срока чата {left_word} {days_left} {days_word}"
            await send_message(chat["owner_id"], message, get_disabled_sub_chat_notif_keyboard(chat_id))


    @classmethod
    async def every_day(cls) -> None:
        """Ежедневный запуск задачь"""

        while True:
            await asyncio.sleep(86400 - ((time.time() + 10800) % 86400) + 10)

            redis_cursor = get_redis_cursor()
            psql_connect, psql_cursor = get_postgresql_connection()

            try:
                cls.create_database_backup()
                cls.remove_old_database_backup()

                bot_statistics = IncomesService.get_day_statistics(redis_cursor, psql_cursor)
                cls.reset_day_statistics(redis_cursor, psql_cursor)
                cls.write_day_statistics(bot_statistics, psql_cursor)
                await cls.inform_owners_incomes(bot_statistics, period="день")

                current_date = datetime.today()
                current_day = current_date.day
                current_week_day = current_date.weekday()

                await DayTopService.reward_winners(redis_cursor, psql_cursor)

                if current_day == 1:
                    await RublesTopService.reward_winners(redis_cursor, psql_cursor)

                if current_week_day == 0:
                    cls.reset_week_statistics(psql_cursor)
                    await WeekTopService.reward_winners(redis_cursor, psql_cursor)
                    await ClansTopService.reward_winners(redis_cursor, psql_cursor)
                    await WeekRublesTopService.reward_winners(redis_cursor, psql_cursor)
                    await cls.inform_owners_week_incomes(psql_cursor)

                if current_week_day == 5:
                    await ChatsTopService.reward_winners(redis_cursor, psql_cursor)

                if TopSettings.SWITCH_COINS_TOP and TopSettings.DATETIME_COINS_TOP is not None:

                    if TopSettings.DATETIME_COINS_TOP == current_date:
                        await CoinsTopService.reward_winners(redis_cursor, psql_cursor)

                    if TopSettings.DATETIME_COINS_TOP == current_date + timedelta(days=4):
                        CoinsTopService.reset_points(psql_cursor)

                await cls.send_notif_about_end_chat_sub(psql_cursor)

            except:
                traceback.print_exc()

            finally:
                psql_cursor.close()
                psql_connect.close()
                redis_cursor.close()


    @classmethod
    async def run_workers(cls) -> None:
        """Запускает задачи"""

        workers = [
            cls.every_day,
            cls.reser_user_data,
            cls.reset_subscribe_chats,
            BonusRepostService.publish_post_end_bonus,
            PromoCodeService.run_collector_expired_promocodes
        ]

        for worker in workers:
            threading.Thread(target=asyncio.run, args=[worker()], daemon=True).start()
