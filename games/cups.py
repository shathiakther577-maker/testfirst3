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


CUPS_NUMBERS = [1, 2, 3, 4, 5]
CUPS_STRING_NUMBERS = [str(x) for x in CUPS_NUMBERS]


class CupsResult(BaseModel):
    cup_number: str
    chances: dict[str, int]


class CupsGameModel(BaseGameModel):

    @staticmethod
    def _generate_chances() -> list[int]:
        """Генерирует шансы появления стаканчиков"""

        chances = []
        percents = 100

        number = random.randint(1, 70)
        chances.append(number)
        percents -= number

        for _ in range(3):
            number = random.randint(1, int(percents // 2))
            chances.append(number)
            percents -= number

        chances.append(percents)
        random.shuffle(chances)

        return chances


    @classmethod
    def create_game(cls, chat_id: int, psql_cursor: DictCursor) -> dict:

        chances = cls._generate_chances()
        dict_chances = dict(zip(CUPS_STRING_NUMBERS, chances))
        cup_number = random.choices(CUPS_NUMBERS, chances)[0]
        game_result = CupsResult(cup_number=cup_number, chances=dict_chances)

        str_hash = f"{cup_number}|{cls.get_secret_game_key(20)}"
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
            "game_mode": Games.CUPS.value,
            "game_result": json.dumps(game_result.json()),
            "str_hash": str_hash,
            "enc_hash": enc_hash
        })

        return game_result.dict()


    @classmethod
    def format_game_result(cls, game_result: dict) -> CupsResult:

        return CupsResult(**game_result)


    @classmethod
    def is_winning(cls, game_result: CupsResult, rate_type: str) -> bool:

        return game_result.cup_number == rate_type


    @classmethod
    def get_coefficient(
            cls,
            rate_type: str,
            game_result: CupsResult,
            *,
            calculate_winnings: bool = False
    ) -> int | float:

        return round(95 / game_result.chances[rate_type], 2)


    @classmethod
    def get_all_rates_type(cls) -> list:

        return CUPS_STRING_NUMBERS


    @classmethod
    def get_rate_type_ru(cls, rate_type: str) -> str:

        return f"{rate_type} стаканчик"


    @classmethod
    def check_opposite_rates(
            cls,
            rate_type: str,
            user_rates_type: list[str | None]
    ) -> bool:

        opposite_rates = ((2, CUPS_STRING_NUMBERS), )
        return cls.logic_opposite_rates(rate_type, user_rates_type, opposite_rates)


    @classmethod
    def check_accrual_top_points(cls, rates: list[RatesSchema | None]) -> bool:

        return cls._check_coverage_bets(rates)


    @classmethod
    def get_result_message(cls, game_result: CupsResult, short: bool = False) -> str:

        cup_number = game_result.cup_number
        coefficient_ru = f"(x{cls.get_coefficient(cup_number, game_result)})"

        if short:
            return f"{cup_number} {coefficient_ru}"

        return f"Монетка оказалась под {cup_number} стаканчиком! {coefficient_ru}"


    @classmethod
    async def get_result_attachment(cls, game_result: CupsResult) -> str:

        image_path = await Painter.draw_image(
            width=1080, height=1080,
            template_path=Path(Config.PROJECT_ROOT, "painter", "cups", "template.html"),
            jinja_args={
                "cup_number": game_result.cup_number,
                "coefficient": cls.get_coefficient(game_result.cup_number, game_result)
            }
        )
        attachment = await upload_photo(open(image_path, "rb"))
        os.remove(image_path)

        return attachment


    @classmethod
    def get_game_keyboard(cls, game_result: dict | None) -> ReplyKeyboardMarkup:

        game_result = cls.format_game_result(game_result)
        buttons = [
            [
                KeyboardButton(text="Банк"),
                KeyboardButton(text="Помощь"),
                KeyboardButton(text="Баланс")
            ]
        ]

        row = []
        for index, cup_number in enumerate(CUPS_STRING_NUMBERS, 1):
            cup_number = str(cup_number)
            row.append(KeyboardButton(text=f"{cup_number} (x{cls.get_coefficient(cup_number, game_result)})"))
            if index % 3 == 0:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

        return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


    @classmethod
    def handler_current_rate(
            cls,
            user_data: UserSchema,
            chat_data: ChatSchema,
            game_result: CupsResult,
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


BaseGameModel.GAMES_MODEL[Games.CUPS] = CupsGameModel
