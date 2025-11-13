from psycopg2.extras import DictCursor

from schemas.user_in_chat import UserChatSchema, UserChatMenu


class UserChatService:
    """Сервис для управления дополнительными данными пользователя в чате"""

    @classmethod
    def get_data(
            cls,
            user_id: int,
            chat_id: int,
            psql_cursor: DictCursor
    ) -> UserChatSchema:
        """Возвращает данные пользователя в чате"""

        psql_cursor.execute("""
            SELECT * FROM user_in_chat
            WHERE user_id = %(user_id)s AND
                  chat_id = %(chat_id)s
        """, {
            "user_id": user_id,
            "chat_id": chat_id
        })
        psql_response = psql_cursor.fetchone()

        if psql_response is None:
            data = cls._insert_into(user_id, chat_id, psql_cursor)
        else:
            data = UserChatSchema(**psql_response)

        return data


    @staticmethod
    def _insert_into(
            user_id: int,
            chat_id: int,
            psql_cursor: DictCursor
    ) -> UserChatSchema:
        """Записывает данные пользователя в чат"""

        data = UserChatSchema(user_id=user_id, chat_id=chat_id)

        psql_cursor.execute("""
            INSERT INTO user_in_chat (user_id, chat_id)
            VALUES (%(user_id)s, %(chat_id)s)
        """, data.dict())

        return data


    @staticmethod
    def update_menu(
            user_id: int,
            chat_id: int,
            menu: UserChatMenu | None,
            psql_cursor: DictCursor
    ) -> None:
        """Обновляет меню пользователя в чате"""

        psql_cursor.execute("""
            UPDATE user_in_chat
            SET menu = %(menu)s
            WHERE user_id = %(user_id)s AND
                  chat_id = %(chat_id)s
        """, {
            "menu": menu.value if menu else None,
            "user_id": user_id,
            "chat_id": chat_id
        })
