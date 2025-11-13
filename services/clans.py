import random
from typing import Optional

from redis.client import Redis
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from psycopg2.extras import DictCursor

from settings import TelegramBotSettings, ClanSettings

from schemas.users import UserSchema, UserMenu
from schemas.clans import ClanSchema, MiniClanSchema, MemberScheme, ClanRole, \
    ClanJoinType, ExtraCreateClan, ExtraOwnerClan, clan_join_type_translation
from schemas.redis import RedisKeys

from modules.additional import format_number
from modules.databases.users import get_user_data, update_user_menu, \
    update_user_extra_data
from modules.telegram.bot import send_message, send_keyboard

from vk_bot.template_messages import CLAN_GREETING, CLAN_NOT_FOUND, CLAN_IS_CLOSED, \
    YOU_HAVE_CLAN, APPLICATION_SENT, APPLICATION_ALREADY_SENT, DATA_OUTDATED, \
    MAX_COUNT_MEMBERS_IN_CLAN, NOT_OVERCOME_CLAN_BARRIER
from vk_bot.keyboards.pages import add_back_page, add_next_page
from vk_bot.keyboards.clans_menu import get_clan_join_keyboard, get_clan_menu_keyboard, \
    get_clan_member_keyboard, get_keyboard_answer_owner_clan


