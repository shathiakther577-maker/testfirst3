from redis.client import Redis
from psycopg2.extras import DictCursor
from psycopg2._psycopg import connection as Connection

from games.base import BaseGameModel
from games.rates import RatesService

from schemas.users import UserSchema, UserStatus
from schemas.chats import ChatSchema, ChatStatsPeriod, ALL_CHAT_STATS_PERIOD
from schemas.games import Games, ALL_GAMES_VALUES
from schemas.redis import RedisKeys
from schemas.user_in_chat import UserChatSchema, UserChatMenu

from tops.day_top import DayTopService
from tops.week_top import WeekTopService
from tops.chats_top import ChatsTopService
from tops.clans_top import ClansTopService
from tops.rubles_top import RublesTopService

from services.chats import ChatsService
from services.user_in_chat import UserChatService
from services.transfer_coins import TransferCoinsService

from modules.additional import convert_number
from modules.databases.chats import get_game_data, get_chat_data
from modules.telegram.bot import send_message

from telegram_bot.modules.active_chat import handler_change_chat_name, handler_change_game_mode, \
    handler_change_game_timer, handler_add_helper, handler_del_helper, get_user_balance_message, \
    handler_change_chat_owner, handler_article_notify
from telegram_bot.keyboards.other import empty_keyboard
from telegram_bot.keyboards.active_chat import get_keyboard_change_game_mode, get_chat_management_keyboard, \
    keyboard_repeat_bet, keyboard_cancel_event_menu


