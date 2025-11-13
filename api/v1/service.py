from fastapi import HTTPException

from databases.redis import get_redis_cursor
from databases.postgresql import get_postgresql_connection

from schemas.users import UserStatus
from schemas.transfer_coins import TransferCoinsType
from api.v1.schemas import UserBalance, TransactionType, Transaction, \
    SetCallback, DropCallback

from services.callback_api import CallbackService
from services.transfer_coins import TransferCoinsService

from modules.databases.users import get_user_data


class ApiService:

    def __init__(self) -> None:
        self.redis_cursor = get_redis_cursor()
        self.psql_connect, self.psql_cursor = get_postgresql_connection()


    def __del__(self) -> None:
        self.redis_cursor.close()
        self.psql_cursor.close()
        self.psql_connect.close()


    def get_user_banalce(
            self,
            user_id: int,
    ) -> UserBalance:
        """Возвращает баланс пользователя"""

        user_data = get_user_data(user_id, self.psql_cursor)
        return UserBalance(user_id=user_data.user_id, balance=user_data.coins)


    def get_user_transactions(
            self,
            user_id: int,
            type: TransactionType,
            offset: int,
            limit: int
    ) -> list[Transaction | None]:
        """Возвращает переводы пользователя"""

        transactions = TransferCoinsService.get_user_transfers(
            user_id, TransferCoinsType(type.value), offset, limit, self.psql_cursor,
            convert_type=False
        )
        transactions = [Transaction(**x) for x in transactions]

        return transactions


    def user_verification(
            self,
            search_id: int
    ) -> bool:
        """Проверяет пользователя (Подробности к владельцам проекта)"""

        user_data = get_user_data(search_id, self.psql_cursor)

        if user_data is None:
            return False

        if user_data.banned:
            return False

        if (
            user_data.all_win >= 20_000_000 or
            user_data.all_lost >= 20_000_000 or
            user_data.status == UserStatus.ADMIN
        ):
            return True

        return False


    def send_coins(
            self,
            sender_id: int,
            recipient_id: int,
            amount: int
    ) -> Transaction:
        """Переводит коины пользователю"""

        checking = TransferCoinsService.check_possibility(
            sender_id, recipient_id, amount, self.psql_cursor
        )

        if checking.access is False:
            raise HTTPException(status_code=403, detail=checking.error)

        transaction = TransferCoinsService.send_coins(
            sender_id=sender_id, recipient_id=recipient_id,
            amount=amount, psql_cursor=self.psql_cursor
        ).dict()
        transaction["created_at"] = str(transaction["created_at"])

        return Transaction(**transaction)


    def set_callback_address(
            self,
            user_id: int,
            url: str
    ) -> SetCallback:
        """Устанавливает callback адрес"""

        callback = CallbackService.update_user_callback(
            user_id=user_id, callback_url=url,
            psql_cursor=self.psql_cursor
        )

        return SetCallback(
            callback_url=callback.callback_url,
            callback_secret=callback.callback_secret
        )


    def drop_callback_address(
        self,
        user_id: int
    ) -> DropCallback:
        """Удаляет callback адрес"""

        callback = CallbackService.delete_user_callback(
            user_id=user_id, psql_cursor=self.psql_cursor
        )

        return DropCallback(response=callback.response)
