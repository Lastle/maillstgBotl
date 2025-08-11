#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для проверки структуры базы данных
"""

from database.models import engine
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_db_structure():
    """Проверяет структуру базы данных"""
    try:
        with engine.connect() as conn:
            # Проверяем структуру таблицы accounts
            result = conn.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = 'accounts'
                ORDER BY ordinal_position
            """))
            columns = [(row[0], row[1], row[2]) for row in result]
            logger.info(f"Колонки таблицы accounts: {columns}")
            
            # Проверяем структуру таблицы night_mode
            result = conn.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = 'night_mode'
                ORDER BY ordinal_position
            """))
            columns = [(row[0], row[1], row[2]) for row in result]
            logger.info(f"Колонки таблицы night_mode: {columns}")
            
            # Проверяем структуру таблицы mailings
            result = conn.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = 'mailings'
                ORDER BY ordinal_position
            """))
            columns = [(row[0], row[1], row[2]) for row in result]
            logger.info(f"Колонки таблицы mailings: {columns}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке БД: {e}")
        raise

if __name__ == "__main__":
    check_db_structure()
