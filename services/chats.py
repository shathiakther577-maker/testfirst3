from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from psycopg2.extras import DictCursor

from schemas.users import UserSchema, UserStatus
from schemas.chats import ChatSchema, ChatType, ChatStatsPeriod, ChatStatsSchema, \
    ChatStatsUserSchema, ChatHelperSchema, CHAT_STATS_PAYLOAD
from schemas.games import Games

from modules.additional import format_number
from modules.databases.users import get_user_data


class ChatsService:

    @classmethod
    def register_chat(
            cls,
            chat_id: int,
            psql_cursor: DictCursor
    ) -> None:
        """Добавляет чат в базу данных"""

        psql_cursor.execute("INSERT INTO chats (chat_id) VALUES (%s)", (chat_id,))


    @classmethod
    def update_owner_id(
            cls,
            chat_id: int,
            owner_id: int,
            psql_cursor: DictCursor
    ) -> None:
        """Обновляет идентификатор владельца чата"""

        psql_cursor.execute("""
            UPDATE chats
            SET owner_id = %(owner_id)s
            WHERE chat_id = %(chat_id)s
        """, {
            "owner_id": owner_id,
            "chat_id": chat_id
        })


    @classmethod
    def update_game_mode(
            cls,
            chat_id: int,
            game_mode: Games,
            psql_cursor: DictCursor
    ) -> None:
        """Обновляет игровой режим в чате"""

        psql_cursor.execute("""
            UPDATE chats
            SET game_mode = %(game_mode)s
            WHERE chat_id = %(chat_id)s
        """, {
            "game_mode": game_mode.value,
            "chat_id": chat_id
        })


    @classmethod
    def update_type(
            cls,
            chat_id: int,
            chat_type: ChatType,
            psql_cursor: DictCursor
    ) -> None:
        """Обновляет тип подписки в чате"""

        psql_cursor.execute("""
            UPDATE chats
            SET type = %(chat_type)s
            WHERE chat_id = %(chat_id)s
        """, {
            "chat_type": chat_type.value,
            "chat_id": chat_id
        })


    @classmethod
    def update_chat_name(
            cls,
            chat_id: int,
            new_name: str,
            psql_cursor: DictCursor
    ) -> None:
        """Обновляет название клана"""

        psql_cursor.execute("""
            UPDATE chats
            SET name = %(name)s
            WHERE chat_id = %(chat_id)s
        """, {
            "name": new_name,
            "chat_id": chat_id
        })


    @classmethod
    def get_days_subscription_left(
            cls,
            chat_id: int,
            psql_cursor: DictCursor
    ) -> int:
        """Возвращает сколько дней подписки осталось"""

        psql_cursor.execute("""
            SELECT GREATEST(ROUND(EXTRACT(
                EPOCH FROM (chats.life_datetime - NOW())
            ) / 86400), 0) as days_left
            FROM chats
            WHERE chat_id = %s
        """, (chat_id,))
        days_left = int(psql_cursor.fetchone()["days_left"])

        return days_left


    @classmethod
    def update_life_datetime(
            cls,
            chat_id: int,
            month: int,
            psql_cursor: DictCursor
    ) -> None:
        """Обновляет время жизни чата (текущее время + month)"""

        psql_cursor.execute("""
            UPDATE chats
            SET is_activated = True,
                life_datetime = NOW() + INTERVAL '%(month)s MONTH'
            WHERE chat_id = %(chat_id)s
        """, {
            "month": month,
            "chat_id": chat_id
        })


    @classmethod
    def get_my_chats(
        cls,
        user_id: int,
        psql_cursor: DictCursor,
        offset: int,
        limit: int
    ) -> list[ChatSchema | None]:
        """Возвращает чаты которые принадлежат пользователю"""

        psql_cursor.execute("""
            SELECT * FROM chats
            WHERE owner_id = %(user_id)s
            ORDER BY chat_id ASC, is_activated DESC
            OFFSET %(offset)s
            LIMIT %(limit)s
        """, {
            "user_id": user_id,
            "offset": offset,
            "limit": limit
        })
        chats = [ChatSchema(**x) for x in psql_cursor.fetchall()]

        return chats


    @classmethod
    def get_count_my_chats(
            cls,
            owner_id: int,
            psql_cursor: DictCursor
    ) -> int:
        """Возвращает количество чатов которые принадлежат пользователю"""

        psql_cursor.execute("""
            SELECT COUNT(*) as count_chats
            FROM chats
            WHERE owner_id = %s
        """, (owner_id,)),
        psql_response = psql_cursor.fetchone()["count_chats"]

        return psql_response


    @classmethod
    def prolong_life_datetime(
            cls,
            chat_id: int,
            days: int,
            psql_cursor: DictCursor
    ) -> None:
        """Продлевает подписку в чате"""

        psql_cursor.execute("""
            UPDATE chats
            SET life_datetime = life_datetime + INTERVAL '%(days)s DAYS'
            WHERE chat_id = %(chat_id)s
        """, {
            "days": days,
            "chat_id": chat_id
        })


    @staticmethod
    def _get_stats_sql_condition(period: ChatStatsPeriod) -> str:
        """Возвращает условие по которому выполняется поиск в базе данных"""

        condition = "WHERE rates.chat_id = %(chat_id)s AND "

        if period == ChatStatsPeriod.DAY:
            condition += "DATE(rates.created_at) = current_date"

        elif period == ChatStatsPeriod.WEEK:
            condition += """
                DATE(rates.created_at) >= date_trunc('week', current_date) AND
                DATE(rates.created_at) <= current_date
            """

        elif period == ChatStatsPeriod.ALL_TIME:
            condition += "TRUE = TRUE"

        else:
            raise ValueError()

        return condition


    @staticmethod
    def _get_stats_name(period: ChatStatsPeriod) -> str:
        """Возвращает сообщение с названием статистики"""

        if period == ChatStatsPeriod.DAY:
            name = "сегодня"

        elif period == ChatStatsPeriod.WEEK:
            name = "неделю"

        elif period == ChatStatsPeriod.ALL_TIME:
            name = "все время"

        else:
            raise ValueError()

        return f"📊 Статистика беседы за {name}"


    @classmethod
    def get_chat_stats_for_period(
            cls,
            chat_id: int,
            period: ChatStatsPeriod,
            psql_cursor: DictCursor
    ) -> ChatStatsSchema:
        """Возвращает общую статистику за период"""

        psql_cursor.execute(f"""
            SELECT COALESCE(SUM(rates.amount), 0) as rates_amount,
                   COALESCE(COUNT(DISTINCT rates.user_id), 0) as count_users,
                   COALESCE(SUM(rates.owner_income), 0) as owner_incomes
            FROM rates JOIN users ON rates.user_id = users.user_id
            {cls._get_stats_sql_condition(period)}
        """, {
            "chat_id": chat_id
        })
        psql_response = psql_cursor.fetchone()

        return ChatStatsSchema(**psql_response)


    @classmethod
    def get_users_stats_for_period(
            cls,
            chat_id: int,
            period: ChatStatsPeriod,
            psql_cursor: DictCursor
    )-> list[ChatStatsUserSchema | None]:
        """Возвращает 10 лучших пользователей по сумме ставок"""

        psql_cursor.execute(f"""
            SELECT rates.user_id as user_id,
                   users.status as user_status,
                   users.full_name as full_name,
                   SUM(rates.amount) as rates_amount
            FROM rates JOIN users ON rates.user_id = users.user_id
            {cls._get_stats_sql_condition(period)}
            GROUP BY rates.user_id, users.status, users.full_name
            ORDER BY rates_amount DESC
            LIMIT 10
        """, {
            "chat_id": chat_id
        })

        users = []
        for user in psql_cursor.fetchall():
            prefix = UserSchema.get_user_prefix(UserStatus(user["user_status"]))
            user["full_name"] = f"{prefix}{user['full_name']}{prefix}"
            users.append(ChatStatsUserSchema(**user))

        return users


    @classmethod
    def get_stats_message(
            cls,
            chat_id: int,
            period: ChatStatsPeriod,
            psql_cursor: DictCursor
    ) -> str:
        """Возвращает сообщение о статистики чата"""

        stats = cls.get_chat_stats_for_period(chat_id, period, psql_cursor)
        users = cls.get_users_stats_for_period(chat_id, period, psql_cursor)

        message = f"""
            {cls._get_stats_name(period)}

            💰 Ставок: {format_number(stats.rates_amount)}
            💳 Прибыль владельца: {format_number(stats.owner_incomes)}
            👤 Активных игроков: {format_number(stats.count_users)}
        """

        if len(users) > 0:
            message += "\n🔥 Топ игроков:"

        for index, user in enumerate(users, 1):
            user_name = UserSchema.format_vk_name(user.user_id, user.full_name)
            rates_amount = format_number(user.rates_amount)
            message += f"\n{index}) {user_name} - поставил {rates_amount} коинов"

        return message


    @classmethod
    def get_stats_keyboard(cls) -> str:
        """Возвращает клавиатуру для выбора статистики"""

        keyboard = VkKeyboard(one_time=False, inline=True)
        keyboard.add_button(
            label="День",
            color=VkKeyboardColor.POSITIVE,
            payload={
                "event": CHAT_STATS_PAYLOAD,
                "period": ChatStatsPeriod.DAY.value
            }
        )
        keyboard.add_button(
            label="Неделя",
            color=VkKeyboardColor.POSITIVE,
            payload={
                "event": CHAT_STATS_PAYLOAD,
                "period": ChatStatsPeriod.WEEK.value
            }
        )
        keyboard.add_line()

        keyboard.add_button(
            label="Все время",
            color=VkKeyboardColor.POSITIVE,
            payload={
                "event": CHAT_STATS_PAYLOAD,
                "period": ChatStatsPeriod.ALL_TIME.value
            }
        )

        return keyboard.get_keyboard()


    @classmethod
    def get_helper(
            cls,
            user_id: int,
            chat_id: int,
            psql_cursor: DictCursor
    ) -> ChatHelperSchema | None:
        """Возвращает помощника чата если он есть"""

        psql_cursor.execute("""
            SELECT * FROM chat_helpers
            WHERE user_id = %(user_id)s AND
                  chat_id = %(chat_id)s
        """, {
            "user_id": user_id,
            "chat_id": chat_id
        })
        psql_response = psql_cursor.fetchone()
        helper = ChatHelperSchema(**psql_response) if psql_response else None

        return helper


    @classmethod
    def get_helpers(
            cls,
            chat_id: int,
            psql_cursor: DictCursor
    ) -> list[ChatHelperSchema | None]:
        """Возвращает помощников чата в данном чате"""

        psql_cursor.execute("""
            SELECT * FROM chat_helpers
            WHERE chat_id = %s
            ORDER BY status
        """, (chat_id,))
        psql_response = psql_cursor.fetchall()
        helpers = [ChatHelperSchema(**x) for x in psql_response]

        return helpers


    @classmethod
    def create_helper(
            cls,
            user_id: int,
            chat_id: int,
            psql_cursor: DictCursor
    ) -> ChatHelperSchema:
        """Добавляет помощника в базу данных"""

        helper = ChatHelperSchema(user_id=user_id, chat_id=chat_id)

        psql_cursor.execute("""
            INSERT INTO chat_helpers (user_id, chat_id, status)
            VALUES (%(user_id)s, %(chat_id)s, %(status)s)
        """, helper.dict())

        return helper


    @classmethod
    def delete_helper(
            cls,
            user_id: int,
            chat_id: int,
            psql_cursor: DictCursor
    ) -> None:
        """Удаляет пользователя из помощников чата"""

        psql_cursor.execute("""
            DELETE FROM chat_helpers
            WHERE user_id = %(user_id)s AND
                  chat_id = %(chat_id)s
        """, {
            "user_id": user_id,
            "chat_id": chat_id
        })


    @classmethod
    def is_helper(
            cls,
            user_id: int,
            chat_id: int,
            psql_cursor: DictCursor
    ) -> bool:
        """Проверяет, является ли пользователь помощником чата"""

        return bool(cls.get_helper(user_id, chat_id, psql_cursor))


    @classmethod
    def get_helpers_message(
            cls,
            chat_data: ChatSchema,
            psql_cursor: DictCursor
    ) -> str:
        """Возвращает сообщение о помощниках чата"""

        owner_id = chat_data.owner_id
        owner_data = get_user_data(owner_id, psql_cursor)

        message = f"👑 Владелец беседы:\n{owner_data.vk_name}\n\n"
        helpers = cls.get_helpers(chat_data.chat_id, psql_cursor)

        if len(helpers) > 0:
            message += "👥 Помощники:\n"

        for helper in helpers:
            helper_data = get_user_data(helper.user_id, psql_cursor)
            message += f"{helper_data.vk_name}\n"

        return message
