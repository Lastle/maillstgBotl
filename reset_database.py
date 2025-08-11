#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для сброса и пересоздания базы данных
"""

from database.models import Base, engine
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def reset_database():
    """Удаляет все таблицы и создает их заново"""
    try:
        logger.info("Удаление всех таблиц...")
        
        # Удаляем все таблицы
        Base.metadata.drop_all(bind=engine)
        
        logger.info("Создание таблиц заново...")
        
        # Создаем все таблицы
        Base.metadata.create_all(bind=engine)
        
        logger.info("✅ База данных успешно пересоздана!")
        
        # Проверяем созданные таблицы
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """))
            tables = [row[0] for row in result]
            logger.info(f"Созданные таблицы: {tables}")
            
            # Проверяем структуру таблицы night_mode
            result = conn.execute(text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'night_mode'
            """))
            columns = [(row[0], row[1]) for row in result]
            logger.info(f"Колонки таблицы night_mode: {columns}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка при пересоздании БД: {e}")
        raise

if __name__ == "__main__":
    reset_database()
