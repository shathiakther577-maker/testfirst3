import asyncio
import threading
from redis.client import Redis
from psycopg2.extras import DictCursor

from settings import Config
from games.base import BaseGameModel

from schemas.users import UserSchema, UserStatus, UserMenu
from schemas.chats import INCOME_CHAT_TYPE
from schemas.games import Games
from schemas.redis import RedisKeys

from services.incomes import IncomesService
from services.promocode import PromoCodeService
from services.bonus_repost import BonusRepostService
from services.bonus_subscription import BonusSubscriptionService
from services.notification import NotificationsService, NotifyChats
from services.transfer_coins import TransferCoinsService, TransferWhiteListService
from services.reset_user_data import ResetUserServices

from modules.additional import strtobool, format_number
from modules.databases.users import update_user_menu, update_user_extra_data, \
    get_user_data, set_coins, give_coins, take_coins, update_user_name, update_free_nick_change
from modules.databases.chats import get_game_data
from modules.vkontakte.bot import send_message
from modules.vkontakte.users import get_registration_date, get_user_friends, kick_user_from_chat


from vk_bot.template_messages import BACK_MAIN_MENU, COMMAND_NOT_FOUND
from vk_bot.modules.admin_menu import AdminPanel, UserIdNotFound, UserDataNotFound, \
    UsersDataNotFound, ChatIdNotFound, ChatTypeNotFound, ChatDataNotFound, GameModeNotFound, \
    ChatLifeDatetimeError, NumberNotFound, MaxTextLen, TimeStamp, ClansTop, restart_bot, \
    get_time_stamp_keyboard, add_up_profit, get_develore_income, clear_developer_income, \
    change_works_status, TIME_STAMPS, TOPS, TOPS_NAME
from vk_bot.modules.active_chat import handler_change_game_mode
from vk_bot.modules.mailing_menu import ExtraMailing, get_mailing_menu_keyboard
from vk_bot.keyboards.main_menu import get_main_menu_keyboard
from vk_bot.keyboards.admin_menu import get_admin_menu_keyboard


ADMIN_HELP_MESSAGE = """
    help - Показать список всех команд
    mailing - Перекидывает в меню рассылки

    СТАТИСТИКА
    • incames - Показывает доход проекта
    • stats|statistics - Показывает статистику проекта
    • active - Показывает статистику активности
    • luckys mode[day/week/all_time] - Показывает самых везучих игроков
    • losers mode[day/week/all_time] - Показывает самых невезучих игроков

    ВЫДАЧА COIN'S
    • set user_id amount - Устанавливает пользователю WC
    • give user_id amount - Выдает пользователю WC
    • take user_id amount - Забирает у пользователя WC

    СТАТУСЫ ПОЛЬЗОВАТЕЛЕЙ
    • zero user_id - Удалить пользователя
    • user user_id - Установить пользователю статус "user"
    • admin user_id - Установить пользователю статус "admin"
    • honest user_id - Установить пользователю статус "honest"
    • scammer user_id - Установить пользователю статус "scammer"

    ИНФО ПОЛЬЗОВАТЕЛИ/ЧАТЫ/ПРОМОКОДЫ
    • uinfo|user_info user_id - Информация о пользователе
    • cinfo|chat_info chat_id - Информация о чате
    • pinfo|promo_info promo_id - Информация о промокодах пользователя

    БЛОКИРОВКИ
    • uban|user_ban user_id - Забанить игрока
    • unban|user_unban user_id - Разбанить игрока
    • fban|friend_ban user_id - Заблокировать пользователя вместе с друзьями
    • fnban|friend_unban user_id - Разблокировать ользователя вместе с друзьями
    • pban|promo_ban user_id - Заблокировать использование промокодов
    • pnban|promo_unban user_id - Разблокировать использование промокодов
    • tban|transfer_ban user_id - Заблокировать переводы пользователю
    • tnban|transfer_unban user_id - Разблокировать переводы пользователю
    • nkban|nickname_ban user_id - Заблокировать смену никнейма пользователю
    • nknban|nickname_unban user_id - Разблокировать смену никнейма пользователю
    • twl|transfer_white_list mode[add/del] user_id - Добавляет или удаляет пользователя в белом списке переводов

    СМЕНА НИКОВ
    • uname|user_name user_id text[50] - Сменить имя пользователя
    • udesc|user_description user_id text[250]|"clear" - Сменить описание пользователя
    • ufnick|user_free_nick user_id value[True/False] - Выдает или забирает бесплатную смену ника

    НАСТРОЙКИ ЧАТОВ
    • chat type chat_id types[Premium/Premium+] - Изменяет тип чата
    • chat owner chat_id user_id - Изменяет владельца чата
    • chat timer chat_id seconds - Изменяет таймер чата
    • chat game_mode chat_id game_mode[dice/wheel/...] - Изменяет игровой режим в чате
    • chat life chat_id datetime[%Y-%m-%d %H:%M:%S] - Изменяет время жизни чата

    УПРАВЛЕНИЕ ТОПАМИ
    • resettop mode[all_time/day/week/clan/coins/rubles/week_rubles]- Сбрасывает статистику топов
    • itop|incrtop mode[all_time/day/week/clan/coins/rubles/week_rubles] user_id amount - Увеличить значение топа у пользователя
    • dtop|decrtop mode[all_time/day/week/clan/coins/rubles/week_rubles] user_id amount - Уменьшить значение топа у пользователя

    БОНУС ЗА РЕПОСТ
    • post - Показывает активные бонусы за репост
    • npost post_id reward[WC] sub_reward[WC] activations seconds - Создать бонус за репост
    • dpost post_id - Удаляет бонус за репост

    БОНУС ЗА ПОДПИСКУ
    • subbonus - Показывает активные бонусы за подписку
    • nsubbonus reward[WC] - Создать разовый бонус за подписку
    • dsubbonus bonus_id - Удаляет бонус за подписку

    ПРОГРАММИСТ
    • dev - Выводит сколько вышло
    • dev_clear - Отчищает сколько вышло

    ДРУГОЕ
    • restart_bot - Перезапускает бота
    • api mode[on/off] - Включает или отключает работу api
    • auto_games mode[on/off] - Включает или отключает работу авто игр
    • quiet_mode mode[on/off] - Включает или отключает тихий режим
    • start_game game_id - Принудительно запускает игру в чате
"""


