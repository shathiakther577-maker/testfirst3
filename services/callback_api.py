import json
import aiohttp
from psycopg2.extras import DictCursor

from settings import ProxySettings
from schemas.access_tokens import CallbackSchema, DropCallback
from services.security import SecurityService


class CallbackService:
    """Сервис для отправки callback api"""

    @classmethod
    def get_user_callback(
            cls,
            user_id: int,
            psql_cursor: DictCursor
    ) -> CallbackSchema | None:
        """Возвращает callback данные пользователя"""

        psql_cursor.execute("""
            SELECT callback_url, callback_secret
            FROM access_tokens
            WHERE user_id = %(user_id)s
        """, {
            "user_id": user_id
        })
        psql_response = psql_cursor.fetchone()

        return CallbackSchema(**psql_response) if psql_response else None


    @classmethod
    def update_user_callback(
            cls,
            user_id: int,
            callback_url: str,
            psql_cursor: DictCursor
    ) -> CallbackSchema:
        """Обновляет callback данные пользователя"""

        callback_secret = SecurityService.generate_secret_key(length=24)

        psql_cursor.execute("""
            UPDATE access_tokens
            SET callback_url = %(callback_url)s,
                callback_secret = %(callback_secret)s
            WHERE user_id = %(user_id)s
        """, {
            "callback_url": callback_url,
            "callback_secret": callback_secret,
            "user_id": user_id
        })

        return CallbackSchema(
            callback_url=callback_url,
            callback_secret=callback_secret
        )


    @classmethod
    def delete_user_callback(
            cls,
            user_id: int,
            psql_cursor: DictCursor
    ) -> DropCallback:
        """Удаляет callback данные пользователя"""

        psql_cursor.execute("""
            UPDATE access_tokens
            SET callback_url = NULL,
                callback_secret = NULL
            WHERE user_id = %(user_id)s
        """, {
            "user_id": user_id
        })

        return DropCallback()


    @classmethod
    async def send_callback_message(
            cls,
            callback_url: str,
            message: dict
    ) -> None:
        """Отправляет данные пользователю на сервер"""

        try:
            async with aiohttp.ClientSession(
                    connector=aiohttp.TCPConnector(ssl=False)
            ) as session:
                headers = {
                    "user-agent": "Black Coin Callback",
                    "Content-Type": "application/json"
                }
                data = json.dumps(message, ensure_ascii=False)

                kwargs = {}
                if ProxySettings.WORKS is True:
                    kwargs["proxy"] = ProxySettings.LINK

                await session.post(callback_url, headers=headers, data=data, **kwargs)

        except:
            pass
