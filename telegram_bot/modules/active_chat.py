from psycopg2.extras import DictCursor

from games.base import BaseGameModel
from schemas.users import UserSchema
from schemas.chats import ChatSchema, ChatHelperStatus
from schemas.games import Games

from services.chats import ChatsService
from services.user_in_chat import UserChatService

from modules.additional import format_number
from modules.databases.chats import get_chat_data
from modules.telegram.users import get_user_id


def handler_change_chat_name(
        user_data: UserSchema,
        chat_data: ChatSchema,
        chat_name: str,
        psql_cursor: DictCursor
) -> str:
    """Обрабатывает смену имени чата"""

    if len(chat_name) > 50:
        return "❌ Имя чата должно содержать не более 50 символов"

    ChatsService.update_chat_name(chat_data.chat_id, chat_name, psql_cursor)
    return f"Новое название чата: {chat_name}"


def handler_change_game_mode(
        user_data: UserSchema,
        chat_data: ChatSchema,
        game_mode: Games,
        psql_cursor: DictCursor
) -> tuple[str, str]:
    """Обрабатывает смену игрового режима"""

    # Обновляем режим игры в чате
    ChatsService.update_game_mode(chat_data.chat_id, game_mode, psql_cursor)
    
    # Создаем новую игру для нового режима
    game_model = BaseGameModel.GAMES_MODEL[game_mode]
    game_model.create_game(chat_data.chat_id, psql_cursor)
    
    # Получаем ID новой игры
    psql_cursor.execute(
        "SELECT game_id FROM games WHERE chat_id = %s AND game_mode = %s ORDER BY game_id DESC LIMIT 1",
        [chat_data.chat_id, game_mode.value]
    )
    new_game = psql_cursor.fetchone()
    if new_game:
        new_game_id = new_game["game_id"]
        # Обновляем game_id в чате
        psql_cursor.execute(
            "UPDATE chats SET game_id = %s WHERE chat_id = %s",
            [new_game_id, chat_data.chat_id]
        )
    
    # Получаем новую игру и клавиатуру
    psql_cursor.execute("SELECT * FROM games WHERE game_id = %s", [new_game_id])
    game_data_dict = psql_cursor.fetchone()
    import json
    game_data_dict["game_result"] = json.loads(game_data_dict["game_result"])
    
    # Возвращаем новую клавиатуру
    new_keyboard = game_model.get_game_keyboard(game_data_dict["game_result"])
    
    return f"✅ Игровой режим изменен на {game_mode.value}", new_keyboard


def handler_change_game_timer(
        user_data: UserSchema,
        chat_data: ChatSchema,
        new_timer: str,
        psql_cursor: DictCursor
) -> str:
    """Обрабатывает смену таймера игры"""

    try:
        timer = int(new_timer)
        if timer < 5 or timer > 300:
            return "❌ Таймер должен быть от 5 до 300 секунд"

        ChatsService.update_game_timer(chat_data.chat_id, timer, psql_cursor)
        return f"✅ Таймер игры установлен на {timer} секунд"
    except ValueError:
        return "❌ Введите число"


async def handler_add_helper(
        user_data: UserSchema,
        chat_data: ChatSchema,
        helper_link: str,
        psql_cursor: DictCursor
) -> str:
    """Обрабатывает добавление помощника"""

    helper_id = await get_user_id(helper_link)
    if helper_id is None:
        return "❌ Пользователь не найден"

    ChatsService.add_helper(chat_data.chat_id, helper_id, ChatHelperStatus.BASE, psql_cursor)
    return f"✅ Помощник добавлен"


async def handler_del_helper(
        user_data: UserSchema,
        chat_data: ChatSchema,
        helper_link: str,
        psql_cursor: DictCursor
) -> str:
    """Обрабатывает удаление помощника"""

    helper_id = await get_user_id(helper_link)
    if helper_id is None:
        return "❌ Пользователь не найден"

    ChatsService.del_helper(chat_data.chat_id, helper_id, psql_cursor)
    return f"✅ Помощник удален"


def get_user_balance_message(user_data: UserSchema, psql_cursor: DictCursor | None = None) -> str:
    """Возвращает сообщение с балансом пользователя"""
    
    # Если передан psql_cursor, загружаем актуальный баланс из БД
    if psql_cursor:
        from modules.databases.users import get_user_data
        fresh_user_data = get_user_data(user_data.user_id, psql_cursor)
        if fresh_user_data:
            user_data = fresh_user_data
    
    return f"Ваш баланс: {format_number(user_data.coins)} WC"


async def handler_change_chat_owner(
        user_data: UserSchema,
        chat_data: ChatSchema,
        new_owner_link: str,
        psql_cursor: DictCursor
) -> str:
    """Обрабатывает смену владельца чата"""

    new_owner_id = await get_user_id(new_owner_link)
    if new_owner_id is None:
        return "❌ Пользователь не найден"

    ChatsService.update_owner_id(chat_data.chat_id, new_owner_id, psql_cursor)
    return f"✅ Владелец чата изменен"


def handler_article_notify(
        user_data: UserSchema,
        chat_data: ChatSchema,
        psql_cursor: DictCursor
) -> str:
    """Обрабатывает включение/выключение уведомлений о статьях"""

    new_value = not chat_data.article_notify
    ChatsService.update_article_notify(chat_data.chat_id, new_value, psql_cursor)
    status = "включены" if new_value else "выключены"
    return f"✅ Уведомления о статьях {status}"

