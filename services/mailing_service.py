import asyncio
import random
from datetime import datetime
from typing import Dict, List, Optional, Any
from telethon import TelegramClient
from telethon.errors import ChatAdminRequiredError, FloodWaitError, UserNotParticipantError, UsernameNotOccupiedError, PeerIdInvalidError, ChatIdInvalidError
from telethon.tl.types import Channel
from telethon.tl.functions.channels import JoinChannelRequest
from database.models import Account, Group, Mailing, MailingHistory
from database.database import get_async_db
from sqlalchemy import select, func
from utils.helpers import calculate_interval, truncate_text, format_time_ago
from services.night_mode import get_night_mode_settings
# API credentials теперь берутся из аккаунта

class MailingService:
    """Сервис для управления рассылкой"""
    
    def __init__(self):
        self.active_mailings: Dict[int, asyncio.Task] = {}
        self.clients: Dict[int, TelegramClient] = {}
        
        # Асинхронная очистка будет вызвана из main.py
    
    def _to_channel_id(self, raw_id: int) -> int:
        """Конвертирует raw_id в channel_id"""
        s = str(raw_id)
        return int(s[4:]) if s.startswith('-100') else abs(int(raw_id))
    
    async def _resolve_entity(self, client: TelegramClient, group: Group) -> Optional[Any]:
        """Резолвит entity для группы по её tg_id через список диалогов"""
        try:
            # tg_id хранится как строка, приводим к int
            raw_id = int(group.tg_id)
            target_id = self._to_channel_id(raw_id)
            for d in await client.get_dialogs():
                ent = getattr(d, 'entity', None)
                if isinstance(ent, Channel) and getattr(ent, 'id', None) == target_id:
                    return ent
        except Exception as e:
            print(f"⚠️ Поиск entity по tg_id не удался: {e}")
        return None
    
    async def cleanup_old_mailings(self):
        """Асинхронно очищает старые рассылки при запуске"""
        async with get_async_db() as db:
            from sqlalchemy import select
            
            result = await db.execute(
                select(Mailing).filter(Mailing.is_active == True)
            )
            old_mailings = result.scalars().all()
            
            for mailing in old_mailings:
                mailing.is_active = False
                mailing.stopped_at = datetime.utcnow()
            
            await db.commit()
            if old_mailings:
                print(f"🧹 Очищено {len(old_mailings)} старых рассылок при запуске")
    
    async def create_client(self, account: Account) -> TelegramClient:
        """Создает клиент для аккаунта"""
        if account.id in self.clients:
            return self.clients[account.id]
        
        # Используем API credentials из аккаунта или глобальные
        from config import TELEGRAM_API_ID, TELEGRAM_API_HASH
        api_id = account.api_id if account.api_id and account.api_id != 0 else TELEGRAM_API_ID
        api_hash = account.api_hash if account.api_hash else TELEGRAM_API_HASH
        
        session_name = f"session_{account.phone.replace('+', '')}"
        client = TelegramClient(session_name, api_id=api_id, api_hash=api_hash)
        await client.connect()
        
        if not await client.is_user_authorized():
            raise Exception(f"Аккаунт {account.phone} не авторизован")
        
        self.clients[account.id] = client
        print(f"🔌 Клиент для аккаунта {account.phone} создан и сохранен")
        return client
    
    async def start_mailing(self, mailing_id: int) -> Dict[str, Any]:
        """Запускает рассылку"""
        print(f"🔧 Запускаем рассылку {mailing_id}...")
        
        async with get_async_db() as db:
            # Получаем рассылку
            mailing_result = await db.execute(
                select(Mailing).filter(Mailing.id == mailing_id)
            )
            mailing = mailing_result.scalar_one_or_none()
            
            if not mailing:
                print(f"❌ Рассылка {mailing_id} не найдена!")
                return {"success": False, "error": "Рассылка не найдена"}
            
            if mailing.is_active:
                print(f"⚠️ Рассылка {mailing_id} уже запущена!")
                return {"success": False, "error": "Рассылка уже запущена"}
            
            # Проверяем, не запущена ли уже задача
            if mailing_id in self.active_mailings:
                print(f"⚠️ Задача рассылки {mailing_id} уже запущена!")
                return {"success": False, "error": "Рассылка уже запущена"}
            
            # Обновляем статус
            mailing.is_active = True
            mailing.started_at = datetime.utcnow()
            await db.commit()
            print(f"✅ Статус рассылки {mailing_id} обновлен")
        
        # Запускаем задачу рассылки
        task = asyncio.create_task(self._mailing_worker(mailing_id))
        self.active_mailings[mailing_id] = task
        print(f"🚀 Задача рассылки {mailing_id} создана")
        
        return {"success": True, "message": "Рассылка запущена"}
    
    async def stop_mailing(self, mailing_id: int) -> Dict[str, Any]:
        """Останавливает рассылку"""
        if mailing_id in self.active_mailings:
            task = self.active_mailings[mailing_id]
            task.cancel()
            del self.active_mailings[mailing_id]
        
        async with get_async_db() as db:
            # Получаем рассылку
            mailing_result = await db.execute(
                select(Mailing).filter(Mailing.id == mailing_id)
            )
            mailing = mailing_result.scalar_one_or_none()
            
            if mailing:
                mailing.is_active = False
                mailing.stopped_at = datetime.utcnow()
                await db.commit()
        
        return {"success": True, "message": "Рассылка остановлена"}
    
    async def _mailing_worker(self, mailing_id: int):
        """Рабочий процесс рассылки"""
        print(f"🔄 Рабочий процесс рассылки {mailing_id} запущен")
        
        # Инициализируем переменные для finally блока
        account = None
        group = None
        
        try:
            async with get_async_db() as db:
                # Получаем рассылку
                mailing_result = await db.execute(
                    select(Mailing).filter(Mailing.id == mailing_id)
                )
                mailing = mailing_result.scalar_one_or_none()
                
                if not mailing:
                    print(f"❌ Рассылка {mailing_id} не найдена в базе")
                    return
                
                # Получаем аккаунт
                account_result = await db.execute(
                    select(Account).filter(Account.id == mailing.account_id)
                )
                account = account_result.scalar_one_or_none()
                
                # Получаем группу
                group_result = await db.execute(
                    select(Group).filter(Group.id == mailing.group_id)
                )
                group = group_result.scalar_one_or_none()
                
                if not account or not group:
                    print(f"❌ Аккаунт или группа не найдены для рассылки {mailing_id}")
                    return
                
                print(f"📱 Работаем с аккаунтом {account.phone} и группой {getattr(group, 'name', str(group.id))}")
            
            # Создаем или получаем клиент
            print(f"🔌 Получаем клиент для аккаунта {account.phone}...")
            client = await self.create_client(account)
            print(f"✅ Клиент получен")
            
            # Первая проверка перед циклом
            async with get_async_db() as db:
                result = await db.execute(
                    select(Mailing).filter(Mailing.id == mailing_id)
                )
                mailing = result.scalar_one_or_none()
                if not mailing or not mailing.is_active:
                    print(f"🛑 Рассылка {mailing_id} неактивна, выходим")
                    return
            
            cycle_count = 0
            while True:
                cycle_count += 1
                # Проверяем, активна ли рассылка (реже, чтобы не блокировать БД)
                if cycle_count % 10 == 0:  # Проверяем каждый 10-й цикл
                    try:
                        async with get_async_db() as db:
                            result = await db.execute(
                                select(Mailing).filter(Mailing.id == mailing_id)
                            )
                            mailing = result.scalar_one_or_none()
                            if not mailing or not mailing.is_active:
                                print(f"🛑 Рассылка {mailing_id} остановлена или неактивна")
                                break
                    except Exception as e:
                        print(f"⚠️ Ошибка проверки активности рассылки {mailing_id}: {e}")
                        # Продолжаем работу, не прерываем из-за ошибки БД
                
                # Вычисляем интервал с учетом ночного режима
                night_settings = get_night_mode_settings()
                interval = calculate_interval(
                    mailing.min_interval, 
                    mailing.max_interval,
                    night_settings["is_enabled"],
                    night_settings["start_hour"],
                    night_settings["end_hour"]
                )
                
                print(f"⏰ Рассылка {mailing_id}: ждем {interval} минут...")
                
                # Ждем интервал
                await asyncio.sleep(interval * 60)
                
                print(f"📤 Рассылка {mailing_id}: отправляем сообщение...")
                
                # Отправляем сообщение
                ok = await self._send_message(client, group.id, mailing.id)
                if ok:
                    print(f"✅ Отправлено сообщение в группу {getattr(group, 'name', str(group.id))} (рассылка {mailing_id})")
                else:
                    print(f"⚠️ Сообщение НЕ отправлено в группу {getattr(group, 'name', str(group.id))} (рассылка {mailing_id})")
                
        except asyncio.CancelledError:
            print(f"🛑 Рассылка {mailing_id} отменена")
        except Exception as e:
            print(f"❌ Ошибка в рассылке {mailing_id}: {e}")
        finally:
            # Проверяем, используется ли клиент другими рассылками
            try:
                if account and account.id in self.clients:
                    # Проверяем, есть ли другие активные рассылки для этого аккаунта
                    async with get_async_db() as db:
                        result = await db.execute(
                            select(func.count(Mailing.id)).filter(
                                Mailing.account_id == account.id,
                                Mailing.is_active == True,
                                Mailing.id != mailing_id
                            )
                        )
                        other_mailings = result.scalar()
                    
                    if other_mailings == 0:
                        # Закрываем клиент только если нет других рассылок
                        await self.clients[account.id].disconnect()
                        del self.clients[account.id]
                        print(f"🔌 Клиент для аккаунта {account.phone} закрыт (нет других рассылок)")
                    else:
                        print(f"🔌 Клиент для аккаунта {account.phone} остается открытым ({other_mailings} других рассылок)")
            except Exception as e:
                print(f"⚠️ Ошибка при проверке клиента: {e}")
            
                    # Очищаем задачу
        if mailing_id in self.active_mailings:
            del self.active_mailings[mailing_id]
            print(f"🧹 Задача рассылки {mailing_id} очищена")
    

    
    async def _send_message(self, client: TelegramClient, group_id: int, mailing_id: int) -> bool:
        """Отправляет сообщение в группу"""
        try:
            async with get_async_db() as db:
                mailing = (await db.execute(select(Mailing).filter(Mailing.id == mailing_id))).scalar_one_or_none()
                group   = (await db.execute(select(Group).filter(Group.id == group_id))).scalar_one_or_none()
                if not mailing or not group:
                    print(f"❌ Данные не найдены для рассылки {mailing_id}")
                    return False

                print("📋 === ОТЛАДКА ГРУППЫ ===")
                print(f"Название: {getattr(group, 'name', str(group.id))} | tg_id: {getattr(group, 'tg_id', '?')} | type: {getattr(group, 'type', '?')}")

                entity = await self._resolve_entity(client, group)
                if not entity:
                    print("⛔ Не удалось получить entity (возможно, аккаунт не состоит в группе)")
                    return False

                # Если это канал (broadcast) — без прав админа отправлять нельзя
                if isinstance(entity, Channel) and entity.broadcast:
                    print("⛔ Это канал (broadcast). Нужны админ-права. Пропускаем.")
                    return False

                # Если это супергруппа (megagroup) — проверяем что мы участник
                if isinstance(entity, Channel) and entity.megagroup:
                    print("👥 Это супергруппа (megagroup)")
                    # Пропускаем автоматическое присоединение - аккаунт может быть заблокирован
                    # Отправляем только если уже состоим в группе

                # Подготовка текста: поддержка нескольких вариантов через '||'
                selected_text = (mailing.text or "").strip()
                if selected_text and "||" in selected_text:
                    variants = [v.strip() for v in selected_text.split("||") if v.strip()]
                    if variants:
                        import random as _r
                        selected_text = _r.choice(variants)
                
                # Отправка
                mailing_type = getattr(mailing, 'mailing_type', None) or ("photo" if getattr(mailing, 'photo_path', None) and not selected_text else ("photo_with_text" if getattr(mailing, 'photo_path', None) and selected_text else "text"))
                if mailing_type == "text":
                    await client.send_message(entity, selected_text)
                elif mailing_type == "photo":
                    await client.send_file(entity, mailing.photo_path)
                elif mailing_type == "photo_with_text":
                    await client.send_file(entity, mailing.photo_path, caption=selected_text)
                else:
                    await client.send_message(entity, selected_text)

                # История — только при успехе (подстраиваемся под актуальную модель)
                try:
                    history = MailingHistory(
                        mailing_id=mailing.id,
                        group_id=str(getattr(group, 'tg_id', group.id)),
                        group_title=getattr(group, 'name', str(group.id)),
                        status='sent',
                        error_message=None,
                    )
                    db.add(history)
                    await db.commit()
                    print(f"📝 История сохранена для рассылки {mailing_id}")
                except Exception as he:
                    # Не падаем, если схема отличается
                    print(f"⚠️ Не удалось сохранить историю: {he}")
                return True

        except Exception as e:
            print(f"❌ Общая ошибка в _send_message: {e}")
            return False
    
    async def start_broadcast_all(self, text: str, mailing_type: str, 
                                interval_type: str, min_interval: int, 
                                max_interval: int, photo_path: Optional[str] = None) -> Dict[str, Any]:
        """Запускает рассылку во все аккаунты"""
        print(f"🔍 Начинаем рассылку: {text[:50] if text else 'без текста'}...")
        
        async with get_async_db() as db:
            # Получаем аккаунты
            accounts_result = await db.execute(
                select(Account).filter(Account.is_active == True)
            )
            accounts = accounts_result.scalars().all()
            print(f"📱 Найдено активных аккаунтов: {len(accounts)}")
            
            if not accounts:
                print("❌ Нет активных аккаунтов!")
                return {"success": False, "error": "Нет активных аккаунтов"}
            
            created_mailing_ids = []
            for account in accounts:
                # Получаем группы для аккаунта
                groups_result = await db.execute(
                    select(Group).filter(Group.account_id == account.id)
                )
                groups = groups_result.scalars().all()
                print(f"👥 Аккаунт {account.phone}: найдено групп {len(groups)}")
                
                for group in groups:
                    print(f"   📋 Группа: {getattr(group, 'name', str(group.id))}")
                    mailing = Mailing(
                        text=text,
                        photo_path=photo_path,
                        mailing_type=mailing_type,
                        interval_type=interval_type,
                        min_interval=min_interval,
                        max_interval=max_interval,
                        account_id=account.id,
                        group_id=group.id,
                        is_active=False  # Создаем как неактивную
                    )
                    db.add(mailing)
                    await db.flush()  # Получаем ID без коммита
                    created_mailing_ids.append(mailing.id)
                    print(f"   ✅ Создана рассылка ID: {mailing.id}")
            
            await db.commit()
        
        print(f"🚀 Запускаем {len(created_mailing_ids)} рассылок...")
        
        # Запускаем все рассылки с небольшой задержкой
        for i, mailing_id in enumerate(created_mailing_ids):
            result = await self.start_mailing(mailing_id)
            print(f"   📤 Рассылка {mailing_id}: {result}")
            
            # Небольшая задержка между запуском рассылок
            if i < len(created_mailing_ids) - 1:
                await asyncio.sleep(1)
        
        return {"success": True, "message": f"Запущено {len(created_mailing_ids)} рассылок"}
    
    async def stop_broadcast_all(self) -> Dict[str, Any]:
        """Останавливает все рассылки"""
        stopped_count = 0
        
        async with get_async_db() as db:
            # Получаем активные рассылки
            active_mailings_result = await db.execute(
                select(Mailing).filter(Mailing.is_active == True)
            )
            active_mailings = active_mailings_result.scalars().all()
            
            for mailing in active_mailings:
                await self.stop_mailing(mailing.id)
                stopped_count += 1
        
        return {"success": True, "message": f"Остановлено {stopped_count} рассылок"}
    
    async def get_mailing_history(self, limit: int = 10) -> List[Dict]:
        """Получает историю рассылок"""
        try:
            async with get_async_db() as db:
                result = await db.execute(
                    select(MailingHistory)
                    .order_by(MailingHistory.sent_at.desc())
                    .limit(limit)
                )
                history = result.scalars().all()
                
                history_list = []
                for item in history:
                    # Получаем информацию об аккаунте
                    account_result = await db.execute(
                        select(Account).filter(Account.id == item.account_id)
                    )
                    account = account_result.scalar_one_or_none()
                    
                    # Получаем информацию о группе
                    group_result = await db.execute(
                        select(Group).filter(Group.id == item.group_id)
                    )
                    group = group_result.scalar_one_or_none()
                    
                    history_list.append({
                        'sent_at': format_time_ago(item.sent_at),
                        'text': item.text,
                        'account_name': account.phone if account else "Неизвестно",
                        'group_title': group.title if group else "Неизвестно"
                    })
                
                return history_list
        except Exception as e:
            print(f"❌ Ошибка при получении истории: {e}")
            return []

    async def get_all_mailings(self) -> List[Dict]:
        """Получает список последних 10 рассылок"""
        try:
            async with get_async_db() as db:
                result = await db.execute(
                    select(Mailing)
                    .order_by(Mailing.created_at.desc())
                    .limit(10)
                )
                mailings = result.scalars().all()
                
                mailings_list = []
                for mailing in mailings:
                    # Получаем информацию об аккаунте
                    account_result = await db.execute(
                        select(Account).filter(Account.id == mailing.account_id)
                    )
                    account = account_result.scalar_one_or_none()
                    
                    # Получаем информацию о группе
                    group_result = await db.execute(
                        select(Group).filter(Group.id == mailing.group_id)
                    )
                    group = group_result.scalar_one_or_none()
                    
                    # Определяем статус
                    status = "🟢 Активна" if mailing.is_active else "🔴 Остановлена"
                    
                    mailings_list.append({
                        'id': mailing.id,
                        'status': status,
                        'text': truncate_text(mailing.text or "", 50),
                        'account_name': account.phone if account else "Неизвестно",
                        'group_title': group.title if group else "Неизвестно",
                        'mailing_type': mailing.mailing_type,
                        'min_interval': mailing.min_interval,
                        'max_interval': mailing.max_interval,
                        'created_at': mailing.created_at.strftime("%d.%m.%Y %H:%M"),
                        'is_active': mailing.is_active
                    })
                
                return mailings_list
        except Exception as e:
            print(f"❌ Ошибка при получении списка рассылок: {e}")
            return []

    async def get_mailing_details(self, mailing_id: int) -> Optional[Dict]:
        """Получает детальную информацию о рассылке"""
        try:
            async with get_async_db() as db:
                result = await db.execute(
                    select(Mailing).filter(Mailing.id == mailing_id)
                )
                mailing = result.scalar_one_or_none()
                
                if not mailing:
                    return None
                
                # Получаем информацию об аккаунте
                account_result = await db.execute(
                    select(Account).filter(Account.id == mailing.account_id)
                )
                account = account_result.scalar_one_or_none()
                
                # Получаем информацию о группе
                group_result = await db.execute(
                    select(Group).filter(Group.id == mailing.group_id)
                )
                group = group_result.scalar_one_or_none()
                
                # Получаем количество отправленных сообщений
                history_result = await db.execute(
                    select(func.count(MailingHistory.id)).filter(
                        MailingHistory.mailing_id == mailing_id
                    )
                )
                sent_count = history_result.scalar()
                
                return {
                    'id': mailing.id,
                    'status': "🟢 Активна" if mailing.is_active else "🔴 Остановлена",
                    'text': mailing.text or "Без текста",
                    'account_name': account.phone if account else "Неизвестно",
                    'group_title': group.title if group else "Неизвестно",
                    'mailing_type': mailing.mailing_type,
                    'min_interval': mailing.min_interval,
                    'max_interval': mailing.max_interval,
                    'created_at': mailing.created_at.strftime("%d.%m.%Y %H:%M"),
                    'sent_count': sent_count,
                    'is_active': mailing.is_active
                }
        except Exception as e:
            print(f"❌ Ошибка при получении деталей рассылки: {e}")
            return None
    
    async def cleanup(self):
        """Очищает ресурсы"""
        # Останавливаем все рассылки
        for mailing_id in list(self.active_mailings.keys()):
            await self.stop_mailing(mailing_id)
        
        # Отключаем клиенты (создаем копию для безопасной итерации)
        clients_to_disconnect = list(self.clients.values())
        self.clients.clear()  # Очищаем словарь сразу
        
        for client in clients_to_disconnect:
            try:
                await client.disconnect()
            except:
                pass

# Глобальный экземпляр сервиса
mailing_service = MailingService()
# Очистка старых рассылок выполняется асинхронно в main.py 