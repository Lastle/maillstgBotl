#!/usr/bin/env python3
"""
Скрипт миграции базы данных PostgreSQL для изменения поля enabled в таблице night_mode с String на Boolean
"""

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sys

# Параметры подключения (замени на свои)
DB_NAME = "tgmaill"
DB_USER = "postgres"
DB_PASSWORD = "1463"
DB_HOST = "localhost"
DB_PORT = 5432

def migrate_night_mode():
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        # Проверяем тип столбца enabled
        cursor.execute("""
            SELECT data_type FROM information_schema.columns
            WHERE table_name='night_mode' AND column_name='enabled'
        """)
        result = cursor.fetchone()
        
        if result and result[0] == 'boolean':
            print("Поле enabled уже имеет тип boolean!")
            cursor.close()
            conn.close()
            return True
        
        print("Начинаю миграцию поля enabled в таблице night_mode...")
        
        # Добавляем новое поле с типом boolean
        cursor.execute(sql.SQL("ALTER TABLE night_mode ADD COLUMN enabled_bool BOOLEAN DEFAULT FALSE"))
        print("Добавлено поле enabled_bool с типом boolean")
        
        # Переносим данные из старого поля в новое
        cursor.execute("""
            UPDATE night_mode 
            SET enabled_bool = CASE 
                WHEN enabled = 'true' THEN TRUE 
                WHEN enabled = 'false' THEN FALSE 
                ELSE FALSE 
            END
        """)
        print("Данные перенесены из поля enabled в enabled_bool")
        
        # Удаляем старое поле
        cursor.execute(sql.SQL("ALTER TABLE night_mode DROP COLUMN enabled"))
        print("Удалено старое поле enabled")
        
        # Переименовываем новое поле
        cursor.execute(sql.SQL("ALTER TABLE night_mode RENAME COLUMN enabled_bool TO enabled"))
        print("Поле enabled_bool переименовано в enabled")
        
        cursor.close()
        conn.close()
        print("Миграция завершена успешно!")
        return True
        
    except Exception as e:
        print(f"Ошибка миграции: {e}")
        return False

if __name__ == "__main__":
    migrate_night_mode()
