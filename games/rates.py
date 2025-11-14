from typing import TypeVar, Optional
from redis.client import Redis
import json
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from psycopg2.extras import DictCursor
from psycopg2._psycopg import connection as Connection

from settings import VkBotSettings, NotifyChats, Config, Temp
from games.auto_game import AutoGameService

from schemas.users import UserSchema, UserStatus
from schemas.chats import ChatSchema, INCOME_CHAT_TYPE
from schemas.games import Games
from schemas.rates import RatesSchema
from schemas.redis import RedisKeys

from services.notification import NotificationsService

from modules.additional import strtobool, format_number, convert_number, get_word_case
from modules.databases.users import get_user_data, give_coins
from modules.databases.chats import get_chat_data, get_game_data
from modules.telegram.bot import send_message


GAME_MODEL = TypeVar("GAME_MODEL")  # bound=BaseGameModel
GAME_RESULT = TypeVar("GAME_RESULT")  # bound=pydantic(BaseModel)


VABANK_TRIGGER = ["вб", "вабанк", "vb", "vabank"]


class RatesService:

    @classmethod
    def get_rate_limit(
            cls,
            rate_type: str,
            game_model: GAME_MODEL,
            game_result: GAME_RESULT
    ) -> int:
        """Возвращает сумму максимальной ставки на событие"""
        # Здесь распаковываются ставки split(" ")

        rates_type = rate_type.split(" ")
        rate_limit = min([
            Config.MAX_WINNING // game_model.get_coefficient(x, game_result)
            for x in rates_type
        ])

        return int(rate_limit)


    @staticmethod
    def get_user_rates(
            user_id: int,
            game_id: int,
            psql_cursor: DictCursor
    ) -> list[Optional[RatesSchema]]:
        """Возвращает ставки пользователя в игре"""

        psql_cursor.execute("""
            SELECT * FROM rates
            WHERE game_id = %(game_id)s AND
                  user_id = %(user_id)s
        """, {
            "game_id": game_id,
            "user_id": user_id
        })
        psql_response = psql_cursor.fetchall()
        user_rates = [RatesSchema(**x) for x in psql_response]

        return user_rates


    @classmethod
    def _get_user_rates_type_in_game(
            cls,
            user_id: int,
            game_id: int,
            psql_cursor: DictCursor
    ) -> list[Optional[str]]:
        """Возвращает события на которые ставил пользователь в конкретной игре"""

        rates = cls.get_user_rates(user_id, game_id, psql_cursor)
        return [x.rate_type for x in rates]


    @classmethod
    def _get_bet_amunt_in_game(
            cls,
            user_id: int,
            game_id: int,
            rate_type: str,
            psql_cursor: DictCursor
    ) -> int:
        """Возвращает сумму ставки на события в конкретной игре"""

        psql_cursor.execute("""
            SELECT amount FROM rates
            WHERE user_id = %(user_id)s AND
                  game_id = %(game_id)s AND
                  rate_type = %(rate_type)s
        """, {
            "user_id": user_id,
            "game_id": game_id,
            "rate_type": rate_type
        })
        psql_response = psql_cursor.fetchone()

        return psql_response["amount"] if psql_response else 0


    @classmethod
    def _calculate_profit_chat_owner(
            cls,
            user_data: UserSchema,
            chat_data: ChatSchema,
            rate_amount: int,
            psql_cursor: DictCursor
    ) -> int:
        """Возвращает сумму сколько начислено владельцу чата за принятую ставку"""

        income = int(INCOME_CHAT_TYPE[chat_data.type] / 100 * rate_amount)
        income = income * (user_data.status != UserStatus.ADMIN)

        if income > 0:
            give_coins(chat_data.owner_id, income, psql_cursor)

        return income


    @classmethod
    async def _accept_bet(
            cls,
            user_id: int,
            chat_id: int,
            game_id: int,
            amount: str | int,
            rate_type: str,
            game_model: GAME_MODEL,
            psql_cursor: DictCursor,
            psql_connection: Connection,
            number_games: int = 1,
            from_auto_game: bool = False,
            number_auto_games: int = 0
    ) -> tuple[str, bool, str | None]:
        """Возвращает сообщение пользователю, статус принятия ставки, лог о принятии ставки"""

        user_data = get_user_data(user_id, psql_cursor)
        user_name = user_data.vk_name
        user_coins = user_data.coins

        chat_data = get_chat_data(chat_id, psql_cursor)
        game_mode = chat_data.game_mode
        current_game_id = chat_data.game_id

        game_data = get_game_data(current_game_id, psql_cursor)
        game_result = game_model.format_game_result(game_data.game_result)
        game_all_rates = game_model.get_all_rates_type()

        if (
            current_game_id != game_id or
            rate_type not in game_all_rates
        ):
            return f"{user_name} данные устарели, ставка отклонена", False, None

        rate_limit = cls.get_rate_limit(rate_type, game_model, game_result)
        old_rate_amount = cls._get_bet_amunt_in_game(user_id, game_id, rate_type, psql_cursor)
        split_amount = amount.split(" ") if isinstance(amount, str) else []

        if isinstance(amount, int):
            amount = amount

        elif VkBotSettings.APPEAL_TO_BOT in amount and len(split_amount) == 2:
            amount = convert_number(split_amount[-1])

        elif amount in VABANK_TRIGGER:
            amount = rate_limit if user_coins > rate_limit else user_coins

            if amount + old_rate_amount > rate_limit:
                amount -= old_rate_amount

            if amount <= 0:
                return f"{user_name}, у вас уже стоит максимальная ставка на событие", False, None

        else:
            amount = convert_number(amount)

        if amount is None:
            return f"{user_name}, не получилось распознать сумму ставки", False, None

        if amount < 1:
            return f"{user_name}, минимальная ставка - 1 коин", False, None

        if not from_auto_game and user_coins < amount * number_games:
            return f"{user_name}, на вашем балансе недостаточно средств", False, None

        user_rates_type = cls._get_user_rates_type_in_game(user_id, game_id, psql_cursor)
        opposite_rates = game_model.check_opposite_rates(rate_type, user_rates_type)

        if opposite_rates:
            return f"{user_name}, вы уже поставили на противоположное событие!", False, None

        rate_type_ru = game_model.get_rate_type_ru(rate_type)
        rate_type_ru = f"на {rate_type_ru}" if rate_type_ru else ""

        if amount + old_rate_amount > rate_limit:
            return f"{user_name}, максимальный размер ставки {rate_type_ru} -- {format_number(rate_limit)}", False, None

        if game_data.time_left is not None and game_data.time_left < 3:
            return f"{user_name}, до конца раунда осталось менее 3 секунд, ставки не принимаются", False, None

        owner_income = cls._calculate_profit_chat_owner(user_data, chat_data, amount, psql_cursor)
        rate_data = RatesSchema(
            user_id=user_id, chat_id=chat_id, game_id=game_id,
            amount=amount, rate_type=rate_type, game_mode=game_mode,
            owner_income=owner_income
        )
        _rate_data: dict = rate_data.dict()

        psql_connection.autocommit = False

        try:
            if old_rate_amount == 0:
                psql_cursor.execute("""
                    INSERT INTO rates (
                        user_id, chat_id, game_id, amount,
                        rate_type, game_mode, owner_income
                    ) VALUES (
                        %(user_id)s, %(chat_id)s, %(game_id)s, %(amount)s,
                        %(rate_type)s, %(game_mode)s, %(owner_income)s
                    )
                """, _rate_data)
            else:
                psql_cursor.execute("""
                    UPDATE rates
                    SET amount = amount + %(amount)s,
                        owner_income = owner_income + %(owner_income)s
                    WHERE user_id = %(user_id)s AND
                        game_id = %(game_id)s AND
                        rate_type = %(rate_type)s
                """, _rate_data)

            if not from_auto_game:
                total_amount = rate_data.amount * number_games
                
                # Проверяем баланс перед списанием
                if user_coins < total_amount:
                    raise ValueError(f"Insufficient balance: {user_coins} < {total_amount}")

                psql_cursor.execute("""
                    UPDATE users
                    SET coins = coins - %(amount)s,
                        rates_count = rates_count + %(number_games)s
                    WHERE user_id = %(user_id)s AND coins >= %(amount)s
                """, {
                    "amount": total_amount,
                    "number_games": number_games,
                    "user_id": user_id
                })
                
                # Проверяем что обновление прошло успешно
                if psql_cursor.rowcount == 0:
                    raise ValueError(f"Failed to deduct coins: insufficient balance or user not found")

                psql_cursor.execute("""
                    SELECT coins
                    FROM users
                    WHERE user_id = %(user_id)s
                """, {
                    "user_id": user_id
                })

                result = psql_cursor.fetchone()
                if result is None:
                    raise ValueError(f"User {user_id} not found after update")
                
                new_balance = result["coins"]
                if new_balance < 0:
                    raise ValueError(f"Balance became negative after bet: {new_balance}")

                psql_cursor.execute("""
                    UPDATE user_in_chat
                    SET last_rate_amount = %(amount)s
                    WHERE user_id = %(user_id)s AND
                        chat_id = %(chat_id)s
                """, _rate_data)

                if number_games > 1:
                    AutoGameService.insert_auto_game(
                        user_id=user_id, chat_id=chat_id, amount=amount, rate_type=rate_type,
                        game_mode=game_mode, number_games=number_games-1, psql_cursor=psql_cursor
                    )

            psql_connection.commit()

        except:
            psql_connection.rollback()
            return f"{user_name}, вы не можете поставить ставку, так как на вашем балансе нет коинов", False, None

        finally:
            psql_connection.autocommit = True

        format_amount = format_number(amount)
        winning_amount = int(amount * game_model.get_coefficient(
            rate_type, game_result, calculate_winnings=True
        )) if game_model.is_winning(game_result, rate_type) else 0

        if game_data.time_left is not None:
            end_round = f"{game_data.time_left} (Запущено)"
        else:
            end_round = f"{chat_data.game_timer} (Будет запущено)"

        admin_message = None
        if amount >= Config.NOTIFICATION_RATE or winning_amount >= Config.NOTIFICATION_WIN:
            admin_message = f"""
                {f"📍 Авто игры 📍 осталось {format_number(number_auto_games)}" if from_auto_game else ""}
                {user_name} поставил {format_amount} WC {rate_type_ru}
                Выигрыш: {format_number(winning_amount)}
                Исход: {game_model.get_result_message(game_result, short=True)}
                Баланс: {format_number(int(user_coins - amount))}
                До конца раунда: {end_round}
                Номер чата: {int(chat_id - 2E9)} ({game_id})
            """

        return f"{user_name}, успешная ставка {format_amount} WC {rate_type_ru}", True, admin_message


    @classmethod
    def _save_rate_message(
            cls,
            game_id: int,
            chat_id: int,
            user_id: int,
            rate_type: str,
            response_bet: str,
            redis_rates_cursor: Redis
    ) -> None:
        """Сохраняет сообщение в базу данных redis"""

        rates_key = f"{game_id}:{chat_id}:{user_id}:{rate_type}"
        redis_rates_cursor.setex(name=rates_key, value=response_bet, time=600)


    @classmethod
    def _get_rate_response(
            cls,
            chat_id: int,
            game_id: int,
            user_data: UserSchema,
            total_count_bets: int,
            number_accepted_bets: int,
            rates_type: list[str]
    ) -> tuple[str, str]:
        """Возвращает сообщение и клавиатуру о принятых ставках"""

        accept_ru = get_word_case(number_accepted_bets, ("поставлена", "поставлены", "поставлено"))

        total_count_bets = format_number(total_count_bets)
        number_accepted_bets = format_number(number_accepted_bets)

        response = f"{user_data.telegram_name}, успешно {accept_ru} {number_accepted_bets} из {total_count_bets} ставок"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                text="Информация о ставках",
                callback_data=json.dumps({
                    "event": "get_rates_message",
                    "game_id": game_id,
                    "chat_id": chat_id,
                    "user_id": user_data.user_id,
                    "rates_type": " ".join(rates_type)
                })
            )]
        ])

        return response, keyboard


    @classmethod
    def get_rates_message(
            cls,
            payload: dict,
            psql_cursor: DictCursor,
            redis_rates_cursor: Redis
    ) -> str:
        """Возвращает сообщение по нажатию на кнопку (Информация о ставках)"""

        game_id = payload["game_id"]
        chat_id = payload["chat_id"]
        user_id = payload["user_id"]

        rates_message = []

        for rate_type in payload["rates_type"].split(" "):
            rates_key = f"{game_id}:{chat_id}:{user_id}:{rate_type}"
            rates_message.append(redis_rates_cursor.get(rates_key))

        rates_message = [x for x in rates_message if x is not None]

        if len(rates_message) == 0:
            return "⚠ Данные хранятся 10 минут, данные могут изменяться при новой ставке на эти же события в этой игре"

        rates_message = "\n".join(rates_message)
        game_enc_hash = f"Хеш игры: {get_game_data(game_id, psql_cursor).enc_hash}"

        return f"{rates_message}\n\n{game_enc_hash}"


    @classmethod
    def _run_game(
            cls,
            game_id: int,
            game_model: GAME_MODEL,
            psql_cursor: DictCursor,
            redis_cursor: Redis
    ) -> None:
        """Запускает игру если она до этого была не запущена"""

        try:
            game_data = get_game_data(game_id, psql_cursor)
            if game_data is None:
                print(f"[GAME ERROR] Game {game_id} not found in _run_game", flush=True)
                return
            
            time_left = game_data.time_left
            is_in_temp = game_id in Temp.GAMES
            end_datetime = game_data.end_datetime
            
            print(f"[GAME] _run_game: game_id={game_id}, time_left={time_left}, end_datetime={end_datetime}, in_temp={is_in_temp}", flush=True)
            
            # КРИТИЧНО: Проверяем end_datetime, а не только time_left
            # Если end_datetime не установлен, нужно вызвать init_game
            if (time_left is None or end_datetime is None) and not is_in_temp:
                print(f"[GAME] Запуск init_game для игры {game_id} (time_left={time_left}, end_datetime={end_datetime})", flush=True)
                game_model.init_game(game_id, psql_cursor, redis_cursor)
                print(f"[GAME] init_game завершен для игры {game_id}", flush=True)
            else:
                print(f"[GAME] Игра {game_id} уже запущена (time_left={time_left}, end_datetime={end_datetime}, in_temp={is_in_temp})", flush=True)
        except Exception as e:
            print(f"[GAME ERROR] Ошибка в _run_game для игры {game_id}: {e}", flush=True)
            import traceback
            traceback.print_exc()


    @classmethod
    async def accept_bets(
            cls,
            user_id: int,
            chat_id: int,
            game_id: int,
            amount: str | int,
            rates_type: list[str],
            game_model: GAME_MODEL,
            psql_cursor: DictCursor,
            psql_connection: Connection,
            redis_cursor: Redis
    ) -> str:
        """Возвращает сообщение и клавиатуру о принятых ставках"""

        rates_status = []
        response_parts = []
        admin_log_parts = []

        for rate_type in rates_type:
            response_bet, bet_status, admin_log = await cls._accept_bet(
                user_id=user_id, chat_id=chat_id, game_id=game_id,
                amount=amount, rate_type=rate_type, game_model=game_model,
                psql_cursor=psql_cursor, psql_connection=psql_connection
            )
            rates_status.append(bet_status)
            response_parts.append(response_bet)
            admin_log_parts.append(admin_log)

        admin_log = "\n\n".join([x for x in admin_log_parts if x is not None])
        if bool(admin_log):
            await NotificationsService.send_notification(NotifyChats.RATES, admin_log)

        if rates_status.count(True) > 0:
            cls._run_game(game_id, game_model, psql_cursor, redis_cursor)

        return "\n".join(response_parts)


    @classmethod
    async def accept_repeat_game(
            cls,
            user_id: int,
            chat_id: int,
            game_id: int,
            game_model: GAME_MODEL,
            psql_cursor: DictCursor,
            psql_connection: Connection,
            redis_cursor: Redis,
            number_games: int = 1
    ) -> str:
        """Возвращает сообщение и клавиатуру о принятых авто играх"""

        user_data = get_user_data(user_id, psql_cursor)
        user_name = user_data.vk_name

        if not strtobool(redis_cursor.get(RedisKeys.AUTO_GAMES_WORK.value) or "1"):
            return f"{user_name}, сервис временно недоступен"

        if number_games <= 0:
            return f"{user_name}, количество авто игр должно быть больше нуля"

        chat_data = get_chat_data(chat_id, psql_cursor)
        game_mode = chat_data.game_mode
        user_count_auto_game = AutoGameService.get_count_auto_games(user_id, chat_id, game_mode, psql_cursor)

        if user_count_auto_game > 0:
            return f"{user_name}, у вас уже есть активная авто-игра, дождитесь окончания"

        if number_games > 1 and user_count_auto_game + number_games > 1000:
            return f"{user_name}, нельзя ставить больше 1000 авто игр"

        psql_cursor.execute("""
            SELECT MAX(rates.game_id) as found_game_id
            FROM rates
            WHERE rates.user_id = %(user_id)s AND
                  rates.chat_id = %(chat_id)s AND
                  rates.game_mode = %(game_mode)s
        """, {
            "user_id": user_id,
            "chat_id": chat_id,
            "game_mode": game_mode
        })
        found_game_id = psql_cursor.fetchone()["found_game_id"]

        if found_game_id is None:
            return f"{user_name}, вы еще не сыграли ни одной игры в этом режиме"

        psql_cursor.execute("""
            SELECT * FROM rates
            WHERE game_id = %(found_game_id)s AND
                  user_id = %(user_id)s
        """, {
            "found_game_id": found_game_id,
            "user_id": user_id
        })
        found_rates = [RatesSchema(**x) for x in psql_cursor.fetchall()]
        sum_found_rates = sum([x.amount for x in found_rates])
        count_found_rates = len(found_rates)

        if sum_found_rates < 15_000:
            return f"""
                {user_name}, ваши ставки не подходят по условиям.
                Минимальная сумма всех ставок должна быть 15 000
            """

        if user_data.coins < sum_found_rates:
            return f"{user_name}, на вашем балансе недостаточно средств"

        game_data = get_game_data(chat_data.game_id, psql_cursor)
        time_left = game_data.time_left

        if game_data.game_id != game_id:
            return f"{user_name} данные устарели, ставка отклонена"

        if time_left is not None and time_left <= count_found_rates:
            return f"{user_name}, к сожалению мы не успеем поставить ваши ставки за {time_left} сек"

        rates_status = []
        response_parts = []
        admin_log_parts = []

        for rate in found_rates:
            rate_type = rate.rate_type
            response_bet, bet_status, admin_log = await cls._accept_bet(
                user_id=user_id, chat_id=chat_id, game_id=game_id,
                amount=rate.amount, rate_type=rate_type, game_model=game_model,
                psql_cursor=psql_cursor, psql_connection=psql_connection,
                number_games=number_games
            )
            rates_status.append(bet_status)
            response_parts.append(response_bet)
            admin_log_parts.append(admin_log)

        admin_log = "\n\n".join([x for x in admin_log_parts if x is not None])
        if bool(admin_log):
            await NotificationsService.send_notification(NotifyChats.RATES, admin_log)

        if rates_status.count(True) > 0:
            cls._run_game(game_id, game_model, psql_cursor, redis_cursor)

        return "\n".join(response_parts)


    @classmethod
    async def accept_auto_games(
            cls,
            chat_id: int,
            games_models: dict[Games, GAME_MODEL],
            psql_cursor: DictCursor,
            psql_connection: Connection,
            redis_cursor: Redis
    ) -> None:
        """Ставит авто игры"""

        chat_data = get_chat_data(chat_id, psql_cursor)

        if (
            not strtobool(redis_cursor.get(RedisKeys.AUTO_GAMES_WORK.value) or "1") or
            strtobool(redis_cursor.get(RedisKeys.QUIET_MODE.value) or "0") or
            chat_data.is_activated is False
        ):
            return None

        game_id = chat_data.game_id
        game_model = games_models[chat_data.game_mode]

        auto_games = AutoGameService.get_auto_games(chat_id, chat_data.game_mode, psql_cursor)
        rates_status = []
        response_parts = []
        admin_log_parts = []

        for auto_game in auto_games:
            rate_type = auto_game.rate_type
            response_bet, bet_status, admin_log = await cls._accept_bet(
                user_id=auto_game.user_id, chat_id=chat_id, game_id=game_id,
                amount=auto_game.amount, rate_type=rate_type, game_model=game_model,
                psql_cursor=psql_cursor, psql_connection=psql_connection,
                from_auto_game=True, number_auto_games=auto_game.number_games-1
            )
            rates_status.append(bet_status)
            response_parts.append(response_bet)
            admin_log_parts.append(admin_log)

            if bet_status is True:
                AutoGameService.decrement_auto_games(auto_game, psql_cursor)

        admin_log = "\n\n".join([x for x in admin_log_parts if x is not None])
        if bool(admin_log):
            await NotificationsService.send_notification(NotifyChats.RATES, admin_log)

        if rates_status.count(True) > 0:
            cls._run_game(game_id, game_model, psql_cursor, redis_cursor)

        if bool(response_parts):
            await send_message(chat_id, "\n".join(response_parts))
