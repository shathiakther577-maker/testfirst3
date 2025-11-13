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


MEGA_DICE_NUMBER = [1, 2, 3, 4, 5, 6]
MEGA_DICE_COLOR = ["red", "black"]


class MegaDiceResult(BaseModel):

    dice_1: str
    dice_2: str
    dice_sum: str
    color: str


class MegaDiceGameModel(BaseGameModel):

    @classmethod
    def create_game(cls, chat_id: int, psql_cursor: DictCursor) -> dict:

        dice_1 = random.choice(MEGA_DICE_NUMBER)
        dice_2 = random.choice(MEGA_DICE_NUMBER)
        dice_sum = dice_1 + dice_2
        color = random.choice(MEGA_DICE_COLOR)
        game_result = MegaDiceResult(dice_1=dice_1, dice_2=dice_2, dice_sum=dice_sum, color=color)

        str_hash = f"{dice_1}|{dice_2}|{color}|{cls.get_secret_game_key(20)}"
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
            "game_mode": Games.MEGA_DICE.value,
            "game_result": json.dumps(game_result.json()),
            "str_hash": str_hash,
            "enc_hash": enc_hash
        })

        return game_result.dict()


    @classmethod
    def format_game_result(cls, game_result: dict) -> MegaDiceResult:

        return MegaDiceResult(**game_result)


    @classmethod
    def is_winning(cls, game_result: MegaDiceResult, rate_type: str) -> bool:

        if "-" in rate_type:
            start, stop = map(int, rate_type.split("-"))
            rate_range = [str(x) for x in range(start, stop+1)]
        else:
            rate_range = []

        return (
            rate_type == game_result.dice_sum or
            rate_type == game_result.color or

            "-" in rate_type and
            game_result.dice_sum in rate_range
        )


    @classmethod
    def get_coefficient(
            cls,
            rate_type: str,
            game_result: MegaDiceResult,
            *,
            calculate_winnings: bool = False
    ) -> int | float:

        if rate_type == "5-8":
            return 1.5

        if rate_type in MEGA_DICE_COLOR:
            return 1.9

        if rate_type == "9-12":
            return 3

        if rate_type == "2-4":
            return 5

        if rate_type == "7":
            return 5.8

        if rate_type in ["6", "8"]:
            return 6

        if rate_type in ["5", "9"]:
            return 8

        if rate_type in ["4", "10"]:
            return 11

        if rate_type in ["3", "11"]:
            return 17

        if rate_type in ["2", "12"]:
            return 34

        raise ValueError()


    @classmethod
    def get_all_rates_type(cls) -> list:

        return [
            "2", "3", "4", "5", "6", "7",
            "8", "9", "10", "11", "12",
            "2-4", "5-8", "9-12"
        ] + MEGA_DICE_COLOR


    @classmethod
    def get_rate_type_ru(cls, rate_type: str) -> str:

        if rate_type == "red":
            return "красное"

        elif rate_type == "black":
            return "черное"

        else:
            return rate_type


    @classmethod
    def check_opposite_rates(cls, rate_type: str, user_rates_type: list[str | None]) -> bool:

        opposite_rates = (
            (1, MEGA_DICE_COLOR),
            (2, ["2-4", "5-8", "9-12"]),
        )
        return cls.logic_opposite_rates(rate_type, user_rates_type, opposite_rates)


    @classmethod
    def check_accrual_top_points(cls, rates: list[RatesSchema | None]) -> bool:

        accrual = []
        grouped_rates = cls._group_rates_by_type(rates)

        accrual.append(cls._check_coverage_bets(grouped_rates))
        accrual.append(cls._check_opposite_bets(
            grouped_rates,
            opposite_bets=(("red", "black"),)
        ))

        return all(accrual)


    @classmethod
    def get_result_message(cls, game_result: MegaDiceResult, short: bool = False) -> str:

        dice_1 = game_result.dice_1
        dice_2 = game_result.dice_2
        color = cls.get_rate_type_ru(game_result.color)

        if short:
            return f"{game_result.dice_sum} {color}, {dice_1=} {dice_2=}"

        return f"Выпали кубики {dice_1} и {dice_2}, {color}"


    @classmethod
    async def get_result_attachment(cls, game_result: MegaDiceResult) -> str:

        attachment = {
            "red": {
                "1_1": "photo-207204376_457441452",
                "1_2": "photo-207204376_457441458",
                "1_3": "photo-207204376_457441464",
                "1_4": "photo-207204376_457441470",
                "1_5": "photo-207204376_457441476",
                "1_6": "photo-207204376_457441482",
                "2_1": "photo-207204376_457441453",
                "2_2": "photo-207204376_457441459",
                "2_3": "photo-207204376_457441465",
                "2_4": "photo-207204376_457441471",
                "2_5": "photo-207204376_457441477",
                "2_6": "photo-207204376_457441483",
                "3_1": "photo-207204376_457441454",
                "3_2": "photo-207204376_457441460",
                "3_3": "photo-207204376_457441466",
                "3_4": "photo-207204376_457441472",
                "3_5": "photo-207204376_457441478",
                "3_6": "photo-207204376_457441484",
                "4_1": "photo-207204376_457441455",
                "4_2": "photo-207204376_457441461",
                "4_3": "photo-207204376_457441467",
                "4_4": "photo-207204376_457441473",
                "4_5": "photo-207204376_457441479",
                "4_6": "photo-207204376_457441485",
                "5_1": "photo-207204376_457441456",
                "5_2": "photo-207204376_457441462",
                "5_3": "photo-207204376_457441468",
                "5_4": "photo-207204376_457441474",
                "5_5": "photo-207204376_457441480",
                "5_6": "photo-207204376_457441486",
                "6_1": "photo-207204376_457441457",
                "6_2": "photo-207204376_457441463",
                "6_3": "photo-207204376_457441469",
                "6_4": "photo-207204376_457441475",
                "6_5": "photo-207204376_457441481",
                "6_6": "photo-207204376_457441487"
            },
            "black": {
                "1_1": "photo-207204376_457441488",
                "1_2": "photo-207204376_457441489",
                "1_3": "photo-207204376_457441490",
                "1_4": "photo-207204376_457441491",
                "1_5": "photo-207204376_457441492",
                "1_6": "photo-207204376_457441493",
                "2_1": "photo-207204376_457441494",
                "2_2": "photo-207204376_457441422",
                "2_3": "photo-207204376_457441423",
                "2_4": "photo-207204376_457441424",
                "2_5": "photo-207204376_457441425",
                "2_6": "photo-207204376_457441426",
                "3_1": "photo-207204376_457441427",
                "3_2": "photo-207204376_457441428",
                "3_3": "photo-207204376_457441429",
                "3_4": "photo-207204376_457441430",
                "3_5": "photo-207204376_457441431",
                "3_6": "photo-207204376_457441432",
                "4_1": "photo-207204376_457441433",
                "4_2": "photo-207204376_457441434",
                "4_3": "photo-207204376_457441435",
                "4_4": "photo-207204376_457441436",
                "4_5": "photo-207204376_457441437",
                "4_6": "photo-207204376_457441438",
                "5_1": "photo-207204376_457441439",
                "5_2": "photo-207204376_457441440",
                "5_3": "photo-207204376_457441441",
                "5_4": "photo-207204376_457441442",
                "5_5": "photo-207204376_457441443",
                "5_6": "photo-207204376_457441444",
                "6_1": "photo-207204376_457441445",
                "6_2": "photo-207204376_457441447",
                "6_3": "photo-207204376_457441448",
                "6_4": "photo-207204376_457441449",
                "6_5": "photo-207204376_457441450",
                "6_6": "photo-207204376_457441451"
            }
        }
        return attachment[game_result.color][f"{game_result.dice_1}_{game_result.dice_2}"]


    @classmethod
    def get_game_keyboard(cls, game_result: dict | None) -> ReplyKeyboardMarkup:

        buttons = [
            [
                KeyboardButton(text="Банк"),
                KeyboardButton(text="Повторить"),
                KeyboardButton(text="Баланс")
            ],
            [
                KeyboardButton(text="Красное (x1.9)"),
                KeyboardButton(text="Черное (x1.9)")
            ],
            [
                KeyboardButton(text="2 (x34)"),
                KeyboardButton(text="3 (x17)"),
                KeyboardButton(text="4 (x11)")
            ],
            [
                KeyboardButton(text="5 (x8)"),
                KeyboardButton(text="6 (x6)"),
                KeyboardButton(text="7 (x5.8)"),
                KeyboardButton(text="8 (x6)")
            ],
            [
                KeyboardButton(text="9 (x8)"),
                KeyboardButton(text="10 (x11)"),
                KeyboardButton(text="11 (x17)"),
                KeyboardButton(text="12 (x34)")
            ],
            [
                KeyboardButton(text="2-4 (x5)"),
                KeyboardButton(text="5-8 (x1.5)"),
                KeyboardButton(text="9-12 (x3)")
            ]
        ]

        return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


    @classmethod
    def handler_current_rate(
            cls,
            user_data: UserSchema,
            chat_data: ChatSchema,
            game_result: MegaDiceResult,
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


BaseGameModel.GAMES_MODEL[Games.MEGA_DICE] = MegaDiceGameModel
