from fastapi import HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from databases.redis import get_redis_cursor
from databases.postgresql import get_postgresql_connection

from schemas.redis import RedisKeys
from services.access_tokens import ApiAccessTokensService
from modules.additional import strtobool
from modules.databases.users import get_user_data, update_users_last_activity


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth")


class ApiSecurity:

    @staticmethod
    def authorization_in_api(
            access_token: str = Depends(oauth2_scheme)
    ) -> int:
        """Возвращает user_id если пользователь смог авторизоваться"""

        redis_cursor = get_redis_cursor()
        psql_connect, psql_cursor = get_postgresql_connection()

        try:
            if ApiAccessTokensService.validate_access_token(access_token) is False:
                raise HTTPException(status_code=401, detail="not authenticated")

            access_token_data = ApiAccessTokensService.get_access_token_data(access_token, psql_cursor)
            if access_token_data is None:
                raise HTTPException(status_code=401, detail="not authenticated")

            user_data = get_user_data(access_token_data.user_id, psql_cursor)
            if user_data is None:
                raise HTTPException(status_code=401, detail="not authenticated")

            if (
                not strtobool(redis_cursor.get(RedisKeys.API_WORK.value) or "1") or
                strtobool(redis_cursor.get(RedisKeys.QUIET_MODE.value) or "0")
            ):
                raise HTTPException(status_code=503, detail="not authenticated")

            if user_data.banned is True:
                raise HTTPException(status_code=403, detail="user is banned")

            update_users_last_activity(user_data.user_id, psql_cursor)
            return user_data.user_id

        finally:
            redis_cursor.close()
            psql_cursor.close()
            psql_connect.close()


    @staticmethod
    def authorization_in_website(
            form_data: OAuth2PasswordRequestForm
    ) -> dict:
        """Возвращает данные для авторизации на сайте в меню api"""

        redis_cursor = get_redis_cursor()
        psql_connect, psql_cursor = get_postgresql_connection()

        try:
            access_token = form_data.password

            if ApiAccessTokensService.validate_access_token(access_token) is False:
                raise HTTPException(status_code=401, detail="not authenticated")

            access_token_data = ApiAccessTokensService.get_access_token_data(access_token, psql_cursor)
            if access_token_data is None:
                raise HTTPException(status_code=401, detail="not authenticated")

            user_data = get_user_data(access_token_data.user_id, psql_cursor)
            if user_data is None:
                raise HTTPException(status_code=401, detail="not authenticated")

            if (
                not strtobool(redis_cursor.get(RedisKeys.API_WORK.value) or "1") or
                strtobool(redis_cursor.get(RedisKeys.QUIET_MODE.value) or "0")
            ):
                raise HTTPException(status_code=503, detail="temporarily unavailable")

            if form_data.username != str(user_data.user_id):
                raise HTTPException(status_code=401, detail="not authenticated")

            if user_data.banned is True:
                raise HTTPException(status_code=403, detail="user is banned")

            update_users_last_activity(user_data.user_id, psql_cursor)
            return {"access_token": access_token, "token_type": "bearer"}

        finally:
            redis_cursor.close()
            psql_cursor.close()
            psql_connect.close()
