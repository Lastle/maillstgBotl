#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для загрузки групп всех аккаунтов в базу данных
"""

import asyncio
from telethon import TelegramClient
from database.models import Account, Group
from database.database import get_db
from config import TELEGRAM_API_ID, TELEGRAM_API_HASH
import logging

logging.basicConfig(level=logging.INFO, encoding='utf-8')
logger = logging.getLogger(__name__)

async def load_account_groups(account):
    """Загружает группы для конкретного аккаунта"""
    try:
        client = TelegramClient(account.session_path, TELEGRAM_API_ID, TELEGRAM_API_HASH)
        await client.connect()
        
        if await client.is_user_authorized():
            logger.info(f"📱 Загружаем группы для {account.name} ({account.phone})")
            
            # Получаем все диалоги
            dialogs = await client.get_dialogs()
            groups_count = 0
            channels_count = 0
            
            # Очищаем старые группы этого аккаунта
            with next(get_db()) as db:
                db.query(Group).filter(Group.account_id == account.id).delete()
                db.commit()
            
            # Добавляем новые группы
            with next(get_db()) as db:
                for dialog in dialogs:
                    if dialog.is_group or dialog.is_channel:
                        group_type = 'group' if dialog.is_group else 'channel'
                        
                        group = Group(
                            account_id=account.id,
                            tg_id=str(dialog.id),
                            name=dialog.name or "Без названия",
                            type=group_type
                        )
                        db.add(group)
                        
                        if dialog.is_group:
                            groups_count += 1
                        else:
                            channels_count += 1
                
                db.commit()
            
            logger.info(f"  ✅ Загружено: {groups_count} групп, {channels_count} каналов")
            return {"groups": groups_count, "channels": channels_count}
            
        else:
            logger.warning(f"❌ Аккаунт {account.name} не авторизован")
            return {"error": "Не авторизован"}
            
    except Exception as e:
        logger.error(f"❌ Ошибка при загрузке групп для {account.name}: {e}")
        return {"error": str(e)}
    finally:
        try:
            await client.disconnect()
        except:
            pass

async def load_all_groups():
    """Загружает группы для всех аккаунтов"""
    logger.info("🔄 Начинаем загрузку групп для всех аккаунтов")
    
    with next(get_db()) as db:
        accounts = db.query(Account).all()
        logger.info(f"📊 Найдено аккаунтов: {len(accounts)}")
    
    total_groups = 0
    total_channels = 0
    
    for account in accounts:
        result = await load_account_groups(account)
        if "error" not in result:
            total_groups += result["groups"]
            total_channels += result["channels"]
    
    logger.info(f"\n🎉 Загрузка завершена!")
    logger.info(f"📈 Общая статистика: {total_groups} групп, {total_channels} каналов")
    
    # Показываем итоговую статистику по аккаунтам
    logger.info("\n📋 Статистика по аккаунтам:")
    with next(get_db()) as db:
        accounts = db.query(Account).all()
        for account in accounts:
            groups = db.query(Group).filter(Group.account_id == account.id).all()
            group_count = len([g for g in groups if g.type == 'group'])
            channel_count = len([g for g in groups if g.type == 'channel'])
            logger.info(f"  📱 {account.name}: {group_count} групп, {channel_count} каналов")

if __name__ == "__main__":
    asyncio.run(load_all_groups())
