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


LUCKY_COINS_CUPS = [1, 2, 3, 4, 5]
LUCKY_COINS_STRING_CUPS = [str(x) for x in LUCKY_COINS_CUPS]
LUCKY_COINS_COEFFICIENT = [2, 3, 5, 7, 15]
LUCKY_COINS_COEFFICIENT_CHANCES = [15, 25, 45, 10, 5]


class LuckyCoinsResult(BaseModel):
    cup_number: str
    coefficient: int


class LuckyCoinsGameModel(BaseGameModel):

    @classmethod
    def create_game(cls, chat_id: int, psql_cursor: DictCursor) -> dict:

        cup_number = random.choice(LUCKY_COINS_CUPS)
        coefficient = random.choices(LUCKY_COINS_COEFFICIENT, LUCKY_COINS_COEFFICIENT_CHANCES)[0]
        game_result = LuckyCoinsResult(cup_number=cup_number, coefficient=coefficient)

        str_hash = f"{cup_number}|x{coefficient}|{cls.get_secret_game_key(20)}"
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
            "game_mode": Games.LUCKY_COINS.value,
            "game_result": json.dumps(game_result.json()),
            "str_hash": str_hash,
            "enc_hash": enc_hash
        })

        return game_result.dict()


    @classmethod
    def format_game_result(cls, game_result: dict) -> LuckyCoinsResult:

        return LuckyCoinsResult(**game_result)


    @classmethod
    def is_winning(cls, game_result: LuckyCoinsResult, rate_type: str) -> bool:

        return game_result.cup_number == rate_type


    @classmethod
    def get_coefficient(
            cls,
            rate_type: str,
            game_result: LuckyCoinsResult,
            *,
            calculate_winnings: bool = False
    ) -> int | float:

        if calculate_winnings:
            return game_result.coefficient

        return 12


    @classmethod
    def get_all_rates_type(cls) -> list:

        return LUCKY_COINS_STRING_CUPS


    @classmethod
    def get_rate_type_ru(cls, rate_type: str) -> str:

        return f"{rate_type} стаканчик"


    @classmethod
    def check_opposite_rates(
            cls,
            rate_type: str,
            user_rates_type: list[str | None]
    ) -> bool:

        opposite_rates = ((2, LUCKY_COINS_STRING_CUPS), )
        return cls.logic_opposite_rates(rate_type, user_rates_type, opposite_rates)


    @classmethod
    def check_accrual_top_points(cls, rates: list[RatesSchema | None]) -> bool:

        return cls._check_coverage_bets(rates)


    @classmethod
    def get_result_message(cls, game_result: LuckyCoinsResult, short: bool = False) -> str:

        cup_number = game_result.cup_number
        coefficient_ru = f"(x{game_result.coefficient})"

        if short:
            return f"{cup_number} {coefficient_ru}"

        return f"Монетка оказалась под {cup_number} стаканчиком! {coefficient_ru}"


    @classmethod
    async def get_result_attachment(cls, game_result: LuckyCoinsResult) -> str:

        attachment = {
            "1": {
                2: "photo-207204376_457441419",
                3: "photo-207204376_457441420",
                5: "photo-207204376_457441396",
                7: "photo-207204376_457441397",
                15: "photo-207204376_457441398"
            },
            "2": {
                2: "photo-207204376_457441399",
                3: "photo-207204376_457441400",
                5: "photo-207204376_457441401",
                7: "photo-207204376_457441402",
                15: "photo-207204376_457441403"
            },
            "3": {
                2: "photo-207204376_457441404",
                3: "photo-207204376_457441405",
                5: "photo-207204376_457441406",
                7: "photo-207204376_457441407",
                15: "photo-207204376_457441408"
            },
            "4": {
                2: "photo-207204376_457441409",
                3: "photo-207204376_457441410",
                5: "photo-207204376_457441411",
                7: "photo-207204376_457441412",
                15: "photo-207204376_457441413"
            },
            "5": {
                2: "photo-207204376_457441414",
                3: "photo-207204376_457441415",
                5: "photo-207204376_457441416",
                7: "photo-207204376_457441417",
                15: "photo-207204376_457441418"
            }
        }
        return attachment[game_result.cup_number][game_result.coefficient]


    @classmethod
    def get_game_keyboard(cls, game_result: dict | None) -> ReplyKeyboardMarkup:

        buttons = [
            [
                KeyboardButton(text="Банк"),
                KeyboardButton(text="Повторить"),
                KeyboardButton(text="Баланс")
            ],
            [
                KeyboardButton(text="1"),
                KeyboardButton(text="2"),
                KeyboardButton(text="3")
            ],
            [
                KeyboardButton(text="4"),
                KeyboardButton(text="5")
            ]
        ]

        return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


    @classmethod
    def handler_current_rate(
            cls,
            user_data: UserSchema,
            chat_data: ChatSchema,
            game_result: LuckyCoinsResult,
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


BaseGameModel.GAMES_MODEL[Games.LUCKY_COINS] = LuckyCoinsGameModel
