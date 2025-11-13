import asyncio
import traceback

from redis.client import Redis
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from psycopg2.extras import DictCursor

from settings import TopSettings, NotifyChats, Config

from tops.base import BaseTop, BaseTopService
from schemas.users import UserSchema
from services.incomes import IncomesService
from services.notification import NotificationsService

from modules.additional import format_number, reduce_number
from modules.databases.users import reward_user_top
from modules.vkontakte.bot import send_message

from vk_bot.keyboards.pages import add_back_page, add_next_page


class ClansTop(BaseTop):
    NAME: str = "clan"
    MAPPING: int = 5
    REWARDS: dict[int | int] | None = {
        1: 10_000_000,
        2: 5_000_000,
        3: 2_500_000,
        4: 1_500_000,
        5: 1_000_000
    }


class ClansTopService(BaseTopService):

    @classmethod
    def get_winners(
            cls,
            psql_cursor: DictCursor,
            offset: int,
            limit: int
    ) -> list[dict | None]:

        psql_cursor.execute("""
            SELECT clans.clan_id, clans.owner_id,
                   clans.tag, clans.name,
                   COALESCE(SUM(users.clan_points), 0) as points
            FROM clans
            LEFT JOIN users ON clans.clan_id = users.clan_id
            WHERE users.status NOT IN %(ignore_status)s AND
                  users.user_id NOT IN %(ignore_user_ids)s AND
                  clans.clan_id NOT IN %(ignore_clan_ids)s
            GROUP BY clans.clan_id, clans.owner_id,
                     clans.tag, clans.name, clans.tag
            ORDER BY points DESC, clan_id DESC
            OFFSET %(offset)s
            LIMIT %(limit)s
        """, {
            "ignore_status": cls.IGNORE_STATUS,
            "ignore_user_ids": cls.IGNORE_USER_IDS,
            "ignore_clan_ids": cls.IGNORE_CLANS_IDS,
            "offset": offset,
            "limit": limit
        })
        winners = psql_cursor.fetchall()

        for winner in winners:
            winner["points"] = int(winner["points"])

        return winners


    @classmethod
    def get_position(
            cls,
            data: int,  # clan_id
            psql_cursor: DictCursor
    ) -> int:

        if data in cls.IGNORE_CHATS_IDS:
            return 0

        try:
            participants = cls.get_number_participants(psql_cursor)
            winners_ids = [x["clan_id"] for x in cls.get_winners(psql_cursor, 0, participants)]
            return winners_ids.index(data) + 1

        except:
            return 0


    @classmethod
    def get_number_participants(cls, psql_cursor: DictCursor) -> int:

        psql_cursor.execute("""
            SELECT COUNT(clans.clan_id) as participants
            FROM clans
            LEFT JOIN users ON clans.clan_id = users.clan_id
            WHERE users.status NOT IN %(ignore_status)s AND
                  users.user_id NOT IN %(ignore_user_ids)s AND
                  clans.clan_id NOT IN %(ignore_clan_ids)s
        """, {
            "ignore_status": cls.IGNORE_STATUS,
            "ignore_user_ids": cls.IGNORE_USER_IDS,
            "ignore_clan_ids": cls.IGNORE_CLANS_IDS
        })
        participants = psql_cursor.fetchone()["participants"]

        return participants


    @classmethod
    def get_message(
            cls,
            data: UserSchema,
            psql_cursor: DictCursor,
            offset: int = 0,
            limit: int = ClansTop.MAPPING
    ) -> tuple[str, str | None]:

        if TopSettings.SWITCH_CLANS_TOP is False:
            return "Топ временно не работает", None

        reward = ClansTop.REWARDS
        winners = cls.get_winners(psql_cursor, offset, limit)
        participants = cls.get_number_participants(psql_cursor)

        response = "🎁 Топ кланов\n"
        keyboard = VkKeyboard(one_time=False, inline=True)

        for position, winner in enumerate(winners, offset + 1):
            winner_name = f"[{winner['tag']}] {UserSchema.format_vk_name(winner['owner_id'], winner['name'])}"
            winner_points = winner["points"]

            response += f"\n{position}) {winner_name} - {format_number(winner_points)} коинов"
            if cls.can_get_reward(winner_points, reward, position):
                response += f" (приз {reduce_number(reward[position])} BC)"

        if data.clan_id != None:
            clan_position = cls.get_position(data.clan_id, psql_cursor)
            response += f"\n\nКлан в котором вы состоите находится на {clan_position} месте"

        back_page = offset != 0
        next_page = participants - offset - limit > 0 and 5 * limit > offset + limit

        if back_page:
            add_back_page(
                keyboard,
                full_test=not next_page,
                payload={"event": "get_top_clans_message", "offset": offset - limit}
            )

        if next_page:
            add_next_page(
                keyboard,
                full_test=not back_page,
                payload={"event": "get_top_clans_message", "offset": offset + limit}
            )

        if back_page or next_page:
            keyboard.add_line()

        keyboard.add_line()

        keyboard.add_button(
            label="Кланы",
            color=VkKeyboardColor.POSITIVE,
            payload={"event": "go_clan_menu"}
        )

        return response, keyboard.get_keyboard()


    @classmethod
    def reset_points(cls, psql_cursor: DictCursor) -> None:

        psql_cursor.execute("UPDATE users SET clan_points = 0")


    @classmethod
    def get_clan_members(
            cls,
            clan_id: int,
            psql_cursor: DictCursor
    ) -> list:
        """Возвращает участников клана для награждения"""

        psql_cursor.execute("""
            SELECT user_id, full_name, clan_points as points
            FROM users
            WHERE clan_id = %(clan_id)s AND
                  status NOT IN %(ignore_status)s AND
                  user_id NOT IN %(ignore_user_ids)s
            ORDER BY clan_points DESC
        """, {
            "clan_id": clan_id,
            "ignore_status": cls.IGNORE_STATUS,
            "ignore_user_ids": cls.IGNORE_USER_IDS,
        })
        members = psql_cursor.fetchall()

        return members


    @classmethod
    async def reward_winners(
            cls,
            redis_cursor: Redis,
            psql_cursor: DictCursor
    ) -> None:

        try:
            if TopSettings.SWITCH_CLANS_TOP is False:
                return None

            reward = ClansTop.REWARDS
            winners = cls.get_winners(psql_cursor, 0, max(reward.keys()))

            tasks = []
            admin_message = "🏆 Победители топа кланов:\n"

            for clan_position, winner in enumerate(winners, 1):
                clan_id = winner["clan_id"]
                owner_id = winner["owner_id"]
                clan_points = winner["points"]

                if cls.can_get_reward(clan_points, reward, clan_position):
                    clan_name = UserSchema.format_vk_name(owner_id, winner["name"])
                    clan_reward = reward[clan_position]

                    admin_message += f"\n\n{clan_position}) клан {clan_name} выиграл {format_number(clan_reward)}"
                    clan_members = cls.get_clan_members(clan_id, psql_cursor)

                    for member_position, member in enumerate(clan_members, 1):
                        user_id = member["user_id"]
                        user_name = UserSchema.format_vk_name(user_id, member["full_name"])
                        user_points = member["points"]

                        user_reward = user_points / clan_points * clan_reward * 0.9
                        if user_id == owner_id:
                            user_reward += clan_reward * 0.1
                        user_reward = int(user_reward)

                        reward_user_top(user_id, user_reward, psql_cursor)
                        IncomesService.records_additional_expenses(user_reward, redis_cursor)

                        user_points = format_number(user_points)
                        user_reward = format_number(user_reward)

                        tasks.append(send_message(
                            peer_id=user_id,
                            message=f"""
                                🏆 Неделя подошла к концу, Ваш клан занял {clan_position} место
                                🚀 {user_reward} BC уже на твоем балансе
                            """
                        ))
                        admin_message += f"\n{clan_position}.{member_position}) {user_name} - наиграл {user_points} выиграл {user_reward}"

            await asyncio.gather(*tasks)
            await NotificationsService.send_notification(NotifyChats.TOP_REWARD, admin_message)

        except:
            await send_message(
                peer_id=Config.DEVELOPER_ID,
                message=f"⚠️ Упал топ кланов:\n\n{traceback.format_exc()}\n\n{winners}"
            )
            traceback.print_exc()

        finally:
            cls.reset_points(psql_cursor)