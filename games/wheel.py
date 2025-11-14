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


WHEEL_RED_NUMBER = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
WHEEL_BLACK_NUMBER = [2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35]
WHEEL_GREEN_NUMBER = [0]
WHEEL_ALL_NUMBERS = WHEEL_RED_NUMBER + WHEEL_BLACK_NUMBER + WHEEL_GREEN_NUMBER
WHEEL_STRING_GREEN_NUMBER = [str(x) for x in WHEEL_GREEN_NUMBER]
WHEEL_STRING_ALL_NUMBERS = [str(x) for x in WHEEL_ALL_NUMBERS]
WHEEL_MIN_NUMBER = min(WHEEL_ALL_NUMBERS)
WHEEL_MAX_NUMBER = max(WHEEL_ALL_NUMBERS)


class WheelResult(BaseModel):
    number: str
    color: str
    even_odd: str


class WheelGameModel(BaseGameModel):

    @staticmethod
    def _get_color_by_number(number: int) -> str:
        """Возвращает цвет числа"""

        if number in WHEEL_RED_NUMBER:
            return "red"

        if number in WHEEL_BLACK_NUMBER:
            return "black"

        if number in WHEEL_GREEN_NUMBER:
            return "green"

        raise ValueError()


    @classmethod
    def create_game(cls, chat_id: int, psql_cursor: DictCursor) -> dict:

        number = random.choice(WHEEL_ALL_NUMBERS)
        color = cls._get_color_by_number(number)
        even_odd = "empty" if number == 0 else "even" if number % 2 == 0 else "odd"
        game_result = WheelResult(number=number, color=color, even_odd=even_odd)

        str_hash = f"{number}|{color}|{cls.get_secret_game_key(20)}"
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
            "game_mode": Games.WHEEL.value,
            "game_result": json.dumps(game_result.json()),
            "str_hash": str_hash,
            "enc_hash": enc_hash
        })

        return game_result.dict()


    @classmethod
    def format_game_result(cls, game_result: dict) -> WheelResult:

        return WheelResult(**game_result)


    @classmethod
    def is_winning(cls, game_result: WheelResult, rate_type: str) -> bool:

        if "-" in rate_type:
            rate_range_start, rate_range_end = map(int, rate_type.split("-"))
            rate_range = [str(x) for x in range(rate_range_start, rate_range_end + 1)]
        else:
            rate_range = []

        return (
            rate_type == game_result.number or
            rate_type == game_result.color or

            rate_type == game_result.even_odd and
            game_result.number not in WHEEL_STRING_GREEN_NUMBER or

            "-" in rate_type and
            game_result.number in rate_range
        )


    @classmethod
    def get_coefficient(
            cls,
            rate_type: str,
            game_result: WheelResult,
            *,
            calculate_winnings: bool = False
    ) -> int | float:

        if rate_type in [
            "red", "black", "even", "odd",
            "1-18", "19-36"
        ]:
            return 2

        if rate_type in ["1-12", "13-24", "25-36"]:
            return 3

        if rate_type.isdecimal():
            if calculate_winnings:
                return 35
            return 28

        raise ValueError()


    @classmethod
    def get_all_rates_type(cls) -> list:

        return [
            "red", "black", "even", "odd",
            "1-18", "19-36", "1-12", "13-24", "25-36"
        ] + WHEEL_STRING_ALL_NUMBERS


    @classmethod
    def get_rate_type_ru(cls, rate_type: str) -> str:

        if rate_type == "red":
            return "красное"

        elif rate_type == "black":
            return "черное"

        elif rate_type == "green":
            return "зеленое"

        elif rate_type == "even":
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
            (1, ["red", "black"]),
            (1, ["even", "odd"]),
            (1, ["1-18", "19-36"]),
            (2, ["1-12", "13-24", "25-36"])
        )
        return cls.logic_opposite_rates(rate_type, user_rates_type, opposite_rates)


    @classmethod
    def check_accrual_top_points(cls, rates: list[RatesSchema | None]) -> bool:

        accrual = []
        grouped_rates = cls._group_rates_by_type(rates)

        accrual.append(cls._check_coverage_bets(grouped_rates))
        accrual.append(cls._check_opposite_bets(
            grouped_rates,
            opposite_bets=(("red", "black"), ("even", "odd"), ("1-18", "19-36"))
        ))

        return all(accrual)


    @classmethod
    def get_result_message(cls, game_result: WheelResult, short: bool = False) -> str:

        number = game_result.number
        color = cls.get_rate_type_ru(game_result.color)

        if short:
            return f"{number}, {color}"

        return f"Выпало число {number}, {color}"


    @classmethod
    async def get_result_attachment(cls, game_result: WheelResult) -> str:

        attachment = {
            "0": "photo-207204376_457441620",
            "1": "photo-207204376_457441606",
            "2": "photo-207204376_457441626",
            "3": "photo-207204376_457441618",
            "4": "photo-207204376_457441624",
            "5": "photo-207204376_457441639",
            "6": "photo-207204376_457441630",
            "7": "photo-207204376_457441614",
            "8": "photo-207204376_457441636",
            "9": "photo-207204376_457441610",
            "10": "photo-207204376_457441638",
            "11": "photo-207204376_457441634",
            "12": "photo-207204376_457441616",
            "13": "photo-207204376_457441632",
            "14": "photo-207204376_457441608",
            "15": "photo-207204376_457441622",
            "16": "photo-207204376_457441604",
            "17": "photo-207204376_457441628",
            "18": "photo-207204376_457441612",
            "19": "photo-207204376_457441623",
            "20": "photo-207204376_457441607",
            "21": "photo-207204376_457441625",
            "22": "photo-207204376_457441611",
            "23": "photo-207204376_457441637",
            "24": "photo-207204376_457441603",
            "25": "photo-207204376_457441627",
            "26": "photo-207204376_457441619",
            "27": "photo-207204376_457441631",
            "28": "photo-207204376_457441615",
            "29": "photo-207204376_457441613",
            "30": "photo-207204376_457441635",
            "31": "photo-207204376_457441609",
            "32": "photo-207204376_457441621",
            "33": "photo-207204376_457441605",
            "34": "photo-207204376_457441629",
            "35": "photo-207204376_457441617",
            "36": "photo-207204376_457441633"
        }

        return attachment[game_result.number]

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
                InlineKeyboardButton(text="Четное", callback_data='{"rate":"even"}'),
                InlineKeyboardButton(text="На число", callback_data='{"rate":"number"}'),
                InlineKeyboardButton(text="Нечетное", callback_data='{"rate":"odd"}')
            ],
            [
                InlineKeyboardButton(text="1-18", callback_data='{"rate":"1-18"}'),
                InlineKeyboardButton(text="19-36", callback_data='{"rate":"19-36"}')
            ],
            [
                InlineKeyboardButton(text="1-12", callback_data='{"rate":"1-12"}'),
                InlineKeyboardButton(text="13-24", callback_data='{"rate":"13-24"}'),
                InlineKeyboardButton(text="25-36", callback_data='{"rate":"25-36"}')
            ],
            [
                InlineKeyboardButton(text="Красное", callback_data='{"rate":"red"}'),
                InlineKeyboardButton(text="0", callback_data='{"rate":"0"}'),
                InlineKeyboardButton(text="Черное", callback_data='{"rate":"black"}')
            ]
        ]

        return InlineKeyboardMarkup(inline_keyboard=buttons)


    @classmethod
    def handler_current_rate(
            cls,
            user_data: UserSchema,
            chat_data: ChatSchema,
            game_result: WheelResult,
            user_chat_data: UserChatSchema,
            message: str,
            payload: dict | None,
            psql_cursor: DictCursor
    ) -> tuple[str, str | None] | None:

        user_id = user_data.user_id
        chat_id = chat_data.chat_id
        rate_type = None

        if payload is not None and payload.get("event") == "update_rate_type":
            rate_type = payload.get("rate_type")
            cls.update_current_rate(chat_id, user_id, rate_type, psql_cursor)

        elif user_chat_data.current_rate == "set_number":

            rate_types = []
            for item in message.split(" "):
                item_split_hyphen = item.split("-")

                if item.isdecimal() and item in WHEEL_STRING_ALL_NUMBERS:
                    rate_types.append(int(item))

                elif (
                    len(item_split_hyphen) == 2 and
                    item_split_hyphen[0].isdecimal() and
                    item_split_hyphen[1].isdecimal()
                ):
                    first_number, last_number = map(int, item_split_hyphen)

                    if (
                        first_number >= WHEEL_MIN_NUMBER and
                        last_number <= WHEEL_MAX_NUMBER and
                        last_number > first_number
                    ):
                        rate_types.extend(list(range(first_number, last_number+1)))

            rate_types = sorted(set(rate_types))
            rate_type = " ".join(map(str, rate_types)) if rate_types else None
            cls.update_current_rate(chat_id, user_id, rate_type, psql_cursor)

            if rate_type is None:
                return f"{user_data.vk_name}, не получилось распознать ставку ", None

        if rate_type is not None:

            if rate_type == "set_number":
                response = f"{user_data.vk_name}, на какое число ставишь?"
                keyboard = None

            else:
                response, keyboard = cls.get_keyboard_pay_rates(
                    chat_data, user_chat_data, rate_type, game_result, psql_cursor
                )
            return response, keyboard

        return None


BaseGameModel.GAMES_MODEL[Games.WHEEL] = WheelGameModel