async def handler_active_chat(
    user_id: int,
    user_data: UserSchema,
    chat_id: int,
    chat_data: ChatSchema,
    user_chat_data: UserChatSchema,
    message: str,
    original_message: str,
    fwd_messages: list | None,
    payload: dict | None,
    psql_cursor: DictCursor,
    psql_connection: Connection,
    redis_cursor: Redis,
):
    """Обрабатывает сообщения в активированном чате"""

    is_payload = payload is not None
    split_message = message.split(" ")
    len_split_message = len(split_message)
    split_original_message = original_message.split(" ")

    # Логируем для отладки кнопок
    if original_message in ["🎮 Начать", "🔄 Обновить", "Начать", "Обновить", "начать", "обновить"] or message in ["начать", "обновить"]:
        print(f"[DEBUG] Button pressed: message='{message}', original_message='{original_message}', chat_id={chat_id}", flush=True)

    clear_chat_menu = True
    clear_current_rate = True

    # Проверяем, что игра существует в GAMES_MODEL
    if chat_data.game_mode not in BaseGameModel.GAMES_MODEL:
        # Если игра не найдена, отправляем сообщение об ошибке
        response = f"❌ Игра {chat_data.game_mode.value} не поддерживается. Пожалуйста, выберите другую игру."
        keyboard = None
        await send_message(chat_id, response, keyboard)
        return
    
    game_data = get_game_data(chat_data.game_id, psql_cursor) if chat_data.game_id else None
    
    if game_data is None:
        # Если игра не найдена, создаем новую
        game_model = BaseGameModel.GAMES_MODEL[chat_data.game_mode]
        game_result_dict = game_model.create_game(chat_data.chat_id, psql_cursor)
        # Получаем последний game_id для этого чата
        psql_cursor.execute("""
            SELECT game_id FROM games
            WHERE chat_id = %(chat_id)s
            ORDER BY game_id DESC
            LIMIT 1
        """, {"chat_id": chat_data.chat_id})
        result = psql_cursor.fetchone()
        if result:
            new_game_id = result["game_id"]
            # Обновляем game_id в чате
            psql_cursor.execute("""
                UPDATE chats
                SET game_id = %(game_id)s
                WHERE chat_id = %(chat_id)s
            """, {
                "game_id": new_game_id,
                "chat_id": chat_data.chat_id
            })
            game_data = get_game_data(new_game_id, psql_cursor)
            chat_data.game_id = new_game_id
        else:
            # Если все еще нет game_id, пропускаем обработку
            return
    
    game_model = BaseGameModel.GAMES_MODEL[chat_data.game_mode]
    game_result = game_model.format_game_result(game_data.game_result)

    response = None
    keyboard = None

    # Обработка текстовых команд и callback кнопок
    # Проверяем как текст (для ReplyKeyboard), так и payload (для InlineKeyboard)
    # КРИТИЧНО: Проверяем кнопки "Начать" и "Обновить" ПЕРВЫМИ, чтобы они обрабатывались до других команд
    try:
        # КРИТИЧНО: message уже в нижнем регистре, проверяем original_message для точного совпадения
        if original_message in ["🎮 Начать", "Начать", "начать", "🎮", "начать игру", "Начать игру"] or message in ["начать", "начать игру"]:
            # Начать новую игру (если текущая завершена)
            print(f"[DEBUG] Начать button: message='{message}', original_message='{original_message}'", flush=True)
            try:
                if not game_data.is_active:
                    # Игра завершена, создаем новую
                    game_model = BaseGameModel.GAMES_MODEL[chat_data.game_mode]
                    game_result_dict = game_model.create_game(chat_data.chat_id, psql_cursor)
                    # Коммитим создание игры
                    psql_connection.commit()
                    # Получаем последний game_id для этого чата
                    psql_cursor.execute("""
                        SELECT game_id FROM games
                        WHERE chat_id = %(chat_id)s
                        ORDER BY game_id DESC
                        LIMIT 1
                    """, {"chat_id": chat_data.chat_id})
                    result = psql_cursor.fetchone()
                    if result:
                        new_game_id = result["game_id"]
                        # Обновляем game_id в чате
                        psql_cursor.execute("""
                            UPDATE chats
                            SET game_id = %(game_id)s
                            WHERE chat_id = %(chat_id)s
                        """, {
                            "game_id": new_game_id,
                            "chat_id": chat_data.chat_id
                        })
                        psql_connection.commit()
                        # Получаем новую игру
                        from modules.databases.chats import get_game_data
                        new_game_data = get_game_data(new_game_id, psql_cursor)
                        if new_game_data:
                            game_data = new_game_data
                            chat_data.game_id = new_game_id
                            game_result = game_model.format_game_result(new_game_data.game_result)
                            response = "🎮 Новая игра начата!"
                            keyboard = game_model.get_game_keyboard(game_result)
                        else:
                            response = "❌ Ошибка при создании новой игры"
                    else:
                        response = "❌ Ошибка при создании новой игры"
                else:
                    # Игра еще активна
                    response = "🎮 Игра уже активна!"
                    keyboard = game_model.get_game_keyboard(game_data.game_result)
            except Exception as e:
                print(f"[ERROR] Error starting new game: {e}", flush=True)
                import traceback
                traceback.print_exc()
                response = f"Ошибка при запуске новой игры: {e}"
        
        # КРИТИЧНО: message уже в нижнем регистре, проверяем original_message для точного совпадения
        elif original_message in ["🔄 Обновить", "Обновить", "обновить", "🔄", "обновить клавиатуру", "Обновить клавиатуру"] or message in ["обновить", "обновить клавиатуру"]:
            # Обновление клавиатуры игры
            print(f"[DEBUG] Обновить button: message='{message}', original_message='{original_message}'", flush=True)
            try:
                # Обновляем game_data на актуальную версию
                fresh_game_data = get_game_data(chat_data.game_id, psql_cursor) if chat_data.game_id else None
                if fresh_game_data:
                    game_data = fresh_game_data
                    game_result = game_model.format_game_result(fresh_game_data.game_result)
                    response = "🔄 Клавиатура обновлена"
                    keyboard = game_model.get_game_keyboard(game_result)
                else:
                    response = "❌ Игра не найдена"
            except Exception as e:
                print(f"[ERROR] Error refreshing keyboard: {e}", flush=True)
                import traceback
                traceback.print_exc()
                response = f"Ошибка при обновлении клавиатуры: {e}"
        
        elif (is_payload and payload and payload.get("event") == "get_game_bank") or message in ["банк", "Банк"]:
            response, keyboard = game_model.get_game_bank_message(chat_data, game_data, psql_cursor)

        elif is_payload and payload and payload.get("event") == "get_last_games":
            response = game_model.get_last_game_message(chat_id, psql_cursor)

        elif (is_payload and payload and payload.get("event") == "repeat_bet") or message in ["повторить", "Повторить"]:
            response = "Выберите метод"
            keyboard = keyboard_repeat_bet

        elif (is_payload and payload and payload.get("event") == "get_user_balance") or message in ["баланс", "Баланс"]:
            response = get_user_balance_message(user_data, psql_cursor)

        elif (
            is_payload and payload and
            payload.get("event") == "get_chat_help" or
            message in ["help", "/help"]
        ):
            response = "Команды владельцев частных бесед:"
            keyboard = get_chat_management_keyboard(chat_data)

        elif (
            is_payload and payload and payload.get("event") == "get_chat_stats" and
            payload.get("period") in ALL_CHAT_STATS_PERIOD or
            message in ["stats", "/stats", "статистика"]
        ):
            try:
                if is_payload and payload:
                    period_str = payload.get("period")
                    if period_str in ALL_CHAT_STATS_PERIOD:
                        period = ChatStatsPeriod(period_str)
                    else:
                        period = ChatStatsPeriod.DAY
                else:
                    period = ChatStatsPeriod.DAY

                response = ChatsService.get_stats_message(chat_id, period, psql_cursor)
                keyboard = ChatsService.get_stats_keyboard()
            except Exception as e:
                print(f"[ERROR] Error in get_chat_stats: {e}", flush=True)
                import traceback
                traceback.print_exc()
                response = "Ошибка при получении статистики"

        elif is_payload and payload and payload.get("event") == "cancel_event_menu":
            response = "Действие отменено"
        
        elif is_payload and payload and payload.get("event") == "refresh_keyboard":
            # Обновление клавиатуры
            try:
                response = "🔄 Клавиатура обновлена"
                keyboard = game_model.get_game_keyboard(game_data.game_result)
            except Exception as e:
                print(f"[ERROR] Error refreshing keyboard: {e}", flush=True)
                response = "Ошибка при обновлении клавиатуры"
        

        elif is_payload and payload and payload.get("event") == "change_chat_name":
            try:
                clear_chat_menu = False
                response = "Укажите новое имя чата"
                keyboard = keyboard_cancel_event_menu
                UserChatService.update_menu(user_id, chat_id, UserChatMenu.CHAT_NAME, psql_cursor)
            except Exception as e:
                print(f"[ERROR] Error in change_chat_name: {e}", flush=True)
                response = "Ошибка при изменении имени чата"

        elif (
            message in ["/article_notify", "article_notify"] or
            is_payload and payload and payload.get("event") == "article_notify"
        ):
            response = handler_article_notify(user_data, chat_data, psql_cursor)

        elif (
            split_original_message[0] in ["/name", "name"] and len_split_message >= 2 or
            user_chat_data.menu == UserChatMenu.CHAT_NAME
        ):
            if not user_chat_data.menu == UserChatMenu.CHAT_NAME:
                chat_name = original_message.replace("/", "", 1).replace("name", "", 1).strip()
            else:
                chat_name = original_message
            response = handler_change_chat_name(user_data, chat_data, chat_name, psql_cursor)

        elif (
            is_payload and payload and
            payload.get("event") == "change_game_mode" and
            len(payload) == 1
        ):
            try:
                clear_chat_menu = False
                response = "Выберите новый игровой режим"
                keyboard = get_keyboard_change_game_mode()
                UserChatService.update_menu(user_id, chat_id, UserChatMenu.CHANGE_GAME, psql_cursor)
            except Exception as e:
                print(f"[ERROR] Error in change_game_mode menu: {e}", flush=True)
                response = "Ошибка при смене режима игры"

        elif (
            (
                is_payload and payload and
                payload.get("event") == "change_game_mode" and
                payload.get("game_mode") in ALL_GAMES_VALUES
            ) or (
                split_message[0] in ["/game", "game"] and
                len_split_message == 2 and
                split_message[1] in ALL_GAMES_VALUES
            )
        ):
            try:
                game_mode = Games(payload.get("game_mode") if is_payload and payload else split_message[1])
                response, keyboard = handler_change_game_mode(user_data, chat_data, game_mode, psql_cursor)
                # Отправляем новую клавиатуру сразу
                await send_message(chat_id, response, keyboard)
                return
            except Exception as e:
                print(f"[ERROR] Error changing game mode: {e}", flush=True)
                import traceback
                traceback.print_exc()
                response = "Ошибка при смене режима игры"

        elif message in ["/game", "game"]:
            response = f"""
                Смена игрового режима: /game режим или /help\n
                Доступные режимы: {", ".join(ALL_GAMES_VALUES)}
            """

        elif message in ["timer", "/timer"]:
            response = f"""
                Смена таймера игры: /timer время_в_секундах или /help
                Значение игрового таймера в данный момент: {chat_data.game_timer}
            """

        elif is_payload and payload and payload.get("event") == "change_game_timer":
            clear_chat_menu = False
            response = "Укажите новое время игрового таймера в секундах"
            keyboard = keyboard_cancel_event_menu
            UserChatService.update_menu(user_id, chat_id, UserChatMenu.CHANGE_TIMER, psql_cursor)

        elif (
            split_message[0] in ["/timer", "timer"] and len_split_message == 2 or
            user_chat_data.menu == UserChatMenu.CHANGE_TIMER
        ):
            new_timer = message.replace("/", "", 1).replace("timer", "", 1).strip()
            response = handler_change_game_timer(user_data, chat_data, new_timer, psql_cursor)

        elif is_payload and payload and payload.get("event") == "add_chat_helper":
            clear_chat_menu = False
            response = "Укажите какого пользователя добавить в помощники"
            keyboard = keyboard_cancel_event_menu
            UserChatService.update_menu(user_id, chat_id, UserChatMenu.ADD_HELPER, psql_cursor)

        elif (
            split_message[0] in ["/add_helper", "add_helper"] and len_split_message == 2 or
            user_chat_data.menu == UserChatMenu.ADD_HELPER
        ):
            if not user_chat_data.menu == UserChatMenu.ADD_HELPER:
                helper_link = split_message[1]
            else:
                helper_link = message
            response = await handler_add_helper(user_data, chat_data, helper_link, psql_cursor)

        elif is_payload and payload and payload.get("event") == "del_chat_helper":
            clear_chat_menu = False
            response = "Укажите какого пользователя удалить из помощников"
            keyboard = keyboard_cancel_event_menu
            UserChatService.update_menu(user_id, chat_id, UserChatMenu.DEL_HELPER, psql_cursor)

        elif (
            split_message[0] in ["/del_helper", "del_helper"] and len_split_message == 2 or
            user_chat_data.menu == UserChatMenu.DEL_HELPER
        ):
            if not user_chat_data.menu == UserChatMenu.DEL_HELPER:
                helper_link = split_message[1]
            else:
                helper_link = message
            response = await handler_del_helper(user_data, chat_data, helper_link, psql_cursor)

        elif split_message[0] in ["/owner", "owner"] and len_split_message == 2:
            response = await handler_change_chat_owner(user_data, chat_data, split_message[1], psql_cursor)

        elif (
            is_payload and payload and payload.get("event") == "show_personnel" or
            message in ["helpers", "/helpers"]
        ):
            response = ChatsService.get_helpers_message(chat_data, psql_cursor)

        elif (
            split_message[0] == "перевод" and
            (
                (
                    len_split_message == 3
                ) or (
                    len_split_message == 2 and
                    fwd_messages is not None and
                    len(fwd_messages) == 1
                )
            )
        ):
            response, keyboard = await TransferCoinsService.transfer_coins_in_message(
                sender_data=user_data, split_message=split_message, fwd_messages=fwd_messages,
                psql_cursor=psql_cursor, redis_cursor=redis_cursor
            )

        elif (
            is_payload and payload and
            payload.get("event") == RedisKeys.TRANSFERS_IN_CHAT.value and
            payload.get("sender_id") == user_id
        ):
            response = TransferCoinsService.handler_transfer_coins_in_message(
                sender_id=user_id, payload=payload,
                psql_cursor=psql_cursor, redis_cursor=redis_cursor
            )

        elif message == "топ дня" or message == "топ дня":
            response, _ = DayTopService.get_message(user_data, psql_cursor)

        elif message == "топ недели" or message == "топ недели":
            response, _ = WeekTopService.get_message(user_data, psql_cursor)

        elif message in ["топ чатов", "топ бесед", "топ чатов", "топ бесед"]:
            response, _ = ChatsTopService.get_message(chat_data, psql_cursor)

        elif message == "топ кланов" or message == "топ кланов":
            response, _ = ClansTopService.get_message(user_data, psql_cursor)

        elif message == "топ монеток" or message == "топ монеток":
            response, _ = RublesTopService.get_message(user_data, psql_cursor)

        elif message == "!чат":
            response = f"Текущий чат: {chat_id}"

        elif (
            message in ["убрать клаву", "убрать клавиатуру"] and
            user_data.status == UserStatus.ADMIN
        ):
            response = "✅"
            keyboard = empty_keyboard

        elif (
            message in [
                "выдать клаву", "выдать клавиатуру",
                "вернуть клаву", "вернуть клавиатуру"
            ] and user_data.status == UserStatus.ADMIN
        ):
            response = "✅"
            keyboard = game_model.get_game_keyboard(game_data.game_result)

        # Если есть payload с rate - это нажатие на кнопку ставки (inline)
        elif is_payload and payload and payload.get("rate") is not None:
            try:
                rate_type = payload.get("rate")
                if not isinstance(rate_type, str):
                    print(f"[ERROR] Invalid rate_type in payload: {rate_type}", flush=True)
                    response = "Ошибка: неверный тип ставки"
                else:
                    # Устанавливаем тип ставки для пользователя
                    game_model.update_current_rate(chat_data.chat_id, user_data.user_id, rate_type, psql_cursor)
                    # Получаем клавиатуру для ввода суммы ставки
                    response, keyboard = game_model.get_keyboard_pay_rates(chat_data, user_chat_data, rate_type, game_result, psql_cursor)
                    clear_current_rate = False
            except Exception as e:
                print(f"[ERROR] Error processing rate button: {e}", flush=True)
                import traceback
                traceback.print_exc()
                response = "Ошибка при обработке ставки"
    
        # Обработка текстовых ставок (x2, x3, x5, x50) - для ReplyKeyboard
        elif message in ["x2", "x3", "x5", "x50", "X2", "X3", "X5", "X50"]:
            rate_type = message.lower().replace("x", "")
            # Устанавливаем тип ставки для пользователя
            game_model.update_current_rate(chat_data.chat_id, user_data.user_id, rate_type, psql_cursor)
            # Получаем клавиатуру для ввода суммы ставки
            response, keyboard = game_model.get_keyboard_pay_rates(chat_data, user_chat_data, rate_type, game_result, psql_cursor)
            clear_current_rate = False
        
        # Обработка кнопок с суммами ставок (payload содержит "amount")
        elif is_payload and payload and payload.get("amount") is not None and payload.get("event") is None:
            try:
                amount = payload.get("amount")
                rate_type = user_chat_data.current_rate
                
                if rate_type is None:
                    response = "❌ Сначала выберите тип ставки"
                else:
                    # Принимаем ставку с указанной суммой
                    response = await RatesService.accept_bets(
                        user_id=user_id, chat_id=chat_id, game_id=chat_data.game_id,
                        amount=str(amount), rates_type=[rate_type], game_model=game_model,
                        psql_cursor=psql_cursor, psql_connection=psql_connection,
                        redis_cursor=redis_cursor
                    )
                    clear_current_rate = False
            except Exception as e:
                print(f"[ERROR] Error accepting bet with amount button: {e}", flush=True)
                import traceback
                traceback.print_exc()
                response = f"❌ Ошибка при принятии ставки: {e}"
        
        # Обработка ставок через текстовые сообщения (для VK совместимости)
        elif response_current_rate := game_model.handler_current_rate(
            user_data, chat_data, game_result, user_chat_data,
            message, payload, psql_cursor
        ):
            clear_current_rate = False
            response, keyboard = response_current_rate

        elif is_payload and payload and payload.get("event") == "accept_repeat_game":
            try:
                response = await RatesService.accept_repeat_game(
                    user_id=user_id, chat_id=chat_id, game_id=chat_data.game_id,
                    game_model=game_model, psql_cursor=psql_cursor,  psql_connection=psql_connection,
                    redis_cursor=redis_cursor
                )
            except Exception as e:
                print(f"[ERROR] Error in accept_repeat_game: {e}", flush=True)
                import traceback
                traceback.print_exc()
                response = "Ошибка при повторении игры"

        elif is_payload and payload and payload.get("event") == "auto_game":
            try:
                clear_chat_menu = False
                UserChatService.update_menu(user_id, chat_id, UserChatMenu.AUTO_GAME, psql_cursor)
                response = "Введите количество игр, которые хотите повторить"
            except Exception as e:
                print(f"[ERROR] Error in auto_game menu: {e}", flush=True)
                response = "Ошибка при настройке авто-игры"
        
    except Exception as e:
        print(f"[ERROR] Error in handler_active_chat button processing: {e}", flush=True)
        import traceback
        traceback.print_exc()
        if response is None:
            response = "Произошла ошибка при обработке команды"

    # Обработка вне try-except блока (для совместимости с существующим кодом)
    if user_chat_data.current_rate is not None and response is None:

        rates = user_chat_data.current_rate.split(" ")
        game_model.update_current_rate(chat_id, user_id, None, psql_cursor)
        clear_current_rate = False

        response = await RatesService.accept_bets(
            user_id=user_id, chat_id=chat_id, game_id=chat_data.game_id,
            amount=message, rates_type=rates, game_model=game_model,
            psql_cursor=psql_cursor, psql_connection=psql_connection,
            redis_cursor=redis_cursor
        )

    elif (
        user_chat_data.menu == UserChatMenu.AUTO_GAME and
        convert_number(message) is not None
    ):
        response = await RatesService.accept_repeat_game(
            user_id=user_id, chat_id=chat_id, game_id=chat_data.game_id,
            game_model=game_model, psql_cursor=psql_cursor, psql_connection=psql_connection,
            redis_cursor=redis_cursor, number_games=convert_number(message)
        )

    if clear_chat_menu is True and user_chat_data.menu is not None:
        UserChatService.update_menu(user_id, chat_id, None, psql_cursor)

    if clear_current_rate is True and user_chat_data.current_rate is not None:
        game_model.update_current_rate(chat_id, user_id, None, psql_cursor)

    # В оригинале VK всегда отправляется сообщение, даже если response is None
    # (тогда отправляется пустое сообщение с клавиатурой)
    # В Telegram отправляем если есть response или keyboard
    try:
        if response is not None or keyboard is not None:
            # Если keyboard не установлена, используем игровую inline-клавиатуру
            if keyboard is None:
                keyboard = game_model.get_game_keyboard(game_data.game_result)
            await send_message(chat_id, response, keyboard)
        else:
            # Если нет response и keyboard, отправляем только клавиатуру
            keyboard = game_model.get_game_keyboard(game_data.game_result)
            await send_message(chat_id, None, keyboard)
    except Exception as e:
        print(f"ERROR in handler_active_chat: {e}", flush=True)
        import traceback
        traceback.print_exc()

