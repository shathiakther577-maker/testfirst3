import os
import re
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


AVIATOR_NUMBERS = [x for x in range(1_00, 1_000_01)]
AVIATOR_NUMBERS_CHANCES = [1 / (x ** 2.20) for x in AVIATOR_NUMBERS]
AVIATOR_STRING_COEFFICIENTS = [str(round(x / 100, 2)) for x in AVIATOR_NUMBERS][5:]

MIN_AVIATOR_RATE_TYPE = float(AVIATOR_STRING_COEFFICIENTS[0])
MAX_AVIATOR_RATE_TYPE = float(AVIATOR_STRING_COEFFICIENTS[-1])


class AviatorResult(BaseModel):

    coefficient: str


class AviatorGameModel(BaseGameModel):

    @staticmethod
    def _generate_coefficient() -> int | float:
        """Генерирует коэффициент для игры"""

        coefficient = random.choices(AVIATOR_NUMBERS, AVIATOR_NUMBERS_CHANCES)[0]

        if coefficient == 1.0:
            return 0

        return round(coefficient / 100, 2)


    @classmethod
    def create_game(cls, chat_id: int, psql_cursor: DictCursor) -> dict:

        coefficient = cls._generate_coefficient()
        game_result = AviatorResult(coefficient=coefficient)

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
            "game_mode": Games.AVIATOR.value,
            "game_result": json.dumps(game_result.json()),
            "str_hash": str_hash,
            "enc_hash": enc_hash
        })

        return game_result.dict()


    @classmethod
    def format_game_result(cls, game_result: dict) -> AviatorResult:

        return AviatorResult(**game_result)


    @classmethod
    def is_winning(cls, game_result: AviatorResult, rate_type: str) -> bool:

        return float(game_result.coefficient) >= float(rate_type)


    @classmethod
    def get_coefficient(
            cls,
            rate_type: str,
            game_result: AviatorResult,
            *,
            calculate_winnings: bool = False
    ) -> int | float:

        coefficient = float(rate_type)

        if calculate_winnings:
            return coefficient

        if 1.05 <= coefficient <= 1.19:
            return 0.595

        if 1.20 <= coefficient <= 1.49:
            return 0.7209677419354839

        if 1.5 <= coefficient <= 1.99:
            return 0.9328124999999999

        if 2 <= coefficient <= 2.99:
            return 1.3590909090909091

        if 3 <= coefficient <= 3.99:
            return 1.760294117647059

        if 4 <= coefficient <= 6.49:
            return 2.7814285714285716

        if 6.50 <= coefficient <= 9.99:
            return 4.1625000000000005

        if 10 <= coefficient <= 14.99:
            return 6.077027027027027

        if 15 <= coefficient <= 19.99:
            return 7.89078947368421

        if 20 <= coefficient <= 24.99:
            return 9.61153846153846

        if 25 <= coefficient <= 29.99:
            return 11.246249999999998

        if 30 <= coefficient <= 34.99:
            return 12.801219512195123

        if 35 <= coefficient <= 39.99:
            return 14.282142857142857

        if 40 <= coefficient <= 44.99:
            return 15.694186046511629

        if 45 <= coefficient <= 49.99:
            return 17.042045454545455

        if 50 <= coefficient <= 57.49:
            return 19.163333333333334

        if 57.50 <= coefficient <= 64.99:
            return 21.192391304347826

        if 65 <= coefficient <= 72.49:
            return 23.135106382978723

        if 72.50 <= coefficient <= 79.99:
            return 24.996874999999996

        if 80 <= coefficient <= 87.49:
            return 26.78265306122449

        if 87.50 <= coefficient <= 94.49:
            return 28.347

        if 95 <= coefficient <= 104.99:
            return 30.879411764705882

        if 105 <= coefficient <= 114.99:
            return 33.170192307692304

        if 115 <= coefficient <= 124.99:
            return 35.37452830188679

        if 125 <= coefficient <= 134.99:
            return 37.49722222222223

        if 135 <= coefficient <= 144.99:
            return 39.54272727272728

        if 145 <= coefficient <= 159.99:
            return 42.854464285714286

        if 160 <= coefficient <= 174.99:
            return 46.05

        if 175 <= coefficient <= 189.99:
            return 49.1353448275862

        if 190 <= coefficient <= 204.99:
            return 52.11610169491526

        if 205 <= coefficient <= 229.99:
            return 57.4975

        if 230 <= coefficient <= 254.99:
            return 59.763281250000006

        if 255 <= coefficient <= 279.99:
            return 61.762499999999996

        if 280 <= coefficient <= 304.99:
            return 63.53958333333334

        if 305 <= coefficient <= 329.99:
            return 65.1296052631579

        if 330 <= coefficient <= 354.99:
            return 66.560625

        if 355 <= coefficient <= 379.99:
            return 66.27732558139535

        if 380 <= coefficient <= 404.99:
            return 66.03097826086957

        if 405 <= coefficient <= 429.99:
            return 64.4985

        if 430 <= coefficient <= 454.99:
            return 65.6235576923077

        if 455 <= coefficient <= 479.99:
            return 66.66527777777777

        if 480 <= coefficient <= 504.99:
            return 67.63258928571429

        if 505 <= coefficient <= 539.99:
            return 69.82629310344828

        if 540 <= coefficient <= 574.99:
            return 71.87375

        if 575 <= coefficient <= 609.99:
            return 73.78911290322581

        if 610 <= coefficient <= 644.99:
            return 75.584765625

        if 645 <= coefficient <= 679.99:
            return 77.2715909090909

        if 680 <= coefficient <= 714.99:
            return 78.85919117647059

        if 715 <= coefficient <= 749.99:
            return 80.35607142857143

        if 750 <= coefficient <= 799.99:
            return 79.99900000000001

        if 800 <= coefficient <= 849.99:
            return 79.6865625

        if 850 <= coefficient <= 899.99:
            return 79.41088235294117

        if 900 <= coefficient <= 949.99:
            return 79.16583333333334

        if 950 <= coefficient <= 1000:
            return 75.0

        raise ValueError()


    @classmethod
    def get_all_rates_type(cls) -> list:

        return AVIATOR_STRING_COEFFICIENTS


    @classmethod
    def get_rate_type_ru(cls, rate_type: str) -> str:

        return f"x{rate_type}"


    @classmethod
    def check_opposite_rates(cls, rate_type: str, user_rates_type: list[str | None]) -> bool:

        if len(user_rates_type) >= 5:
            return True

        return False


    @classmethod
    def check_accrual_top_points(cls, rates: list[RatesSchema | None]) -> bool:

        return True


    @classmethod
    def get_result_message(cls, game_result: AviatorResult, short: bool = False) -> str:

        rate_type_ru = f"x{game_result.coefficient}"

        if short:
            return rate_type_ru

        return f"Выпал коэффициент {rate_type_ru}"


    @classmethod
    async def get_result_attachment(cls, game_result: AviatorResult) -> str:

        coefficient = float(game_result.coefficient)

        if coefficient < 2:
            aviator_number = 1
        elif coefficient < 5:
            aviator_number = 2
        elif coefficient < 15:
            aviator_number = 3
        elif coefficient < 30:
            aviator_number = 4
        else:
            aviator_number = 5

        img_path = await Painter.draw_image(
            width=1080, height=1080,
            template_path=Path(Config.PROJECT_ROOT, "painter", "aviator", "template.html"),
            jinja_args={
                "aviator_number": aviator_number,
                "coefficient": coefficient
            }
        )
        attachment = await upload_photo(open(img_path, "rb"))
        os.remove(img_path)

        return attachment


    @classmethod
    def get_game_keyboard(cls, game_result: dict | None) -> ReplyKeyboardMarkup:

        buttons = [
            [
                KeyboardButton(text="Банк"),
                KeyboardButton(text="Повторить"),
                KeyboardButton(text="Баланс")
            ],
            [KeyboardButton(text="Сделать ставку")]
        ]

        return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


    @staticmethod
    def _extract_coefficient(message: str) -> float | None:
        # pattern = r"[хx](?P<coefficient>[0-9]+\.?[0-9]*)"
        pattern = r"(?P<coefficient>[0-9]+\.?[0-9]*)"
        match = re.match(pattern, message)
        if match is None:
            return None
        return round(float(match.groupdict()["coefficient"]), 2)


    @classmethod
    def handler_current_rate(
            cls,
            user_data: UserSchema,
            chat_data: ChatSchema,
            game_result: AviatorResult,
            user_chat_data: UserChatSchema,
            message: str,
            payload: dict | None,
            psql_cursor: DictCursor
    ) -> tuple[str, str | None] | None:

        user_id = user_data.user_id
        chat_id = chat_data.chat_id

        if payload is not None and payload.get("event") == "update_rate_type":
            cls.update_current_rate(chat_id, user_id, "update_rate_type", psql_cursor)
            return "Введи коэффициент на который хотите поставить", None

        elif user_chat_data.current_rate == "update_rate_type":

            coefficient = cls._extract_coefficient(message)
            if (
                coefficient is not None and
                MIN_AVIATOR_RATE_TYPE <= coefficient <= MAX_AVIATOR_RATE_TYPE
            ):
                rate_type = str(coefficient)
                response, keyboard = cls.get_keyboard_pay_rates(
                    chat_data, user_chat_data, rate_type, game_result, psql_cursor
                )

            else:
                rate_type = None
                response = f"Коэффициент должен находиться в диапазоне от {MIN_AVIATOR_RATE_TYPE} до {MAX_AVIATOR_RATE_TYPE}"
                keyboard = None

            cls.update_current_rate(chat_id, user_id, rate_type, psql_cursor)
            return response, keyboard

        return None


BaseGameModel.GAMES_MODEL[Games.AVIATOR] = AviatorGameModel
