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


UNDER7OVER_NUMBER = [1, 2, 3, 4, 5, 6]
UNDER7OVER_RATES_TYPE = ["over", "equal", "under"]  # < = >


class Under7OverResult(BaseModel):

    dice_1: str
    dice_2: str
    dice_sum: str


class Under7OverGameModel(BaseGameModel):

    @classmethod
    def create_game(cls, chat_id: int, psql_cursor: DictCursor) -> dict:

        dice_1 = random.choice(UNDER7OVER_NUMBER)
        dice_2 = random.choice(UNDER7OVER_NUMBER)
        dice_sum = dice_1 + dice_2
        game_result = Under7OverResult(dice_1=dice_1, dice_2=dice_2, dice_sum=dice_sum)

        str_hash = f"{dice_1}|{dice_2}|{cls.get_secret_game_key(20)}"
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
            "game_mode": Games.UNDER_7_OVER.value,
            "game_result": json.dumps(game_result.json()),
            "str_hash": str_hash,
            "enc_hash": enc_hash
        })

        return game_result.dict()


    @classmethod
    def format_game_result(cls, game_result: dict) -> Under7OverResult:

        return Under7OverResult(**game_result)


    @classmethod
    def is_winning(cls, game_result: Under7OverResult, rate_type: str) -> bool:

        dice_sum = int(game_result.dice_sum)

        return (
            rate_type == "over" and dice_sum < 7 or
            rate_type == "equal" and dice_sum == 7 or
            rate_type == "under" and dice_sum > 7
        )


    @classmethod
    def get_coefficient(
            cls,
            rate_type: str,
            game_result: Under7OverResult,
            *,
            calculate_winnings: bool = False
    ) -> int | float:

        if rate_type in ["under", "over"]:
            return 2.3

        if rate_type == "equal":
            return 5.8

        raise ValueError()


    @classmethod
    def get_all_rates_type(cls) -> list:

        return UNDER7OVER_RATES_TYPE


    @classmethod
    def get_rate_type_ru(cls, rate_type: str) -> str:

        if rate_type == "under":
            return "выпадение числа больше 7"

        if rate_type == "equal":
            return "выпадение 7"

        if rate_type == "over":
            return "выпадение числа меньше 7"


    @classmethod
    def check_opposite_rates(cls, rate_type: str, user_rates_type: list[str | None]) -> bool:

        opposite_rates = ((1, UNDER7OVER_RATES_TYPE), )
        return cls.logic_opposite_rates(rate_type, user_rates_type, opposite_rates)


    @classmethod
    def check_accrual_top_points(cls, rates: list[RatesSchema | None]) -> bool:

        return cls._check_coverage_bets(rates)


    @classmethod
    def get_result_message(cls, game_result: Under7OverResult, short: bool = False) -> str:

        dice_1 = game_result.dice_1
        dice_2 = game_result.dice_2
        dice_sum = game_result.dice_sum

        if short:
            return f"{dice_sum}"

        return f"Выпали числа {dice_1} и {dice_2}, результат: {dice_sum}"


    @classmethod
    async def get_result_attachment(cls, game_result: Under7OverResult) -> str:

        attachment = {
            "1_1": "photo-207204376_457441584",
            "1_2": "photo-207204376_457441590",
            "1_3": "photo-207204376_457441596",
            "1_4": "photo-207204376_457441602",
            "1_5": "photo-207204376_457441572",
            "1_6": "photo-207204376_457441578",
            "2_1": "photo-207204376_457441585",
            "2_2": "photo-207204376_457441591",
            "2_3": "photo-207204376_457441597",
            "2_4": "photo-207204376_457441567",
            "2_5": "photo-207204376_457441573",
            "2_6": "photo-207204376_457441579",
            "3_1": "photo-207204376_457441586",
            "3_2": "photo-207204376_457441592",
            "3_3": "photo-207204376_457441598",
            "3_4": "photo-207204376_457441568",
            "3_5": "photo-207204376_457441574",
            "3_6": "photo-207204376_457441580",
            "4_1": "photo-207204376_457441587",
            "4_2": "photo-207204376_457441593",
            "4_3": "photo-207204376_457441599",
            "4_4": "photo-207204376_457441569",
            "4_5": "photo-207204376_457441575",
            "4_6": "photo-207204376_457441581",
            "5_1": "photo-207204376_457441588",
            "5_2": "photo-207204376_457441594",
            "5_3": "photo-207204376_457441600",
            "5_4": "photo-207204376_457441570",
            "5_5": "photo-207204376_457441576",
            "5_6": "photo-207204376_457441582",
            "6_1": "photo-207204376_457441589",
            "6_2": "photo-207204376_457441595",
            "6_3": "photo-207204376_457441601",
            "6_4": "photo-207204376_457441571",
            "6_5": "photo-207204376_457441577",
            "6_6": "photo-207204376_457441583"
        }

        return attachment[f"{game_result.dice_1}_{game_result.dice_2}"]


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
                InlineKeyboardButton(text="Под", callback_data='{"rate":"under"}'),
                InlineKeyboardButton(text="7", callback_data='{"rate":"7"}'),
                InlineKeyboardButton(text="Над", callback_data='{"rate":"over"}')
            ]
        ]

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @classmethod
    def handler_current_rate(
            cls,
            user_data: UserSchema,
            chat_data: ChatSchema,
            game_result: Under7OverResult,
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


BaseGameModel.GAMES_MODEL[Games.UNDER_7_OVER] = Under7OverGameModel