async def handler_admin_menu(
    *,
    admin_id: int,
    admin_data: UserSchema,
    message: str,
    original_message: str,
    fwd_messages: list | None,
    payload: dict | None,
    psql_cursor: DictCursor,
    redis_cursor: Redis
) -> None:
    """Обрабатывает сообщения в меню администраторов"""

    keyboard = get_admin_menu_keyboard()
    is_payload = payload is not None

    split_message = message.split(" ")
    split_original_message = original_message.split(" ")

    if fwd_messages and len(fwd_messages) > 0 and fwd_messages[0]["from_id"] > 0:
        split_message.insert(1, fwd_messages[0]["from_id"])
        split_original_message.insert(1, fwd_messages[0]["from_id"])

    len_split_message = len(split_message)

    try:

        if message == "меню" or is_payload and payload.get("event") == "go_main_menu":
            response = BACK_MAIN_MENU
            keyboard = get_main_menu_keyboard(admin_data)
            update_user_menu(admin_id, UserMenu.MAIN, psql_cursor)

        elif message == "help" or is_payload and payload.get("event") == "help":
            response = ADMIN_HELP_MESSAGE

        elif message == "incomes" or is_payload and payload.get("event") == "incomes":

            day_statistics = IncomesService.get_day_statistics(redis_cursor, psql_cursor)
            day_profit = {
                "coins": day_statistics.coins_income,
                "rubles": day_statistics.rubles_income
            }

            psql_cursor.execute("""
                SELECT COALESCE(SUM(coins_income), 0) as coins,
                    COALESCE(SUM(rubles_income), 0) as rubles
                FROM bot_statistics
                WHERE DATE_TRUNC('week', datetime) = DATE_TRUNC('week', CURRENT_DATE)
            """)
            week_profit = add_up_profit(psql_cursor.fetchone(), day_profit)

            psql_cursor.execute("""
                SELECT COALESCE(SUM(coins_income), 0) as coins,
                    COALESCE(SUM(rubles_income), 0) as rubles
                FROM bot_statistics
                WHERE EXTRACT(MONTH FROM datetime) = EXTRACT(MONTH FROM CURRENT_DATE) AND
                    EXTRACT(YEAR FROM datetime) = EXTRACT(YEAR FROM CURRENT_DATE)
            """)
            month_profit = add_up_profit(psql_cursor.fetchone(), day_profit)

            psql_cursor.execute("""
                SELECT COALESCE(SUM(coins_income), 0) as coins,
                    COALESCE(SUM(rubles_income), 0) as rubles
                FROM bot_statistics
            """)
            all_profit = add_up_profit(psql_cursor.fetchone(), day_profit)

            psql_cursor.execute("""
                SELECT COALESCE(SUM(coins), 0) as user_coins,
                    COALESCE(SUM(all_win), 0) as all_win,
                    COALESCE(SUM(all_lost), 0) as all_lost,
                    COALESCE(SUM(day_win), 0) as day_win,
                    COALESCE(SUM(day_lost), 0) as day_lost
                FROM users
                WHERE status NOT IN %(ignore_user_status)s
            """, {
                "ignore_user_status": (UserStatus.ADMIN, UserStatus.MARKET)
            })
            users_stats = psql_cursor.fetchone()

            psql_cursor.execute("""
                SELECT COALESCE(
                    SUM(promocodes.reward * promocodes.quantity), 0
                ) as promocodes_amount
                FROM promocodes JOIN users ON users.user_id = promocodes.owner_id
                WHERE status NOT IN %(ignore_user_status)s
            """, {
                "ignore_user_status": (UserStatus.ADMIN, UserStatus.MARKET)
            })
            promocodes_amount = psql_cursor.fetchone()["promocodes_amount"]

            psql_cursor.execute("""
                SELECT COALESCE(
                    SUM(auto_games.amount * auto_games.number_games), 0
                ) as auto_games_amount
                FROM auto_games JOIN users ON users.user_id = auto_games.user_id
                WHERE status NOT IN %(ignore_user_status)s
            """, {
                "ignore_user_status": (UserStatus.ADMIN, UserStatus.MARKET)
            })
            auto_games_amount = psql_cursor.fetchone()["auto_games_amount"]

            total_amount = (
                int(users_stats["user_coins"]) +
                int(promocodes_amount) +
                int(auto_games_amount)
            )

            response = f"""
                📊 Статистика прибыли

                💰 У игроков на руках: {format_number(total_amount)}

                💸 Всего выиграли коинов: {format_number(int(users_stats["all_win"]))}
                💳 Всего проиграли коинов: {format_number(int(users_stats["all_lost"]))}
                💰 Stinks за все время: {format_number(all_profit["coins"])} ({format_number(all_profit["rubles"] // 1_000)})
                💰 Stinks за неделю: {format_number(week_profit["coins"])} ({format_number(week_profit["rubles"] // 1_000)})
                💰 Stinks за месяц: {format_number(month_profit["coins"])} ({format_number(month_profit["rubles"] // 1_000)})

                💸 Сегодня выиграли коинов: {format_number(int(users_stats["day_win"]))}
                💳 Сегодня проиграли коинов: {format_number(int(users_stats["day_lost"]))}
                💰 Stinks: {format_number(day_profit["coins"])} ({format_number(day_profit["rubles"] // 1_000)})
            """

        elif message in ["stats", "statistics"] or is_payload and payload.get("event") == "statistics":

            psql_cursor.execute("""
                SELECT game_mode, SUM(income) as income
                FROM games
                WHERE DATE(end_datetime) = CURRENT_DATE
                GROUP BY game_mode
                ORDER BY income DESC
            """)
            day_games_profit = psql_cursor.fetchall()

            response_day_games = "".join([
                f"\n💰 {Games(x['game_mode']).name}: {format_number(int(x['income']))}"
                for x in day_games_profit
            ])

            psql_cursor.execute("""
                SELECT game_mode, SUM(income) as income
                FROM games
                GROUP BY game_mode
                ORDER BY income DESC
            """)
            all_games_profit = psql_cursor.fetchall()

            response_all_games = "".join([
                f"\n💰 {Games(x['game_mode']).name}: {format_number(int(x['income']))}"
                for x in all_games_profit
            ])

            psql_cursor.execute("""
                SELECT COALESCE(SUM(day_rates), 0) as day,
                       COALESCE(SUM(all_rates), 0) as all
                FROM users
                WHERE status NOT IN %(ignore_user_status)s
            """, {
                "ignore_user_status": (UserStatus.ADMIN, UserStatus.MARKET)
            })
            rates = psql_cursor.fetchone()

            psql_cursor.execute("""
                SELECT COALESCE(SUM(payments.coins), 0) as coins,
                       COALESCE(SUM(payments.rubles), 0) as rubles
                FROM payments JOIN users ON payments.user_id = users.user_id
                WHERE DATE(payments.accepted_at) = CURRENT_DATE AND
                    users.status NOT IN %(ignore_user_status)s
            """, {
                "ignore_user_status": (UserStatus.ADMIN, UserStatus.MARKET)
            })
            day_payments = psql_cursor.fetchone()

            psql_cursor.execute("""
                SELECT COALESCE(SUM(payments.coins), 0) as coins,
                       COALESCE(SUM(payments.rubles), 0) as rubles
                FROM payments JOIN users ON payments.user_id = users.user_id
                WHERE users.status NOT IN %(ignore_user_status)s
            """, {
                "ignore_user_status": (UserStatus.ADMIN, UserStatus.MARKET)
            })
            all_payments = psql_cursor.fetchone()

            day_other_profit = IncomesService.get_additional_income(redis_cursor)
            day_other_expenses = IncomesService.get_additional_expenses(redis_cursor)

            psql_cursor.execute("""
                SELECT COALESCE(SUM(additional_income), 0) as other_profit,
                       COALESCE(SUM(additional_income), 0) as other_expenses
                FROM bot_statistics
            """)
            bot_statistics = psql_cursor.fetchone()

            response = f"""
                📊 Прочее

                📅 Сегодня: {response_day_games}
                🕹️ Поставлено: {format_number(rates["day"])}
                🔄 Куплено WC: {format_number(int(day_payments["coins"]))} ({format_number(int(day_payments["coins"] // 1_000))})
                🧾 Получено: {format_number(day_other_profit)}
                🧾 Роздано: {format_number(day_other_expenses)}

                📅 За все время: {response_all_games}
                🕹️ Поставлено: {format_number(rates["all"])}
                🔄 Куплено WC: {format_number(int(all_payments["coins"]))} ({format_number(int(all_payments["coins"] // 1_000))})
                🧾 Получено: {format_number(int(bot_statistics["other_profit"] + day_other_profit))}
                🧾 Роздано: {format_number(int(bot_statistics["other_expenses"] + day_other_expenses))}
            """

        elif message == "active" or is_payload and payload.get("event") == "active":

            psql_cursor.execute("""
                SELECT COALESCE(COUNT(user_id), 0) as count
                FROM users
                WHERE DATE(created_at) = CURRENT_DATE
            """)
            new_user_day = int(psql_cursor.fetchone()["count"])

            psql_cursor.execute("""
                SELECT COALESCE(COUNT(user_id), 0) as count
                FROM users
            """)
            count_users = int(psql_cursor.fetchone()["count"])

            psql_cursor.execute("""
                SELECT COALESCE(COUNT(user_id), 0) as count
                FROM users
                WHERE day_rates > 0
            """)
            day_activ_users = int(psql_cursor.fetchone()["count"])

            psql_cursor.execute("""
                SELECT COALESCE(COUNT(user_id), 0) as count
                FROM users
                WHERE all_rates > 0
            """)
            all_activ_users = int(psql_cursor.fetchone()["count"])

            psql_cursor.execute("""
                SELECT COALESCE(COUNT(chats.chat_id), 0) as count
                FROM chats JOIN users ON chats.owner_id = users.user_id
                WHERE chats.is_activated = TRUE AND
                    users.status NOT IN %(ignore_user_status)s
            """, {
                "ignore_user_status": (UserStatus.ADMIN, UserStatus.MARKET)
            })
            count_chats = int(psql_cursor.fetchone()["count"])

            response = f"""
                📊 Статистика активности:

                👤 Всего игроков: {format_number(count_users)}
                👤 Новых за сегодня: {format_number(new_user_day)}

                🗣 Активных игроков: {format_number(all_activ_users)}
                🗣 Сегодня: {format_number(day_activ_users)}

                🌐 Всего приватных чатов: {format_number(count_chats)}
            """

        elif message == "топ" or is_payload and payload.get("event") == "top_users":
            psql_cursor.execute("""
                SELECT user_id, full_name, status, coins
                FROM users
                WHERE status NOT IN %(ignore_user_status)s
                ORDER BY coins DESC
                LIMIT 20
            """, {
                "ignore_user_status": (UserStatus.ADMIN, UserStatus.MARKET)
            })
            top_users = psql_cursor.fetchall()

            response = "Топ игроков по балансу\n"
            for position, user in enumerate(top_users, 1):
                prefix = UserSchema.get_user_prefix(user["status"])
                user["full_name"] = f"{prefix}{user['full_name']}{prefix}"
                user_name = UserSchema.format_vk_name(user["user_id"], user["full_name"])
                response += f"\n{position}) {user_name} - {format_number(user['coins'])}"

        elif message in ["mailing", "рассылка"] or is_payload and payload.get("event") == "mailing":
            response = "Введи ссылку на вложение по типу photo-192514282_457381934 или нажми пропустить"
            keyboard = get_mailing_menu_keyboard()

            update_user_menu(admin_id, UserMenu.MAILING, psql_cursor)
            update_user_extra_data(admin_id, ExtraMailing(), psql_cursor)

        elif (
            (
                not is_payload and
                split_message[0] == "luckys" and
                len_split_message == 2 and
                split_message[1] in TIME_STAMPS
            ) or (
                is_payload and
                payload.get("event") == "luckys" and
                len(payload) == 1
            ) or (
                is_payload and
                payload.get("event") == "luckys" and
                payload.get("time_stamp") in TIME_STAMPS
            )
        ):

            if is_payload:
                time_stamp = payload.get("time_stamp", TimeStamp.DAY.value)
            else:
                time_stamp = split_message[1]

            sql_field = f"{time_stamp}_win - {time_stamp}_lost {'+ top_profit' if time_stamp == 'all' else ''}"
            psql_cursor.execute(f"""
                SELECT user_id, full_name, status, {sql_field} as points
                FROM users
                WHERE status NOT IN %(ignore_user_status)s
                GROUP BY user_id, full_name
                HAVING {sql_field} > 0
                ORDER BY points DESC
                LIMIT 10
            """, {
                "ignore_user_status": (UserStatus.ADMIN.value, UserStatus.MARKET.value)
            })
            psql_response = psql_cursor.fetchall()

            response = "🎲 Самые везучие игроки"
            keyboard = get_time_stamp_keyboard(event="luckys")

            for data in psql_response:
                prefix = UserSchema.get_user_prefix(data["status"])
                data["full_name"] = f"{prefix}{data['full_name']}{prefix}"
                response += f"""

                    {UserSchema.format_vk_name(data["user_id"], data["full_name"])}
                    💰 Выиграл {format_number(data["points"])} коинов
                """

        elif (
            (
                not is_payload and
                split_message[0] == "lusers" and
                len_split_message == 2 and
                split_message[1] in TIME_STAMPS
            ) or (
                is_payload and
                payload.get("event") == "lusers" and
                len(payload) == 1
            ) or (
                is_payload and
                payload.get("event") == "lusers" and
                payload.get("time_stamp") in TIME_STAMPS
            )
        ):

            if is_payload:
                time_stamp = payload.get("time_stamp", TimeStamp.DAY.value)
            else:
                time_stamp = split_message[1]

            sql_field = f"-1 * ({time_stamp}_win - {time_stamp}_lost {'+ top_profit' if time_stamp == 'all' else ''})"
            psql_cursor.execute(f"""
                SELECT user_id, full_name, status, {sql_field} as points
                FROM users
                WHERE status NOT IN %(ignore_user_status)s
                GROUP BY user_id, full_name
                HAVING {sql_field} > 0
                ORDER BY points DESC
                LIMIT 10
            """, {
                "ignore_user_status": (UserStatus.ADMIN.value, UserStatus.MARKET.value)
            })
            psql_response = psql_cursor.fetchall()

            response = "🎲 Самые невезучие игроки"
            keyboard = get_time_stamp_keyboard(event="lusers")

            for data in psql_response:
                prefix = UserSchema.get_user_prefix(data["status"])
                data["full_name"] = f"{prefix}{data['full_name']}{prefix}"
                response += f"""

                    {UserSchema.format_vk_name(data["user_id"], data["full_name"])}
                    💰 Проиграл {format_number(data["points"])} коинов
                """

        elif split_message[0] == "set" and len_split_message == 3:

            user_data = await AdminPanel.get_user_data(split_message[1], psql_cursor)
            number = AdminPanel.get_number(split_message[2])
            set_coins(user_data.user_id, number, psql_cursor)

            response = f"Баланс {user_data.vk_name} изменен на {format_number(number)} WC"
            await NotificationsService.send_notification(
                chat=NotifyChats.MAIN,
                message=f"{admin_data.vk_name} изменил баланс {user_data.vk_name} на {format_number(number)} WC"
            )
            await send_message(
                peer_id=user_data.user_id,
                message=f"🅰 Администратор изменил Ваш баланс на {format_number(number)} WC"
            )

        elif split_message[0] == "give" and len_split_message == 3:

            user_data = await AdminPanel.get_user_data(split_message[1], psql_cursor)
            number = AdminPanel.get_number(split_message[2])
            give_coins(user_data.user_id, number, psql_cursor)

            response = f"{user_data.vk_name} получил {format_number(number)} WC"
            await NotificationsService.send_notification(
                chat=NotifyChats.MAIN,
                message=f"{admin_data.vk_name} выдал {user_data.vk_name} {format_number(number)} WC"
            )
            await send_message(
                peer_id=user_data.user_id,
                message=f"🅰 Администратор выдал Вам {format_number(number)} WC"
            )

        elif split_message[0] == "take" and len_split_message == 3:

            user_data = await AdminPanel.get_user_data(split_message[1], psql_cursor)
            number = AdminPanel.get_number(split_message[2])
            take_coins(user_data.user_id, number, psql_cursor)

            response = f"У {user_data.vk_name} изъято {format_number(number)} WC"
            await NotificationsService.send_notification(
                chat=NotifyChats.MAIN,
                message=f"{admin_data.vk_name} изъял у {user_data.vk_name} {format_number(number)} WC"
            )
            await send_message(
                peer_id=user_data.user_id,
                message=f"🅰 Администратор забрал у вас {format_number(number)} WC"
            )

        elif split_message[0] == "zero" and len_split_message == 2:
            user_data = await AdminPanel.get_user_data(split_message[1], psql_cursor)

            psql_cursor.execute("""
                DELETE FROM users
                WHERE user_id = %(user_id)s
            """, {
                "user_id": user_data.user_id
            })

            response = f"Все данные о {user_data.vk_name} удалены"

        elif split_message[0] == "user" and len_split_message == 2:
            user_data = await AdminPanel.get_user_data(split_message[1], psql_cursor)
            AdminPanel.update_user_status(user_data.user_id, UserStatus.USER, psql_cursor)

            response = f"{user_data.vk_name} теперь пользователь"
            await NotificationsService.send_notification(
                chat=NotifyChats.MAIN,
                message=f"{admin_data.vk_name} снял с {user_data.vk_name} админку"
            )

        elif split_message[0] == "admin" and len_split_message == 2:
            user_data = await AdminPanel.get_user_data(split_message[1], psql_cursor)
            AdminPanel.update_user_status(user_data.user_id, UserStatus.ADMIN, psql_cursor)

            response = f"{user_data.vk_name} теперь админ"
            await NotificationsService.send_notification(
                chat=NotifyChats.MAIN,
                message=f"{admin_data.vk_name} выдал {user_data.vk_name} админку"
            )

        elif split_message[0] == "honest" and len_split_message == 2:
            user_data = await AdminPanel.get_user_data(split_message[1], psql_cursor)
            AdminPanel.update_user_status(user_data.user_id, UserStatus.HONEST, psql_cursor)
            user_data = get_user_data(user_data.user_id, psql_cursor)
            response = f"{user_data.vk_name} выдан статус честного игрока"

        elif split_message[0] == "scammer" and len_split_message == 2:
            user_data = await AdminPanel.get_user_data(split_message[1], psql_cursor)
            AdminPanel.update_user_status(user_data.user_id, UserStatus.SCAMMER, psql_cursor)
            user_data = get_user_data(user_data.user_id, psql_cursor)
            response = f"{user_data.vk_name} выдан статус мошенника"

        elif split_message[0] in ["uinfo", "user_info"] and len_split_message == 2:
            user_data = await AdminPanel.get_user_data(split_message[1], psql_cursor)

            response = f"""
                👤 Имя: {user_data.vk_name}
                📅 Дата регистрации: {await get_registration_date(user_data.user_id)}
                💰 Баланс: {format_number(user_data.coins)}
                💰 Куплено WC: {format_number(user_data.coins_purchased)}

                🌐 Ставок: {format_number(user_data.rates_count)}
                ✅ Выиграно: {format_number(user_data.all_win)}
                ❌ Проиграно {format_number(user_data.all_lost)}
                💳 Прибыль за сегодня: {format_number(user_data.day_win - user_data.day_lost)}
                💳 Прибыль за неделю: {format_number(user_data.week_win - user_data.week_lost)}
                💳 Прибыль за все время: {format_number(user_data.all_win - user_data.all_lost + user_data.top_profit)}
            """

            psql_cursor.execute("""
                SELECT chat_id
                FROM chats
                WHERE owner_id = %(owner_id)s
                ORDER BY chat_id ASC
            """, {
                "owner_id": user_data.user_id
            })
            chat_ids = [str(int(x["chat_id"] - 2E9)) for x in psql_cursor.fetchall()]
            if len(chat_ids) > 0:
                response += f"\n\n 🔐 Приватные чаты: {', '.join(chat_ids)}"

            promocodes = PromoCodeService.get_user_pormocodes(user_data.user_id, psql_cursor)
            if len(promocodes) > 0:
                response += f"\n\n💬 Активные промокоды: {', '.join([x.name for x in promocodes])}"

            banned_parts = [
                "🚫 Пользователь находится в бане" if user_data.banned else "",
                "🚫 Пользователь не может переводить" if user_data.banned_transfer else "",
                "🚫 Пользователь не может менять никнейм" if user_data.banned_nickname else "",
                "🚫 Пользователь не может пользоваться промокодами" if user_data.banned_promo else ""
            ]
            banned_response = "\n".join([x for x in banned_parts if bool(x)])

            if bool(banned_response):
                response += f"\n\n{banned_response}"

        elif split_message[0] in ["cinfo", "chat_info"] and len_split_message == 2:
            chat_data = AdminPanel.get_chat_data(split_message[1], psql_cursor)
            owner_data = get_user_data(chat_data.owner_id, psql_cursor)
            owner_name = UserSchema.format_vk_name(chat_data.owner_id, owner_data.full_name) if owner_data else "Не выбран"

            chat_name = f"({chat_data.name})" if chat_data.name else ""
            chat_type = chat_data.type.value if chat_data.type else "Не выбран"
            chat_owner_income = INCOME_CHAT_TYPE[chat_type] if chat_data.type else "-"
            chat_game_mode = chat_data.game_mode.name if chat_data.game_mode else "Не выбран"
            chat_life_datetime = chat_data.life_datetime.strftime("%Y-%m-%d %H:%M:%S")

            response = f"""
                📊 Информация о чате №{chat_data.chat_id} {chat_name}:
                🎮 GameID: {chat_data.game_id}

                👤 Владелец: {owner_name}
                💎 Тип: {chat_type} ({chat_owner_income}%)
                🌐 Режим: {chat_game_mode}
                ⌛ Активен до: {chat_life_datetime}
                🕒 Продолжительность игры: {chat_data.game_timer} сек.
            """

        elif split_message[0] in ["pinfo", "promo_info"] and len_split_message == 2:
            user_data = await AdminPanel.get_user_data(split_message[1], psql_cursor)
            promocodes = PromoCodeService.get_user_pormocodes(user_data.user_id, psql_cursor)

            response = f"Активные промокоды {user_data.vk_name}\n\n"
            response += "".join([PromoCodeService.format_promocode_message(x) for x in promocodes])

        elif split_message[0] in ["uban", "user_ban"] and len_split_message >= 2:

            users_data = await AdminPanel.get_users_data(split_message[1:], psql_cursor)
            users_name = [x.vk_name for x in users_data]

            psql_cursor.execute("""
                UPDATE users
                SET banned = TRUE
                WHERE user_id IN %(user_ids)s
            """, {
                "user_ids": tuple([x.user_id for x in users_data])
            })

            for user_data in users_data:

                user_id = user_data.user_id
                reset_data = ResetUserServices.reset_data(user_id, psql_cursor)
                IncomesService.records_additional_incomes(reset_data.total_amount, redis_cursor)

                await NotificationsService.send_notification(
                    chat=NotifyChats.RESET_USER_ACCOINT,
                    message=f"{user_data.vk_name} заблокирован {reset_data.reset_message}"
                )

                psql_cursor.execute("""
                    SELECT chat_id FROM user_in_chat
                    WHERE user_id = %(user_id)s
                """, {
                    "user_id": user_id
                })
                user_in_chats = [int(x["chat_id"] - 2E9) for x in psql_cursor.fetchall()]
                [await kick_user_from_chat(user_id, chat_id) for chat_id in user_in_chats]

                psql_cursor.execute("""
                    DELETE FROM user_in_chat
                    WHERE user_id = %(user_id)s
                """, {
                    "user_id": user_id
                })

            response = f"Заблокировал: {', '.join(users_name)}"

        elif split_message[0] in ["unban", "user_unban"] and len_split_message >= 2:
            users_data = await AdminPanel.get_users_data(split_message[1:], psql_cursor)
            users_name = [x.vk_name for x in users_data]

            psql_cursor.execute("""
                UPDATE users
                SET banned = FALSE
                WHERE user_id IN %(user_ids)s
            """, {
                "user_ids": tuple([x.user_id for x in users_data])
            })

            response = f"Разблокировал: {', '.join(users_name)}"

        elif split_message[0] in ["fban", "friend_ban"] and len_split_message == 2:

            user_data = await AdminPanel.get_user_data(split_message[1], psql_cursor)
            friend_ids = await get_user_friends(user_data.user_id)
            friends_data = await AdminPanel.get_users_data(friend_ids, psql_cursor)
            users_data = friends_data + [user_data]

            psql_cursor.execute("""
                UPDATE users
                SET banned = TRUE
                WHERE user_id IN %(user_ids)s
            """, {
                "user_ids": tuple([x.user_id for x in users_data])
            })

            for user_data in users_data:

                user_id = user_data.user_id
                reset_data = ResetUserServices.reset_data(user_id, psql_cursor)
                IncomesService.records_additional_incomes(reset_data.total_amount, redis_cursor)

                await NotificationsService.send_notification(
                    chat=NotifyChats.RESET_USER_ACCOINT,
                    message=f"{user_data.vk_name} заблокирован {reset_data.reset_message}"
                )

                psql_cursor.execute("""
                    SELECT chat_id FROM user_in_chat
                    WHERE user_id = %(user_id)s
                """, {
                    "user_id": user_id
                })
                user_in_chats = [int(x["chat_id"] - 2E9) for x in psql_cursor.fetchall()]
                [await kick_user_from_chat(user_id, chat_id) for chat_id in user_in_chats]

                psql_cursor.execute("""
                    DELETE FROM user_in_chat
                    WHERE user_id = %(user_id)s
                """, {
                    "user_id": user_id
                })

            response = f"Заблокировал: {', '.join([x.vk_name for x in users_data])}"

        elif split_message[0] in ["fnban", "friend_unban"] and len_split_message == 2:

            user_data = await AdminPanel.get_user_data(split_message[1], psql_cursor)
            friend_ids = await get_user_friends(user_data.user_id)
            friends_data = await AdminPanel.get_users_data(friend_ids, psql_cursor)
            users_data = friends_data + [user_data]

            psql_cursor.execute("""
                UPDATE users
                SET banned = FALSE
                WHERE user_id IN %(user_ids)s
            """, {
                "user_ids": tuple([x.user_id for x in users_data])
            })

            response = f"Разблокировал: {', '.join([x.vk_name for x in users_data])}"

        elif split_message[0] in ["pban", "promo_ban"] and len_split_message == 2:
            user_data = await AdminPanel.get_user_data(split_message[1], psql_cursor)

            psql_cursor.execute("""
                UPDATE users
                SET banned_promo = True
                WHERE user_id = %(user_id)s
            """, {
                "user_id": user_data.user_id
            })

            response = f"{user_data.vk_name} больше не может пользоваться промокодами"

        elif split_message[0] in ["pnban", "promo_unban"] and len_split_message == 2:
            user_data = await AdminPanel.get_user_data(split_message[1], psql_cursor)

            psql_cursor.execute("""
                UPDATE users
                SET banned_promo = FALSE
                WHERE user_id = %(user_id)s
            """, {
                "user_id": user_data.user_id
            })

            response = f"{user_data.vk_name} может пользваотеля промокодами"

        elif split_message[0] in ["tban", "transfer_ban"] and len_split_message == 2:

            user_data = await AdminPanel.get_user_data(split_message[1], psql_cursor)
            TransferCoinsService.update_banned_transfer(user_data.user_id, True, psql_cursor)
            response = f"{user_data.vk_name} больше не может переводить коины"

        elif split_message[0] in ["tnban", "transfer_unban"] and len_split_message == 2:

            user_data = await AdminPanel.get_user_data(split_message[1], psql_cursor)
            TransferCoinsService.update_banned_transfer(user_data.user_id, False, psql_cursor)
            response = f"{user_data.vk_name} может переводить коины"

        elif split_message[0] in ["nkban", "nickname_ban"] and len_split_message == 2:

            user_data = await AdminPanel.get_user_data(split_message[1], psql_cursor)

            psql_cursor.execute("""
                UPDATE users
                SET banned_nickname = True
                WHERE user_id = %(user_id)s
            """, {
                "user_id": user_data.user_id
            })

            response = f"{user_data.vk_name} больше не может менять никнейм"

        elif split_message[0] in ["nknban", "nickname_unban"] and len_split_message == 2:

            user_data = await AdminPanel.get_user_data(split_message[1], psql_cursor)

            psql_cursor.execute("""
                UPDATE users
                SET banned_nickname = False
                WHERE user_id = %(user_id)s
            """, {
                "user_id": user_data.user_id
            })

            response = f"{user_data.vk_name} может менять никнейм"

        elif split_message[0] in ["twl", "transfer_white_list"] and len_split_message == 3 and split_message[1] in ["add", "del"]:

            user_data = await AdminPanel.get_user_data(split_message[2], psql_cursor)
            user_id = user_data.user_id

            user_in_white_list = TransferWhiteListService.search(user_id, psql_cursor)

            if split_message[1] == "add":
                if user_in_white_list is False:
                    TransferWhiteListService.insert_user(user_id, psql_cursor)
                    response = f"{user_data.vk_name} добавлен в белый список"
                else:
                    response = f"{user_data.vk_name} уже есть в белом списке"

            elif split_message[1] == "del":
                if user_in_white_list is True:
                    TransferWhiteListService.delete_user(user_id, psql_cursor)
                    response = f"{user_data.vk_name} удален из белого списка"
                else:
                    response = f"{user_data.vk_name} нет в белом списке"

            else:
                raise Exception("from transfer_white_list")

        elif split_message[0] in ["uname", "user_name"] and len_split_message >= 3:
            user_data = await AdminPanel.get_user_data(split_message[1], psql_cursor)
            user_id = user_data.user_id

            new_user_name = " ".join(split_original_message[2:])
            if len(new_user_name) <= 0 or len(new_user_name) > 50:
                raise MaxTextLen("❌ Максимальный размер имени пользователя 50 символов")

            update_user_name(user_id, new_user_name, psql_cursor)
            new_user_name = UserSchema.format_vk_name(user_id, new_user_name)

            response = f"Имя {user_data.vk_name} изменено на {new_user_name}"
            await send_message(
                peer_id=user_id,
                message=f"🅰Администратор изменил ваше имя на {new_user_name}"
            )

        elif split_message[0] in ["udesc", "user_description"] and len_split_message >= 3:
            user_data = await AdminPanel.get_user_data(split_message[1], psql_cursor)
            user_description = " ".join(split_original_message[2:])
            user_description = None if user_description == "clear" else user_description

            if isinstance(user_description, str) and len(user_description) > 250:
                raise MaxTextLen("❌ Максимальный размер описания пользователя 250 символов")

            psql_cursor.execute("""
                UPDATE users
                SET description = %(description)s
                WHERE user_id = %(user_id)s
            """, {
                "description": user_description,
                "user_id": user_data.user_id
            })

            response = f"У {user_data.vk_name} установлено новое описание \"{user_description}\""

        elif (
            split_message[0] in ["ufnick", "user_free_nick"] and
            split_message[2] in ["true", "false"] and
            len_split_message == 3
        ):

            user_data = await AdminPanel.get_user_data(split_message[1], psql_cursor)
            free_change = strtobool(split_message[2])

            update_free_nick_change(user_data.user_id, free_change, psql_cursor)
            response = f"{user_data.vk_name} {'может' if free_change else 'не может'} бесплатно поменять ник"

        elif split_message[0] == "chat" and len_split_message == 4 and split_message[1] == "type":

            chat_data = AdminPanel.get_chat_data(split_message[2], psql_cursor)
            new_chat_type = AdminPanel.get_chat_type(split_message[3]).value

            chat_id = chat_data.chat_id
            psql_cursor.execute("""
                UPDATE chats
                SET type = %(new_chat_type)s
                WHERE chat_id = %(chat_id)s
            """, {
                "new_chat_type": new_chat_type,
                "chat_id": chat_id
            })

            response = f"В чате {chat_id} изменен тип на {new_chat_type}"

        elif split_message[0] == "chat" and len_split_message == 4 and split_message[1] == "owner":

            chat_data = AdminPanel.get_chat_data(split_message[2], psql_cursor)
            new_owner_data = await AdminPanel.get_user_data(split_message[3], psql_cursor)

            chat_id = chat_data.chat_id
            psql_cursor.execute("""
                UPDATE chats
                SET owner_id = %(new_owner_id)s
                WHERE chat_id = %(chat_id)s
            """, {
                "new_owner_id": new_owner_data.user_id,
                "chat_id": chat_id
            })

            response = f"В чате {chat_id} изменен владелец на {new_owner_data.vk_name}"

        elif split_message[0] == "chat" and len_split_message == 4 and split_message[1] == "timer":

            chat_data = AdminPanel.get_chat_data(split_message[2], psql_cursor)
            new_timer = AdminPanel.get_number(split_message[3])
            new_timer = min(max(new_timer, 0), 32_767)

            chat_id = chat_data.chat_id
            psql_cursor.execute("""
                UPDATE chats
                SET game_timer = %(new_timer)s
                WHERE chat_id = %(chat_id)s
            """, {
                "new_timer": new_timer,
                "chat_id": chat_id
            })

            response = f"В чате {chat_id} изменена продолжительность игры на {new_timer} сек."

        elif split_message[0] == "chat" and len_split_message == 4 and split_message[1] == "game_mode":

            chat_data = AdminPanel.get_chat_data(split_message[2], psql_cursor)
            new_game_mode = AdminPanel.get_game_mode(split_message[3])

            chat_id = chat_data.chat_id
            chat_response, chat_keyboard = handler_change_game_mode(admin_data, chat_data, new_game_mode, psql_cursor)
            await send_message(chat_id, chat_response, chat_keyboard)

            response = f"Чат {chat_id} получил сообщение: {chat_response}"

        elif split_message[0] == "chat" and len_split_message >= 4  and split_message[1] == "life":

            chat_data = AdminPanel.get_chat_data(split_message[2], psql_cursor)
            new_life_datetime = AdminPanel.get_life_datetime(" ".join(split_message[3:]))

            chat_id = chat_data.chat_id
            psql_cursor.execute("""
                UPDATE chats
                SET life_datetime = %(new_life_datetime)s
                WHERE chat_id = %(chat_id)s
            """, {
                "new_life_datetime": new_life_datetime,
                "chat_id": chat_id
            })

            response = f"В чате {chat_id} изменено время жизни чата на {new_life_datetime}"

        elif split_message[0] == "resettop" and len_split_message == 2 and split_message[1] in TOPS_NAME:
            TOPS[split_message[1]].reset_points(psql_cursor)
            response = f"Сбросил очки топа {split_message[1]}"

        elif split_message[0] in ["itop", "incrtop"] and len_split_message == 4 and split_message[1] in TOPS_NAME:
            user_data = await AdminPanel.get_user_data(split_message[2], psql_cursor)
            incr_amount = AdminPanel.get_number(split_message[3])

            top_name = split_message[1]
            sql_field = "clan_points" if top_name == ClansTop.NAME else f"{top_name}_top_points"

            psql_cursor.execute(f"""
                UPDATE users
                SET {sql_field} = {sql_field} + %(incr_amount)s
                WHERE user_id = %(user_id)s
            """, {
                "incr_amount": incr_amount,
                "user_id": user_data.user_id
            })

            response = f"У {user_data.vk_name} увеличен топ {top_name} на {format_number(incr_amount)}"

        elif split_message[0] in ["dtop", "decrtop"] and len_split_message == 4 and split_message[1] in TOPS_NAME:
            user_data = await AdminPanel.get_user_data(split_message[2], psql_cursor)
            dncr_amount = AdminPanel.get_number(split_message[3])

            top_name = split_message[1]
            sql_field = "clan_points" if top_name == ClansTop.NAME else f"{top_name}_top_points"

            psql_cursor.execute(f"""
                UPDATE users
                SET {sql_field} = {sql_field} - %(dncr_amount)s
                WHERE user_id = %(user_id)s
            """, {
                "dncr_amount": dncr_amount,
                "user_id": user_data.user_id
            })

            response = f"У {user_data.vk_name} уменьшен топ {top_name} на {format_number(dncr_amount)}"

        elif message == "post":
            response = BonusRepostService.get_active_bonus_response_message(psql_cursor)

        elif split_message[0] == "npost" and len_split_message == 6:
            post_id = AdminPanel.get_number(split_message[1])
            reward = AdminPanel.get_number(split_message[2])
            sub_reward = AdminPanel.get_number(split_message[3])
            activations = AdminPanel.get_number(split_message[4])
            life_seconds = AdminPanel.get_number(split_message[5])

            if BonusRepostService.get_bonus_post(post_id, psql_cursor) is None:
                bonus_post = BonusRepostService.create_bonus_posts(
                    post_id=post_id, reward=reward, sub_reward=sub_reward,
                    activations=activations,life_seconds=life_seconds, psql_cursor=psql_cursor
                )
                response = BonusRepostService.format_bonus_post_message(bonus_post)
            else:
                response = "❌ Данный пост уже создан"

        elif split_message[0] == "dpost" and len_split_message == 2:
            post_id = AdminPanel.get_number(split_message[1])
            BonusRepostService.delete_post(post_id, psql_cursor)
            response = f"Удален бонус за репост {post_id}"

        elif message == "subbonus":
            response = BonusSubscriptionService.get_active_bonuses_response_message(psql_cursor)

        elif split_message[0] == "nsubbonus" and len_split_message == 2:
            reward = AdminPanel.get_number(split_message[1])
            bonus = BonusSubscriptionService.create_bonus(reward=reward, psql_cursor=psql_cursor)
            response = f"✅ Создан бонус за подписку:\n{BonusSubscriptionService.format_bonus_message(bonus)}"

        elif split_message[0] == "dsubbonus" and len_split_message == 2:
            bonus_id = AdminPanel.get_number(split_message[1])
            if BonusSubscriptionService.get_bonus(bonus_id, psql_cursor) is not None:
                BonusSubscriptionService.delete_bonus(bonus_id, psql_cursor)
                response = f"✅ Удален бонус за подписку {bonus_id}"
            else:
                response = f"❌ Бонус {bonus_id} не найден"

        elif message == "dev":
            response = get_develore_income(psql_cursor, redis_cursor)

        elif message == "dev_clear":
            develore_income = get_develore_income(psql_cursor, redis_cursor)
            clear_developer_income(psql_cursor)

            response = f"Данные обнулены\n\n{develore_income}"
            await send_message(Config.DEVELOPER_ID, develore_income)

        elif split_message[0] == "api" and len_split_message == 2 and split_message[1] in ["on", "off"]:
            work_status = strtobool(split_message[1])
            change_works_status(work_status)
            redis_cursor.set(RedisKeys.API_WORK.value, int(work_status))
            response = f"API {'включен' if work_status else 'выключен'}"

        elif split_message[0] == "auto_games" and len_split_message == 2 and split_message[1] in ["on", "off"]:
            work_status = strtobool(split_message[1])
            redis_cursor.set(RedisKeys.AUTO_GAMES_WORK.value, int(work_status))
            response = f"Авто игры {'включены' if work_status else 'выключены'}"

        elif split_message[0] == "quiet_mode" and len_split_message == 2 and split_message[1] in ["on", "off"]:
            work_status = strtobool(split_message[1])
            redis_cursor.set(RedisKeys.QUIET_MODE.value, int(work_status))
            response = f"Тихий режим {'включен' if work_status else 'выключен'}"

        elif split_message[0] == "start_game" and len_split_message == 2 and split_message[1].isdecimal():
            game_data = get_game_data(split_message[1], psql_cursor)
            game_model = BaseGameModel.GAMES_MODEL[game_data.game_mode]
            game_model.init_game(game_data.game_id, psql_cursor, redis_cursor)
            response = f"Запущена игра № {game_data.game_id} в чате № {int(game_data.chat_id - 2E9)}"

        elif message == "restart_bot":
            threading.Thread(target=asyncio.run, args=[restart_bot()], daemon=True).start()
            response = "die Höllenmaschine wird in 20 Sekunden neu gestartet"

        else:
            response = COMMAND_NOT_FOUND

    except (
        UserIdNotFound, UserDataNotFound, UsersDataNotFound,
        ChatIdNotFound, ChatDataNotFound, ChatTypeNotFound,
        GameModeNotFound, ChatLifeDatetimeError, NumberNotFound,
        MaxTextLen
    ) as error_text:
        response = str(error_text)

    await send_message(admin_id, response, keyboard)
