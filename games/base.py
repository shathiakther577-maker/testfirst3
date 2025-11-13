import json
import random
import asyncio
import threading

from abc import ABC, abstractmethod
from typing import Type, TypeVar, Optional, Sized
from string import ascii_letters
from datetime import datetime
from redis.client import Redis
import json
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from psycopg2.extras import DictCursor
from psycopg2._psycopg import connection as Connection

from settings import TopSettings, Temp
from games.rates import RatesService

from schemas.users import UserSchema, UserStatus
from schemas.chats import ChatSchema
from schemas.games import GameSchema, Games
from schemas.rates import RatesSchema, GameRateSchema, CalculateRateSchema
from schemas.user_in_chat import UserChatSchema

from modules.additional import format_number, get_word_case
from modules.databases.users import get_user_data
from modules.databases.chats import get_chat_data, get_game_data
from modules.telegram.bot import send_message

from databases.redis import get_redis_cursor
from databases.postgresql import get_postgresql_connection

from vk_bot.template_messages import DATA_OUTDATED_LOWER
from vk_bot.keyboards.other import empty_keyboard
from vk_bot.keyboards.active_chat import keyboard_game_bank


GAME_RESULT = TypeVar("GAME_RESULT")


# VK статьи удалены - больше не используются


class BaseGameModel(ABC):

    DELAY_BEFORE_RESULT: int = 1
    # Задержка (в секундах) после слов "Итак, результаты раунда...".

    GAMES_MODEL: dict[Games, Type["BaseGameModel"]] = {}  # При написании игры в конце файла ->
    # добавить игровую модель в словарь и инициализировать в backend_pre_start.py
    # пример BaseGameModel.GAMES_MODEL[Games.WHEEL] = WheelGameModel
    # Не придумал как избавиться от замыкания


    @classmethod
    @abstractmethod
    def create_game(cls, chat_id: int, psql_cursor: DictCursor) -> dict:
        """Создает игру и возвращает результаты игры"""
        ...


    @classmethod
    @abstractmethod
    def format_game_result(cls, game_result: dict) -> GAME_RESULT:
        """Распаковывает dict (результат игры) в BaseModel"""
        ...


    @classmethod
    @abstractmethod
    def is_winning(cls, game_result: GAME_RESULT, rate_type: str) -> bool:
        """Проверяет выиграна ли ставка"""
        ...


    @classmethod
    @abstractmethod
    def get_coefficient(
            cls,
            rate_type: str,
            game_result: GAME_RESULT,
            *,
            calculate_winnings: bool = False  # Флаг принятия коэффициентов для расчета выигрыша
    ) -> int | float:
        """Возвращает выигрышный коэффициент"""
        ...


    @classmethod
    @abstractmethod
    def get_all_rates_type(cls) -> list:
        """Возвращает все события на которые можно ставить """
        ...


    @classmethod
    @abstractmethod
    def get_rate_type_ru(cls, rate_type: str) -> str | None:
        """Возвращает название ставки читабельном для пользователя"""
        ...


    @classmethod
    def logic_opposite_rates(
            cls,
            rate_type: str,
            user_rates_type: list[Optional[str]],
            opposite_rates: tuple[tuple[int, list[str]]]
    ) -> bool:
        """Логика выполнения check_opposite_rates"""
        # кортеж(допустимое количество, типы событий)
        # если найденное количество >= допустимое количество возвращается True

        for rate in opposite_rates:
            counter, events = rate

            if (
                rate_type in events and
                len([x for x in events if x in user_rates_type and x != rate_type]) >= counter
            ):
                return True

        return False


    @classmethod
    @abstractmethod
    def check_opposite_rates(
            cls,
            rate_type: str,
            user_rates_type: list[Optional[str]]
    ) -> bool:
        """Проверяет что пользователь не поставил на противоположное событие"""
        # если True значит пользователь ставит на противоположное событие
        ...


    @classmethod
    def _group_rates_by_type(cls, rates: list[RatesSchema | None]) -> dict:
        """Группирует ставки по rate_type"""

        grouped_rates = {}

        for rate in rates:
            rate_type = rate.rate_type

            if rate_type not in grouped_rates:
                grouped_rates[rate_type] = {"rate_sum": 0}

            grouped_rates[rate_type]["rate_sum"] += rate.amount

        return grouped_rates


    @classmethod
    def _check_coverage_bets(cls, rates: Sized) -> bool:
        """Проверяет насколько событий поставлено"""

        return len(rates) / len(cls.get_all_rates_type()) <= 0.8
        # Если закрыли равно или больше (0.8) 80% -> False


    @classmethod
    def _check_opposite_bets(
            cls,
            grouped_rates: dict,
            *,
            opposite_bets: tuple
    ) -> bool:
        """Проверяет суммы на противоположные ставки"""

        for rate_type_1, rate_type_2 in opposite_bets:

            if rate_type_1 in grouped_rates and rate_type_2 in grouped_rates:

                rate_sum_1 = grouped_rates[rate_type_1]["rate_sum"]
                rate_sum_2 = grouped_rates[rate_type_2]["rate_sum"]

                max_rate_sum = max(rate_sum_1, rate_sum_2)
                min_rate_sum = min(rate_sum_1, rate_sum_2)

                if (max_rate_sum - min_rate_sum) / min_rate_sum <= 0.4:
                    # Если разница между противоположными ставка меньше или равна (0.4) 40 %
                    return False

        return True


    @classmethod
    @abstractmethod
    def check_accrual_top_points(
        cls,
        rates: list[Optional[RatesSchema]]
    ) -> bool:
        """Проверяет начислять ли очки в топы"""

        return True


    @classmethod
    @abstractmethod
    def get_result_message(cls, game_result: GAME_RESULT, short: bool = False) -> str:
        """Возвращает строку исхода игры"""
        # если short is True возвращаются краткий итог для логов
        ...


    @classmethod
    @abstractmethod
    async def get_result_attachment(cls, game_result: GAME_RESULT) -> str:
        """Возвращает картинку исхода игры"""
        ...


    @classmethod
    async def additional_game_logic_before(cls, game_data: GameSchema) -> None:
        """Дополнительная игровая логика перед игрой"""
        pass


    @classmethod
    async def additional_game_logic_after(cls, game_data: GameSchema) -> None:
        """Дополнительная игровая логика после игрой"""
        pass


    @classmethod
    @abstractmethod
    def get_game_keyboard(cls, game_result: dict | None) -> InlineKeyboardMarkup | ReplyKeyboardMarkup:
        """Возвращает клавиатуру игры"""
        ...


    @staticmethod
    def get_secret_game_key(length: int) -> str:
        """Возвращает секретную строку для хэша"""

        secret = random.choices(ascii_letters, k=length)
        secret = "".join(secret)

        return secret


    @staticmethod
    def update_current_rate(
            chat_id: int,
            user_id: int,
            rate_type: str | None,
            psql_cursor: DictCursor
    ) -> None:
        """Обновляет на что в данный момент ставит пользователь"""

        psql_cursor.execute("""
            UPDATE user_in_chat
            SET current_rate = %(rate_type)s
            WHERE user_id = %(user_id)s AND
                  chat_id = %(chat_id)s
        """, {
            "rate_type": rate_type,
            "chat_id": chat_id,
            "user_id": user_id
        })


    @staticmethod
    def clear_current_rates(
            chat_id: int,
            psql_cursor: DictCursor
    ) -> None:
        """Обнуляет на что хотят поставить пользователи"""

        psql_cursor.execute("""
            UPDATE user_in_chat
            SET current_rate = NULL
            WHERE chat_id = %s
        """, (chat_id,))


    @classmethod
    @abstractmethod
    def handler_current_rate(
        cls,
        user_data: UserSchema,
        chat_data: ChatSchema,
        game_result: GAME_RESULT,
        user_chat_data: UserChatSchema,
        message: str,
        payload: dict | None,
        psql_cursor: DictCursor
    ) -> tuple[str, str | None] | None:
        """Принятие ставок в игре"""
        # Если это ставка возвращает сообщение и клавиатуру
        # Если нет, обязательно вернуть None
        ...


    @classmethod
    def get_keyboard_pay_rates(
        cls,
        chat_data: ChatSchema,
        user_chat_data: UserChatSchema,
        rate_type: str,
        game_result: GAME_RESULT,
        psql_cursor: DictCursor
    ) -> tuple[str, str | None]:
        """Возвращает сообщение и клавиатуру для оплаты ставки"""

        user_id = user_chat_data.user_id
        user_data = get_user_data(user_id, psql_cursor)
        user_name = user_data.telegram_name
        user_coins = user_data.coins

        valid_rate_types = cls.get_all_rates_type()
        if not all([x in valid_rate_types for x in rate_type.split(" ")]):
            return f"{user_name}, {DATA_OUTDATED_LOWER}", None

        if user_coins != 0:

            rate_limit = RatesService.get_rate_limit(rate_type, cls, game_result)
            max_bet = user_coins if rate_limit > user_coins else rate_limit

            rate_type_ru = cls.get_rate_type_ru(rate_type)
            response = f"{user_name}, введи ставку {f'на {rate_type_ru}' if rate_type_ru else ''} ИЛИ нажми кнопку:"
            response += f"\nМаксимальный размер ставки - {format_number(max_bet)}"

            buttons = []
            last_rate_amount = user_chat_data.last_rate_amount

            if last_rate_amount is not None:
                buttons.append([InlineKeyboardButton(
                    text=str(last_rate_amount),
                    callback_data=json.dumps({"amount": last_rate_amount})
                )])
                buttons.append([InlineKeyboardButton(
                    text=str(last_rate_amount * 2),
                    callback_data=json.dumps({"amount": last_rate_amount * 2})
                )])
                buttons.append([InlineKeyboardButton(
                    text=str(user_coins),
                    callback_data=json.dumps({"amount": user_coins})
                )])
            else:
                buttons.append([InlineKeyboardButton(
                    text=str(max_bet),
                    callback_data=json.dumps({"amount": max_bet})
                )])

            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        else:
            cls.update_current_rate(chat_data.chat_id, user_id, None, psql_cursor)
            response, keyboard = f"{user_name}, на твоём балансе нет BC!", None

        return response, keyboard


    @classmethod
    def init_game(
            cls,
            game_id: int,
            psql_cursor: DictCursor,
            redis_cursor: Redis
    ) -> None:
        """Запускает игру переводя ее в ожидание"""

        if game_id in Temp.GAMES:
            return
        Temp.GAMES.append(game_id)

        game_data = get_game_data(game_id, psql_cursor)
        chat_data = get_chat_data(game_data.chat_id, psql_cursor)

        if game_data.time_left is None:
            time_left = chat_data.game_timer

            psql_cursor.execute("""
                UPDATE games
                SET end_datetime = NOW() + INTERVAL '%(seconds)s second'
                WHERE game_id = %(game_id)s
            """, {
                "seconds": time_left,
                "game_id": game_id
            })

        else:
            time_left = max(game_data.time_left, 0)

        threading.Thread(
            target=asyncio.run, args=[cls.submit_results(game_id, time_left)], daemon=True
        ).start()


    @classmethod
    def get_rates_in_game(
            cls,
            game_id: int,
            psql_cursor: DictCursor
    ) -> list[GameRateSchema | None]:
        """
            Возвращает ставки которые были в игре с дополнительными параметрами
            для расчета победителей
        """

        psql_cursor.execute("""
            SELECT rates.*,
                   users.full_name as user_full_name,
                   users.status as user_status,
                   users.clan_id as clan_id
            FROM rates JOIN users ON rates.user_id = users.user_id
            WHERE rates.game_id = %(game_id)s
            ORDER BY rates.rate_type, rates.amount DESC
        """, {
            "game_id": game_id
        })
        psql_response = psql_cursor.fetchall()

        rates = []
        for rate in psql_response:
            status = rate["user_status"]
            prefix = UserSchema.get_user_prefix(UserStatus(status) if status else None)
            rate["user_full_name"] = f"{prefix}{rate['user_full_name']}{prefix}"
            rates.append(GameRateSchema(**rate))

        return rates


    @classmethod
    def calculate_winnings(
            cls,
            rates: list[Optional[GameRateSchema]],
            game_result: GAME_RESULT
    ) -> list[Optional[CalculateRateSchema]]:
        """Вычисляет победителей"""

        new_rates = []

        for rate in rates:
            is_winning = cls.is_winning(game_result, rate.rate_type)
            winning_amount = round(
                rate.amount * cls.get_coefficient(
                    rate.rate_type, game_result,
                    calculate_winnings=True
                )
            ) if is_winning else 0

            new_rates.append(CalculateRateSchema(
                **rate.dict(),
                is_winning=is_winning,
                winning_amount=winning_amount
            ))

        return sorted(new_rates, key=lambda rate: rate.is_winning, reverse=True)


    @classmethod
    def _grouped_rates_by_user_id(
            cls,
            rates: list[Optional[CalculateRateSchema]]
    ) -> dict[int, dict]:
        """Группирует ставки по user_id"""

        grouped_rates = {}

        for rate in rates:
            user_id = rate.user_id

            if user_id not in grouped_rates:
                grouped_rates[user_id] = {
                    "clan_id": rate.clan_id,
                    "rates_sum": 0,
                    "winning_sum": 0,
                    "clean_winning": 0,
                    "clean_losing": 0,
                    "user_status": rate.user_status
                }

            grouped_rates[user_id]["rates_sum"] += rate.amount

            if rate.is_winning:
                grouped_rates[user_id]["winning_sum"] += rate.winning_amount
                grouped_rates[user_id]["clean_winning"] += rate.winning_amount - rate.amount
            else:
                grouped_rates[user_id]["clean_losing"] += rate.amount

        return grouped_rates


    @classmethod
    def write_game_result(
            cls,
            game_id: int,
            rates: list[Optional[CalculateRateSchema]],
            psql_cursor: DictCursor,
            psql_connection: Connection
    ) -> bool:
        """Записывает в базу данных результаты игры и возвращает что все записалось"""

        bot_income = 0
        accrual_top_points = cls.check_accrual_top_points(rates)

        psql_connection.autocommit = False

        try:
            for user_id, rate in cls._grouped_rates_by_user_id(rates).items():

                rates_sum = rate["rates_sum"]
                winning_sum = rate["winning_sum"]
                clean_winning = rate["clean_winning"]
                clean_losing = rate["clean_losing"]

                top_points = max(clean_winning - clean_losing, 0) * accrual_top_points
                clan_points = top_points if rate["clan_id"] is not None else 0
                coins_top_points = top_points if (
                    TopSettings.DATETIME_COINS_TOP and
                    datetime.now().date() < TopSettings.DATETIME_COINS_TOP
                ) else 0

                accrue_bot_income: bool = rate["user_status"] != UserStatus.ADMIN
                # Условие, которое показывает начислять ли прибыль за игру у игрока

                psql_cursor.execute("""
                    UPDATE users
                    SET coins = coins + %(coins)s,
                        clan_points = clan_points + %(clan_points)s,
                        all_top_points = all_top_points + %(top_points)s,
                        day_top_points = day_top_points + %(top_points)s,
                        week_top_points = week_top_points + %(top_points)s,
                        coins_top_points = coins_top_points + %(coins_top_points)s,
                        rubles_top_points = rubles_top_points + %(top_points)s,
                        week_rubles_top_points = week_rubles_top_points + %(top_points)s
                    WHERE user_id = %(user_id)s
                """, {
                    "coins": winning_sum,
                    "clan_points": clan_points,
                    "top_points": top_points,
                    "coins_top_points": coins_top_points,
                    "user_id": user_id
                })

                psql_cursor.execute("""
                    UPDATE users
                    SET day_win = day_win + %(winning)s,
                        day_lost = day_lost + %(losing)s,
                        day_rates = day_rates + %(rates)s,

                        week_win = week_win + %(winning)s,
                        week_lost = week_lost + %(losing)s,
                        week_rates = week_rates + %(rates)s,

                        all_win = all_win + %(winning)s,
                        all_lost = all_lost + %(losing)s,
                        all_rates = all_rates + %(rates)s
                    WHERE user_id = %(user_id)s
                """, {
                    "winning": clean_winning,
                    "losing": clean_losing,
                    "rates": rates_sum,
                    "user_id": user_id
                })

                if accrue_bot_income:
                    bot_income -= clean_winning if accrue_bot_income else 0
                    bot_income += clean_losing if accrue_bot_income else 0

            psql_cursor.execute("""
                UPDATE games
                SET income = %(bot_income)s
                WHERE game_id = %(game_id)s
            """, {
                "bot_income": bot_income,
                "game_id": game_id
            })

            psql_cursor.execute("""
                INSERT INTO completed_games (game_id)
                VALUES (%(game_id)s)
            """, {"game_id": game_id})

            psql_connection.commit()
            return True

        except:
            psql_connection.rollback()
            return False

        finally:
            psql_connection.autocommit = True


    @classmethod
    def get_game_message(
            cls,
            rates: list[Optional[CalculateRateSchema]],
            game_data: GameSchema,
            game_result: GAME_RESULT
    ) -> str:
        """Возвращает итоговое сообщение игры"""

        message = f"{cls.get_result_message(game_result)}\n"

        for rate in rates:
            emoji = "✅" if rate.is_winning else "❌"
            user_name = UserSchema.format_vk_name(rate.user_id, rate.user_full_name)

            rate_type_ru = cls.get_rate_type_ru(rate.rate_type)
            rate_type_ru = f"на {rate_type_ru}" if rate_type_ru else ""

            rate_amount = rate.amount
            format_amount = f"ставка {format_number(rate_amount)} {get_word_case(rate_amount, ('коин', 'коина', 'коинов'))}"
            rate_status_ru = "выиграла!" if rate.is_winning else "проиграла"
            winning_ru = f"(приз {format_number(rate.winning_amount)} BC)" if rate.is_winning else ""

            message += f"\n{emoji} {user_name} {format_amount} {rate_type_ru} {rate_status_ru} {winning_ru}"

        message += f"\n\nХеш игры: {game_data.enc_hash}\nПроверка честности: {game_data.str_hash}"

        return message


    @classmethod
    async def send_article_message(cls, chat_data: ChatSchema) -> None:
        """Отправляет сообщения с статьей (отключено для Telegram)"""
        # Функция отключена - статьи VK больше не используются
        pass


    @classmethod
    def create_new_game(
            cls,
            chat_id: int,
            game_mode: Games,
            psql_cursor: DictCursor
    ) -> dict:
        """Создает игру и возвращает ее результат"""

        game_model = cls.GAMES_MODEL[game_mode]
        game_result = game_model.create_game(chat_id, psql_cursor)

        return game_result


    @classmethod
    async def submit_results(
            cls,
            game_id: int,
            time_left: int,
    ) -> None:
        """Выдает результаты игры"""

        redis_cursor = get_redis_cursor()
        psql_connection, psql_cursor = get_postgresql_connection()

        try:
            game_data = get_game_data(game_id, psql_cursor)
            chat_id = game_data.chat_id

            await asyncio.sleep(max(time_left - cls.DELAY_BEFORE_RESULT, 0))
            await cls.additional_game_logic_after(game_data)
            await send_message(chat_id=chat_id, message="Итак, результаты раунда...")
            await asyncio.sleep(cls.DELAY_BEFORE_RESULT)

            chat_data = get_chat_data(game_data.chat_id, psql_cursor)
            game_result = cls.format_game_result(game_data.game_result)

            rates = cls.get_rates_in_game(game_id, psql_cursor)
            rates = cls.calculate_winnings(rates, game_result)
            write_status = cls.write_game_result(game_id, rates, psql_cursor, psql_connection)

            if write_status is False:
                return

            if chat_data.new_game_mode:
                new_game_mode = chat_data.new_game_mode
                psql_cursor.execute("""
                    UPDATE chats
                    SET game_mode = %(game_mode)s,
                        new_game_mode = NULL
                    WHERE chat_id = %(chat_id)s
                """, {
                    "game_mode": new_game_mode.value,
                    "chat_id": chat_id
                })
                cls.clear_current_rates(chat_id, psql_cursor)
            else:
                new_game_mode = chat_data.game_mode

            new_game_model = cls.GAMES_MODEL[new_game_mode]
            new_game_result = cls.create_new_game(chat_id, new_game_mode, psql_cursor)
            Temp.GAMES.remove(game_id)

            psql_cursor.execute("""
                UPDATE games SET is_active = FALSE
                WHERE game_id = %(game_id)s
            """, {
                "game_id": game_id
            })

            message = cls.get_game_message(rates, game_data, game_result)
            keyboard = new_game_model.get_game_keyboard(new_game_result) if chat_data.is_activated else empty_keyboard
            attachment = await cls.get_result_attachment(game_result)

            await send_message(chat_id=chat_id, message=message, keyboard=keyboard, photo=attachment)
            await cls.send_article_message(chat_data)
            await cls.additional_game_logic_before(game_data)
            await RatesService.accept_auto_games(chat_id, cls.GAMES_MODEL, psql_cursor, psql_connection, redis_cursor)

        finally:
            redis_cursor.close()
            psql_cursor.close()
            psql_connection.close()


    @classmethod
    def get_game_bank_message(
            cls,
            chat_data: ChatSchema,
            game_data: GameSchema,
            psql_cursor: DictCursor
    ) -> tuple[str, str]:
        """Возвращает сообщения о поставленных ставках и клавиатуру"""

        rates = cls.get_rates_in_game(game_data.game_id, psql_cursor)
        rates.sort(key=lambda rate: rate.rate_type)

        if len(rates) > 0:

            rates_amount = format_number(sum([x.amount for x in rates]))
            message = f"Всего поставлено: {rates_amount} BC"

            current_rate_type = None
            for rate in rates:
                rate_type = rate.rate_type

                if current_rate_type != rate_type:
                    rate_type_ru = cls.get_rate_type_ru(rate_type)
                    message += f"\n\nСтавки на {rate_type_ru}:"
                    current_rate_type = rate_type

                user_name = UserSchema.format_vk_name(rate.user_id, rate.user_full_name)
                message += f"\n{user_name} - {format_number(rate.amount)} BC"

            if game_data.time_left is not None:

                if game_data.time_left < -10:
                    message += f"\n\n🎮 : {game_data.game_id}"
                message += f"\n\nДо конца раунда: {game_data.time_left} сек.\nХеш игры: {game_data.enc_hash}"

            else:
                message += f"\n\nХеш игры: {game_data.enc_hash}"

        else:
            game_time = chat_data.game_timer
            message = f"""
                🎰 В ожидании ставок...

                ⏳ {game_time} {get_word_case(game_time, ("секунда", "секунды", "секунд"))}

                Хеш игры: {game_data.enc_hash}
            """

        return message, keyboard_game_bank


    @classmethod
    def get_last_game_message(
            cls,
            chat_id: int,
            psql_cursor: DictCursor
    ) -> str:
        """Возвращает сообщение о прошедших играх"""

        psql_cursor.execute("""
            SELECT * FROM games
            WHERE chat_id = %(chat_id)s AND
                  is_active = FALSE
            ORDER BY game_id DESC
            LIMIT 5
        """, {
            "chat_id": chat_id
        })
        last_games = psql_cursor.fetchall()

        if len(last_games) > 0:
            message = "Последние игры:\n"

            for number, last_game in enumerate(last_games, 1):
                last_game["game_result"] = json.loads(last_game["game_result"])
                game = GameSchema(**last_game)

                game_model = cls.GAMES_MODEL[game.game_mode]
                game_result = game_model.format_game_result(game.game_result)

                message += f"""
                    {number}) {game_model.get_result_message(game_result)}
                    Хеш: {game.enc_hash}
                    Проверка честности: {game.str_hash}
                """

        else:
            message = "В этой беседе ещё не было игр"

        return message
