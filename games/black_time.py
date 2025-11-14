import os
import json
import random
import hashlib
from pathlib import Path
from pydantic import BaseModel
from psycopg2.extras import DictCursor
import json
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

from settings import Config

from games.base import BaseGameModel
from painter import Painter

from schemas.users import UserSchema
from schemas.chats import ChatSchema
from schemas.games import Games
from schemas.rates import RatesSchema
from schemas.user_in_chat import UserChatSchema

# upload_photo будет реализован в modules.telegram.bot при необходимости


BLACK_TIME_BLUE_NUMBER = [1, 3, 5, 7, 9]
BLACK_TIME_RED_NUMBER = [2, 4, 6, 8, 10]


class BlackTimeResult(BaseModel):

    color: str
    count_cubes: str

    blue_sum: int
    blue_cubes: list[str]

    red_sum: int
    red_cubes: list[str]


class BlackTimeGameModel(BaseGameModel):


    @staticmethod
    def _get_win_color(blue_sum: int, red_sum: int) -> str:
        """Возвращает цвет который победил если сумма кубиков одинаковая возвращает ничью"""

        if blue_sum > red_sum:
            return "blue"

        elif red_sum > blue_sum:
            return "red"

        else:
            return "draw"


    @staticmethod
    def _is_draw(game_result: BlackTimeResult) -> bool:
        """Возвращает True если сумма кубиков равна"""

        return  game_result.blue_cubes == game_result.red_cubes


    @classmethod
    def create_game(cls, chat_id: int, psql_cursor: DictCursor) -> dict:

        blue_cubes = random.choices(BLACK_TIME_BLUE_NUMBER, k=random.randint(1, 5))
        blue_sum = sum(blue_cubes)

        red_cubes = random.choices(BLACK_TIME_RED_NUMBER, k=random.randint(1, 5))
        red_sum = sum(red_cubes)

        color = cls._get_win_color(blue_sum, red_sum)
        count_cubes = len(blue_cubes) + len(red_cubes)

        game_result = BlackTimeResult(
            color=color, count_cubes=count_cubes,
            blue_sum=blue_sum, blue_cubes=blue_cubes,
            red_sum=red_sum, red_cubes=red_cubes
        )

        str_hash = f"blue:{sum(blue_cubes)}|red:{sum(red_cubes)}|cubes:{count_cubes}|{cls.get_secret_game_key(20)}"
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
            "game_mode": Games.BLACK_TIME.value,
            "game_result": json.dumps(game_result.json()),
            "str_hash": str_hash,
            "enc_hash": enc_hash
        })

        return game_result.dict()


    @classmethod
    def format_game_result(cls, game_result: dict) -> BlackTimeResult:

        return BlackTimeResult(**game_result)


    @classmethod
    def is_winning(cls, game_result: BlackTimeResult, rate_type: str) -> bool:

        return (
            cls._is_draw(game_result) or
            rate_type == game_result.color or
            rate_type == game_result.count_cubes
        )


    @classmethod
    def get_coefficient(
            cls,
            rate_type: str,
            game_result: BlackTimeResult,
            *,
            calculate_winnings: bool = False
    ) -> int | float:


        if (
            cls._is_draw(game_result) and
            (
                rate_type in ["blue", "red"] or
                rate_type != game_result.count_cubes
            ) and
            calculate_winnings
        ):
            return 1

        if rate_type == "blue":
            return 2

        if rate_type == "red":
            return 1.7

        if rate_type in ["2", "10"]:
            return 23.5

        if rate_type in ["3", "9"]:
            return 11.7

        if rate_type in ["4", "8"]:
            return 7.8

        if rate_type in ["5", "7"]:
            return 5.8

        if rate_type == "6":
            return 4.7

        raise ValueError()


    @classmethod
    def get_all_rates_type(cls) -> list:

        return [
            "blue", "red",
            "1", "2", "3", "4", "5",
            "6", "7", "8", "9", "10"
        ]


    @classmethod
    def get_rate_type_ru(cls, rate_type: str) -> str:

        if rate_type == "draw":  # сделано только для get result message
            return "ничья"

        elif rate_type == "blue":
            return "синие"

        elif rate_type == "red":
            return "красные"

        else:
            return f"{rate_type} кубиков"


    @classmethod
    def check_opposite_rates(cls, rate_type: str, user_rates_type: list[str | None]) -> bool:

        opposite_rates = (
            (1, ["red", "blue"]),
            (5, ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"])
        )
        return cls.logic_opposite_rates(rate_type, user_rates_type, opposite_rates)


    @classmethod
    def check_accrual_top_points(cls, rates: list[RatesSchema | None]) -> bool:

        return cls._check_coverage_bets(rates)


    @classmethod
    def get_result_message(cls, game_result: BlackTimeResult, short: bool = False) -> str:

        color = cls.get_rate_type_ru(game_result.color)

        if short:
            return f"{game_result.count_cubes} кубиков, {color}"

        if cls._is_draw(game_result):
            return "Ничья"

        return f"Выиграли {color} кубики"


    @classmethod
    async def get_result_attachment(cls, game_result: BlackTimeResult) -> str:

        img_path = await Painter.draw_image(
            width=1080, height=1080,
            template_path=Path(Config.PROJECT_ROOT, "painter", "black_time", "template.html"),
            jinja_args={
                "left_sum": game_result.blue_sum,
                "left_cubes": game_result.blue_cubes,
                "right_sum": game_result.red_sum,
                "right_cubes": game_result.red_cubes
            }
        )
        attachment = await upload_photo(open(img_path, "rb"))
        os.remove(img_path)

        return attachment


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
                InlineKeyboardButton(text="2 (x23.5)", callback_data='{"rate":"2"}'),
                InlineKeyboardButton(text="3 (x11.7)", callback_data='{"rate":"3"}'),
                InlineKeyboardButton(text="4 (x7.8)", callback_data='{"rate":"4"}')
            ],
            [
                InlineKeyboardButton(text="5 (x5.8)", callback_data='{"rate":"5"}'),
                InlineKeyboardButton(text="6 (x4.7)", callback_data='{"rate":"6"}'),
                InlineKeyboardButton(text="7 (x5.8)", callback_data='{"rate":"7"}')
            ],
            [
                InlineKeyboardButton(text="8 (x7.8)", callback_data='{"rate":"8"}'),
                InlineKeyboardButton(text="9 (x11.7)", callback_data='{"rate":"9"}'),
                InlineKeyboardButton(text="10 (x23.5)", callback_data='{"rate":"10"}')
            ],
            [
                InlineKeyboardButton(text="Синие (x2)", callback_data='{"rate":"blue"}'),
                InlineKeyboardButton(text="Красные (x1.7)", callback_data='{"rate":"red"}')
            ]
        ]

        return InlineKeyboardMarkup(inline_keyboard=buttons)


    @classmethod
    def handler_current_rate(
            cls,
            user_data: UserSchema,
            chat_data: ChatSchema,
            game_result: BlackTimeResult,
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


BaseGameModel.GAMES_MODEL[Games.BLACK_TIME] = BlackTimeGameModel
