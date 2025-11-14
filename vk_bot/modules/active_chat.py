from psycopg2.extras import DictCursor

from games.base import BaseGameModel

from schemas.users import UserSchema, UserStatus
from schemas.chats import ChatSchema
from schemas.games import Games

from services.chats import ChatsService
from services.security import SecurityService

from modules.additional import convert_number, format_number
from modules.databases.users import get_user_data
from modules.databases.chats import get_chat_data, get_game_data
from modules.vkontakte.users import get_user_id

from vk_bot.template_messages import PATTERN_BANNED_SYMBOLS, USER_NOT_FOUND, \
    ACCESS_FOR_CHAT_OWNER, ACCESS_FOR_CHAT_OWNER_AND_HELPERS, THIS_NOT_LINK


def get_user_balance_message(user_data: UserSchema) -> str:
    """Возвращает сообщение о балансе пользователя"""

    user_name = user_data.vk_name
    user_coins = user_data.coins
    user_rubles = user_data.rubles

    if user_coins > 0:
        response = f"{user_name}, твой баланс: {format_number(user_coins)} WC"
    else:
        response = f"{user_name}, на твоем балансе нет коинов..."

    if user_rubles > 0:
        response += f"\n{user_name}, твой баланс: {format_number(user_rubles)} монеток"

    return response


def handler_change_chat_name(
        user_data: UserSchema,
        chat_data: ChatSchema,
        chat_name: str,
        psql_cursor: DictCursor
) -> str:
    """Обрабатывает сообщения смены названия чата"""

    if not (
        user_data.user_id == chat_data.owner_id or
        user_data.status == UserStatus.ADMIN
    ):
        return ACCESS_FOR_CHAT_OWNER

    banned_symbols = SecurityService.check_banned_symbols(chat_name)

    if len(banned_symbols) > 0:
        banned_symbols = ", ".join(banned_symbols)
        return PATTERN_BANNED_SYMBOLS.format(banned_symbols)

    if not 0 < len(chat_name) <= 12:
        return "Максимальная длина названия чата 12 символов"

    ChatsService.update_chat_name(chat_data.chat_id, chat_name, psql_cursor)
    return f"Новое название чата: {chat_name}"


def handler_change_game_mode(
        user_data: UserSchema,
        chat_data: ChatSchema,
        game_mode: Games,
        psql_cursor: DictCursor
) -> tuple[str, str | None]:
    """Обрабатывает смену игрового режима"""

    user_id = user_data.user_id
    chat_id = chat_data.chat_id

    if not (
        user_id == chat_data.owner_id or
        user_data.status == UserStatus.ADMIN or
        ChatsService.is_helper(user_id, chat_id, psql_cursor)
    ):
        return ACCESS_FOR_CHAT_OWNER_AND_HELPERS, None

    chat_id = chat_data.chat_id

    psql_cursor.execute("""
        SELECT * FROM auto_games
        WHERE chat_id = %s
    """, [chat_id])
    found_auto_games = bool(psql_cursor.fetchall())

    if found_auto_games:
        return "Нельзя сменить игровой режим пока идут авто игры", None

    if chat_data.game_mode == game_mode:
        return "Данный режим уже установлен", None

    chat_data = get_chat_data(chat_id, psql_cursor)
    game_id = chat_data.game_id
    game_data = get_game_data(game_id, psql_cursor)

    sql_data = {
        "game_mode": game_mode.value,
        "chat_id": chat_id
    }

    if game_data.time_left is None:
        game_result = BaseGameModel.create_new_game(chat_id, game_mode, psql_cursor)
        BaseGameModel.clear_current_rates(chat_id, psql_cursor)
        psql_cursor.execute("""
            UPDATE chats SET game_mode = %(game_mode)s
            WHERE chat_id = %(chat_id)s
        """, sql_data)
        psql_cursor.execute("DELETE FROM games WHERE game_id = %s", [game_id])

        keyboard = BaseGameModel.GAMES_MODEL[game_mode].get_game_keyboard(game_result)
        return f"Режим игры изменен на {game_mode.name}", keyboard

    else:
        psql_cursor.execute("""
            UPDATE chats SET new_game_mode = %(game_mode)s
            WHERE chat_id = %(chat_id)s
        """, sql_data)
        return "Игровой режим будет изменен по окончании текущей игры", None


