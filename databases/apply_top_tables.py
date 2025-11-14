#!/usr/bin/env python3
"""Скрипт для создания таблиц топов в базе данных"""

import sys
import os

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from databases.postgresql import get_postgresql_connection

def apply_sql_file(sql_file_path: str):
    """Применяет SQL файл к базе данных"""
    
    print(f"Читаем SQL файл: {sql_file_path}")
    with open(sql_file_path, 'r', encoding='utf-8') as f:
        sql_content = f.read()
    
    # Разделяем на команды, учитывая $$ блоки
    commands = []
    current_command = ""
    in_dollar_block = False
    dollar_tag = None
    
    i = 0
    while i < len(sql_content):
        char = sql_content[i]
        
        # Проверяем начало $$ блока
        if i < len(sql_content) - 1 and sql_content[i:i+2] == '$$':
            if not in_dollar_block:
                in_dollar_block = True
                # Находим тег после $$
                tag_start = i + 2
                tag_end = tag_start
                while tag_end < len(sql_content) and sql_content[tag_end] not in ['\n', ' ', '\t']:
                    tag_end += 1
                dollar_tag = sql_content[tag_start:tag_end] if tag_end > tag_start else ""
                current_command += '$$' + dollar_tag
                i += 2
                continue
            else:
                # Проверяем конец $$ блока
                if i + 1 < len(sql_content) and sql_content[i+1] == ';':
                    current_command += '$$'
                    commands.append(current_command.strip())
                    current_command = ""
                    in_dollar_block = False
                    dollar_tag = None
                    i += 2  # Пропускаем $$ и ;
                    continue
        
        current_command += char
        
        # Если не в $$ блоке, проверяем конец команды
        if not in_dollar_block and char == ';':
            if current_command.strip():
                commands.append(current_command.strip())
            current_command = ""
        
        i += 1
    
    # Добавляем последнюю команду если есть
    if current_command.strip():
        commands.append(current_command.strip())
    
    conn, cur = get_postgresql_connection()
    try:
        for i, command in enumerate(commands, 1):
            if command:
                print(f"Выполняем команду {i}/{len(commands)}...")
                try:
                    cur.execute(command)
                    print(f"✅ Команда {i} выполнена успешно")
                except Exception as e:
                    # Если таблица/функция уже существует - это нормально
                    error_str = str(e).lower()
                    if any(x in error_str for x in ["already exists", "duplicate", "cannot create"]):
                        print(f"⚠️ Команда {i}: {e} (пропускаем)")
                    else:
                        print(f"❌ Ошибка в команде {i}: {e}")
                        raise
        
        conn.commit()
        print("\n✅ Все команды выполнены успешно!")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Ошибка при выполнении SQL: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    sql_file = os.path.join(os.path.dirname(__file__), "create_top_tables.sql")
    if not os.path.exists(sql_file):
        print(f"❌ Файл {sql_file} не найден!")
        sys.exit(1)
    
    print("=" * 50)
    print("Создание таблиц для топов")
    print("=" * 50)
    
    try:
        apply_sql_file(sql_file)
        print("\n✅ Готово! Таблицы созданы.")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        sys.exit(1)

