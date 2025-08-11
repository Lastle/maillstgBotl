#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для импорта всех существующих сессий в базу данных
"""

import os
import asyncio
from telethon import TelegramClient
from database.models import Account
from database.database import next_get_db
from config import TELEGRAM_API_ID, TELEGRAM_API_HASH
import logging

logging.basicConfig(level=logging.INFO, encoding='utf-8')
logger = logging.getLogger(__name__)

async def import_session_to_db(session_file):
    """Импортирует сессию в базу данных"""
    session_name = session_file.replace('.session', '')
    
    try:
        # Создаем клиент с существующей сессией
        client = TelegramClient(session_name, TELEGRAM_API_ID, TELEGRAM_API_HASH)
        
        await client.connect()
        
        if await client.is_user_authorized():
            # Получаем информацию о пользователе
            me = await client.get_me()
            
            # Проверяем, есть ли уже такой аккаунт в БД
            with next_get_db() as db:
                existing_account = db.query(Account).filter(Account.tg_id == str(me.id)).first()
                
                if not existing_account:
                    # Добавляем новый аккаунт
                    account = Account(
                        tg_id=str(me.id),
                        phone=me.phone if hasattr(me, 'phone') and me.phone else f"+{session_name.replace('session_', '')}",
                        name=me.first_name or me.username or f"User_{me.id}",
                        api_id=str(TELEGRAM_API_ID),
                        api_hash=TELEGRAM_API_HASH,
                        session_path=session_name
                    )
                    db.add(account)
                    db.commit()
                    
                    logger.info(f"✅ Добавлен аккаунт: {account.name} ({account.phone}) - ID: {account.tg_id}")
                else:
                    logger.info(f"⚠️ Аккаунт уже существует: {existing_account.name} ({existing_account.phone})")
        else:
            logger.warning(f"❌ Сессия {session_name} не авторизована")
            
        await client.disconnect()
        
    except Exception as e:
        logger.error(f"❌ Ошибка при импорте сессии {session_name}: {e}")

async def import_all_sessions():
    """Импортирует все найденные сессии"""
    session_files = [
        'session_14175706252.session',
        'session_14316815822.session', 
        'session_380686662002.session',
        'session_380686662003.session',
        'session_48608395363.session',
        'session_919525704829.session',
        'session_959782907883.session',
        'session_959784691910.session',
        'session_959785658943.session',
        'test_session_959784691910.session',
        'user_1332770104.session'
    ]
    
    logger.info(f"🔍 Найдено {len(session_files)} файлов сессий")
    
    for session_file in session_files:
        if os.path.exists(session_file):
            logger.info(f"📁 Обрабатываем: {session_file}")
            await import_session_to_db(session_file)
        else:
            logger.warning(f"⚠️ Файл не найден: {session_file}")
    
    # Показываем все аккаунты в БД
    logger.info("\n📊 Все аккаунты в базе данных:")
    with next_get_db() as db:
        accounts = db.query(Account).all()
        for account in accounts:
            logger.info(f"  • {account.name} ({account.phone}) - TG ID: {account.tg_id}")
    
    logger.info(f"\n✅ Импорт завершен! Всего аккаунтов в БД: {len(accounts)}")

if __name__ == "__main__":
    asyncio.run(import_all_sessions())
