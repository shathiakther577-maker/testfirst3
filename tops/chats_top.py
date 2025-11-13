import asyncio
import traceback
from datetime import datetime

from redis.client import Redis
from vk_api.keyboard import VkKeyboard
from psycopg2.extras import DictCursor

from settings import TopSettings, NotifyChats, Config

from tops.base import BaseTop, BaseTopService
from schemas.users import UserSchema
from schemas.chats import ChatSchema
from services.incomes import IncomesService
from services.notification import NotificationsService

from modules.additional import format_number, reduce_number
from modules.databases.users import reward_user_top
from modules.vkontakte.bot import send_message


class ChatsTop(BaseTop):
    NAME: str = "chats"
    MAPPING: int = 15
    REWARDS: dict[int | int] | None = {
        1: 0.45,
        2: 0.25,
        3: 0.15,
        4: 0.10,
        5: 0.05
    }  # в процентах где 1 = 100%


class ChatsTopService(BaseTopService):

    @staticmethod
    def _get_sql_timestamp(form_reward_winners: bool) -> str:
        """возвращает условие временной метки sql"""

        if form_reward_winners:
            return """
                WHERE DATE(rates.created_at) >= DATE(NOW() - INTERVAL '7 days') AND
                      DATE(rates.created_at) <= DATE(NOW() - INTERVAL '1 days')
            """

        current_weekday = datetime.today().weekday()

        days_since_last_saturday = (current_weekday + 2) % 7
        # Вычисляем, сколько дней назад была прошлая суббота (0 - если сегодня суббота)

        days_until_friday = (4 - current_weekday) % 7
        # Вычисляем, сколько дней осталось до пятницы (0 - если сегодня пятница)

        return f"""
            WHERE DATE(rates.created_at) >= DATE(NOW() - INTERVAL '{days_since_last_saturday} DAY') AND
                  DATE(rates.created_at) <= DATE(NOW() + INTERVAL '{days_until_friday} DAY')
        """


    @classmethod
    def get_winners(
            cls,
            psql_cursor: DictCursor,
            offset: int,
            limit: int,
            *,
            form_reward_winners: bool = False
    ) -> list[dict | None]:

        psql_cursor.execute(f"""
            SELECT chats.chat_id, chats.owner_id, chats.name,
                   COALESCE(SUM(rates.amount), 0) as points
            FROM chats
            JOIN rates ON chats.chat_id = rates.chat_id
            JOIN users AS users_c ON chats.owner_id = users_c.user_id
            JOIN users AS users_r ON rates.user_id = users_r.user_id
            {cls._get_sql_timestamp(form_reward_winners)} AND
                  users_c.status NOT IN %(ignore_status)s AND
                  users_r.status NOT IN %(ignore_status)s AND
                  chats.chat_id NOT IN %(ignore_chats_ids)s
            GROUP BY chats.chat_id
            ORDER BY points DESC, chats.chat_id DESC
            OFFSET %(offset)s
            LIMIT %(limit)s
        """, {
            "ignore_status": cls.IGNORE_STATUS,
            "ignore_user_ids": cls.IGNORE_USER_IDS,
            "ignore_chats_ids": cls.IGNORE_CHATS_IDS,
            "offset": offset,
            "limit": limit
        })
        winners = psql_cursor.fetchall()

        for winner in winners:
            winner["points"] = int(winner["points"])

        return winners


    @classmethod
    def get_bank(
            cls,
            psql_cursor: DictCursor,
            *,
            form_reward_winners: bool = False
    ) -> int:
        """возвращает сумму банка который будет разыгрываться"""

        psql_cursor.execute(f"""
            SELECT COALESCE(SUM(rates.amount) / 100 * 0.3, 0) as top_bank
            FROM chats
            JOIN rates ON chats.chat_id = rates.chat_id
            JOIN users AS users_c ON chats.owner_id = users_c.user_id
            JOIN users AS users_r ON rates.user_id = users_r.user_id
            {cls._get_sql_timestamp(form_reward_winners)} AND
                  users_c.status NOT IN %(ignore_status)s AND
                  users_r.status NOT IN %(ignore_status)s AND
                  rates.user_id NOT IN %(ignore_user_ids)s AND
                  chats.chat_id NOT IN %(ignore_chats_ids)s
        """, {
            "ignore_status": cls.IGNORE_STATUS,
            "ignore_user_ids": cls.IGNORE_USER_IDS,
            "ignore_chats_ids": cls.IGNORE_CHATS_IDS
        })

        return psql_cursor.fetchone()["top_bank"]


    @classmethod
    def get_position(cls, data: ChatSchema, psql_cursor: DictCursor) -> int:

        if data.chat_id in cls.IGNORE_CHATS_IDS:
            return 0

        try:
            participants = cls.get_number_participants(psql_cursor)
            winners_ids = [x["chat_id"] for x in cls.get_winners(psql_cursor, 0, participants)]
            return winners_ids.index(data.chat_id) + 1

        except:
            return 0


    @classmethod
    def get_number_participants(cls, psql_cursor: DictCursor) -> int:

        psql_cursor.execute("""
            SELECT COUNT(chats.chat_id) as participants
            FROM chats JOIN users ON chats.owner_id = users.user_id
            WHERE users.status NOT IN %(ignore_status)s AND
                  chats.owner_id NOT IN %(ignore_user_ids)s AND
                  chats.chat_id NOT IN %(ignore_chats_ids)s
        """, {
            "ignore_status": cls.IGNORE_STATUS,
            "ignore_user_ids": cls.IGNORE_USER_IDS,
            "ignore_chats_ids": cls.IGNORE_CHATS_IDS
        })
        participants = psql_cursor.fetchone()["participants"]

        return participants


    @classmethod
    def get_message(
            cls,
            data: ChatSchema,
            psql_cursor: DictCursor,
            offset: int = 0,
            limit: int = ChatsTop.MAPPING
    ) -> tuple[str, str | None]:

        if TopSettings.SWITCH_CHATS_TOP is False:
            return "Топ временно не работает", None

        reward = ChatsTop.REWARDS
        winners = cls.get_winners(psql_cursor, offset, limit)
        top_bank = cls.get_bank(psql_cursor)

        response = "🎁 Топ чатов\n"
        keyboard = VkKeyboard(one_time=False, inline=True)

        for position, winner in enumerate(winners, offset + 1):
            chat_id = winner["chat_id"]
            owner_id = winner["owner_id"]
            chat_name = winner["name"]

            winner_name = UserSchema.format_vk_name(owner_id, chat_name if chat_name else int(chat_id - 2E9))
            winner_points = winner["points"]

            response += f"\n{position}) {winner_name} - наиграл {format_number(winner_points)}"
            if cls.can_get_reward(winner_points, reward, position):
                response += f" (приз {reduce_number(int(top_bank * reward[position]))} BC)"

        response += f"\n\nТекущий чат находится на {cls.get_position(data, psql_cursor)} месте"


        return response, keyboard.get_keyboard()


    @classmethod
    def reset_points(cls, psql_cursor: DictCursor) -> None:
        pass


    @classmethod
    async def reward_winners(
            cls,
            redis_cursor: Redis,
            psql_cursor: DictCursor
    ) -> None:

        try:
            if TopSettings.SWITCH_CHATS_TOP is False:
                return None

            reward = ChatsTop.REWARDS
            winners = cls.get_winners(psql_cursor, 0, max(reward.keys()), form_reward_winners=True)
            top_bank = cls.get_bank(psql_cursor, form_reward_winners=True)

            tasks = []
            admin_message = f"Банк топа {format_number(top_bank)}\n🏆 Победители топа чатов:\n"

            for position, winner in enumerate(winners, 1):
                chat_id = winner["chat_id"]
                owner_id = winner["owner_id"]
                chat_name = winner["name"]

                winner_name = UserSchema.format_vk_name(owner_id, chat_name if chat_name else int(chat_id - 2E9))
                winner_points = winner["points"]

                if cls.can_get_reward(winner_points, reward, position):
                    owner_reward = int(top_bank * reward[position])

                    reward_user_top(owner_id, owner_reward, psql_cursor)
                    IncomesService.records_additional_expenses(owner_reward, redis_cursor)

                    winner_points = format_number(winner_points)
                    owner_reward = format_number(owner_reward)

                    tasks.append(send_message(
                        peer_id=owner_id,
                        message=f"""
                            🏆 Твой чат {winner_name} занял {position} место в топе чатов
                            🚀 {owner_reward} BC уже на твоем балансе
                        """
                    ))
                    admin_message += f"\n{position}) {winner_name} - наиграл {winner_points} выиграл {owner_reward}"

            await asyncio.gather(*tasks)
            await NotificationsService.send_notification(NotifyChats.TOP_REWARD, admin_message)

        except:
            await send_message(
                peer_id=Config.DEVELOPER_ID,
                message=f"⚠️ Упал топ чатов:\n\n{traceback.format_exc()}\n\n{winners}"
            )
            traceback.print_exc()

        finally:
            cls.reset_points(psql_cursor)






