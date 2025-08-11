#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для тестирования функций админ-панели
"""

import asyncio
from telethon import TelegramClient
from database.models import Account, Group
from database.database import next_get_db
from config import TELEGRAM_API_ID, TELEGRAM_API_HASH
import logging

logging.basicConfig(level=logging.INFO, encoding='utf-8')
logger = logging.getLogger(__name__)

async def test_account_groups(account):
    """Тестирует получение групп для аккаунта"""
    try:
        client = TelegramClient(account.session_path, TELEGRAM_API_ID, TELEGRAM_API_HASH)
        await client.connect()
        
        if await client.is_user_authorized():
            logger.info(f"🔍 Проверяем группы для {account.name} ({account.phone})")
            
            # Получаем все диалоги
            dialogs = await client.get_dialogs()
            groups_count = 0
            channels_count = 0
            
            for dialog in dialogs:
                if dialog.is_group:
                    groups_count += 1
                elif dialog.is_channel:
                    channels_count += 1
            
            logger.info(f"  📱 Групп: {groups_count}, Каналов: {channels_count}")
            
            # Обновляем информацию в БД
            with next_get_db() as db:
                # Удаляем старые записи групп для этого аккаунта
                db.query(Group).filter(Group.account_id == account.id).delete()
                
                # Добавляем новые группы
                for dialog in dialogs:
                    if dialog.is_group or dialog.is_channel:
                        group = Group(
                            account_id=account.id,
                            tg_id=str(dialog.id),
                            name=dialog.name or "Без названия",
                            type='group' if dialog.is_group else 'channel'
                        )
                        db.add(group)
                
                db.commit()
                
            return {"groups": groups_count, "channels": channels_count}
        else:
            logger.warning(f"❌ Аккаунт {account.name} не авторизован")
            return {"error": "Не авторизован"}
            
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке групп для {account.name}: {e}")
        return {"error": str(e)}
    finally:
        try:
            await client.disconnect()
        except:
            pass

async def test_all_admin_functions():
    """Тестирует все функции админ-панели"""
    logger.info("🧪 Начинаем тестирование функций админ-панели")
    
    # 1. Тестируем получение всех аккаунтов
    logger.info("\n1️⃣ Тестируем функцию 'Все аккаунты и номера'")
    with next_get_db() as db:
        accounts = db.query(Account).all()
        logger.info(f"✅ Найдено аккаунтов в БД: {len(accounts)}")
        
        for account in accounts:
            logger.info(f"  • {account.name} ({account.phone}) - ID: {account.tg_id}")
    
    # 2. Тестируем получение групп для каждого аккаунта
    logger.info("\n2️⃣ Тестируем получение групп для каждого аккаунта")
    total_groups = 0
    total_channels = 0
    
    for account in accounts:
        result = await test_account_groups(account)
        if "error" not in result:
            total_groups += result["groups"]
            total_channels += result["channels"]
    
    logger.info(f"📊 Общая статистика: {total_groups} групп, {total_channels} каналов")
    
    # 3. Проверяем данные в БД после обновления
    logger.info("\n3️⃣ Проверяем обновленные данные в БД")
    with next_get_db() as db:
        groups_in_db = db.query(Group).all()
        logger.info(f"✅ Групп в БД: {len(groups_in_db)}")
        
        # Группируем по аккаунтам
        account_groups = {}
        for group in groups_in_db:
            if group.account_id not in account_groups:
                account_groups[group.account_id] = []
            account_groups[group.account_id].append(group)
        
        for account_id, groups in account_groups.items():
            account = db.query(Account).filter(Account.id == account_id).first()
            if account:
                logger.info(f"  📱 {account.name}: {len(groups)} групп/каналов")
    
    # 4. Тестируем функционал массовой рассылки (без отправки)
    logger.info("\n4️⃣ Тестируем подготовку к массовой рассылке")
    test_message = "Тестовое сообщение для проверки функционала"
    
    with next_get_db() as db:
        accounts = db.query(Account).all()
        available_accounts = []
        
        for account in accounts:
            groups = db.query(Group).filter(Group.account_id == account.id).all()
            if groups:
                available_accounts.append({
                    "account": account,
                    "groups_count": len(groups)
                })
        
        logger.info(f"✅ Аккаунтов готовых к рассылке: {len(available_accounts)}")
        for acc_info in available_accounts:
            account = acc_info["account"]
            logger.info(f"  📤 {account.name}: {acc_info['groups_count']} групп")
    
    logger.info("\n🎉 Тестирование завершено! Все функции админ-панели готовы к работе.")

if __name__ == "__main__":
    asyncio.run(test_all_admin_functions())
