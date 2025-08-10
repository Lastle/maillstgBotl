#!/usr/bin/env python3
"""
Скрипт миграции базы данных PostgreSQL для добавления полей api_id и api_hash в таблицу accounts
"""

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Параметры подключения (замени на свои)
DB_NAME = "tgmails"
DB_USER = "postgres"
DB_PASSWORD = "1245"
DB_HOST = "localhost"
DB_PORT = 5432

def migrate_database():
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

        # Проверяем наличие столбцов
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name='accounts' AND column_name IN ('api_id', 'api_hash')
        """)
        existing_columns = {row[0] for row in cursor.fetchall()}

        if 'api_id' in existing_columns and 'api_hash' in existing_columns:
            print("✅ Поля api_id и api_hash уже существуют!")
            cursor.close()
            conn.close()
            return True

        print("🔄 Начинаю миграцию...")

        if 'api_id' not in existing_columns:
            cursor.execute(sql.SQL("ALTER TABLE accounts ADD COLUMN api_id INTEGER DEFAULT 0"))
            print("✅ Добавлено поле api_id")

        if 'api_hash' not in existing_columns:
            cursor.execute(sql.SQL("ALTER TABLE accounts ADD COLUMN api_hash TEXT DEFAULT ''"))
            print("✅ Добавлено поле api_hash")

        # Обновляем существующие записи, если вдруг null
        cursor.execute("UPDATE accounts SET api_id = 0 WHERE api_id IS NULL")
        cursor.execute("UPDATE accounts SET api_hash = '' WHERE api_hash IS NULL")

        cursor.close()
        conn.close()

        print("✅ Миграция завершена успешно!")
        print("⚠️  ВАЖНО: Существующие аккаунты нужно будет переавторизовать с новыми API credentials!")

        return True

    except Exception as e:
        print(f"❌ Ошибка при миграции: {e}")
        return False

if __name__ == "__main__":
    migrate_database()
