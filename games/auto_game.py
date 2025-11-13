from typing import Optional
from psycopg2.extras import DictCursor

from schemas.games import Games
from schemas.auto_game import AutoGameSchema


class AutoGameService:

    @staticmethod
    def get_auto_games(
            chat_id: int,
            game_mode: Games,
            psql_cursor: DictCursor
    ) -> list[Optional[AutoGameSchema]]:
        """Возвращает все авто игры в чате"""

        psql_cursor.execute("""
            SELECT * FROM auto_games
            WHERE chat_id = %(chat_id)s AND
                  game_mode = %(game_mode)s
        """, {
            "chat_id": chat_id,
            "game_mode": game_mode.value
        })
        psql_response = psql_cursor.fetchall()
        auto_games = [AutoGameSchema(**x) for x in psql_response]

        return auto_games


    @staticmethod
    def insert_auto_game(
            user_id: int,
            chat_id: int,
            amount: int,
            rate_type: str,
            game_mode: Games,
            number_games: int,
            psql_cursor: DictCursor
    ) -> None:
        """Добавляет авто игры в базу данных"""

        auto_game = AutoGameSchema(
            user_id=user_id, chat_id=chat_id,
            amount=amount, rate_type=rate_type,
            game_mode=game_mode, number_games=number_games
        ).dict()

        psql_cursor.execute("""
            SELECT * FROM auto_games
            WHERE user_id = %(user_id)s AND
                  chat_id = %(chat_id)s AND
                  rate_type = %(rate_type)s AND
                  game_mode = %(game_mode)s
        """, auto_game)
        search_auto_game = bool(psql_cursor.fetchall())

        if search_auto_game is True:
            psql_cursor.execute("""
                UPDATE auto_games
                SET number_games = number_games + %(number_games)s
                WHERE user_id = %(user_id)s AND
                      chat_id = %(chat_id)s AND
                      rate_type = %(rate_type)s AND
                      game_mode = %(game_mode)s
            """, auto_game)
        else:
            psql_cursor.execute("""
                INSERT INTO auto_games (
                    user_id, chat_id, amount, rate_type,
                    game_mode, number_games
                ) VALUES (
                    %(user_id)s, %(chat_id)s, %(amount)s, %(rate_type)s,
                    %(game_mode)s, %(number_games)s
                )
            """, auto_game)


    @staticmethod
    def decrement_auto_games(
            auto_game: AutoGameSchema,
            psql_cursor: DictCursor
    ) -> None:
        """Уменьшает количество игр если игры подошли к концу удаляет их"""

        if auto_game.number_games - 1 > 0:
            psql_cursor.execute("""
                UPDATE auto_games
                SET number_games = number_games - 1
                WHERE user_id = %(user_id)s AND
                      chat_id = %(chat_id)s AND
                      rate_type = %(rate_type)s AND
                      game_mode = %(game_mode)s
            """, auto_game.dict())

        else:
            psql_cursor.execute("""
                DELETE FROM auto_games
                WHERE user_id = %(user_id)s AND
                      chat_id = %(chat_id)s AND
                      rate_type = %(rate_type)s AND
                      game_mode = %(game_mode)s
            """, auto_game.dict())


    @staticmethod
    def get_count_auto_games(
            user_id: int,
            chat_id: int,
            game_mode: Games,
            psql_cursor: DictCursor
    ) -> int:
        """Возвращает количество авто игр пользователя в чате"""

        psql_cursor.execute("""
            SELECT COALESCE(MAX(number_games), 0) as count_auto_games
            FROM auto_games
            WHERE user_id = %(user_id)s AND
                  chat_id = %(chat_id)s AND
                  game_mode = %(game_mode)s
        """, {
            "user_id": user_id,
            "chat_id": chat_id,
            "game_mode": game_mode
        })
        count = psql_cursor.fetchone()["count_auto_games"]

        return count
