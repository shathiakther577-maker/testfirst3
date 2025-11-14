from redis.client import Redis
from psycopg2.extras import DictCursor

from tops.base import BaseTop, BaseTopService
from schemas.users import UserSchema

from modules.additional import format_number


class MonthTop(BaseTop):
    NAME: str = "month"
    MAPPING: int = 20
    REWARDS: dict[int, int] | None = None  # Награды за топ месяца (можно настроить)


class MonthTopService(BaseTopService):

    @classmethod
    def get_winners(
            cls,
            psql_cursor: DictCursor,
            offset: int,
            limit: int
    ) -> list[dict | None]:

        # Топ месяца = топ за текущий месяц (используем month_top_points если есть, иначе считаем по дате)
        psql_cursor.execute("""
            SELECT user_id, status, full_name,
                   COALESCE(month_top_points, 0) as points
            FROM users
            WHERE status NOT IN %(ignore_status)s AND
                  user_id NOT IN %(ignore_user_ids)s
            ORDER BY points DESC, user_id DESC
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
            data.status.value in cls.IGNORE_STATUS or
            data.user_id in cls.IGNORE_USER_IDS
        ):
            return 0

        psql_cursor.execute("""
            SELECT COUNT(*) + 1 as position
            FROM users
            WHERE status NOT IN %(ignore_status)s AND
                  user_id NOT IN %(ignore_user_ids)s AND
                  (COALESCE(month_top_points, 0) > %(points)s OR
                   (COALESCE(month_top_points, 0) = %(points)s AND user_id < %(user_id)s))
        """, {
            "ignore_status": cls.IGNORE_STATUS,
            "ignore_user_ids": cls.IGNORE_USER_IDS,
            "points": getattr(data, 'month_top_points', 0),
            "user_id": data.user_id
        })
        position = psql_cursor.fetchone()["position"]

        return int(position)

    @classmethod
    def get_number_participants(cls, psql_cursor: DictCursor) -> int:

        psql_cursor.execute("""
            SELECT COUNT(*) as count
            FROM users
            WHERE status NOT IN %(ignore_status)s AND
                  user_id NOT IN %(ignore_user_ids)s AND
                  COALESCE(month_top_points, 0) > 0
        """, {
            "ignore_status": cls.IGNORE_STATUS,
            "ignore_user_ids": cls.IGNORE_USER_IDS
        })
        count = psql_cursor.fetchone()["count"]

        return int(count)

    @classmethod
    def get_message(
            cls,
            data: UserSchema,
            psql_cursor: DictCursor,
            offset: int = 0,
            limit: int = MonthTop.MAPPING
    ) -> tuple[str, str | None]:

        reward = MonthTop.REWARDS
        winners = cls.get_winners(psql_cursor, offset, limit)
        participants = cls.get_number_participants(psql_cursor)

        response = "🔥 Топ игроков месячного рейтинга\n"
        response += f"Участников: {format_number(participants)}\n"

        for position, winner in enumerate(winners, offset + 1):
            winner_name = UserSchema.format_telegram_name(winner["user_id"], winner["full_name"])
            winner_points = winner["points"]

            response += f"\n{position}) {winner_name} - {format_number(winner_points)} очков"
            if cls.can_get_reward(winner_points, reward, position):
                response += f" 🎁 {format_number(reward[position])} WC"

        user_position = cls.get_position(data, psql_cursor)
        if user_position > 0:
            response += f"\n\nТвоя позиция: {user_position}"

        keyboard = None  # Можно добавить inline клавиатуру для пагинации

        return response, keyboard

    @classmethod
    def reset_points(cls, psql_cursor: DictCursor) -> None:
        """Сбрасывает очки месячного топа"""

        psql_cursor.execute("""
            UPDATE users
            SET month_top_points = 0
        """)

    @classmethod
    async def reward_winners(cls, redis_cursor: Redis, psql_cursor: DictCursor) -> None:
        """Награждает победителей месячного топа"""

        if MonthTop.REWARDS is None:
            return

        reward = MonthTop.REWARDS
        winners = cls.get_winners(psql_cursor, 0, max(reward.keys()))

        for position, winner in enumerate(winners, 1):
            if position in reward:
                from modules.databases.users import give_coins
                give_coins(winner["user_id"], reward[position], psql_cursor)


