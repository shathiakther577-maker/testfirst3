#!/usr/bin/env python3
"""Скрипт для проверки существования всех необходимых таблиц в базе данных"""
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from databases.postgresql import get_postgresql_connection
from schemas.bot_statistics import BotStatisticsSchema
from schemas.transfer_white_list import TransferWhiteListSchema
from schemas.users import UserSchema
from schemas.clans import ClanSchema
from schemas.chats import ChatSchema, UserChatSchema, ChatHelperSchema
from schemas.games import GameSchema
from schemas.rates import RatesSchema
from schemas.payments import PaymentSchema
from schemas.auto_game import AutoGameSchema
from schemas.promocodes import PromoCodeSchema, ActivatedPromoCode
from schemas.access_tokens import AccessTokensSchema
from schemas.transfer_coins import TransferCoinsSchema
from schemas.bonus_repost import BonusPostSchema, BonusRepostLogSchema
from schemas.bonus_subscription import BonusSubscriptionSchema, BonusSubscriptionLogSchema


def check_table_exists(table_name: str, psql_cursor) -> bool:
    """Проверяет существование таблицы"""
    psql_cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = %(table_name)s
        )
    """, {"table_name": table_name})
    return psql_cursor.fetchone()[0]


def check_all_tables() -> tuple[list[str], list[str]]:
    """Проверяет все необходимые таблицы и возвращает списки существующих и отсутствующих"""
    
    # Список всех таблиц из raise_database.py
    required_tables = [
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
        BonusSubscriptionSchema.__tablename__,
        BonusSubscriptionLogSchema.__tablename__,
        PaymentSchema.__tablename__,
    ]
    
    psql_connection, psql_cursor = get_postgresql_connection()
    
    existing_tables = []
    missing_tables = []
    
    try:
        for table_name in required_tables:
            if check_table_exists(table_name, psql_cursor):
                existing_tables.append(table_name)
                print(f"✅ Таблица {table_name} существует")
            else:
                missing_tables.append(table_name)
                print(f"❌ Таблица {table_name} отсутствует")
    
    finally:
        psql_cursor.close()
        psql_connection.close()
    
    return existing_tables, missing_tables


def check_constraints(psql_cursor) -> bool:
    """Проверяет наличие CHECK constraint для coins >= 0"""
    psql_cursor.execute("""
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_schema = 'public'
        AND table_name = 'users'
        AND constraint_type = 'CHECK'
        AND constraint_name LIKE '%coins%'
    """)
    return len(psql_cursor.fetchall()) > 0


if __name__ == "__main__":
    print("=" * 60)
    print("Проверка таблиц базы данных")
    print("=" * 60)
    
    existing, missing = check_all_tables()
    
    print("\n" + "=" * 60)
    print(f"Всего таблиц: {len(existing) + len(missing)}")
    print(f"Существует: {len(existing)}")
    print(f"Отсутствует: {len(missing)}")
    print("=" * 60)
    
    if missing:
        print("\n⚠️  Отсутствующие таблицы:")
        for table in missing:
            print(f"  - {table}")
        print("\nЗапустите raise_database.py для создания недостающих таблиц")
        sys.exit(1)
    else:
        print("\n✅ Все таблицы существуют!")
    
    # Проверяем constraint для coins
    psql_connection, psql_cursor = get_postgresql_connection()
    try:
        has_constraint = check_constraints(psql_cursor)
        if has_constraint:
            print("✅ CHECK constraint для coins >= 0 существует")
        else:
            print("⚠️  CHECK constraint для coins >= 0 отсутствует")
    finally:
        psql_cursor.close()
        psql_connection.close()