def handler_change_game_timer(
        user_data: UserSchema,
        chat_data: ChatSchema,
        timer: str,
        psql_cursor: DictCursor
) -> str:
    """Обрабатывает смену игрового таймера"""

    user_id = user_data.user_id
    chat_id = chat_data.chat_id

    if not (
        user_id == chat_data.owner_id or
        user_data.status == UserStatus.ADMIN or
        ChatsService.is_helper(user_id, chat_id, psql_cursor)
    ):
        return ACCESS_FOR_CHAT_OWNER_AND_HELPERS

    timer = convert_number(timer)

    if timer is None:
        return "Это не похоже на секунды"

    if user_data.status != UserStatus.ADMIN and not 4 <= timer <= 90:
        return "Диапазон игрового таймера от 4 до 90 секунд"

    timer = min(max(timer, 0), 32_767)
    psql_cursor.execute("""
        UPDATE chats SET game_timer = %(timer)s
        WHERE chat_id = %(chat_id)s
    """, {
        "timer": timer,
        "chat_id": chat_data.chat_id
    })

    return f"Время игрового таймера изменено на {timer} сек"


async def handler_add_helper(
        user_data: UserSchema,
        chat_data: ChatSchema,
        helper_link: str,
        psql_cursor: DictCursor
) -> str:
    """Обработчик добавления помощника чата"""

    user_id = user_data.user_id
    chat_id = chat_data.chat_id

    if not (
        user_id == chat_data.owner_id or
        user_data.status == UserStatus.ADMIN
    ):
        return ACCESS_FOR_CHAT_OWNER

    search_user_id = await get_user_id(helper_link)
    search_user_data = get_user_data(search_user_id, psql_cursor)

    if search_user_id is None or search_user_data is None:
        return USER_NOT_FOUND

    if ChatsService.is_helper(search_user_id, chat_id, psql_cursor):
        return "Данный пользователь уже является помощником"

    ChatsService.create_helper(search_user_id, chat_id, psql_cursor)
    return f"{search_user_data.vk_name} добавлен в помощники чата"


async def handler_del_helper(
        user_data: UserSchema,
        chat_data: ChatSchema,
        helper_link: str,
        psql_cursor: DictCursor
) -> str:
    """Обработчик удаления помощника чата"""

    user_id = user_data.user_id
    chat_id = chat_data.chat_id

    if not (
        user_id == chat_data.owner_id or
        user_data.status == UserStatus.ADMIN
    ):
        return ACCESS_FOR_CHAT_OWNER

    search_user_id = await get_user_id(helper_link)
    search_user_data = get_user_data(search_user_id, psql_cursor)

    if search_user_id is None or search_user_data is None:
        return USER_NOT_FOUND

    if not ChatsService.is_helper(search_user_id, chat_id, psql_cursor):
        return "Данного пользователя нет в помощниках"

    ChatsService.delete_helper(search_user_id, chat_id, psql_cursor)
    return f"{search_user_data.vk_name} удален из помощников чата"


async def handler_change_chat_owner(
        user_data: UserSchema,
        chat_data: ChatSchema,
        new_owner: str,
        psql_cursor: DictCursor
) -> str:
    """Меняет владельца чата"""

    if not (
        user_data.status == UserStatus.ADMIN or
        chat_data.owner_id == user_data.user_id
    ):
        return "Сменить владельца беседы может только создатель беседы"

    new_owner_id = await get_user_id(new_owner)
    if new_owner_id is None:
        return THIS_NOT_LINK

    new_owner_data = get_user_data(new_owner_id, psql_cursor)
    if new_owner_data is None:
        return USER_NOT_FOUND

    psql_cursor.execute("""
        UPDATE chats
        SET owner_id = %(new_owner_id)s
        WHERE chat_id = %(chat_id)s
    """, {
        "new_owner_id": new_owner_id,
        "chat_id": chat_data.chat_id
    })

    return f"Новый {UserSchema.format_vk_name(new_owner_id, 'владелец')} беседы"


def handler_article_notify(
        user_data: UserSchema,
        chat_data: ChatSchema,
        psql_cursor: DictCursor
) -> str:
    """переключает отправку уведомлений статей"""

    user_id = user_data.user_id
    chat_id = chat_data.chat_id

    if not (
        user_id == chat_data.owner_id or
        user_data.status == UserStatus.ADMIN or
        ChatsService.is_helper(user_id, chat_id, psql_cursor)
    ):
        return ACCESS_FOR_CHAT_OWNER_AND_HELPERS

    switch = not chat_data.article_notify
    psql_cursor.execute("""
        UPDATE chats
        SET article_notify = %(switch)s
        WHERE chat_id = %(chat_id)s
    """, {
        "switch": switch,
        "chat_id": chat_id
    })

    return f"Показ статей после игр {'включен' if switch else 'выключен'}"
