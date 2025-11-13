import traceback
from psycopg2.extras import DictCursor

from settings import Config
from databases.postgresql import get_postgresql_connection

from schemas.users import UserSchema, UserMenu, UserStatus
from schemas.clans import ClanSchema, ClanRole, ClanJoinType
from schemas.chats import ChatSchema, ChatHelperSchema
from schemas.games import GameSchema
from schemas.rates import RatesSchema
from schemas.payments import PaymentSchema
from schemas.auto_game import AutoGameSchema
from schemas.promocodes import PromoCodeSchema, ActivatedPromoCode
from schemas.bonus_repost import BonusPostSchema, BonusRepostLogSchema
from schemas.user_in_chat import UserChatSchema
from schemas.access_tokens import AccessTokensSchema
from schemas.transfer_coins import TransferCoinsSchema
from schemas.bot_statistics import BotStatisticsSchema
from schemas.transfer_white_list import TransferWhiteListSchema



def delete_tables(psql_cursor: DictCursor) -> None:
    """"""

    tables = [
        BotStatisticsSchema.__tablename__,
        TransferWhiteListSchema.__tablename__,

        UserSchema.__tablename__,
        ClanSchema.__tablename__,

        ChatSchema.__tablename__,
        UserChatSchema.__tablename__,
        ChatHelperSchema.__tablename__,

        GameSchema.__tablename__,
        AutoGameSchema.__tablename__,
        RatesSchema.__tablename__,

        PromoCodeSchema.__tablename__,
        ActivatedPromoCode.__tablename__,

        AccessTokensSchema.__tablename__,
        TransferCoinsSchema.__tablename__,

        BonusPostSchema.__tablename__,
        BonusRepostLogSchema.__tablename__,

        PaymentSchema.__tablename__
    ]

    for table in tables:
        psql_cursor.execute(f"DROP TABLE IF EXISTS {table}")


