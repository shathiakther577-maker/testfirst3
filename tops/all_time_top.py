from redis.client import Redis
from psycopg2.extras import DictCursor

from tops.base import BaseTop, BaseTopService
from schemas.users import UserSchema

from modules.additional import format_number


class AllTimeTop(BaseTop):
    NAME: str = "all_time"
    MAPPING: int = 10
    REWARDS: dict[int, int] | None = None


class AllTimeTopService(BaseTopService):

    @classmethod
    def get_winners(
            cls,
            psql_cursor: DictCursor,
            offset: int,
            limit: int
    ) -> list[dict | None]:

        psql_cursor.execute("""
            SELECT user_id, status, full_name,
                   all_top_points as points
            FROM users
            WHERE status NOT IN %(ignore_status)s AND
                  user_id NOT IN %(ignore_user_ids)s
            ORDER BY all_top_points DESC, user_id DESC
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
            WHERE all_top_points > %(points)s AND
                  status NOT IN %(ignore_status)s AND
                  user_id NOT IN %(ignore_user_ids)s
        """, {
            "points": data.all_top_points,
            "ignore_status": cls.IGNORE_STATUS,
            "ignore_user_ids": cls.IGNORE_USER_IDS
        })
        position = psql_cursor.fetchone()["position"]

        return position


    @classmethod
    def get_number_participants(cls, psql_cursor: DictCursor) -> int:

        psql_cursor.execute("""
            SELECT COUNT(user_id) as participants
            FRON users
            WHERE status NOT IN %(ignore_status)s AND
                  user_id NOT IN %(ignore_user_ids)s
        """, {
            "ignore_status": cls.IGNORE_STATUS,
            "ignore_user_ids": cls.IGNORE_USER_IDS
        })
        participants = psql_cursor.fetchone()["participants"]

        return participants


    @classmethod
    def get_message(
            cls,
            data: UserSchema,
            psql_cursor: DictCursor,
            offset: int = 0,
            limit: int = AllTimeTop.MAPPING
    ) -> tuple[str, str | None]:

        winners = cls.get_winners(psql_cursor, offset, limit)

        response = f"🔥 ТОП-{AllTimeTop.MAPPING} игроков за всё время:\n"
        keyboard = None

        for position, winner in enumerate(winners, offset + 1):
            winner_name = UserSchema.format_vk_name(winner["user_id"], winner["full_name"])
            winner_points = format_number(winner["points"])
            response += f"\n{position}) {winner_name} выиграл {winner_points} коинов"

        response += f"\n\nТы находишься на {cls.get_position(data, psql_cursor)} месте, " \
                    f"выиграв {format_number(data.all_top_points)} коинов за все время."

        return response, keyboard


    @classmethod
    def reset_points(cls, psql_cursor: DictCursor) -> None:

        psql_cursor.execute("UPDATE users SET all_top_points = 0")


    @classmethod
    async def reward_winners(cls, redis_cursor: Redis, psql_cursor: DictCursor) -> None:
        pass
