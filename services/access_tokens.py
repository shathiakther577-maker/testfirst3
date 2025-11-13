from psycopg2.extras import DictCursor

from schemas.access_tokens import AccessTokensSchema
from services.security import SecurityService, ALLOWED_CHARACTERS


class ApiAccessTokensService:
    """Сервис доступа к api"""

    TOKEN_LENGTH = 32  # Длина токена


    @classmethod
    def create_access_token(cls, psql_cursor: DictCursor) -> str:
        """Создает уникальный токен доступа"""

        access_token = SecurityService.generate_secret_key(length=cls.TOKEN_LENGTH)
        access_token_data = cls.get_access_token_data(access_token, psql_cursor)

        if access_token_data is not None:
            cls.create_access_token(psql_cursor)

        return access_token


    @classmethod
    def validate_access_token(cls, access_token: str) -> bool:
        """Проверяет токен api"""

        return (
            len(access_token) == cls.TOKEN_LENGTH and
            all([item in ALLOWED_CHARACTERS for item in access_token])
        )


    @classmethod
    def get_user_access_token_data(
            cls,
            user_id: int,
            psql_cursor: DictCursor
    ) -> AccessTokensSchema | None:
        """Возвращает все данные пользователя из access_tokens"""

        psql_cursor.execute("""
            SELECT * FROM access_tokens
            WHERE user_id = %(user_id)s
        """, {
            "user_id": user_id
        })
        psql_response = psql_cursor.fetchone()

        return AccessTokensSchema(**psql_response) if psql_response else None


    @classmethod
    def get_user_access_token(
            cls,
            user_id: int,
            psql_cursor: DictCursor
    ) -> str | None:
        """Возвращает токен пользователя если он есть"""

        token_data = cls.get_user_access_token_data(user_id, psql_cursor)
        return token_data.token if token_data else None


    @classmethod
    def get_access_token_data(
            cls,
            access_token: str,
            psql_cursor: DictCursor
    ) -> AccessTokensSchema | None:
        """Возвращает все данные о переданном токене"""

        psql_cursor.execute("""
            SELECT * FROM access_tokens
            WHERE token = %(access_token)s
        """, {
            "access_token": access_token
        })
        psql_response = psql_cursor.fetchone()

        return AccessTokensSchema(**psql_response) if psql_response else None


    @classmethod
    def update_user_access_token(
            cls,
            user_id: int,
            psql_cursor: DictCursor
    ) -> str:
        """Обновляет и возвращает токен доступа"""

        new_access_token = cls.create_access_token(psql_cursor)
        access_token_data = cls.get_user_access_token_data(user_id, psql_cursor)
        psql_request_data = {
            "access_token": new_access_token,
            "user_id": user_id
        }

        if access_token_data is not None:
            psql_cursor.execute("""
                UPDATE access_tokens
                SET token = %(access_token)s
                WHERE user_id = %(user_id)s
            """, psql_request_data)

        else:
            psql_cursor.execute("""
                INSERT INTO access_tokens (user_id, token)
                VALUES (%(user_id)s, %(access_token)s)
            """, psql_request_data)

        return new_access_token


    @classmethod
    def get_or_create_access_token(
            cls,
            user_id: int,
            psql_cursor: DictCursor
    ) -> str:
        """Возвращает токен даже если его не было до этого"""

        access_token = cls.get_user_access_token(user_id, psql_cursor)

        if access_token is None:
            access_token = cls.update_user_access_token(user_id, psql_cursor)

        return access_token


    @staticmethod
    def format_message(access_token: str) -> str:
        """Формирует сообщение по шаблону"""

        return f"""
            Твой ключ api: {access_token}

            Напоминаем, что продажа игровых ценностей запрещена правилами проекта!
        """
