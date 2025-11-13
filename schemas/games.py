from enum import Enum
from datetime import datetime
from pydantic import BaseModel


class Games(str, Enum):
    """Все игры которые есть в боте"""

    AVIATOR = "aviator"  # Ставка на x
    UNDER_7_OVER = "under_7_over"  # Больше меньше или равно (7)

    DICE = "dice"  # Кубик от 1 до 6, чётное, нечётное
    MEGA_DICE = "mega_dice"  # Два кубика (сумма) от 2 до 12, красное, черное, 2-4, 5-8, 9-12
    BLACK_TIME = "black_time"  # Кубики (количество) от 2 до 10, Красный, Синий

    WHEEL = "wheel"  # Рулетка от 1 до 36, чётное, нечётное, красное, черное
    DOUBLE = "double"  # Рулетка x2 x3 x5 x50
    DREAM_CATCHER = "dream_catcher"  # Рулетка x1 x2 x5 x10 x20 x40

    CUPS = "cups"  # Стаканчик 1-5 (кэф вероятность стаканчика)
    LUCKY_COINS = "lucky_coins"  # Стаканчик 1-5 (кэф под стаканчиком)


    def __init__(self, game) -> None:
        self.game = game


    @property
    def name(self) -> str:
        """Возвращает название игрового режима"""

        return self.game.replace("_", " ").title()


ALL_GAMES: list[Games] = [game for game in Games]
ALL_GAMES_VALUES: list[str] = [game.value for game in ALL_GAMES]


GAME_NAMES = {
    Games.AVIATOR: "Aviator",
    Games.UNDER_7_OVER: "Под 7 над",

    Games.DICE: "Dice",
    Games.MEGA_DICE: "Mega Dice",
    Games.BLACK_TIME: "Black Time",

    Games.WHEEL: "Wheel",
    Games.DOUBLE: "Double",
    Games.DREAM_CATCHER: "Dream Catcher",

    Games.CUPS: "Cups",
    Games.LUCKY_COINS: "Lucky Coins",
}
# Названия игр которые должны видеть пользователи


class GameSchema(BaseModel):
    """Схема игры"""

    __tablename__ = "games"

    game_id: int  # Идентификатор игры
    chat_id: int  # Идентификатор чата

    game_mode: Games  # Режим игры
    game_result: dict  # Результат игры

    str_hash: str  # Хэш в первоначальном виде
    enc_hash: str  # Хэш в преобразованном виде

    income: int = 0  # Прибыль за игру
    is_active: bool = True  # Показывает активна ли игра
    time_left: int | None = None  # Показывает через сколько закончится игра
    end_datetime: datetime | None = None  # Время конца игры
