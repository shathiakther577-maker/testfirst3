from pydantic import BaseModel
from psycopg2.extras import DictCursor

from services.promocode import PromoCodeService

from modules.additional import format_number
from modules.databases.users import get_user_data, set_coins


class ResetUserData(BaseModel):
    user_id: int  # Идентификатор пользователя
    user_name: str  # Имя пользователя

    balance: int  # Сумма списанная с баланса
    promocode: int  # Сумма удаленных промокодов

    @property
    def total_amount(self) -> int:
        """Возвращает общую сумму списание coins"""

        return self.balance + self.promocode


    @property
    def reset_message(self) -> str:
        """Возвращает текст сколько и где было списано"""

        return f"""
            {format_number(self.balance)} BC с баланса обнулены
            {format_number(self.promocode)} BC с промокодов обнулены
        """


class ResetUserServices:

    @classmethod
    def reset_data(cls, user_id: int, psql_cursor: DictCursor) -> ResetUserData:
        """Обнуляет данные пользователя"""

        user_data = get_user_data(user_id, psql_cursor)
        set_coins(user_id, 0, psql_cursor)

        promocodes = PromoCodeService.get_user_pormocodes(user_id, psql_cursor)
        [PromoCodeService.delete_promocode(x.name, psql_cursor) for x in promocodes]

        return ResetUserData(
            user_id=user_id,
            user_name=user_data.full_name,
            balance=user_data.coins,
            promocode=sum([int(x.reward * x.quantity) for x in promocodes])
        )
