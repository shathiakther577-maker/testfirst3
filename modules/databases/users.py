import json
from pydantic import BaseModel
from psycopg2.extras import DictCursor

from settings import Config

from schemas.users import UserSchema, UserMenu


def get_user_data(
        user_id: int,
        psql_cursor: DictCursor
) -> UserSchema | None:
    """Возвращает данные пользователя из базы данных"""

    if user_id is not None:
        psql_cursor.execute("SELECT * FROM users WHERE user_id = %(user_id)s", {"user_id": user_id})
        psql_response = psql_cursor.fetchone()

        if psql_response is not None and psql_response["extra_data"] is not None:
            psql_response["extra_data"] = json.loads(psql_response["extra_data"])

        user_data = UserSchema(**psql_response) if psql_response else None

        if user_data is not None:

            prefix = user_data.user_prefix
            user_data.full_name = f"{prefix}{user_data.full_name}{prefix}"

            if user_data.show_clan_tag and user_data.clan_id is not None:
                psql_cursor.execute("""
                    SELECT tag FROM clans
                    WHERE clan_id = %(clan_id)s
                """, {
                    "clan_id": user_data.clan_id
                })
                psql_response = psql_cursor.fetchone()
                user_data.full_name = f"({psql_response['tag']}) {user_data.full_name}"

        return user_data

    return None


def register_user(
        user_id: int,
        full_name: str,
        psql_cursor: DictCursor
) -> UserSchema:
    """Добавляет пользователя в базу данных"""

    psql_cursor.execute("""
        INSERT INTO users (user_id, full_name)
        VALUES (%(user_id)s, %(full_name)s)
        RETURNING *
    """, {
        "user_id": user_id,
        "full_name": full_name,
    })
    user_data = UserSchema(**psql_cursor.fetchone())

    return user_data


def update_user_menu(
        user_id: int,
        menu: UserMenu,
        psql_cursor: DictCursor
) -> None:
    """Обновляет меню пользователя"""

    psql_cursor.execute("""
        UPDATE users SET menu = %(menu)s
        WHERE user_id = %(user_id)s
    """, {
        "menu": menu.value,
        "user_id": user_id
    })


def update_user_extra_data(
        user_id: int,
        extra_data: BaseModel | None,
        psql_cursor: DictCursor
) -> None:
    """Обновляет дополнительные данные пользователя"""

    psql_cursor.execute("""
        UPDATE users
        SET extra_data = %(extra_data)s
        WHERE user_id = %(user_id)s
    """, {
        "extra_data": json.dumps(extra_data.json()) if extra_data else None,
        "user_id": user_id
    })


def set_coins(
        user_id: int,
        amount: int,
        psql_cursor: DictCursor
) -> None:
    """Устанавливает баланс coins"""

    psql_cursor.execute("""
        UPDATE users
        SET coins = %(amount)s
        WHERE user_id = %(user_id)s
    """, {
        "amount": amount,
        "user_id": user_id
    })


def take_coins(
        user_id: int,
        amount: int,
        psql_cursor: DictCursor
) -> None:
    """Списывает coins у пользователя"""

    psql_cursor.execute("""
        UPDATE users
        SET coins = coins - %(amount)s
        WHERE user_id = %(user_id)s
    """, {
        "amount": amount,
        "user_id": user_id
    })


def give_coins(
        user_id: int,
        amount: int,
        psql_cursor: DictCursor
) -> None:
    """Выдает coins пользователю"""

    psql_cursor.execute("""
        UPDATE users
        SET coins = coins + %(amount)s
        WHERE user_id = %(user_id)s
    """, {
        "amount": amount,
        "user_id": user_id
    })


def get_user_name(
        user_id: int,
        psql_cursor: DictCursor
) -> str | None:
    """Возвращает имя пользователя из базы данных"""

    psql_cursor.execute("""
        SELECT full_name FROM users
        WHERE user_id = %(user_id)s
    """, {
        "user_id": user_id
    })
    psql_response = psql_cursor.fetchone()

    return psql_response["full_name"] if psql_response is not None else None


def update_user_name(
        user_id: int,
        name: str,
        psql_cursor: DictCursor
) -> None:
    """Обновляет (полное имя) и (имя) пользователя"""

    psql_cursor.execute("""
        UPDATE users
        SET full_name = %(name)s
        WHERE user_id = %(user_id)s
    """, {
        "name": name,
        "user_id": user_id
    })


def reward_user_top(
        user_id: int,
        reward: int,
        psql_cursor: DictCursor
) -> None:
    """Награждает пользователя за топ"""

    psql_cursor.execute("""
        UPDATE users
        SET coins = coins + %(reward)s,
            top_profit = top_profit + %(reward)s
        WHERE user_id = %(user_id)s
    """, {
        "reward": reward,
        "user_id": user_id
    })


def reward_users_rubles_top(
        user_id: int,
        reward: int,
        psql_cursor: DictCursor
) -> None:
    """Награждает пользователя за топ в рублях"""

    psql_cursor.execute("""
        UPDATE users
        SET rubles = rubles + %(reward)s,
            top_profit = top_profit + %(top_profit)s
        WHERE user_id = %(user_id)s
    """, {
        "reward": reward,
        "top_profit": round(reward / Config.EXCHANGE_RUBLES_COINS * 1_000),
        "user_id": user_id
    })


def update_users_last_activity(
        user_id: int,
        psql_cursor: DictCursor
) -> None:
    """Обновляет время последней активности пользователя"""

    try:
        psql_cursor.execute("""
            UPDATE users
            SET last_activity = NOW()
            WHERE user_id = %(user_id)s
        """, {
            "user_id": user_id
        })
    except:
        pass


def update_free_nick_change(
        user_id: int,
        change: bool,
        psql_cursor: DictCursor
) -> None:
    """Выдает или забирает бесплатно смену никнейма"""

    psql_cursor.execute("""
        UPDATE users
        SET free_nick_change = %(change)s
        WHERE user_id = %(user_id)s
    """, {
        "change": change,
        "user_id": user_id
    })
