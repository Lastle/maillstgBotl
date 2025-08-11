#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для просмотра групп подключенного аккаунта
"""

import asyncio
from telethon import TelegramClient
from config import TELEGRAM_API_ID, TELEGRAM_API_HASH

async def check_account_groups():
    """Проверяет группы аккаунта +48608395363"""
    
    # Путь к файлу сессии
    session_file = "session_48608395363"
    
    # Создаем клиент
    client = TelegramClient(session_file, TELEGRAM_API_ID, TELEGRAM_API_HASH)
    
    try:
        await client.start()
        print("Подключились к аккаунту +48608395363")
        
        # Получаем информацию о себе
        me = await client.get_me()
        print(f"Имя: {me.first_name} {me.last_name or ''}")
        print(f"Номер: {me.phone}")
        print(f"ID: {me.id}")
        print("-" * 50)
        
        # Получаем все диалоги (группы, каналы, чаты)
        dialogs = await client.get_dialogs()
        
        groups = []
        channels = []
        private_chats = []
        
        for dialog in dialogs:
            entity = dialog.entity
            
            if hasattr(entity, 'megagroup') and entity.megagroup:
                # Супергруппа
                groups.append({
                    'title': entity.title,
                    'id': entity.id,
                    'username': getattr(entity, 'username', None),
                    'participants_count': getattr(entity, 'participants_count', 'Неизвестно')
                })
            elif hasattr(entity, 'broadcast') and entity.broadcast:
                # Канал
                channels.append({
                    'title': entity.title,
                    'id': entity.id,
                    'username': getattr(entity, 'username', None),
                    'participants_count': getattr(entity, 'participants_count', 'Неизвестно')
                })
            elif hasattr(entity, 'title'):
                # Обычная группа
                groups.append({
                    'title': entity.title,
                    'id': entity.id,
                    'username': getattr(entity, 'username', None),
                    'participants_count': getattr(entity, 'participants_count', 'Неизвестно')
                })
            else:
                # Приватный чат
                name = getattr(entity, 'first_name', '') + ' ' + getattr(entity, 'last_name', '')
                private_chats.append({
                    'name': name.strip(),
                    'id': entity.id,
                    'username': getattr(entity, 'username', None)
                })
        
        # Выводим результаты
        print(f"СТАТИСТИКА:")
        print(f"   Групп: {len(groups)}")
        print(f"   Каналов: {len(channels)}")
        print(f"   Приватных чатов: {len(private_chats)}")
        print("-" * 50)
        
        if groups:
            print("ГРУППЫ:")
            for i, group in enumerate(groups[:10], 1):  # Показываем первые 10
                username_str = f"@{group['username']}" if group['username'] else "Без username"
                print(f"   {i}. {group['title']}")
                print(f"      ID: {group['id']}")
                print(f"      Username: {username_str}")
                print(f"      Участников: {group['participants_count']}")
                print()
            
            if len(groups) > 10:
                print(f"   ... и еще {len(groups) - 10} групп")
        
        if channels:
            print("\nКАНАЛЫ:")
            for i, channel in enumerate(channels[:5], 1):  # Показываем первые 5
                username_str = f"@{channel['username']}" if channel['username'] else "Без username"
                print(f"   {i}. {channel['title']}")
                print(f"      ID: {channel['id']}")
                print(f"      Username: {username_str}")
                print(f"      Подписчиков: {channel['participants_count']}")
                print()
            
            if len(channels) > 5:
                print(f"   ... и еще {len(channels) - 5} каналов")
        
    except Exception as e:
        print(f"Ошибка: {e}")
    
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(check_account_groups())
