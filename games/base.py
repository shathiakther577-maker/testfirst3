import json
import random
import asyncio
import threading
from collections import defaultdict

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
    
    # Блокировки для предотвращения одновременного завершения одной игры
    _game_locks: dict[int, asyncio.Lock] = defaultdict(lambda: asyncio.Lock())
    _game_locks_lock = threading.Lock()  # Защита словаря блокировок
    _processing_games: set[int] = set()  # Игры которые уже обрабатываются
    _processing_games_lock = threading.Lock()  # Защита множества обрабатываемых игр


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
            response, keyboard = f"{user_name}, на твоём балансе нет WC!", None

        return response, keyboard


    @classmethod
    def init_game(
            cls,
            game_id: int,
            psql_cursor: DictCursor,
            redis_cursor: Redis
    ) -> None:
        """Запускает игру переводя ее в ожидание"""
        
        # Получаем соединение для коммита
        psql_connection = psql_cursor.connection

        if game_id in Temp.GAMES:
            return
        Temp.GAMES.append(game_id)

        game_data = get_game_data(game_id, psql_cursor)
        chat_data = get_chat_data(game_data.chat_id, psql_cursor)

        # КРИТИЧНО: Если end_datetime не установлен, устанавливаем его
        if game_data.end_datetime is None:
            if game_data.time_left is None:
                time_left = chat_data.game_timer
            else:
                time_left = max(game_data.time_left, 0)

            # Устанавливаем end_datetime и коммитим сразу
            psql_cursor.execute("""
                UPDATE games
                SET end_datetime = NOW() + INTERVAL '%(seconds)s second'
                WHERE game_id = %(game_id)s
            """, {
                "seconds": time_left,
                "game_id": game_id
            })
            # Коммитим установку end_datetime сразу
            psql_connection.commit()
            print(f"[GAME] Game {game_id}: end_datetime установлен на {time_left} секунд вперед", flush=True)
        else:
            # Если end_datetime уже установлен, используем его для расчета time_left
            if game_data.time_left is None:
                # Вычисляем time_left из end_datetime
                psql_cursor.execute("""
                    SELECT EXTRACT(EPOCH FROM (end_datetime - NOW())) as time_remaining
                    FROM games
                    WHERE game_id = %(game_id)s
                """, {"game_id": game_id})
                time_result = psql_cursor.fetchone()
                if time_result and time_result["time_remaining"] is not None:
                    time_left = max(time_result["time_remaining"], 0)
                else:
                    time_left = chat_data.game_timer
            else:
                time_left = max(game_data.time_left, 0)

        print(f"[GAME] Starting submit_results thread for game {game_id}, time_left={time_left:.1f}s", flush=True)
        
        def run_submit():
            try:
                asyncio.run(cls.submit_results(game_id, time_left))
            except Exception as e:
                print(f"[GAME ERROR] submit_results failed for game {game_id}: {e}", flush=True)
                import traceback
                traceback.print_exc()
        
        thread = threading.Thread(target=run_submit, daemon=True)
        thread.start()
        print(f"[GAME] Thread started for game {game_id}", flush=True)


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

        # ВАЖНО: Используем ОТДЕЛЬНОЕ соединение для записи результатов
        # чтобы избежать проблем с откатом транзакции при закрытии основного соединения
        from databases.postgresql import get_postgresql_connection
        
        # Создаем отдельное соединение для записи результатов
        result_connection, result_cursor = get_postgresql_connection()
        
        # Сначала начисляем выигрыши в отдельной транзакции
        for user_id, rate in cls._grouped_rates_by_user_id(rates).items():
            winning_sum = rate["winning_sum"]
            
            if winning_sum > 0:
                # Начисляем выигрыш в отдельной транзакции с немедленным коммитом
                print(f"[GAME] User {user_id}: начисляем выигрыш {winning_sum} в отдельной транзакции", flush=True)
                try:
                    win_connection, win_cursor = get_postgresql_connection()
                    win_connection.autocommit = False
                    
                    try:
                        win_cursor.execute("""
                            UPDATE users
                            SET coins = coins + %(winning_sum)s
                            WHERE user_id = %(user_id)s
                        """, {
                            "winning_sum": winning_sum,
                            "user_id": user_id
                        })
                        
                        if win_cursor.rowcount == 0:
                            print(f"[GAME ERROR] Failed to add coins for user {user_id} (rowcount=0)", flush=True)
                            raise ValueError(f"Failed to add coins for user {user_id}")
                        
                        win_connection.commit()
                        print(f"[GAME] User {user_id}: выигрыш {winning_sum} начислен и закоммичен", flush=True)
                        
                        # Проверяем баланс после коммита
                        win_cursor.execute("""
                            SELECT coins FROM users WHERE user_id = %(user_id)s
                        """, {"user_id": user_id})
                        check_result = win_cursor.fetchone()
                        if check_result:
                            print(f"[GAME] User {user_id}: баланс после начисления выигрыша = {check_result['coins']}", flush=True)
                        
                    except Exception as e:
                        win_connection.rollback()
                        print(f"[GAME ERROR] Failed to add coins for user {user_id}: {e}", flush=True)
                        raise
                    finally:
                        win_cursor.close()
                        win_connection.close()
                        
                except Exception as e:
                    print(f"[GAME ERROR] Error in separate transaction for user {user_id}: {e}", flush=True)
                    import traceback
                    traceback.print_exc()
                    # Продолжаем обработку других пользователей

        # Теперь обновляем статистику в ОТДЕЛЬНОМ соединении
        # Убеждаемся что autocommit выключен для транзакции
        if result_connection.autocommit:
            print(f"[GAME WARNING] Result connection autocommit was True, setting to False", flush=True)
        result_connection.autocommit = False
        
        print(f"[GAME] Starting statistics update transaction for game {game_id}", flush=True)

        try:
            for user_id, rate in cls._grouped_rates_by_user_id(rates).items():

                rates_sum = rate["rates_sum"]
                winning_sum = rate["winning_sum"]
                clean_winning = rate["clean_winning"]
                clean_losing = rate["clean_losing"]

                # В топ добавляется сумма выигрышей (winning_sum), а не разница выигрышей и проигрышей
                # Если игрок проиграл 5млн и выиграл 1млн, к топу прибавляем 1млн
                # top_points используется для all_top_points (с учетом accrual_top_points)
                top_points = max(winning_sum, 0) * accrual_top_points
                # Для day/week/month_top_points используем winning_sum напрямую (без умножения на accrual_top_points)
                day_top_points_value = max(winning_sum, 0)
                week_top_points_value = max(winning_sum, 0)
                month_top_points_value = max(winning_sum, 0)
                # clan_points также используем winning_sum напрямую
                clan_points = day_top_points_value if rate["clan_id"] is not None else 0
                coins_top_points = day_top_points_value if (
                    TopSettings.DATETIME_COINS_TOP and
                    datetime.now().date() < TopSettings.DATETIME_COINS_TOP
                ) else 0

                accrue_bot_income: bool = rate["user_status"] != UserStatus.ADMIN
                # Условие, которое показывает начислять ли прибыль за игру у игрока
                
                # Логируем информацию
                print(f"[GAME] User {user_id}: rates_sum={rates_sum}, winning_sum={winning_sum}, clean_winning={clean_winning}, clean_losing={clean_losing}", flush=True)
                
                # Обновляем статистику и топ-поинты (НЕ трогаем coins!)
                print(f"[GAME] User {user_id}: обновляем статистику (winning={clean_winning}, losing={clean_losing}, top_points={top_points})", flush=True)
                result_cursor.execute("""
                    UPDATE users
                    SET clan_points = clan_points + %(clan_points)s,
                        all_top_points = all_top_points + %(top_points)s,
                        day_top_points = day_top_points + %(day_top_points_value)s,
                        week_top_points = week_top_points + %(week_top_points_value)s,
                        month_top_points = month_top_points + %(month_top_points_value)s,
                        coins_top_points = coins_top_points + %(coins_top_points)s,
                        rubles_top_points = rubles_top_points + %(top_points)s,
                        week_rubles_top_points = week_rubles_top_points + %(top_points)s,
                        day_win = day_win + %(winning_sum)s,
                        day_lost = day_lost + %(losing)s,
                        day_rates = day_rates + %(rates)s,
                        week_win = week_win + %(winning_sum)s,
                        week_lost = week_lost + %(losing)s,
                        week_rates = week_rates + %(rates)s,
                        all_win = all_win + %(winning_sum)s,
                        all_lost = all_lost + %(losing)s,
                        all_rates = all_rates + %(rates)s
                    WHERE user_id = %(user_id)s
                """, {
                    "clan_points": clan_points,
                    "top_points": top_points,
                    "day_top_points_value": day_top_points_value,
                    "week_top_points_value": week_top_points_value,
                    "month_top_points_value": month_top_points_value,
                    "coins_top_points": coins_top_points,
                    "winning_sum": winning_sum,
                    "losing": clean_losing,
                    "rates": rates_sum,
                    "user_id": user_id
                })
                
                if result_cursor.rowcount == 0:
                    print(f"[GAME ERROR] User {user_id}: UPDATE не выполнен (rowcount=0)!", flush=True)
                else:
                    print(f"[GAME] User {user_id}: статистика обновлена (rowcount={result_cursor.rowcount})", flush=True)
                    
                    # Обновляем таблицы топов (day/week/month/all_time)
                    if winning_sum > 0:
                        try:
                            result_cursor.execute("""
                                SELECT add_user_winnings(%(user_id)s, %(winning_sum)s)
                            """, {
                                "user_id": user_id,
                                "winning_sum": winning_sum
                            })
                            print(f"[GAME] User {user_id}: обновлены таблицы топов (winning_sum={winning_sum})", flush=True)
                        except Exception as e:
                            # Если таблицы еще не созданы, просто логируем
                            print(f"[GAME WARNING] User {user_id}: не удалось обновить таблицы топов: {e}", flush=True)
                    
                    # Проверяем значения после UPDATE (до коммита)
                    result_cursor.execute("""
                        SELECT all_win, day_win, week_win, all_top_points, day_top_points, week_top_points, month_top_points
                        FROM users WHERE user_id = %(user_id)s
                    """, {"user_id": user_id})
                    check_result = result_cursor.fetchone()
                    if check_result:
                        print(f"[GAME] User {user_id}: значения после UPDATE (до коммита): all_win={check_result['all_win']}, day_win={check_result['day_win']}, week_win={check_result['week_win']}, all_top_points={check_result['all_top_points']}", flush=True)

                if accrue_bot_income:
                    bot_income -= clean_winning if accrue_bot_income else 0
                    bot_income += clean_losing if accrue_bot_income else 0

            # ВАЖНО: Обновляем income ДО коммита, чтобы пометить игру как обработанную
            result_cursor.execute("""
                UPDATE games
                SET income = %(bot_income)s,
                    is_active = FALSE
                WHERE game_id = %(game_id)s
            """, {
                "bot_income": bot_income,
                "game_id": game_id
            })
            
            if result_cursor.rowcount == 0:
                print(f"[GAME ERROR] Failed to update game {game_id} income (rowcount=0)!", flush=True)
            else:
                print(f"[GAME] Game {game_id} income updated to {bot_income}, is_active set to FALSE", flush=True)

            # Вставляем в completed_games если таблица существует
            try:
                result_cursor.execute("""
                    INSERT INTO completed_games (game_id)
                    VALUES (%(game_id)s)
                """, {"game_id": game_id})
            except Exception:
                # Таблица может не существовать, это не критично
                pass

            # Коммитим транзакцию со статистикой (выигрыши уже начислены в отдельных транзакциях)
            print(f"[GAME] Коммитим транзакцию для игры {game_id}...", flush=True)
            result_connection.commit()
            print(f"[GAME] Транзакция закоммичена для игры {game_id}", flush=True)
            
            # КРИТИЧНО: Проверяем что income действительно сохранился после коммита
            # Используем новое соединение для проверки
            check_conn, check_cur = get_postgresql_connection()
            check_cur.execute("""
                SELECT income, is_active FROM games WHERE game_id = %(game_id)s
            """, {"game_id": game_id})
            income_check = check_cur.fetchone()
            if income_check:
                if income_check["income"] != bot_income:
                    print(f"[GAME ERROR] Game {game_id} income не совпадает после коммита! Ожидалось {bot_income}, получено {income_check['income']}", flush=True)
                    # Исправляем income в отдельной транзакции
                    check_cur.execute("""
                        UPDATE games SET income = %(bot_income)s WHERE game_id = %(game_id)s
                    """, {"bot_income": bot_income, "game_id": game_id})
                    check_conn.commit()
                    print(f"[GAME] Game {game_id} income исправлен до {bot_income}", flush=True)
                else:
                    print(f"[GAME] Game {game_id} income подтвержден после коммита: {income_check['income']}", flush=True)
            
            # КРИТИЧНО: Проверяем что статистика действительно сохранилась после коммита
            for user_id, rate in cls._grouped_rates_by_user_id(rates).items():
                winning_sum = rate["winning_sum"]
                if winning_sum > 0:  # Проверяем только если был выигрыш
                    check_cur.execute("""
                        SELECT day_top_points, week_top_points, month_top_points, all_top_points, day_win, week_win, all_win
                        FROM users WHERE user_id = %(user_id)s
                    """, {"user_id": user_id})
                    stats_check = check_cur.fetchone()
                    if stats_check:
                        # Проверяем что статистика обновилась (должна быть больше 0 если был выигрыш)
                        expected_day_top = stats_check["day_top_points"]
                        expected_week_top = stats_check["week_top_points"]
                        print(f"[GAME] User {user_id}: статистика после коммита - day_top={expected_day_top}, week_top={expected_week_top}, day_win={stats_check['day_win']}, week_win={stats_check['week_win']}", flush=True)
            
            check_cur.close()
            check_conn.close()
            
            # Закрываем соединение после проверки
            result_cursor.close()
            result_connection.close()
            
            print(f"[GAME] write_game_result: успешно записаны результаты для игры {game_id}", flush=True)
            
            # Проверяем что балансы действительно обновились (выигрыши уже начислены в отдельных транзакциях)
            try:
                import time
                time.sleep(0.1)
                
                check_connection, check_cursor = get_postgresql_connection()
                for user_id, rate in cls._grouped_rates_by_user_id(rates).items():
                    winning_sum = rate["winning_sum"]
                    if winning_sum > 0:
                        check_cursor.execute("""
                            SELECT coins FROM users WHERE user_id = %(user_id)s
                        """, {"user_id": user_id})
                        check_result = check_cursor.fetchone()
                        if check_result:
                            print(f"[GAME] User {user_id}: финальный баланс после всех коммитов = {check_result['coins']}", flush=True)
                check_cursor.close()
                check_connection.close()
            except Exception as e:
                print(f"[GAME WARNING] Не удалось проверить баланс после коммита: {e}", flush=True)
            
            return True

        except Exception as e:
            result_connection.rollback()
            print(f"[GAME ERROR] write_game_result failed for game {game_id}: {e}", flush=True)
            import traceback
            traceback.print_exc()
            return False

        finally:
            # Соединение уже закрыто выше, после коммита
            pass


    @classmethod
    def get_game_message(
            cls,
            rates: list[Optional[CalculateRateSchema]],
            game_data: GameSchema,
            game_result: GAME_RESULT
    ) -> str:
        """Возвращает итоговое сообщение игры"""

        if not rates:
            return f"{cls.get_result_message(game_result)}\n\n❌ Ставок не было\n\nХеш игры: {game_data.enc_hash}\nПроверка честности: {game_data.str_hash}"

        message = f"{cls.get_result_message(game_result)}\n\n📊 Результаты ставок:\n"

        # Сортируем ставки: сначала выигравшие, потом проигравшие
        sorted_rates = sorted(rates, key=lambda r: (not r.is_winning if r else True, -r.amount if r else 0))

        for rate in sorted_rates:
            if rate is None:
                continue
                
            emoji = "✅" if rate.is_winning else "❌"
            # Используем telegram_name вместо vk_name
            user_name = rate.user_full_name if rate.user_full_name else f"User {rate.user_id}"

            rate_type_ru = cls.get_rate_type_ru(rate.rate_type)
            rate_type_ru = f"на {rate_type_ru}" if rate_type_ru else ""

            rate_amount = rate.amount
            format_amount = f"ставка {format_number(rate_amount)} {get_word_case(rate_amount, ('коин', 'коина', 'коинов'))}"
            rate_status_ru = "выиграла!" if rate.is_winning else "проиграла"
            winning_ru = f"(приз {format_number(rate.winning_amount)} WC)" if rate.is_winning else ""

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

        print(f"[GAME] submit_results started for game {game_id}, time_left={time_left}", flush=True)
        
        # Проверяем, не обрабатывается ли уже эта игра
        with cls._processing_games_lock:
            if game_id in cls._processing_games:
                print(f"[GAME] Game {game_id} уже обрабатывается, пропускаем", flush=True)
                return
            cls._processing_games.add(game_id)
        
        # Получаем блокировку для этой игры
        with cls._game_locks_lock:
            game_lock = cls._game_locks[game_id]
        
        try:
            # Используем блокировку для предотвращения одновременного завершения
            async with game_lock:
                redis_cursor = get_redis_cursor()
                psql_connection, psql_cursor = get_postgresql_connection()
                
                # ВАЖНО: Убеждаемся что autocommit выключен для основного соединения
                # чтобы избежать проблем с откатом транзакций
                if psql_connection.autocommit:
                    print(f"[GAME WARNING] Main connection autocommit was True, setting to False", flush=True)
                psql_connection.autocommit = False

                try:
                    # Проверяем состояние игры перед началом обработки
                    game_data = get_game_data(game_id, psql_cursor)
                    if game_data is None:
                        print(f"[GAME ERROR] Game {game_id} not found!", flush=True)
                        return
                    
                    # Проверяем что игра еще активна или не обработана
                    if not game_data.is_active:
                        # Проверяем обработана ли игра (есть ли income И есть ли ставки)
                        psql_cursor.execute("""
                            SELECT g.income, COUNT(r.game_id) as rates_count
                            FROM games g
                            LEFT JOIN rates r ON r.game_id = g.game_id
                            WHERE g.game_id = %(game_id)s
                            GROUP BY g.game_id, g.income
                        """, {"game_id": game_id})
                        check_result = psql_cursor.fetchone()
                        if check_result:
                            income = check_result["income"]
                            rates_count = check_result["rates_count"]
                            # КРИТИЧНО: Если income установлен (не NULL) и != -1, значит игра уже обработана
                            # income может быть 0 (бот не получил прибыль), но это все равно означает что игра обработана
                            # income = -1 означает что игра нуждается в повторной обработке
                            if income is not None and income != -1:
                                print(f"[GAME] Game {game_id} уже завершена и обработана (income={income}, rates={rates_count}), пропускаем", flush=True)
                                return
                            elif rates_count == 0:
                                print(f"[GAME] Game {game_id} завершена, но нет ставок, пропускаем", flush=True)
                                return
                            else:
                                # income=0, income=-1 или income IS NULL - игра не обработана, обрабатываем
                                print(f"[GAME] Game {game_id} завершена, но не обработана (income={income}, rates={rates_count}), обрабатываем", flush=True)
                                # Продолжаем обработку
                        else:
                            print(f"[GAME] Game {game_id} не найдена в БД, пропускаем", flush=True)
                            return
                    
                    chat_id = game_data.chat_id
                    
                    # Проверяем end_datetime и рассчитываем реальное оставшееся время
                    if game_data.end_datetime:
                        # Используем SQL для расчета оставшегося времени, чтобы избежать проблем с timezone
                        psql_cursor.execute("""
                            SELECT EXTRACT(EPOCH FROM (end_datetime - NOW())) as time_remaining
                            FROM games
                            WHERE game_id = %(game_id)s
                        """, {"game_id": game_id})
                        time_result = psql_cursor.fetchone()
                        
                        if time_result and time_result["time_remaining"] is not None:
                            time_remaining = time_result["time_remaining"]
                            print(f"[GAME] Game {game_id}: time_remaining from DB={time_remaining:.1f}s (end_datetime={game_data.end_datetime})", flush=True)
                            
                            # Если время уже вышло, не ждем
                            if time_remaining <= 0:
                                print(f"[GAME] Game {game_id}: время уже вышло (time_remaining={time_remaining:.1f}s), пропускаем ожидание", flush=True)
                                sleep_time = 0
                            else:
                                # Используем реальное оставшееся время вместо переданного time_left
                                sleep_time = max(time_remaining - cls.DELAY_BEFORE_RESULT, 0)
                        else:
                            # Если не удалось получить время из БД, используем переданный time_left
                            print(f"[GAME] Game {game_id}: не удалось получить time_remaining из БД, используем time_left={time_left}", flush=True)
                            sleep_time = max(time_left - cls.DELAY_BEFORE_RESULT, 0)
                    else:
                        # Если нет end_datetime, используем переданный time_left
                        sleep_time = max(time_left - cls.DELAY_BEFORE_RESULT, 0)
                    
                    print(f"[GAME] Game {game_id}: sleeping for {sleep_time:.1f}s (time_left={time_left}, DELAY_BEFORE_RESULT={cls.DELAY_BEFORE_RESULT})", flush=True)
                    if sleep_time > 0:
                        await asyncio.sleep(sleep_time)
                    
                    # Повторно проверяем что игра еще существует после ожидания
                    game_data_check = get_game_data(game_id, psql_cursor)
                    if game_data_check is None:
                        print(f"[GAME ERROR] Game {game_id} not found after sleep!", flush=True)
                        return
                    
                    # Если игра завершена, проверяем обработана ли она
                    if not game_data_check.is_active:
                        psql_cursor.execute("""
                            SELECT income FROM games WHERE game_id = %(game_id)s
                        """, {"game_id": game_id})
                        income_check = psql_cursor.fetchone()
                        if income_check and income_check["income"] is not None and income_check["income"] != 0:
                            print(f"[GAME] Game {game_id} уже завершена и обработана после ожидания (income={income_check['income']}), пропускаем", flush=True)
                            return
                        else:
                            print(f"[GAME] Game {game_id} завершена после ожидания, но не обработана (income={income_check['income'] if income_check else None}), обрабатываем", flush=True)
                    
                    # Обновляем game_data на актуальную версию
                    game_data = game_data_check
                    
                    # КРИТИЧНО: Проверяем income ПЕРЕД отправкой сообщения (без блокировки, чтобы не блокировать обработку)
                    psql_cursor.execute("""
                        SELECT income FROM games WHERE game_id = %(game_id)s
                    """, {"game_id": game_id})
                    income_before_msg = psql_cursor.fetchone()
                    if income_before_msg:
                        income_value = income_before_msg["income"]
                        # КРИТИЧНО: Если income установлен (не NULL), игра уже обработана
                        # income может быть 0 (бот не получил прибыль), но это все равно означает что игра обработана
                        # income = -1 означает что игра нуждается в повторной обработке
                        if income_value is not None and income_value != -1:
                            print(f"[GAME] Game {game_id} уже обработана перед отправкой сообщения (income={income_value}), пропускаем", flush=True)
                            return
                    
                    # Проверяем время еще раз перед отправкой сообщения
                    if game_data.end_datetime:
                        psql_cursor.execute("""
                            SELECT EXTRACT(EPOCH FROM (end_datetime - NOW())) as time_remaining
                            FROM games
                            WHERE game_id = %(game_id)s
                        """, {"game_id": game_id})
                        time_check_result = psql_cursor.fetchone()
                        
                        if time_check_result and time_check_result["time_remaining"] is not None:
                            time_remaining_check = time_check_result["time_remaining"]
                            # Если время уже вышло, отправляем результаты сразу
                            if time_remaining_check <= 0:
                                print(f"[GAME] Game {game_id}: время уже вышло перед отправкой сообщения (time_remaining={time_remaining_check:.1f}s), отправляем результаты сразу", flush=True)
                                # КРИТИЧНО: Еще раз проверяем income перед отправкой сообщения (без блокировки)
                                psql_cursor.execute("""
                                    SELECT income FROM games WHERE game_id = %(game_id)s
                                """, {"game_id": game_id})
                                income_check_msg = psql_cursor.fetchone()
                                if income_check_msg and income_check_msg["income"] is not None and income_check_msg["income"] != -1:
                                    print(f"[GAME] Game {game_id} уже обработана перед отправкой сообщения (income={income_check_msg['income']}), пропускаем", flush=True)
                                    return
                                # Отправляем сообщение сразу без задержки и сразу обрабатываем результаты
                                await cls.additional_game_logic_after(game_data)
                                await send_message(chat_id=chat_id, message="Итак, результаты раунда...")
                                # КРИТИЧНО: Устанавливаем income=0 сразу после отправки сообщения, чтобы предотвратить повторные отправки
                                psql_cursor.execute("""
                                    UPDATE games SET income = 0 WHERE game_id = %(game_id)s AND (income IS NULL OR income = -1)
                                """, {"game_id": game_id})
                                psql_connection.commit()
                                print(f"[GAME] Game {game_id}: установлен income=0 после отправки сообщения", flush=True)
                                # НЕ ждем, сразу обрабатываем результаты
                            else:
                                # Если время еще не вышло, отправляем сообщение с задержкой
                                # КРИТИЧНО: Проверяем income перед отправкой сообщения (без блокировки)
                                psql_cursor.execute("""
                                    SELECT income FROM games WHERE game_id = %(game_id)s
                                """, {"game_id": game_id})
                                income_check_msg2 = psql_cursor.fetchone()
                                if income_check_msg2 and income_check_msg2["income"] is not None and income_check_msg2["income"] != -1:
                                    print(f"[GAME] Game {game_id} уже обработана перед отправкой сообщения (income={income_check_msg2['income']}), пропускаем", flush=True)
                                    return
                                print(f"[GAME] Game {game_id}: sleep completed, processing results...", flush=True)
                                await cls.additional_game_logic_after(game_data)
                                await send_message(chat_id=chat_id, message="Итак, результаты раунда...")
                                # КРИТИЧНО: Устанавливаем income=0 сразу после отправки сообщения, чтобы предотвратить повторные отправки
                                psql_cursor.execute("""
                                    UPDATE games SET income = 0 WHERE game_id = %(game_id)s AND (income IS NULL OR income = -1)
                                """, {"game_id": game_id})
                                psql_connection.commit()
                                print(f"[GAME] Game {game_id}: установлен income=0 после отправки сообщения", flush=True)
                                await asyncio.sleep(cls.DELAY_BEFORE_RESULT)
                        else:
                            # Если не удалось проверить время, проверяем income перед отправкой (без блокировки)
                            psql_cursor.execute("""
                                SELECT income FROM games WHERE game_id = %(game_id)s
                            """, {"game_id": game_id})
                            income_check_msg3 = psql_cursor.fetchone()
                            if income_check_msg3 and income_check_msg3["income"] is not None and income_check_msg3["income"] != -1:
                                print(f"[GAME] Game {game_id} уже обработана перед отправкой сообщения (income={income_check_msg3['income']}), пропускаем", flush=True)
                                return
                            # Если не удалось проверить время, отправляем как обычно
                            print(f"[GAME] Game {game_id}: sleep completed, processing results...", flush=True)
                            await cls.additional_game_logic_after(game_data)
                            await send_message(chat_id=chat_id, message="Итак, результаты раунда...")
                            # КРИТИЧНО: Устанавливаем income=0 сразу после отправки сообщения, чтобы предотвратить повторные отправки
                            psql_cursor.execute("""
                                UPDATE games SET income = 0 WHERE game_id = %(game_id)s AND (income IS NULL OR income = -1)
                            """, {"game_id": game_id})
                            psql_connection.commit()
                            print(f"[GAME] Game {game_id}: установлен income=0 после отправки сообщения", flush=True)
                            await asyncio.sleep(cls.DELAY_BEFORE_RESULT)
                    else:
                        # Если нет end_datetime, проверяем income перед отправкой (без блокировки)
                        psql_cursor.execute("""
                            SELECT income FROM games WHERE game_id = %(game_id)s
                        """, {"game_id": game_id})
                        income_check_msg4 = psql_cursor.fetchone()
                        if income_check_msg4 and income_check_msg4["income"] is not None and income_check_msg4["income"] != -1:
                            print(f"[GAME] Game {game_id} уже обработана перед отправкой сообщения (income={income_check_msg4['income']}), пропускаем", flush=True)
                            return
                        # Если нет end_datetime, отправляем как обычно
                        print(f"[GAME] Game {game_id}: sleep completed, processing results...", flush=True)
                        await cls.additional_game_logic_after(game_data)
                        await send_message(chat_id=chat_id, message="Итак, результаты раунда...")
                        # КРИТИЧНО: Устанавливаем income=0 сразу после отправки сообщения, чтобы предотвратить повторные отправки
                        psql_cursor.execute("""
                            UPDATE games SET income = 0 WHERE game_id = %(game_id)s AND (income IS NULL OR income = -1)
                        """, {"game_id": game_id})
                        psql_connection.commit()
                        print(f"[GAME] Game {game_id}: установлен income=0 после отправки сообщения", flush=True)
                        await asyncio.sleep(cls.DELAY_BEFORE_RESULT)

                    # Еще раз проверяем перед записью результатов
                    game_data_final = get_game_data(game_id, psql_cursor)
                    if game_data_final is None:
                        print(f"[GAME] Game {game_id} не найдена, пропускаем", flush=True)
                        return
                    
                    # Если игра уже завершена, все равно обрабатываем результаты (возможно они не были обработаны)
                    if not game_data_final.is_active:
                        print(f"[GAME] Game {game_id} уже завершена, но обрабатываем результаты на всякий случай", flush=True)
                        # Продолжаем обработку результатов даже если игра завершена
                    
                    # Если время уже вышло, сразу обрабатываем результаты без дополнительных проверок
                    time_remaining_final = None
                    if game_data_final.end_datetime:
                        psql_cursor.execute("""
                            SELECT EXTRACT(EPOCH FROM (end_datetime - NOW())) as time_remaining
                            FROM games
                            WHERE game_id = %(game_id)s
                        """, {"game_id": game_id})
                        time_final_result = psql_cursor.fetchone()
                        if time_final_result and time_final_result["time_remaining"] is not None:
                            time_remaining_final = time_final_result["time_remaining"]
                    
                    # Если время вышло, обрабатываем результаты сразу
                    if time_remaining_final is not None and time_remaining_final <= 0:
                        print(f"[GAME] Game {game_id}: время вышло (time_remaining={time_remaining_final:.1f}s), обрабатываем результаты немедленно", flush=True)
                        # Пропускаем дополнительную задержку и сразу обрабатываем
                    
                    chat_data = get_chat_data(game_data.chat_id, psql_cursor)
                    if chat_data is None:
                        print(f"[GAME ERROR] Chat {game_data.chat_id} not found for game {game_id}!", flush=True)
                        return
                    
                    game_result = cls.format_game_result(game_data.game_result)

                    rates = cls.get_rates_in_game(game_id, psql_cursor)
                    print(f"[GAME] Game {game_id}: found {len(rates)} rates in game", flush=True)
                    
                    if not rates:
                        print(f"[GAME] Game {game_id}: no rates found, skipping results", flush=True)
                        # Помечаем игру как неактивную даже если нет ставок
                        psql_cursor.execute("""
                            UPDATE games SET is_active = FALSE
                            WHERE game_id = %(game_id)s
                        """, {"game_id": game_id})
                        psql_connection.commit()
                        print(f"[GAME] Game {game_id}: marked as inactive (no rates)", flush=True)
                        # Закрываем соединения
                        psql_cursor.close()
                        psql_connection.close()
                        return
                    
                    rates = cls.calculate_winnings(rates, game_result)
                    print(f"[GAME] Game {game_id}: calculated {len(rates)} rates (winners: {sum(1 for r in rates if r.is_winning)})", flush=True)
                    
                    write_status = cls.write_game_result(game_id, rates, psql_cursor, psql_connection)

                    if write_status is False:
                        print(f"[GAME ERROR] Game {game_id}: write_game_result returned False", flush=True)
                        return
                    
                    print(f"[GAME] Game {game_id}: results written successfully", flush=True)

                    # Помечаем игру как неактивную перед созданием новой
                    psql_cursor.execute("""
                        UPDATE games SET is_active = FALSE
                        WHERE game_id = %(game_id)s AND is_active = TRUE
                    """, {
                        "game_id": game_id
                    })
                    
                    # Проверяем что обновление прошло успешно
                    if psql_cursor.rowcount == 0:
                        print(f"[GAME] Game {game_id} уже была помечена как неактивная", flush=True)
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
                    
                    # Удаляем из Temp.GAMES только если игра была в списке
                    if game_id in Temp.GAMES:
                        Temp.GAMES.remove(game_id)

                    message = cls.get_game_message(rates, game_data, game_result)
                    print(f"[GAME] Game {game_id}: message length={len(message)}, rates count={len(rates)}", flush=True)
                    
                    keyboard = new_game_model.get_game_keyboard(new_game_result) if chat_data.is_activated else empty_keyboard
                    
                    # Пытаемся получить attachment, но не блокируем отправку если не получится
                    attachment = None
                    try:
                        attachment = await cls.get_result_attachment(game_result)
                        # Проверяем что attachment валидный и не в VK-формате
                        # VK-формат: "photo-207204376_457441504"
                        # Telegram file_id обычно начинается с других префиксов или это URL
                        if attachment and len(attachment) > 10:
                            # Если это VK-формат (начинается с "photo-"), пропускаем
                            if attachment.startswith("photo-") and "_" in attachment:
                                print(f"[GAME] Game {game_id}: attachment is VK format, skipping photo: {attachment[:30]}", flush=True)
                                attachment = None
                            else:
                                print(f"[GAME] Game {game_id}: attachment obtained (length={len(attachment)})", flush=True)
                        else:
                            print(f"[GAME] Game {game_id}: invalid attachment, skipping photo", flush=True)
                            attachment = None
                    except Exception as e:
                        print(f"[GAME WARNING] Game {game_id}: failed to get attachment: {e}", flush=True)
                        import traceback
                        traceback.print_exc()
                        attachment = None

                    # Отправляем сообщение с результатами
                    # ВАЖНО: отправляем БЕЗ фото сначала, чтобы гарантировать доставку результатов
                    print(f"[GAME] Game {game_id}: sending results message to chat {chat_id}", flush=True)
                    print(f"[GAME] Game {game_id}: message length={len(message)}, rates count={len(rates)}", flush=True)
                    
                    message_sent = False
                    
                    # Сначала пытаемся отправить текстовое сообщение с результатами
                    try:
                        result = await send_message(chat_id=chat_id, message=message, keyboard=keyboard, photo=None)
                        if result:
                            print(f"[GAME] Game {game_id}: results message sent successfully (text)", flush=True)
                            message_sent = True
                        else:
                            print(f"[GAME WARNING] Game {game_id}: send_message returned None", flush=True)
                    except Exception as e:
                        print(f"[GAME ERROR] Game {game_id}: failed to send text message: {e}", flush=True)
                        import traceback
                        traceback.print_exc()
                    
                    # Если текстовое сообщение не отправилось, пробуем еще раз без клавиатуры
                    if not message_sent:
                        try:
                            print(f"[GAME] Game {game_id}: retrying without keyboard", flush=True)
                            result = await send_message(chat_id=chat_id, message=message, keyboard=None, photo=None)
                            if result:
                                print(f"[GAME] Game {game_id}: results message sent without keyboard", flush=True)
                                message_sent = True
                        except Exception as e:
                            print(f"[GAME ERROR] Game {game_id}: failed to send message without keyboard: {e}", flush=True)
                    
                    # Если есть валидное attachment и сообщение отправилось, пытаемся отправить фото отдельно
                    if attachment and message_sent:
                        try:
                            print(f"[GAME] Game {game_id}: sending photo separately", flush=True)
                            await send_message(chat_id=chat_id, message=None, keyboard=None, photo=attachment)
                            print(f"[GAME] Game {game_id}: photo sent successfully", flush=True)
                        except Exception as e:
                            print(f"[GAME WARNING] Game {game_id}: failed to send photo (non-critical): {e}", flush=True)
                            # Это не критично, главное что результаты отправлены
                    
                    await cls.send_article_message(chat_data)
                    await cls.additional_game_logic_before(game_data)
                    await RatesService.accept_auto_games(chat_id, cls.GAMES_MODEL, psql_cursor, psql_connection, redis_cursor)
                    
                    # КРИТИЧНО: Коммитим все изменения в основном соединении
                    # (is_active=FALSE, новая игра, и т.д.)
                    print(f"[GAME] Game {game_id}: committing main transaction", flush=True)
                    psql_connection.commit()
                    print(f"[GAME] Game {game_id}: main transaction committed successfully", flush=True)

                finally:
                    # Закрываем соединения после коммита
                    try:
                        psql_cursor.close()
                        psql_connection.close()
                        print(f"[GAME] Game {game_id}: connections closed", flush=True)
                    except Exception as e:
                        print(f"[GAME WARNING] Game {game_id}: error closing connections: {e}", flush=True)
        
        finally:
            # Удаляем игру из списка обрабатываемых
            with cls._processing_games_lock:
                cls._processing_games.discard(game_id)
            
            # Очищаем блокировку если она больше не нужна (опционально, для экономии памяти)
            # Можно оставить для возможных повторных использований


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
            message = f"Всего поставлено: {rates_amount} WC"

            current_rate_type = None
            for rate in rates:
                rate_type = rate.rate_type

                if current_rate_type != rate_type:
                    rate_type_ru = cls.get_rate_type_ru(rate_type)
                    message += f"\n\nСтавки на {rate_type_ru}:"
                    current_rate_type = rate_type

                # Используем telegram_name вместо vk_name
                user_name = rate.user_full_name if rate.user_full_name else f"User {rate.user_id}"
                message += f"\n{user_name} - {format_number(rate.amount)} WC"

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