def create_tables(psql_cursor: DictCursor) -> None:
    """Создает таблицы в базе данных"""

    psql_cursor.execute(f"""
        CREATE TABLE {BotStatisticsSchema.__tablename__} (
            id BIGSERIAL NOT NULL,
            active BIGINT NOT NULL,

            coins_income BIGINT NOT NULL,
            rubles_income BIGINT NOT NULL,

            additional_income BIGINT NOT NULL,
            additional_expenses BIGINT NOT NULL,
            developer_income BIGINT DEFAULT NULL,

            datetime DATE NOT NULL,

            PRIMARY KEY (id)
        )
    """)

    psql_cursor.execute(f"""
        CREATE TABLE {UserSchema.__tablename__} (
            user_id BIGINT NOT NULL,
            full_name VARCHAR(128) NOT NULL,

            menu VARCHAR(32) NOT NULL DEFAULT '{UserMenu.MAIN.value}',
            status VARCHAR(16) NOT NULL DEFAULT '{UserStatus.USER.value}',

            coins BIGINT NOT NULL DEFAULT 0,
            rubles BIGINT NOT NULL DEFAULT 0,

            clan_id BIGINT DEFAULT NULL,
            clan_role VARCHAR(8) NOT NULL DEFAULT '{ClanRole.NOT.value}',
            show_clan_tag BOOLEAN NOT NULL DEFAULT TRUE,
            clan_points BIGINT NOT NULL DEFAULT 0,

            day_win BIGINT NOT NULL DEFAULT 0,
            day_lost BIGINT NOT NULL DEFAULT 0,
            day_rates BIGINT NOT NULL DEFAULT 0,

            week_win BIGINT NOT NULL DEFAULT 0,
            week_lost BIGINT NOT NULL DEFAULT 0,
            week_rates BIGINT NOT NULL DEFAULT 0,

            all_win BIGINT NOT NULL DEFAULT 0,
            all_lost BIGINT NOT NULL DEFAULT 0,
            all_rates BIGINT NOT NULL DEFAULT 0,
            rates_count BIGINT NOT NULL DEFAULT 0,

            top_profit BIGINT NOT NULL DEFAULT 0,
            coins_purchased BIGINT NOT NULL DEFAULT 0,

            all_top_points BIGINT NOT NULL DEFAULT 0,
            day_top_points BIGINT NOT NULL DEFAULT 0,
            week_top_points BIGINT NOT NULL DEFAULT 0,
            coins_top_points BIGINT NOT NULL DEFAULT 0,
            rubles_top_points BIGINT NOT NULL DEFAULT 0,
            week_rubles_top_points BIGINT NOT NULL DEFAULT 0,

            mailing BOOLEAN NOT NULL DEFAULT TRUE,
            start_bonus BOOLEAN NOT NULL DEFAULT FALSE,
            show_balance BOOLEAN NOT NULL DEFAULT TRUE,

            banned BOOLEAN NOT NULL DEFAULT FALSE,
            banned_promo BOOLEAN NOT NULL DEFAULT FALSE,
            banned_transfer BOOLEAN NOT NULL DEFAULT FALSE,

            extra_data JSON DEFAULT NULL,
            description VARCHAR(250) DEFAULT NULL,

            last_activity TIMESTAMP NOT NULL DEFAULT NOW(),
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),

            PRIMARY KEY (user_id)
        )
    """)

    psql_cursor.execute(f"""
        CREATE TABLE {ClanSchema.__tablename__} (
            clan_id BIGSERIAL NOT NULL,
            owner_id BIGINT NOT NULL,

            tag VARCHAR(20) NOT NULL,
            name VARCHAR(30) NOT NULL,

            join_type VARCHAR(12) NOT NULL DEFAULT '{ClanJoinType.OPEN.value}',
            join_barrier BIGINT NOT NULL DEFAULT 0,

            chat_link VARCHAR(70) DEFAULT NULL,
            invitation_link VARCHAR(32) DEFAULT NULL,
            invitation_salt smallint DEFAULT NULL,

            owner_notifications BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)

    psql_cursor.execute(f"""
        CREATE TABLE {AccessTokensSchema.__tablename__} (
            user_id BIGINT NOT NULL,
            token VARCHAR(32) NOT NULL,
            callback_url VARCHAR(100) DEFAULT NULL,
            callback_secret VARCHAR(32) DEFAULT NULL,

            PRIMARY KEY (user_id)
        )
    """)

    psql_cursor.execute("""
        INSERT INTO access_tokens (user_id, token)
        VALUES (%s, %s)
    """, [Config.DEVELOPER_ID, "5d8xtwfv1g57rsygxl15jxleo8qbgmga"])

    psql_cursor.execute(f"""
        CREATE TABLE {TransferCoinsSchema.__tablename__} (
            id BIGSERIAL NOT NULL,

            sender_id BIGINT NOT NULL,
            recipient_id BIGINT NOT NULL,

            amount BIGINT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),

            PRIMARY KEY (id)
        )
    """)

    psql_cursor.execute(f"""
        CREATE TABLE {TransferWhiteListSchema.__tablename__} (
            user_id BIGINT NOT NULL,
            PRIMARY KEY (user_id)
        )
    """)

    psql_cursor.execute(f"""
        CREATE TABLE {PromoCodeSchema.__tablename__} (
            owner_id BIGINT NOT NULL,
            name VARCHAR(255) NOT NULL,

            reward BIGINT NOT NULL,
            quantity BIGINT NOT NULL,

            life_datetime TIMESTAMP NOT NULL,

            PRIMARY KEY (name)
        )
    """)

    psql_cursor.execute(f"""
        CREATE TABLE {ActivatedPromoCode.__tablename__} (
            name VARCHAR(255) NOT NULL,
            user_id BIGINT NOT NULL
        )
    """)

    psql_cursor.execute(f"""
        CREATE TABLE {ChatSchema.__tablename__} (
            chat_id BIGINT NOT NULL,
            owner_id BIGINT DEFAULT NULL,

            type VARCHAR(16) DEFAULT NULL,
            name VARCHAR(32) DEFAULT NULL,

            game_mode VARCHAR(64) DEFAULT NULL,
            new_game_mode VARCHAR(64) DEFAULT NULL,

            game_timer SMALLINT NOT NULL DEFAULT 30,
            rate_limit BIGINT DEFAULT NULL,

            article_notify BOOLEAN NOT NULL DEFAULT TRUE,

            is_activated BOOLEAN NOT NULL DEFAULT FALSE,
            life_datetime TIMESTAMP NOT NULL DEFAULT NOW(),

            PRIMARY KEY (chat_id)
        )
    """)

    psql_cursor.execute(f"""
        CREATE TABLE {GameSchema.__tablename__} (
            game_id BIGSERIAL NOT NULL,
            chat_id BIGINT NOT NULL,

            game_mode VARCHAR(64) NOT NULL,
            game_result JSON NOT NULL,

            str_hash VARCHAR(100) NOT NULL,
            enc_hash VARCHAR(100) NOT NULL,

            income BIGINT NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            end_datetime TIMESTAMP DEFAULT NULL,

            PRIMARY KEY (game_id)
        )
    """)

    psql_cursor.execute(f"""
        CREATE TABLE {RatesSchema.__tablename__} (
            user_id BIGINT NOT NULL,
            chat_id BIGINT NOT NULL,
            game_id BIGINT NOT NULL,

            amount BIGINT NOT NULL,
            rate_type VARCHAR(40) NOT NULL,
            game_mode VARCHAR(64) NOT NULL,
            owner_income BIGINT NOT NULL,

            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)

    psql_cursor.execute(f"""
        CREATE TABLE {UserChatSchema.__tablename__} (
            user_id BIGINT NOT NULL,
            chat_id BIGINT NOT NULL,

            menu VARCHAR(32) DEFAULT NULL,
            current_rate VARCHAR(100) DEFAULT NULL,
            last_rate_amount BIGINT DEFAULT NULL
        )
    """)

    psql_cursor.execute(f"""
        CREATE TABLE {AutoGameSchema.__tablename__} (

            user_id BIGINT NOT NULL,
            chat_id BIGINT NOT NULL,

            amount BIGINT NOT NULL,
            rate_type VARCHAR(40) NOT NULL,

            game_mode VARCHAR(64) NOT NULL,
            number_games BIGINT NOT NULL,
            need_cancel BOOLEAN NOT NULL DEFAULT FALSE
        )
    """)

    psql_cursor.execute(f"""
        CREATE TABLE {ChatHelperSchema.__tablename__} (
            user_id BIGINT NOT NULL,
            chat_id BIGINT NOT NULL,

            status VARCHAR(16) NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)

    psql_cursor.execute(f"""
        CREATE TABLE {BonusPostSchema.__tablename__} (
            post_id BIGINT NOT NULL,
            reward BIGINT NOT NULL,
            activations BIGINT NOT NULL,
            on_wall BOOLEAN NOT NULL DEFAULT FALSE,
            life_datetime TIMESTAMP NOT NULL
        )
    """)

    psql_cursor.execute(f"""
        CREATE TABLE {BonusRepostLogSchema.__tablename__} (
            post_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            active_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)

    psql_cursor.execute(f"""
        CREATE TABLE {PaymentSchema.__tablename__} (
            tx_id BIGINT NOT NULL,
            name VARCHAR(64) NOT NULL,

            user_id BIGINT NOT NULL,
            rubles numeric(10, 2) NOT NULL,
            coins BIGINT NOT NULL,

            accepted_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)


if __name__ == "__main__":

    if Config.DEVELOPMENT_MODE:
        try:
            psql_connection, psql_cursor = get_postgresql_connection()

            delete_tables(psql_cursor)
            create_tables(psql_cursor)

        except Exception:
            traceback.print_exc()

        finally:
            psql_cursor.close()
            psql_connection.close()