class ClanService:
    """Сервис по работе с кланами"""

    @staticmethod
    def _assigns_clan_owner(
            clan_data: ClanSchema,
            psql_cursor: DictCursor
    ) -> None:
        """Назначает владельца клана"""

        psql_cursor.execute("""
            UPDATE users
            SET clan_id = %(clan_id)s,
                clan_role = %(clan_role)s,
                clan_points = 0
            WHERE user_id = %(user_id)s
        """, {
            "clan_id": clan_data.clan_id,
            "clan_role": ClanRole.OWNER.value,
            "user_id": clan_data.owner_id
        })


    @classmethod
    def create_clan(
            cls,
            owner_id: int,
            clan_tag: str,
            clan_name: str,
            psql_cursor: DictCursor
    ) -> ClanSchema:
        """Создает клан и возвращает его данные"""

        psql_cursor.execute("""
            INSERT INTO clans (owner_id, tag, name)
            VALUES (%(owner_id)s, %(tag)s, %(name)s)
            RETURNING *
        """, {
            "tag": clan_tag,
            "name": clan_name,
            "owner_id": owner_id
        })
        psql_response = psql_cursor.fetchone()
        clan_data = ClanSchema(**psql_response)

        cls._assigns_clan_owner(clan_data, psql_cursor)

        return clan_data


    @staticmethod
    def get_clan_points(
            clan_id: str,
            psql_cursor: DictCursor
    ) -> int:
        """Возвращает очки клана"""

        psql_cursor.execute("""
            SELECT COALESCE(SUM(clan_points), 0) as clan_points
            FROM users
            WHERE clan_id = %(clan_id)s
        """, {
            "clan_id": clan_id
        })
        clan_points = int(psql_cursor.fetchone()["clan_points"])

        return clan_points


    @staticmethod
    def get_clan_count_members(
            clan_id: int,
            psql_cursor: DictCursor
    ) -> int:
        """Возвращает количество участников клана"""

        psql_cursor.execute("""
            SELECT COALESCE(COUNT(*), 0) as count_members
            FROM users
            WHERE clan_id = %(clan_id)s
        """, {
            "clan_id": clan_id
        })
        count_members = int(psql_cursor.fetchone()["count_members"])

        return count_members


    @classmethod
    def get_clan_data(
            cls,
            clan_id: int,
            psql_cursor: DictCursor
    ) -> ClanSchema | None:
        """Возвращает данные клана"""

        psql_cursor.execute("""
            SELECT * FROM clans
            WHERE clan_id = %(clan_id)s
        """, {
            "clan_id": clan_id
        })
        psql_response = psql_cursor.fetchone()

        if psql_response is not None:
            clan_data = ClanSchema(**psql_response)

            clan_data.points = cls.get_clan_points(clan_id, psql_cursor)
            clan_data.count_members = cls.get_clan_count_members(clan_id, psql_cursor)

            return clan_data

        else:
            return None


    @staticmethod
    def get_clans(
            psql_cursor: DictCursor,
            offset: int,
            limit: int
    ) -> list[Optional[MiniClanSchema]]:
        """
            Возвращает список кланов по рейтингу
            с указанным смещением и лимитом
        """

        psql_cursor.execute("""
            SELECT clans.clan_id, clans.owner_id,
                   clans.tag, clans.name,
                   COALESCE(SUM(users.clan_points), 0) as points
            FROM clans
            LEFT JOIN users ON clans.clan_id = users.clan_id
            GROUP BY clans.clan_id, clans.owner_id,
                     clans.tag, clans.name, clans.tag
            ORDER BY points DESC, clan_id DESC
            OFFSET %(offset)s
            LIMIT %(limit)s
        """, {
            "offset": offset,
            "limit": limit
        })
        psql_response = psql_cursor.fetchall()
        clans = [MiniClanSchema(**clan) for clan in psql_response]

        return clans


    @staticmethod
    def get_total_clans_counts(
            psql_cursor: DictCursor
    ) -> int:
        """Возвращает общее количество кланов"""

        psql_cursor.execute("""
            SELECT COALESCE(COUNT(*), 0) as count_clans
            FROM clans
        """)
        total_clans_counts = int(psql_cursor.fetchone()["count_clans"])

        return total_clans_counts


    @classmethod
    def get_clan_position(
            cls,
            clan_id: int,
            psql_cursor: DictCursor
    ) -> int:
        """Возвращает место клана в рейтинге"""

        try:
            total_clans_counts = cls.get_total_clans_counts(psql_cursor)
            all_clans = cls.get_clans(psql_cursor, 0, total_clans_counts)
            all_clans = [clan.clan_id for clan in all_clans]
            clan_position = all_clans.index(clan_id) + 1

            return clan_position

        except:
            return 0


    @classmethod
    def get_clans_message(
            cls,
            psql_cursor: DictCursor,
            offset: int = 0
    ) -> tuple[str, str | None]:
        """Возвращает сообщение и клавиатуру о кланах"""

        COUNT_ROW = 4  # Количество кнопок в строке
        COUNT_CLANS = 8  # Количество кланов которое нужны найти

        clans = cls.get_clans(psql_cursor, offset, COUNT_CLANS)
        total_count_clans = cls.get_total_clans_counts(psql_cursor)

        response = "Топ кланов:\n"
        keyboard = VkKeyboard(one_time=False, inline=True) if clans else None

        start_enumerate = offset + 1
        stop_enumerate = offset + min(COUNT_CLANS, len(clans))

        for number, clan in enumerate(clans, start_enumerate):
            clan_name = UserSchema.format_vk_name(clan.owner_id, clan.name)
            clan_points = format_number(clan.points)

            response += f"\n{number}) [{clan.tag}] {clan_name} - {clan_points} очков"
            keyboard.add_button(
                label=str(number),
                color=VkKeyboardColor.SECONDARY,
                payload={
                    "event": "get_clan_info",
                    "clan_id": clan.clan_id
            })

            if (
                number != start_enumerate and
                number % COUNT_ROW == 0 and
                number != stop_enumerate
            ):
                keyboard.add_line()

        back_page = offset != 0
        next_page = total_count_clans - offset - COUNT_CLANS > 0

        if back_page or next_page:
            keyboard.add_line()  # если есть кнопки вперед и/или назад

        if back_page:
            add_back_page(
                keyboard,
                full_test=next_page is False,
                payload={
                    "event": "get_clans_message",
                    "offset": offset - COUNT_CLANS
            })

        if next_page:
            add_next_page(
                keyboard,
                full_test=offset == 0,
                payload={
                    "event": "get_clans_message",
                    "offset": offset + COUNT_CLANS
            })

        if keyboard is not None:
            keyboard = keyboard.get_keyboard()

        return response, keyboard


    @staticmethod
    def format_message_clan_info(
            clan_data: ClanSchema,
            owner_data: UserSchema
    ) -> str:
        """Возвращает сообщение с информацией о клане"""

        response = f"""
            🏆 [{clan_data.tag}] {clan_data.name}

            🕶 Глава: {owner_data.vk_name}
            💳 Счет: {format_number(clan_data.points)}

            🔒 Тип: {clan_join_type_translation[clan_data.join_type]}
            ✅ Необходимо выиграть для вступления: {format_number(clan_data.join_barrier)}
            👥 Участников: {clan_data.count_members}/{ClanSettings.MAX_COUNT_MEMBERS}
        """

        return response


    @classmethod
    def get_clan_info_message(
            cls,
            psql_cursor: DictCursor,
            *,
            clan_id: int,
            user_data: UserSchema,
    ) -> tuple[str, str]:
        """Возвращает сообщение и клавиатуру с информацией о клане"""

        clan_data = cls.get_clan_data(clan_id, psql_cursor)

        if clan_data is not None:
            owner_data = get_user_data(clan_data.owner_id, psql_cursor)
            response = cls.format_message_clan_info(clan_data, owner_data)
            keyboard = get_clan_join_keyboard(user_data, clan_data)

        else:
            response = CLAN_NOT_FOUND
            keyboard = None

        return response, keyboard


    @staticmethod
    async def send_keyboard_clan_menu(
            user_data: UserSchema,
            psql_cursor: DictCursor
    ) -> None:
        """Отправляет клавиатуру меню клана"""

        user_id = user_data.user_id
        keyboard = get_clan_menu_keyboard(user_data)

        if user_data.clan_role == ClanRole.NOT:
            update_user_extra_data(user_id, ExtraCreateClan(), psql_cursor)

        elif user_data.clan_role == ClanRole.OWNER:
            update_user_extra_data(user_id, ExtraOwnerClan(), psql_cursor)

        await send_keyboard(user_id, keyboard)


    @staticmethod
    async def update_invitation_link(
            clan_id: int,
            psql_cursor: DictCursor
    ) -> None:
        """Обновляет ссылку для входа в клан"""

        salt = random.randint(10000, 32767)
        # В Telegram используем прямую ссылку на бота
        link = f"https://t.me/{TelegramBotSettings.BOT_USERNAME}?start=clan_{clan_id}_{salt}"

        psql_cursor.execute("""
            UPDATE clans
            SET invitation_link = %(link)s,
                invitation_salt = %(salt)s
            WHERE clan_id = %(clan_id)s
        """, {
            "link": link,
            "salt": salt,
            "clan_id": clan_id
        })


    @staticmethod
    async def send_clan_owner_notification(
            clan_data: ClanSchema,
            message: str,
            keyboard: str | None = None,
            *,
            mandatory: bool = False
    ) -> None:
        """
            Отправляет сообщение владельцу клана
            :param mandatory: Если включено, то уведомление отправиться
                в любом случае. Если выключено, то будет проверяться owner_notifications.
        """

        if mandatory or clan_data.owner_notifications:
            await send_message(clan_data.owner_id, message, keyboard)


    @staticmethod
    def reset_user_clan_points(
        user_id: int,
        psql_cursor: DictCursor
    ) -> None:
        """Сбрасывает очки пользователя принесенные в клан"""

        psql_cursor.execute("""
            UPDATE users
            SET clan_points = 0
            WHERE user_id = %(user_id)s
        """, {
            "user_id": user_id
        })


    @classmethod
    def join_clan(
            cls,
            clan_id: int,
            user_id: int,
            psql_cursor: DictCursor
    ) -> None:
        """Вход в клан"""

        cls.reset_user_clan_points(user_id, psql_cursor)
        psql_cursor.execute("""
            UPDATE users
            SET clan_id = %(clan_id)s,
                clan_role = %(clan_role)s
            WHERE user_id = %(user_id)s
        """, {
            "clan_id": clan_id,
            "user_id": user_id,
            "clan_role": ClanRole.MEMBER.value
        })


    @classmethod
    async def go_clan_menu(
            cls,
            user_data: UserSchema,
            psql_cursor: DictCursor
    ) -> tuple[str, str | None]:
        """Направляет пользователя в меню кланов"""

        if user_data.clan_role == ClanRole.NOT:
            response, keyboard = cls.get_clans_message(psql_cursor)

        else:
            response, _ = cls.get_clan_info_message(
                psql_cursor, clan_id=user_data.clan_id, user_data=user_data
            )
            keyboard = get_clan_menu_keyboard(user_data)

        await cls.send_keyboard_clan_menu(user_data, psql_cursor)
        update_user_menu(user_data.user_id, UserMenu.CLANS, psql_cursor)

        return response, keyboard


    @classmethod
    async def handler_clan_join(
            cls,
            clan_id: int,
            user_data: UserSchema,
            psql_cursor: DictCursor
    ) -> tuple[str, str, bool]:
        """Обрабатывает вход в клан возвращает сообщение, клавиатуру"""

        keyboard = None
        clan_data = cls.get_clan_data(clan_id, psql_cursor)

        if clan_data is None:
            response = CLAN_NOT_FOUND

        elif not cls.is_clan_open(clan_data.join_type):
            response = CLAN_IS_CLOSED

        elif not cls.is_have_free_place(clan_data.count_members):
            response = MAX_COUNT_MEMBERS_IN_CLAN

        elif not cls.is_overcome_join_barrier(user_data.all_win, clan_data.join_barrier):
            response = NOT_OVERCOME_CLAN_BARRIER

        else:
            user_id = user_data.user_id
            cls.join_clan(clan_id, user_id, psql_cursor)

            owner_message = f"⚠️ {user_data.vk_name} вступил в клан"
            await cls.send_clan_owner_notification(clan_data, owner_message)

            response = CLAN_GREETING
            keyboard = get_clan_member_keyboard()
            update_user_extra_data(user_id, None, psql_cursor)

        return response, keyboard


    @classmethod
    async def handler_user_application(
            cls,
            psql_cursor: DictCursor,
            redis_cursor: Redis,
            *,
            clan_id: int,
            user_data: UserSchema
    ) -> str:
        """
            Возвращает сообщения результата отправки
            пользователем заявки на вступления в клан
        """

        user_id = user_data.user_id
        clan_data = cls.get_clan_data(clan_id, psql_cursor)
        redis_key = cls.create_redis_key_for_accent_clan(user_id=user_id, clan_id=clan_id)

        if clan_data is None:
            return CLAN_NOT_FOUND

        elif not cls.is_clan_closed(clan_data.join_type):
            response = DATA_OUTDATED

        elif not cls.is_have_free_place(clan_data.count_members):
            response = MAX_COUNT_MEMBERS_IN_CLAN

        elif not cls.is_overcome_join_barrier(user_data.all_win, clan_data.join_barrier):
            response = NOT_OVERCOME_CLAN_BARRIER

        elif cls.redis_check_application_join_clan(redis_key, redis_cursor):
            response = APPLICATION_ALREADY_SENT

        else:
            await cls.send_clan_owner_notification(
                clan_data=clan_data,
                message=f"""
                    👤 {user_data.vk_name} хочет вступить в ваш клан
                    💰 Выиграно сегодня: {format_number(user_data.day_win)}
                    💰 Выиграно за все время: {format_number(user_data.all_win)}
                """,
                keyboard=get_keyboard_answer_owner_clan(user_id, clan_id),
                mandatory=True
            )
            cls.redis_add_application_join_clan(redis_key, redis_cursor)

            response = APPLICATION_SENT

        return response


    @classmethod
    async def reference_clan_join(
            cls,
            reference: str,
            user_data: UserSchema,
            psql_cursor: DictCursor
    ) -> None:
        """Обрабатывает вступление в клан по ссылке"""

        user_id = user_data.user_id

        _, clan_id, clan_salt = reference.split("_")
        clan_data = cls.get_clan_data(clan_id, psql_cursor)

        if user_data.clan_role != ClanRole.NOT:
            response = YOU_HAVE_CLAN

        elif clan_data is None:
            response = CLAN_NOT_FOUND

        elif int(clan_salt) != clan_data.invitation_salt:
            response = DATA_OUTDATED

        elif not cls.is_have_free_place(clan_data.count_members):
            response = MAX_COUNT_MEMBERS_IN_CLAN

        else:
            cls.join_clan(clan_id, user_id, psql_cursor)
            await cls.update_invitation_link(clan_id, psql_cursor)

            owner_message = f"⚠️ {user_data.vk_name} вступил в клан"
            await cls.send_clan_owner_notification(clan_data, owner_message)

            response = CLAN_GREETING

        await send_message(user_id, response)


    @staticmethod
    def get_clan_members(
            clan_id: int,
            psql_cursor: DictCursor,
            offset: int,
            limit: int
    ) -> list[Optional[MemberScheme]]:
        """
            Возвращает список участников клана по рейтингу
            с указанным смещением и лимитом
        """

        psql_cursor.execute("""
            SELECT user_id, full_name,
                   clan_points as points
            FROM users
            WHERE clan_id = %(clan_id)s
            ORDER BY clan_points DESC
            OFFSET %(offset)s
            LIMIT %(limit)s
        """, {
            "clan_id": clan_id,
            "offset": offset,
            "limit": limit
        })
        psql_response = psql_cursor.fetchall()
        members_data = [MemberScheme(**member) for member in psql_response]

        return members_data


    @classmethod
    def get_clan_members_message(
            cls,
            psql_cursor: DictCursor,
            *,
            clan_id: int,
            offset: int = 0
    ) -> tuple[str, str]:
        """Возвращает сообщение и клавиатуру об участниках клана"""

        COUNT_MEMBERS = 5  # Количество участников которые нужно запросить

        count_members = cls.get_clan_data(clan_id, psql_cursor).count_members
        members = cls.get_clan_members(clan_id, psql_cursor, offset, COUNT_MEMBERS)

        response = "Участники клана:\n"
        keyboard = None

        for number, member in enumerate(members, offset+1):
            member_full_name = UserSchema.format_vk_name(member.user_id, member.full_name)
            response += f"\n{number}. {member_full_name} - выиграл {format_number(member.points)} коинов"

        back_page = offset != 0
        next_page = count_members - offset - COUNT_MEMBERS > 0

        if back_page or next_page:
            keyboard = VkKeyboard(one_time=False, inline=True)

        if back_page:
            add_back_page(
                keyboard,
                full_test=next_page is False,
                payload={
                    "event": "get_clan_members_message",
                    "offset": offset - COUNT_MEMBERS
            })

        if next_page:
            add_next_page(
                keyboard,
                full_test=offset == 0,
                payload={
                    "event": "get_clan_members_message",
                    "offset": offset + COUNT_MEMBERS
            })

        if keyboard is not None:
            keyboard = keyboard.get_keyboard()

        return response, keyboard


    @classmethod
    def get_link_clan_chat(
            cls,
            clan_id: int,
            psql_cursor: DictCursor
    ) -> str:
        """Возвращает сообщение ссылкой на чат клана"""

        clan_data = cls.get_clan_data(clan_id, psql_cursor)

        if clan_data.chat_link is not None:
            response = f"Ссылка на беседу клана:\n\n{clan_data.chat_link}"
        else:
            response = "😕 Лидер не указал ссылку на беседу клана"

        return response


    @staticmethod
    def get_members_id(
            clan_id: int,
            psql_cursor: DictCursor
    ) -> list[Optional[int]]:
        """Возвращает идентификаторы участников клана кроме владельца"""

        psql_cursor.execute("""
            SELECT user_id FROM users
            WHERE clan_id = %(clan_id)s
        """, {
            "clan_id": clan_id,
            "clan_role": ClanRole.OWNER.value
        })
        member_ids = psql_cursor.fetchall()
        member_ids = [member_id["user_id"] for member_id in member_ids]

        return member_ids


    @staticmethod
    def leave_clan(
            member_ids: list[int],
            psql_cursor: DictCursor
    ) -> None:
        """Выходит из клана"""

        psql_cursor.execute("""
            UPDATE users
            SET clan_id = %(clan_id)s,
                clan_role = %(clan_role)s,
                clan_points = %(clan_points)s
            WHERE user_id in %(member_ids)s
        """, {
            "clan_id": None,
            "clan_role": ClanRole.NOT.value,
            "clan_points": 0,
            "member_ids": tuple(member_ids)
        })

        psql_cursor.execute("""
            UPDATE users
            SET menu = %(menu)s,
                extra_data = NULL
            WHERE menu = %(check_menu)s AND
                  user_id in %(member_ids)s
        """, {
            "menu": UserMenu.MAIN.value,
            "check_menu": UserMenu.CLANS.value,
            "member_ids": tuple(member_ids)
        })


    @classmethod
    def delete_clan(
            cls,
            clan_id: int,
            member_ids: list[Optional[int]],
            psql_cursor: DictCursor
    ) -> None:
        """Удаляет клан"""

        psql_cursor.execute("""
            DELETE FROM clans
            WHERE clan_id = %(clan_id)s
        """, {
            "clan_id": clan_id
        })
        cls.leave_clan(member_ids, psql_cursor)


    @staticmethod
    def change_clan_tag(
            clan_id: int,
            clan_tag: str,
            psql_cursor: DictCursor
    ) -> None:
        """Меняет тег клана"""

        psql_cursor.execute("""
            UPDATE clans
            SET tag = %(clan_tag)s
            WHERE clan_id = %(clan_id)s
        """, {
            "clan_id": clan_id,
            "clan_tag": clan_tag
        })


    @staticmethod
    def change_clan_name(
            clan_id: int,
            clan_name: str,
            psql_cursor: DictCursor
    ) -> None:
        """Меняет имя клана"""

        psql_cursor.execute("""
            UPDATE clans
            SET name = %(clan_name)s
            WHERE clan_id = %(clan_id)s
        """, {
            "clan_id": clan_id,
            "clan_name": clan_name
        })


    @staticmethod
    def change_chat_link(
            clan_id: int,
            chat_link: str,
            psql_cursor: DictCursor
    ) -> None:
        """Меняет ссылку чата клана"""

        psql_cursor.execute("""
            UPDATE clans
            SET chat_link = %(chat_link)s
            WHERE clan_id = %(clan_id)s
        """, {
            "clan_id": clan_id,
            "chat_link": chat_link
        })


    @staticmethod
    def change_join_type(
            clan_id: int,
            join_type: ClanJoinType,
            psql_cursor: DictCursor
    ) -> None:
        """Меняет тип входа в клан"""

        psql_cursor.execute("""
            UPDATE clans
            SET join_type = %(join_type)s
            WHERE clan_id = %(clan_id)s
        """, {
            "clan_id": clan_id,
            "join_type": join_type.value
        })


    @staticmethod
    def change_join_barrier(
            clan_id: int,
            join_barrier: int,
            psql_cursor: DictCursor
    ) -> None:
        """Меняет барьер для входа"""

        psql_cursor.execute("""
            UPDATE clans
            SET join_barrier = %(join_barrier)s
            WHERE clan_id = %(clan_id)s
        """, {
            "clan_id": clan_id,
            "join_barrier": join_barrier
        })


    @staticmethod
    def switch_owner_notifications(
            clan_id: int,
            owner_notifications: bool,
            psql_cursor: DictCursor
    ) -> bool:
        """
            Переключает состояние отправки уведомление владельцу
            клана и возвращает новое состояние переключателя
        """

        switch = not owner_notifications

        psql_cursor.execute("""
            UPDATE clans
            SET owner_notifications = %(switch)s
            WHERE clan_id = %(clan_id)s
        """, {
            "switch": switch,
            "clan_id": clan_id
        })

        return switch


    @staticmethod
    def create_redis_key_for_accent_clan(
            *, user_id: int, clan_id: int
    ) -> str:
        """
            Создает ключ redis для подачи заявки на вступление в
            # redis_base_key:user_id:clan_id - Пользователь отправил клану
        """

        base_key = RedisKeys.APPLICATION_JOIN_CLAN.value
        return f"{base_key}:{user_id}:{clan_id}"


    @staticmethod
    def create_redis_key_for_accent_user(
            *, clan_id: int, user_id: int
    ) -> str:
        """
            Создает ключ redis для подачи заявки на вступление
            # redis_base_key:clan_id:user_id - Клан отправил пользователю
        """

        base_key = RedisKeys.APPLICATION_JOIN_CLAN.value
        return f"{base_key}:{clan_id}:{user_id}"


    @staticmethod
    def redis_add_application_join_clan(
            redis_key: str,
            redis_cursor: Redis
    ) -> None:
        """Добавляет заявку на вступление или принятия в клан"""

        redis_cursor.setex(
            name=redis_key,
            value=1,
            time=ClanSettings.DELETE_APPLICATION_CLAN
        )


    @staticmethod
    def redis_check_application_join_clan(
            redis_key: str,
            redis_cursor: Redis
    ) -> bool:
        """Проверяет заявку на приглашение или вступления в клан"""

        return bool(redis_cursor.get(redis_key))


    @staticmethod
    def redis_delete_application_join_clan(
        redis_key: str,
        redis_cursor: Redis
    ) -> None:
        """Удаляет заявку на приглашение или вступления"""

        redis_cursor.delete(redis_key)


    @staticmethod
    def check_length_clan_name(clan_name: str) -> bool:
        """Проверяет что имя клана подходит по длине"""

        len_clan_name = len(clan_name)

        return (
            len_clan_name > 0 and
            len_clan_name <= ClanSettings.MAX_CLAN_NAME
        )


    @staticmethod
    def is_name_available(
            clan_name: str,
            psql_cursor: DictCursor
    ) -> bool:
        """
            Проверяет что имя клана не занято
            Возвращает True если имя занято
        """

        psql_cursor.execute("""
            SELECT * FROM clans
            WHERE name = %(clan_name)s
        """, {
            "clan_name": clan_name
        })
        psql_response = psql_cursor.fetchone()

        return not bool(psql_response)


    @staticmethod
    def check_length_clan_tag(clan_tag: str) -> bool:
        """Проверяет что тег клана подходит по длине"""

        len_clan_tag = len(clan_tag)

        return (
            len_clan_tag > 0 and
            len_clan_tag <= ClanSettings.MAX_CLAN_TAG
        )


    @staticmethod
    def is_tag_available(
            clan_tag: str,
            psql_cursor: DictCursor
    ) -> bool:
        """Проверяет что тег клана не занято"""

        psql_cursor.execute("""
            SELECT * FROM clans
            WHERE tag = %(clan_tag)s
        """, {
            "clan_tag": clan_tag
        })
        psql_response = psql_cursor.fetchone()

        return not bool(psql_response)


    @staticmethod
    def is_clan_open(join_type: ClanJoinType) -> bool:
        """Проверяет что вход в клан открыт"""

        return join_type == ClanJoinType.OPEN


    @staticmethod
    def is_clan_closed(join_type: ClanJoinType) -> bool:
        """Проверять закрыт ли клан"""

        return join_type == ClanJoinType.CLOSED


    @staticmethod
    def is_have_free_place(count_members: int) -> bool:
        """Проверяет если ли свободные места в клане для вступления"""

        return count_members < ClanSettings.MAX_COUNT_MEMBERS


    @staticmethod
    def is_overcome_join_barrier(all_win: int, clan_barrier: int) -> bool:
        """Проверяет достаточно ли очков для входа в клан"""

        return all_win >= clan_barrier
