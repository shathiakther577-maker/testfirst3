import json
import random
import hashlib
from pydantic import BaseModel
from psycopg2.extras import DictCursor
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

from games.base import BaseGameModel

from schemas.users import UserSchema
from schemas.chats import ChatSchema
from schemas.games import Games
from schemas.rates import RatesSchema
from schemas.user_in_chat import UserChatSchema


DICE_NUMBER = [1, 2, 3, 4, 5, 6]
DICE_STRING_NUMBER = [str(x) for x in DICE_NUMBER]


class DiceResult(BaseModel):
    numer: str
    even_odd: str


class DiceGameModel(BaseGameModel):

    @classmethod
    def create_game(cls, chat_id: int, psql_cursor: DictCursor) -> dict:

        number = random.choice(DICE_NUMBER)
        even_odd = "even" if number % 2 == 0 else "odd"
        game_result = DiceResult(numer=number, even_odd=even_odd)

        str_hash = f"{number}|{even_odd}|{cls.get_secret_game_key(20)}"
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
            "game_mode": Games.DICE.value,
            "game_result": json.dumps(game_result.json()),
            "str_hash": str_hash,
            "enc_hash": enc_hash
        })

        return game_result.dict()


    @classmethod
    def format_game_result(cls, game_result: dict) -> DiceResult:

        return DiceResult(**game_result)


    @classmethod
    def is_winning(cls, game_result: DiceResult, rate_type: str) -> bool:

        return (
            rate_type == game_result.numer or
            rate_type == game_result.even_odd
        )


    @classmethod
    def get_coefficient(
            cls,
            rate_type: str,
            game_result: DiceResult,
            *,
            calculate_winnings: bool = False
    ) -> int | float:

        if rate_type in ["even", "odd"]:
            return 1.9

        elif rate_type in DICE_STRING_NUMBER:
            return 5

        raise ValueError()


    @classmethod
    def get_all_rates_type(cls) -> list:

        return DICE_STRING_NUMBER + ["even", "odd"]


    @classmethod
    def get_rate_type_ru(cls, rate_type: str) -> str:

        if rate_type == "even":
            return "четное"

        elif rate_type == "odd":
            return "нечетное"

        else:
            return rate_type


    @classmethod
    def check_opposite_rates(
            cls,
            rate_type: str,
            user_rates_type: list[str | None]
    ) -> bool:

        opposite_rates = (
            (1, ["even", "odd"]),
            (3, DICE_STRING_NUMBER)
        )
        return cls.logic_opposite_rates(rate_type, user_rates_type, opposite_rates)


    @classmethod
    def check_accrual_top_points(cls, rates: list[RatesSchema | None]) -> bool:

        accrual = []
        grouped_rates = cls._group_rates_by_type(rates)

        accrual.append(cls._check_coverage_bets(grouped_rates))
        accrual.append(cls._check_opposite_bets(grouped_rates, opposite_bets=(("even", "odd"),)))

        return all(accrual)


    @classmethod
    def get_result_message(cls, game_result: DiceResult, short: bool = False) -> str:

        number = game_result.numer

        if short:
            return number

        return f"Выпало число {number}"


    @classmethod
    async def get_result_attachment(cls, game_result: DiceResult) -> str:

        attachment = {
            "1": "photo-207204376_457441497",
            "2": "photo-207204376_457441498",
            "3": "photo-207204376_457441499",
            "4": "photo-207204376_457441500",
            "5": "photo-207204376_457441501",
            "6": "photo-207204376_457441496"
        }

        return attachment[game_result.numer]


    @classmethod
    def get_game_keyboard(cls, game_result: dict | None) -> InlineKeyboardMarkup:
        """Возвращает inline-клавиатуру игры для Telegram"""
        
        buttons = [
            [
                InlineKeyboardButton(text="Банк", callback_data='{"event":"get_game_bank"}'),
                InlineKeyboardButton(text="Повторить", callback_data='{"event":"repeat_bet"}'),
                InlineKeyboardButton(text="Баланс", callback_data='{"event":"get_user_balance"}')
            ],
            [
                InlineKeyboardButton(text="1", callback_data='{"rate":"1"}'),
                InlineKeyboardButton(text="2", callback_data='{"rate":"2"}'),
                InlineKeyboardButton(text="3", callback_data='{"rate":"3"}')
            ],
            [
                InlineKeyboardButton(text="4", callback_data='{"rate":"4"}'),
                InlineKeyboardButton(text="5", callback_data='{"rate":"5"}'),
                InlineKeyboardButton(text="6", callback_data='{"rate":"6"}')
            ],
            [
                InlineKeyboardButton(text="Четное", callback_data='{"rate":"even"}'),
                InlineKeyboardButton(text="Нечетное", callback_data='{"rate":"odd"}')
            ]
        ]

        return InlineKeyboardMarkup(inline_keyboard=buttons)


    @classmethod
    def handler_current_rate(
            cls,
            user_data: UserSchema,
            chat_data: ChatSchema,
            game_result: DiceResult,
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


BaseGameModel.GAMES_MODEL[Games.DICE] = DiceGameModel
