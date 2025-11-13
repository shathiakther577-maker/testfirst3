import json
from psycopg2.extras import DictCursor

from schemas.games import Games, GameSchema
from schemas.chats import ChatSchema, ChatType


def get_chat_data(
        chat_id: int,
        psql_cursor: DictCursor
) -> ChatSchema | None:
    """Возвращает данные чата"""

    if chat_id is None:
        return None

    psql_cursor.execute("""
        SELECT chats.*, MAX(games.game_id) as game_id
        FROM chats
        LEFT JOIN games ON chats.chat_id = games.chat_id
        WHERE chats.chat_id = %(chat_id)s
        GROUP BY chats.chat_id
    """, {
        "chat_id": chat_id
    })
    psql_response = psql_cursor.fetchone()
    chat_data = ChatSchema(**psql_response) if psql_response else None

    return chat_data


def get_game_data(
        game_id: int,
        psql_cursor: DictCursor
) -> GameSchema:
    """Возвращает данные игры"""

    psql_cursor.execute("""
        SELECT *,
               EXTRACT(EPOCH FROM end_datetime - now()) as time_left
        FROM games
        WHERE game_id = %(game_id)s
        ORDER BY game_id DESC
    """, {
        "game_id": game_id
    })
    psql_response = psql_cursor.fetchone()
    psql_response["game_result"] = json.loads(psql_response["game_result"])
    game_data = GameSchema(**psql_response)

    return game_data
