import json
import random
import hashlib
from pydantic import BaseModel
from psycopg2.extras import DictCursor
import json
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

from games.base import BaseGameModel

from schemas.users import UserSchema
from schemas.chats import ChatSchema
from schemas.games import Games
from schemas.rates import RatesSchema
from schemas.user_in_chat import UserChatSchema


DOUBLE_COEFFICIENT = [2, 3, 5, 50]
DOUBLE_COEFFICIENT_CHANCES = [50, 33, 20, 2]  # Шансы появления коэффициента
DOUBLE_STRING_COEFFICIENT = [str(x) for x in DOUBLE_COEFFICIENT]


class DoubleResult(BaseModel):
    coefficient: str


class DoubleGameModel(BaseGameModel):

    @classmethod
    def create_game(cls, chat_id: int, psql_cursor: DictCursor) -> dict:

        coefficient = random.choices(DOUBLE_COEFFICIENT, DOUBLE_COEFFICIENT_CHANCES)[0]
        game_result = DoubleResult(coefficient=coefficient)

        str_hash = f"x{coefficient}|{cls.get_secret_game_key(20)}"
        enc_hash = hashlib.md5(str_hash.encode()).hexdigest()

        psql_cursor.execute("""
            INSERT INTO games (
                chat_id, game_mode, game_result,
                str_hash, enc_hash
            ) VALUES (
                %(chat_id)s, %(game_mode)s, %(game_result)s,
                %(str_hash)s, %(enc_hash)s
            )
        """, {
            "chat_id": chat_id,
            "game_mode": Games.DOUBLE.value,
            "game_result": json.dumps(game_result.json()),
            "str_hash": str_hash,
            "enc_hash": enc_hash
        })

        return game_result.dict()


    @classmethod
    def format_game_result(cls, game_result: dict) -> DoubleResult:

        return DoubleResult(**game_result)


    @classmethod
    def is_winning(cls, game_result: DoubleResult, rate_type: str) -> bool:

        return game_result.coefficient == rate_type.replace("x", "", 1)


    @classmethod
    def get_coefficient(
            cls,
            rate_type: str,
            game_result: DoubleResult,
            *,
            calculate_winnings: bool = False
    ) -> int | float:

        return int(rate_type.replace("x", "", 1))


    @classmethod
    def get_all_rates_type(cls) -> list:

        return DOUBLE_STRING_COEFFICIENT


    @classmethod
    def get_rate_type_ru(cls, rate_type: str) -> str:

        return f"x{rate_type}"


    @classmethod
    def check_opposite_rates(cls, rate_type: str, user_rates_type: list[str | None]) -> bool:

        opposite_rates = ((2, DOUBLE_STRING_COEFFICIENT), )
        return cls.logic_opposite_rates(rate_type, user_rates_type, opposite_rates)


    @classmethod
    def check_accrual_top_points(cls, rates: list[RatesSchema | None]) -> bool:

        return cls._check_coverage_bets(rates)


    @classmethod
    def get_result_message(cls, game_result: DoubleResult, short: bool = False) -> str:

        rate_type_ru = cls.get_rate_type_ru(game_result.coefficient)

        if short:
            return rate_type_ru

        return f"Выпал множитель {rate_type_ru}"


    @classmethod
    async def get_result_attachment(cls, game_result: DoubleResult) -> str:

        attachment = {
            "2": [
                "photo-207204376_457441504",
                "photo-207204376_457441506",
                "photo-207204376_457441509",
                "photo-207204376_457441511",
            ],
            "3": [
                "photo-207204376_457441503",
                "photo-207204376_457441505",
                "photo-207204376_457441510",
            ],
            "5": ["photo-207204376_457441507"],
            "50": ["photo-207204376_457441508"]
        }
        return random.choice(attachment[game_result.coefficient])


    @classmethod
    def get_game_keyboard(cls, game_result: dict | None) -> ReplyKeyboardMarkup:

        buttons = [
            [
                KeyboardButton(text="Банк"),
                KeyboardButton(text="Повторить"),
                KeyboardButton(text="Баланс")
            ],
            [
                KeyboardButton(text="x2"),
                KeyboardButton(text="x3"),
                KeyboardButton(text="x5")
            ],
            [KeyboardButton(text="x50")]
        ]

        return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


    @classmethod
    def handler_current_rate(
            cls,
            user_data: UserSchema,
            chat_data: ChatSchema,
            game_result: DoubleResult,
            user_chat_data: UserChatSchema,
            message: str,
            payload: dict | None,
            psql_cursor: DictCursor
    ) -> tuple[str, str | None] | None:

        if payload is not None and payload.get("event") == "update_rate_type":
            rate_type = payload.get("rate_type")
            cls.update_current_rate(chat_data.chat_id, user_data.user_id, rate_type, psql_cursor)
            return cls.get_keyboard_pay_rates(chat_data, user_chat_data, rate_type, game_result, psql_cursor)

        return None


BaseGameModel.GAMES_MODEL[Games.DOUBLE] = DoubleGameModel
