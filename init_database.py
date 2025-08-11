#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для инициализации базы данных
"""

from database.models import Base, engine, init_db
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_database():
    """Инициализирует базу данных с правильной структурой"""
    try:
        logger.info("Создание таблиц базы данных...")
        
        # Создаем все таблицы
        Base.metadata.create_all(bind=engine)
        
        logger.info("✅ База данных успешно инициализирована!")
        
        # Проверяем созданные таблицы
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """))
            tables = [row[0] for row in result]
            logger.info(f"Созданные таблицы: {tables}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка при инициализации БД: {e}")
        raise

if __name__ == "__main__":
    init_database()
