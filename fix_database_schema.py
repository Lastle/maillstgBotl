#!/usr/bin/env python3
"""
Скрипт для исправления схемы БД PostgreSQL
Исправляет проблему с полем group_id в таблице mailings
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from database.models import Base, Account, Group, Mailing, MessageLog, MailingHistory, NightMode
from config import SYNC_DATABASE_URL

def fix_database_schema():
    """Исправляет схему БД для корректной работы с group_id"""
    print("Исправление схемы БД PostgreSQL...")
    
    engine = create_engine(SYNC_DATABASE_URL, pool_pre_ping=True)
    
    try:
        with engine.connect() as conn:
            # Проверяем существующую структуру таблицы mailings
            print("Проверка текущей структуры таблицы mailings...")
            result = conn.execute(text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'mailings' 
                ORDER BY ordinal_position;
            """))
            
            columns = result.fetchall()
            print("Текущие столбцы в mailings:")
            for col in columns:
                print(f"  - {col[0]} ({col[1]})")
            
            # Проверяем есть ли проблемное поле
            column_names = [col[0] for col in columns]
            
            if 'groupid' in column_names and 'group_id' not in column_names:
                print("НАЙДЕНА ПРОБЛЕМА: поле называется 'groupid' вместо 'group_id'")
                print("Переименовываем столбец...")
                
                # Переименовываем столбец
                conn.execute(text("ALTER TABLE mailings RENAME COLUMN groupid TO group_id;"))
                conn.commit()
                print("УСПЕШНО: Столбец переименован: groupid -> group_id")
                
            elif 'group_id' in column_names:
                print("УСПЕШНО: Поле group_id уже существует корректно")
                
            else:
                print("ВНИМАНИЕ: Поле group_id отсутствует, добавляем...")
                conn.execute(text("""
                    ALTER TABLE mailings 
                    ADD COLUMN group_id INTEGER REFERENCES groups(id);
                """))
                conn.commit()
                print("УСПЕШНО: Поле group_id добавлено")
            
            # Проверяем финальную структуру
            print("\nФинальная структура таблицы mailings:")
            result = conn.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = 'mailings' 
                ORDER BY ordinal_position;
            """))
            
            for col in result.fetchall():
                nullable = "NULL" if col[2] == "YES" else "NOT NULL"
                print(f"  - {col[0]} ({col[1]}) {nullable}")
                
    except Exception as e:
        print(f"ОШИБКА при исправлении схемы БД: {e}")
        return False
        
    print("УСПЕШНО: Схема БД исправлена!")
    return True

def verify_database_connection():
    """Проверяет подключение к БД"""
    print("Проверка подключения к PostgreSQL...")
    
    engine = create_engine(SYNC_DATABASE_URL, pool_pre_ping=True)
    
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            version = result.fetchone()[0]
            print(f"УСПЕШНО: Подключение установлено! PostgreSQL: {version}")
            return True
    except Exception as e:
        print(f"ОШИБКА подключения к БД: {e}")
        print(f"URL: {SYNC_DATABASE_URL}")
        return False

if __name__ == "__main__":
    print("Запуск исправления схемы БД...")
    
    if not verify_database_connection():
        print("ОШИБКА: Не удалось подключиться к БД. Проверьте настройки в .env")
        sys.exit(1)
    
    if fix_database_schema():
        print("ЗАВЕРШЕНО: Исправление схемы БД выполнено успешно!")
    else:
        print("ОШИБКА: Не удалось исправить схему БД")
        sys.exit(1)
