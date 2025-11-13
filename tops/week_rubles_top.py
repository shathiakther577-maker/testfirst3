import asyncio
import traceback

from redis.client import Redis
from vk_api.keyboard import VkKeyboard
from psycopg2.extras import DictCursor

from settings import TopSettings, NotifyChats, Config

from tops.base import BaseTop, BaseTopService
from schemas.users import UserSchema
from services.incomes import IncomesService
from services.notification import NotificationsService

from modules.additional import format_number, reduce_number
from modules.databases.users import reward_users_rubles_top
from modules.vkontakte.bot import send_message

from vk_bot.keyboards.pages import add_back_page, add_next_page


class WeekRublesTop(BaseTop):
    NAME: str = "week_rubles"
    MAPPING: int = 10
    REWARDS: dict[int | int] | None = {
        1: 8_500,
        2: 6_000,
        3: 4_500,
        4: 3_500,
        5: 2_500,
        6: 1_500,
        7: 1_250,
        8: 1_000,
        9: 750,
        10: 500
    }  # награда в рублях


class WeekRublesTopService(BaseTopService):

    @classmethod
    def get_winners(
            cls,
            psql_cursor: DictCursor,
            offset: int,
            limit: int
    ) -> list[dict | None]:

        psql_cursor.execute("""
            SELECT user_id, status, full_name,
                   week_rubles_top_points as points
            FROM users
            WHERE status NOT IN %(ignore_status)s AND
                  user_id NOT IN %(ignore_user_ids)s
            ORDER BY week_rubles_top_points DESC, user_id DESC
            OFFSET %(offset)s
            LIMIT %(limit)s
        """, {
            "ignore_status": cls.IGNORE_STATUS,
            "ignore_user_ids": cls.IGNORE_USER_IDS,
            "offset": offset,
            "limit": limit
        })
        winners = cls._get_user_prefix(psql_cursor.fetchall())

        return winners


    @classmethod
    def get_position(cls, data: UserSchema, psql_cursor: DictCursor) -> int:

        if (
            data.status in cls.IGNORE_STATUS or
            data.user_id in cls.IGNORE_USER_IDS
        ):
            return 0

        psql_cursor.execute("""
            SELECT COUNT(user_id) + 1 as position
            FROM users
            WHERE week_rubles_top_points > %(points)s AND
                  status NOT IN %(ignore_status)s AND
                  user_id NOT IN %(ignore_user_ids)s
        """, {
            "points": data.week_rubles_top_points,
            "ignore_status": cls.IGNORE_STATUS,
            "ignore_user_ids": cls.IGNORE_USER_IDS
        })
        position = psql_cursor.fetchone()["position"]

        return position


    @classmethod
    def get_number_participants(cls, psql_cursor: DictCursor) -> int:

        psql_cursor.execute("""
            SELECT COUNT(user_id) as participants
            FROM users
            WHERE status NOT IN %(ignore_status)s AND
                  user_id NOT IN %(ignore_user_ids)s
        """, {
            "ignore_status": cls.IGNORE_STATUS,
            "ignore_user_ids": cls.IGNORE_USER_IDS
        })
        count_members = psql_cursor.fetchone()["participants"]

        return count_members


    @classmethod
    def get_message(
            cls,
            data: UserSchema,
            psql_cursor: DictCursor,
            offset: int = 0,
            limit: int = WeekRublesTop.MAPPING
    ) -> tuple[str, str | None]:

        if TopSettings.SWITCH_WEEK_RUBLES_TOP is False:
            return "Топ временно не работает", None

        reward = WeekRublesTop.REWARDS
        winners = cls.get_winners(psql_cursor, offset, limit)
        # participants = cls.get_number_participants(psql_cursor)

        response = f"🎄 Топ недели на {format_number(sum(reward.values()))} монеток\n"
        keyboard = VkKeyboard(one_time=False, inline=True)

        for position, winner in enumerate(winners, offset + 1):
            winner_name = UserSchema.format_vk_name(winner["user_id"], winner["full_name"])
            winner_points = winner["points"]

            response += f"\n{position}) {winner_name} выиграл {format_number(winner_points)} коинов"
            if cls.can_get_reward(winner_points, reward, position):
                response += f" (приз {reduce_number(reward[position])} монеток)"

        user_position = cls.get_position(data, psql_cursor)
        response += f"\n\nТы находишься на {user_position} месте, выиграв {format_number(data.week_rubles_top_points)} коинов"
        if cls.can_get_reward(data.week_rubles_top_points, reward, user_position):
            response += f"\n💰 Возможный выигрыш: {reduce_number(reward[user_position])} монеток"

        # back_page = offset != 0
        # next_page = participants - offset - limit > 0 and 5 * limit > offset + limit

        # if back_page:
        #     add_back_page(
        #         keyboard,
        #         full_test=not next_page,
        #         payload={"event": "get_top_week_rubles_message", "offset": offset - limit}
        #     )

        # if next_page:
        #     add_next_page(
        #         keyboard,
        #         full_test=not back_page,
        #         payload={"event": "get_top_week_rubles_message", "offset": offset + limit}
        #     )

        # if back_page or next_page:
        #     keyboard.add_line()


        return response, keyboard.get_keyboard()


    @classmethod
    def reset_points(cls, psql_cursor: DictCursor) -> None:

        psql_cursor.execute("UPDATE users SET week_rubles_top_points = 0")


    @classmethod
    async def reward_winners(cls, redis_cursor: Redis, psql_cursor: DictCursor) -> None:

        try:
            if TopSettings.SWITCH_WEEK_RUBLES_TOP is False:
                return None

            reward = WeekRublesTop.REWARDS
            winners = cls.get_winners(psql_cursor, 0, max(reward.keys()))

            tasks = []
            admin_message = "🏆 Победители топа недели на монетки:\n"

            keyboard_rubles_reward = VkKeyboard(one_time=False, inline=True)
            keyboard_rubles_reward.add_openlink_button(
                label="Забрать приз",
                link="https://vk.com/black_info_garant"
            )
            keyboard_rubles_reward = keyboard_rubles_reward.get_keyboard()

            for position, winner in enumerate(winners, 1):
                user_id = winner["user_id"]
                user_name = UserSchema.format_vk_name(user_id, winner["full_name"])
                user_points = winner["points"]

                if cls.can_get_reward(user_points, reward, position):
                    user_reward = reward[position]

                    reward_users_rubles_top(user_id, user_reward, psql_cursor)
                    reward_white_coin = round(user_reward / Config.EXCHANGE_RUBLES_COINS * 1_000)
                    IncomesService.records_additional_expenses(reward_white_coin, redis_cursor)

                    user_points = format_number(user_points)
                    user_reward = format_number(user_reward)

                    tasks.append(send_message(
                        peer_id=user_id,
                        message=f"""
                            🏆 {user_name}, ты занял {position} место в ежедневном топе на монетки
                            🚀 {user_reward} монеток уже на твоем балансе
                        """,
                        keyboard=keyboard_rubles_reward
                    ))
                    admin_message += f"\n{position}) {user_name} - наиграл {user_points} выиграл {user_reward}"

            await asyncio.gather(*tasks)
            await NotificationsService.send_notification(NotifyChats.TOP_REWARD, admin_message)

        except:
            await send_message(
                peer_id=Config.DEVELOPER_ID,
                message=f"⚠️ Упал топ недели на монетки:\n\n{traceback.format_exc()}\n\n{winners}"
            )
            traceback.print_exc()

        finally:
            cls.reset_points(psql_cursor)
