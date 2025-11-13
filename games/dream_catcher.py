import json
import random
import asyncio
import hashlib
from pydantic import BaseModel
from psycopg2.extras import DictCursor
import json
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

from games.base import BaseGameModel

from schemas.users import UserSchema
from schemas.chats import ChatSchema
from schemas.games import GameSchema, Games
from schemas.rates import RatesSchema
from schemas.user_in_chat import UserChatSchema

from modules.telegram.bot import send_message


DREAM_CATCHER_OUTCOMES = ["x1", "x2", "x5", "x10", "x20", "x40", "m2", "m7"]
DREAM_CATCHER_OUTCOMES_CHANCES = [46, 30, 14, 8, 4, 2, 2, 1]
DREAM_CATCHER_STRING_OUTCOMES = [x[1:] for x in DREAM_CATCHER_OUTCOMES if x.startswith("x")]


class DreamCatcherResult(BaseModel):
    outcomes: list[str]
    coefficient: str
    multiplier: int


class DreamCatcherGameModel(BaseGameModel):

    @staticmethod
    def _generate_outcomes_game() -> list[str]:
        """Генерирует исход игры"""

        current = ""
        game_result = []
        outcomes = dict(zip(DREAM_CATCHER_OUTCOMES, DREAM_CATCHER_OUTCOMES_CHANCES))

        while not current.startswith("x"):

            if "m7" in game_result or len(game_result) >= 2:
                del outcomes["m7"]

            if len(game_result) >= 2:
                del outcomes["m2"]

            current = random.choices(list(outcomes.keys()), list(outcomes.values()))[0]
            game_result.append(current)

        return game_result


    @staticmethod
    def _get_multiplier(outcomes: list[str]) -> int:
        """Возвращает дополнительный множитель в игре"""

        multiplier = 1

        for x in outcomes[:-1]:
            multiplier *= int(x.replace("m", ""))

        return multiplier


    @classmethod
    def create_game(cls, chat_id: int, psql_cursor: DictCursor) -> dict:

        outcomes = cls._generate_outcomes_game()
        coefficient = outcomes[-1][1:]
        multiplier = cls._get_multiplier(outcomes)
        game_result = DreamCatcherResult(outcomes=outcomes, coefficient=coefficient, multiplier=multiplier)

        str_hash = f"{'|'.join(outcomes)}{cls.get_secret_game_key(20)}"
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
            "game_mode": Games.DREAM_CATCHER.value,
            "game_result": json.dumps(game_result.json()),
            "str_hash": str_hash,
            "enc_hash": enc_hash
        })

        return game_result.dict()


    @classmethod
    def format_game_result(cls, game_result: dict) -> DreamCatcherResult:

        return DreamCatcherResult(**game_result)


    @classmethod
    def is_winning(cls, game_result: DreamCatcherResult, rate_type: str) -> bool:

        return game_result.coefficient == rate_type


    @classmethod
    def get_coefficient(
            cls,
            rate_type: str,
            game_result: DreamCatcherResult,
            *,
            calculate_winnings: bool = False
    ) -> int | float:

        if calculate_winnings:
            return game_result.multiplier * int(rate_type) + 1

        return int(rate_type) + 1


    @classmethod
    def get_all_rates_type(cls) -> list:

        return DREAM_CATCHER_STRING_OUTCOMES


    @classmethod
    def get_rate_type_ru(cls, rate_type: str) -> str:

        return f"x{rate_type}"


    @classmethod
    def check_opposite_rates(cls, rate_type: str, user_rates_type: list[str | None]) -> bool:

        return False


    @classmethod
    def check_accrual_top_points(cls, rates: list[RatesSchema | None]) -> bool:

        return cls._check_coverage_bets(rates)


    @classmethod
    def get_result_message(cls, game_result: DreamCatcherResult, short: bool = False) -> str:

        multiplier = game_result.multiplier
        rate_type_ru = f"x{game_result.coefficient} {f'(*{multiplier})' if multiplier > 1 else ''}"

        if short:
            return rate_type_ru

        return f"Выпал множитель {rate_type_ru}"


    @staticmethod
    def _get_attachment(rate_type: str) -> str:

        attachment = {
            "m2": ["photo-207204376_457441529"],
            "m7": ["photo-207204376_457441557"],

            "1": [
                "photo-207204376_457441512",
                "photo-207204376_457441514",
                "photo-207204376_457441517",
                "photo-207204376_457441519",
                "photo-207204376_457441521",
                "photo-207204376_457441524",
                "photo-207204376_457441526",
                "photo-207204376_457441528",
                "photo-207204376_457441530",
                "photo-207204376_457441533",
                "photo-207204376_457441535",
                "photo-207204376_457441537",
                "photo-207204376_457441540",
                "photo-207204376_457441545",
                "photo-207204376_457441547",
                "photo-207204376_457441549",
                "photo-207204376_457441551",
                "photo-207204376_457441553",
                "photo-207204376_457441556",
                "photo-207204376_457441558",
                "photo-207204376_457441561",
                "photo-207204376_457441564",
                "photo-207204376_457441543",
            ],
            "2": [
                "photo-207204376_457441513",
                "photo-207204376_457441520",
                "photo-207204376_457441523",
                "photo-207204376_457441527",
                "photo-207204376_457441531",
                "photo-207204376_457441534",
                "photo-207204376_457441538",
                "photo-207204376_457441541",
                "photo-207204376_457441544",
                "photo-207204376_457441548",
                "photo-207204376_457441550",
                "photo-207204376_457441554",
                "photo-207204376_457441560",
                "photo-207204376_457441563",
                "photo-207204376_457441565",
            ],
            "5": [
                "photo-207204376_457441515",
                "photo-207204376_457441522",
                "photo-207204376_457441536",
                "photo-207204376_457441539",
                "photo-207204376_457441542",
                "photo-207204376_457441555",
                "photo-207204376_457441562",
            ],
            "10": [
                "photo-207204376_457441518",
                "photo-207204376_457441532",
                "photo-207204376_457441546",
                "photo-207204376_457441559",
            ],
            "20": [
                "photo-207204376_457441525",
                "photo-207204376_457441552",
            ],
            "40": ["photo-207204376_457441516"]
        }
        return random.choice(attachment[rate_type])


    @classmethod
    async def get_result_attachment(cls, game_result: DreamCatcherResult) -> str:

        return cls._get_attachment(game_result.coefficient)


    @classmethod
    async def additional_game_logic_after(cls, game_data: GameSchema) -> None:

        game_result = cls.format_game_result(game_data.game_result)
        multipliers = game_result.outcomes[:-1]

        if len(multipliers) > 0:

            chat_id = game_data.chat_id
            total_multiplier = 1

            for current in multipliers:

                multiplier = int(current.replace("m", ""))
                # можно было сделать через current[1:] дополнительная безопасность вдруг что-то не то попадет
                total_multiplier *= multiplier

                await send_message(chat_id, "Итак, результаты раунда...")
                await asyncio.sleep(cls.DELAY_BEFORE_RESULT)

                await send_message(
                    chat_id=chat_id,
                    message=f"Выпал множитель {multiplier}x\n\nВсе выигрышные ставки в текущем раунде будут умножены на {total_multiplier}x",
                    photo=cls._get_attachment(current)
                )
                await asyncio.sleep(cls.DELAY_BEFORE_RESULT)


    @classmethod
    def get_game_keyboard(cls, game_result: dict | None) -> ReplyKeyboardMarkup:

        buttons = [
            [
                KeyboardButton(text="Банк"),
                KeyboardButton(text="Повторить"),
                KeyboardButton(text="Баланс")
            ],
            [
                KeyboardButton(text="x1"),
                KeyboardButton(text="x2"),
                KeyboardButton(text="x5")
            ],
            [
                KeyboardButton(text="x10"),
                KeyboardButton(text="x20"),
                KeyboardButton(text="x40")
            ]
        ]

        return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


    @classmethod
    def handler_current_rate(
            cls,
            user_data: UserSchema,
            chat_data: ChatSchema,
            game_result: DreamCatcherResult,
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


BaseGameModel.GAMES_MODEL[Games.DREAM_CATCHER] = DreamCatcherGameModel
