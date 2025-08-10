import asyncio
import os
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from utils.keyboards import (
    get_main_menu_keyboard, 
    get_group_menu_keyboard, 
    get_back_keyboard,
    get_back_to_account_keyboard,
    get_back_to_groups_keyboard,
    get_account_groups_keyboard,
    get_cancel_keyboard,
    get_back_to_group_keyboard,
    get_photo_attachment_keyboard
)
from services.auth_service import auth_service
from database.models import Account, Group, Mailing
from database.database import get_db
from telethon import TelegramClient
from telethon.errors import ChatAdminRequiredError, FloodWaitError
# API credentials теперь берутся из аккаунта

router = Router()

class GroupManagement(StatesGroup):
    waiting_group_link = State()
    waiting_mailing_text = State()
    waiting_min_interval = State()
    waiting_max_interval = State()
    waiting_photo = State()

@router.callback_query(F.data.startswith("account_groups:"))
async def show_account_groups(callback: CallbackQuery):
    """Показывает группы аккаунта"""
    account_id = int(callback.data.split(":")[1])
    
    with next(get_db()) as db:
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            await callback.answer("❌ Аккаунт не найден")
            return
        
        groups = db.query(Group).filter(Group.account_id == account_id).all()
    
    if not groups:
        text = f"📋 Список групп для аккаунта {account.phone}:\n\nУ пользователя нет групп."
        await callback.message.edit_text(text, reply_markup=get_back_to_account_keyboard(account_id))
    else:
        text = f"📋 Список групп для аккаунта {account.phone}:\n\nВыберите группу:"
        
        # Подготавливаем данные групп для клавиатуры
        groups_data = []
        for group in groups:
            groups_data.append({
                'id': group.id,
                'title': group.title,
                'is_private': group.is_private
            })
        
        await callback.message.edit_text(
            text, 
            reply_markup=get_account_groups_keyboard(groups_data, account_id)
        )
    
    await callback.answer()

@router.callback_query(F.data.startswith("update_groups:"))
async def update_groups_start(callback: CallbackQuery, state: FSMContext):
    """Начинает обновление групп"""
    account_id = int(callback.data.split(":")[1])
    
    await state.update_data(account_id=account_id)
    
    await callback.message.edit_text(
        "🔄 Обновление информации о группах...\n\n"
        "Это может занять некоторое время.",
        reply_markup=get_back_keyboard()
    )
    
    # Запускаем обновление групп
    await update_groups_for_account(account_id, callback)
    
    await callback.answer()

async def update_groups_for_account(account_id: int, callback: CallbackQuery):
    """Обновляет группы для аккаунта"""
    start_time = asyncio.get_event_loop().time()
    try:
        with next(get_db()) as db:
            account = db.query(Account).filter(Account.id == account_id).first()
            if not account:
                await callback.answer("❌ Аккаунт не найден")
                return
        
        # Используем API credentials из аккаунта или глобальные
        from config import TELEGRAM_API_ID, TELEGRAM_API_HASH
        api_id = account.api_id if account.api_id and account.api_id != 0 else TELEGRAM_API_ID
        api_hash = account.api_hash if account.api_hash else TELEGRAM_API_HASH
        
        # Создаем клиент для аккаунта (сессия только по номеру телефона)
        session_name = f"session_{account.phone.replace('+', '')}"
        client = TelegramClient(session_name, api_id=api_id, api_hash=api_hash)
        
        await client.connect()
        
        if not await client.is_user_authorized():
            await client.disconnect()
            
            # Пытаемся удалить поврежденную сессию
            import os
            session_file = f"session_{account.phone.replace('+', '')}.session"
            if os.path.exists(session_file):
                try:
                    os.remove(session_file)
                except:
                    pass
            
            # Обновляем сообщение с подробной информацией
            await callback.message.edit_text(
                f"❌ Аккаунт {account.phone} не авторизован\n\n"
                f"Возможные причины:\n"
                f"• Сессия устарела или повреждена\n"
                f"• Аккаунт был заблокирован\n"
                f"• Изменились настройки безопасности\n\n"
                f"Сессия удалена. Попробуйте переавторизовать аккаунт.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Переавторизовать", callback_data=f"add_account")],
                    [InlineKeyboardButton(text="⬅️ Назад к аккаунту", callback_data=f"account_menu:{account_id}")]
                ])
            )
            await callback.answer()
            return
        
        # Получаем диалоги (чаты)
        async for dialog in client.iter_dialogs():
            if dialog.is_group or dialog.is_channel:
                # Проверяем, что это группа, а не канал
                try:
                    entity = await client.get_entity(dialog.id)
                    if hasattr(entity, 'megagroup') and entity.megagroup:
                        # Это супергруппа
                        group_type = "supergroup"
                    elif hasattr(entity, 'gigagroup') and entity.gigagroup:
                        # Это гигагруппа
                        group_type = "gigagroup"
                    else:
                        # Это обычная группа
                        group_type = "group"
                    
                    # Получаем количество участников
                    try:
                        participants_count = (await client.get_participants(dialog.id, limit=0)).total
                    except:
                        participants_count = 0
                    
                    # Сохраняем или обновляем группу в базе
                    with next(get_db()) as db:
                        existing_group = db.query(Group).filter(
                            Group.group_id == str(dialog.id),
                            Group.account_id == account_id
                        ).first()
                        
                        if existing_group:
                            # Обновляем существующую группу
                            # Получаем username из entity
                            username = None
                            if hasattr(entity, 'username') and entity.username:
                                username = entity.username
                            
                            existing_group.title = dialog.title
                            existing_group.username = username
                            existing_group.member_count = participants_count
                            existing_group.group_type = group_type
                            existing_group.is_private = not bool(username)  # Приватная если нет username
                        else:
                            # Создаем новую группу
                            # Получаем username из entity
                            username = None
                            if hasattr(entity, 'username') and entity.username:
                                username = entity.username
                            
                            new_group = Group(
                                group_id=str(dialog.id),
                                title=dialog.title,
                                username=username,
                                member_count=participants_count,
                                group_type=group_type,
                                is_private=not bool(username),  # Приватная если нет username
                                account_id=account_id
                            )
                            db.add(new_group)
                        
                        db.commit()
                        
                except Exception as e:
                    print(f"Ошибка при обработке группы {dialog.title}: {e}")
                    continue
        
        await client.disconnect()
        
        # Подсчитываем количество обновленных групп
        with next(get_db()) as db:
            updated_groups = db.query(Group).filter(Group.account_id == account_id).count()
        
        # Показываем результат обновления
        await callback.message.edit_text(
            f"✅ Обновление групп завершено!\n\n"
            f"📊 Найдено групп: {updated_groups}\n"
            f"🕐 Время обновления: {int(asyncio.get_event_loop().time() - start_time)} сек.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 Показать группы", callback_data=f"account_groups:{account_id}")],
                [InlineKeyboardButton(text="⬅️ Назад к аккаунту", callback_data=f"account_menu:{account_id}")]
            ])
        )
        await callback.answer()
        
    except Exception as e:
        error_msg = str(e)
        if "flood" in error_msg.lower():
            final_msg = "❌ Ошибка: Слишком много запросов к Telegram. Попробуйте позже."
        elif "unauthorized" in error_msg.lower() or "authorized" in error_msg.lower():
            final_msg = "❌ Проблема с аккаунтом: требуется повторная авторизация."
        elif "timeout" in error_msg.lower():
            final_msg = "❌ Превышено время ожидания. Проверьте интернет-соединение."
        elif "session" in error_msg.lower():
            final_msg = "❌ Проблема с сессией аккаунта. Попробуйте переавторизовать."
        else:
            final_msg = f"❌ Проблема с аккаунтом: {error_msg}"
        
        # Обновляем сообщение с ошибкой
        await callback.message.edit_text(
            final_msg + "\n\nВернитесь в меню аккаунта и попробуйте позже.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад к аккаунту", callback_data=f"account_menu:{account_id}")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main")]
            ])
        )
        await callback.answer()

@router.callback_query(F.data.startswith("group_menu:"))
async def group_menu(callback: CallbackQuery):
    """Меню конкретной группы"""
    group_id = int(callback.data.split(":")[1])
    
    with next(get_db()) as db:
        group = db.query(Group).filter(Group.id == group_id).first()
        if not group:
            await callback.answer("❌ Группа не найдена")
            return
        
        account = db.query(Account).filter(Account.id == group.account_id).first()
        
        # Получаем статус рассылки для этой группы
        from database.models import Mailing
        active_mailings = db.query(Mailing).filter(
            Mailing.group_id == group_id,
            Mailing.is_active == True
        ).all()
        
        # Информация о группе
        text = f"📊 Информация о группе\n\n"
        text += f"👥 Название: {group.title}\n"
        text += f"✏️ Юзернейм: {group.username or 'Нет юзернейма'}\n"
        text += f"👤 Участников: {group.member_count}\n"
        text += f"📄 Тип: {group.group_type}\n"
        text += f"🆔 ID: {group.group_id}\n\n"
        
        # Статус рассылки
        if active_mailings:
            mailing = active_mailings[0]  # Берем первую активную рассылку
            text += f"📊 Статус рассылки: 🟢 Активна\n"
            text += f"⏰ Интервал: {mailing.min_interval}-{mailing.max_interval} мин\n"
            text += f"📝 Текст рассылки: {mailing.text[:50] + '...' if len(mailing.text or '') > 50 else mailing.text or 'Не установлен'}\n"
            text += f"📷 Фото: {'Есть' if mailing.photo_path else 'Отсутствует'}"
        else:
            text += f"📊 Статус рассылки: ❌ Закончена или не начата\n"
            text += f"⏰ Интервал: Не установлен\n"
            text += f"📝 Текст рассылки: Не установлен\n"
            text += f"📷 Фото: Отсутствует"
    
    has_active_mailing = len(active_mailings) > 0
    await callback.message.edit_text(text, reply_markup=get_group_menu_keyboard(group_id, group.account_id, has_active_mailing))
    await callback.answer()

@router.callback_query(F.data.startswith("delete_group:"))
async def delete_group(callback: CallbackQuery):
    """Удаляет группу"""
    group_id = int(callback.data.split(":")[1])
    
    with next(get_db()) as db:
        group = db.query(Group).filter(Group.id == group_id).first()
        if group:
            # Останавливаем все рассылки этой группы
            from database.models import Mailing
            active_mailings = db.query(Mailing).filter(
                Mailing.group_id == group_id,
                Mailing.is_active == True
            ).all()
            
            for mailing in active_mailings:
                from services.mailing_service import mailing_service
                await mailing_service.stop_mailing(mailing.id)
            
            # Удаляем группу
            db.delete(group)
            db.commit()
            
            await callback.answer("✅ Группа удалена")
        else:
            await callback.answer("❌ Группа не найдена")
    
    # Возвращаемся в список групп
    await show_account_groups(callback)

@router.callback_query(F.data == "back_to_groups")
async def back_to_groups(callback: CallbackQuery):
    """Возврат к списку групп"""
    # Здесь нужно определить, к какому аккаунту возвращаться
    # Пока что возвращаемся в главное меню
    welcome_text = f"👋 Добро пожаловать, {callback.from_user.first_name}!\n\nВыберите действие:"
    await callback.message.edit_text(welcome_text, reply_markup=get_main_menu_keyboard())
    await callback.answer() 

@router.callback_query(F.data.startswith("group_mailing_settings:"))
async def group_mailing_settings(callback: CallbackQuery, state: FSMContext):
    """Настройка рассылки для конкретной группы"""
    group_id = int(callback.data.split(":")[1])
    
    # Сохраняем group_id в состоянии
    await state.update_data(group_id=group_id)
    
    await callback.message.edit_text(
        "📝 Настройка рассылки для группы\n\n"
        "Введите текст рассылки:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(GroupManagement.waiting_mailing_text)
    await callback.answer()

@router.message(GroupManagement.waiting_mailing_text)
async def process_mailing_text(message: Message, state: FSMContext):
    """Обработка текста рассылки"""
    data = await state.get_data()
    group_id = data["group_id"]
    
    await state.update_data(mailing_text=message.text)
    
    await message.answer(
        "📷 Хотите прикрепить фото к рассылке?\n\n"
        "Выберите тип рассылки:",
        reply_markup=get_photo_attachment_keyboard()
    )
    await state.set_state(GroupManagement.waiting_photo)

@router.callback_query(F.data.startswith("photo_attachment:"))
async def process_photo_attachment(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора типа рассылки с изображением"""
    attachment_type = callback.data.split(":")[1]
    
    if attachment_type == "text_only":
        await state.update_data(mailing_type="text", photo_path=None)
        await callback.message.edit_text(
            "⏰ Введите минимальный интервал в минутах:",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(GroupManagement.waiting_min_interval)
        await callback.answer()
        
    elif attachment_type == "only_photo":
        await callback.message.edit_text(
            "📷 Отправьте фото:",
            reply_markup=get_cancel_keyboard()
        )
        await state.update_data(mailing_type="photo")
        await state.set_state(GroupManagement.waiting_photo)
        await callback.answer()
        
    elif attachment_type == "with_text":
        await callback.message.edit_text(
            "📷 Отправьте фото с текстом:",
            reply_markup=get_cancel_keyboard()
        )
        await state.update_data(mailing_type="photo_with_text")
        await state.set_state(GroupManagement.waiting_photo)
        await callback.answer()

@router.message(GroupManagement.waiting_photo)
async def process_photo(message: Message, state: FSMContext):
    """Обработка загруженного фото"""
    data = await state.get_data()
    mailing_type = data.get("mailing_type")
    
    if not message.photo:
        await message.answer("❌ Пожалуйста, отправьте фото. Попробуйте снова:")
        return
    
    # Сохраняем фото
    photo = message.photo[-1]  # Берем самое большое фото
    photo_path = f"photos/{photo.file_id}.jpg"
    
    # Создаем папку photos если её нет
    import os
    os.makedirs("photos", exist_ok=True)
    
    # Скачиваем фото
    await message.bot.download(photo, photo_path)
    
    await state.update_data(photo_path=photo_path)
    
    await message.answer(
        "⏰ Введите минимальный интервал в минутах:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(GroupManagement.waiting_min_interval)

@router.message(GroupManagement.waiting_min_interval)
async def process_min_interval(message: Message, state: FSMContext):
    """Обработка минимального интервала"""
    try:
        min_interval = int(message.text)
        if min_interval < 1:
            await message.answer("❌ Интервал должен быть не менее 1 минуты. Попробуйте снова:")
            return
        
        await state.update_data(min_interval=min_interval)
        
        await message.answer(
            "⏰ Введите максимальный интервал в минутах:",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(GroupManagement.waiting_max_interval)
        
    except ValueError:
        await message.answer("❌ Введите число. Попробуйте снова:")

@router.message(GroupManagement.waiting_max_interval)
async def process_max_interval(message: Message, state: FSMContext):
    """Обработка максимального интервала"""
    try:
        max_interval = int(message.text)
        data = await state.get_data()
        min_interval = data["min_interval"]
        
        if max_interval < min_interval:
            await message.answer(f"❌ Максимальный интервал должен быть не менее {min_interval}. Попробуйте снова:")
            return
        
        # Создаем рассылку
        group_id = data["group_id"]
        mailing_text = data["mailing_text"]
        mailing_type = data.get("mailing_type", "text")
        photo_path = data.get("photo_path")
        
        with next(get_db()) as db:
            group = db.query(Group).filter(Group.id == group_id).first()
            if not group:
                await message.answer("❌ Группа не найдена", reply_markup=get_main_menu_keyboard())
                await state.clear()
                return
            
            # Останавливаем старые рассылки для этой группы
            old_mailings = db.query(Mailing).filter(
                Mailing.group_id == group_id,
                Mailing.is_active == True
            ).all()
            
            for old_mailing in old_mailings:
                old_mailing.is_active = False
            
            # Создаем новую рассылку
            new_mailing = Mailing(
                account_id=group.account_id,
                group_id=group_id,
                text=mailing_text,
                min_interval=min_interval,
                max_interval=max_interval,
                mailing_type=mailing_type,
                photo_path=photo_path,
                is_active=False  # Не запускаем автоматически
            )
            
            db.add(new_mailing)
            db.commit()
            
            await message.answer(
                f"✅ Рассылка настроена для группы {group.title}\n\n"
                f"📝 Текст: {mailing_text[:50]}{'...' if len(mailing_text) > 50 else ''}\n"
                f"⏰ Интервал: {min_interval}-{max_interval} мин\n\n"
                f"Нажмите '▶️ Начать рассылку' в меню группы для запуска.",
                reply_markup=get_back_to_group_keyboard(group_id, group.account_id)
            )
            await state.clear()
        
    except ValueError:
        await message.answer("❌ Введите число. Попробуйте снова:")

@router.callback_query(F.data.startswith("start_group_mailing:"))
async def start_group_mailing(callback: CallbackQuery):
    """Запускает рассылку для конкретной группы"""
    group_id = int(callback.data.split(":")[1])
    
    with next(get_db()) as db:
        group = db.query(Group).filter(Group.id == group_id).first()
        if not group:
            await callback.answer("❌ Группа не найдена")
            return
        
        # Ищем активную рассылку для этой группы
        mailing = db.query(Mailing).filter(
            Mailing.group_id == group_id,
            Mailing.is_active == True
        ).first()
        
        if not mailing:
            # Ищем неактивную рассылку
            mailing = db.query(Mailing).filter(
                Mailing.group_id == group_id,
                Mailing.is_active == False
            ).first()
            
            if not mailing:
                await callback.answer("❌ Сначала настройте рассылку для этой группы")
                return
        
        # Запускаем рассылку
        from services.mailing_service import mailing_service
        result = await mailing_service.start_mailing(mailing.id)
        
        await callback.answer(result["message"])
        
        # Обновляем меню группы
        await group_menu(callback)

@router.callback_query(F.data.startswith("stop_group_mailing:"))
async def stop_group_mailing(callback: CallbackQuery):
    """Останавливает рассылку для конкретной группы"""
    group_id = int(callback.data.split(":")[1])
    
    with next(get_db()) as db:
        # Ищем активную рассылку для этой группы
        mailing = db.query(Mailing).filter(
            Mailing.group_id == group_id,
            Mailing.is_active == True
        ).first()
        
        if not mailing:
            await callback.answer("❌ Активная рассылка не найдена")
            return
        
        # Останавливаем рассылку
        from services.mailing_service import mailing_service
        result = await mailing_service.stop_mailing(mailing.id)
        
        await callback.answer(result["message"])
        
        # Обновляем меню группы
        await group_menu(callback) 

@router.callback_query(F.data == "cancel_operation")
async def cancel_operation(callback: CallbackQuery, state: FSMContext):
    """Отмена операции"""
    await state.clear()
    await callback.answer("❌ Операция отменена")
    
    # Возвращаемся в главное меню
    welcome_text = f"👋 Добро пожаловать, {callback.from_user.first_name}!\n\nВыберите действие:"
    await callback.message.edit_text(welcome_text, reply_markup=get_main_menu_keyboard()) 

@router.callback_query(F.data.startswith("mailing_status:"))
async def show_mailing_status(callback: CallbackQuery):
    """Показывает детальный статус рассылки"""
    group_id = int(callback.data.split(":")[1])
    
    with next(get_db()) as db:
        group = db.query(Group).filter(Group.id == group_id).first()
        if not group:
            await callback.answer("❌ Группа не найдена")
            return
        
        # Получаем активную рассылку
        active_mailing = db.query(Mailing).filter(
            Mailing.group_id == group_id,
            Mailing.is_active == True
        ).first()
        
        if active_mailing:
            # Рассылка активна
            text = f"📊 Статус рассылки для группы {group.title}\n\n"
            text += f"🟢 Статус: Активна\n"
            text += f"⏰ Интервал: {active_mailing.min_interval}-{active_mailing.max_interval} мин\n"
            text += f"📝 Тип: {active_mailing.mailing_type}\n"
            text += f"📝 Текст: {active_mailing.text[:100]}{'...' if len(active_mailing.text or '') > 100 else ''}\n"
            if active_mailing.photo_path:
                text += f"📷 Фото: Есть\n"
            else:
                text += f"📷 Фото: Нет\n"
            text += f"🕐 Создана: {active_mailing.created_at.strftime('%d.%m.%Y %H:%M')}"
        else:
            # Рассылка неактивна
            inactive_mailing = db.query(Mailing).filter(
                Mailing.group_id == group_id,
                Mailing.is_active == False
            ).first()
            
            text = f"📊 Статус рассылки для группы {group.title}\n\n"
            text += f"🔴 Статус: Неактивна\n"
            
            if inactive_mailing:
                text += f"⏰ Интервал: {inactive_mailing.min_interval}-{inactive_mailing.max_interval} мин\n"
                text += f"📝 Тип: {inactive_mailing.mailing_type}\n"
                text += f"📝 Текст: {inactive_mailing.text[:100]}{'...' if len(inactive_mailing.text or '') > 100 else ''}\n"
                if inactive_mailing.photo_path:
                    text += f"📷 Фото: Есть\n"
                else:
                    text += f"📷 Фото: Нет\n"
                text += f"🕐 Создана: {inactive_mailing.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
                text += f"💡 Нажмите '▶️ Начать рассылку' для запуска"
            else:
                text += f"❌ Рассылка не настроена\n\n"
                text += f"💡 Нажмите '📝 Текст и Интервал рассылки' для настройки"
    
    await callback.message.edit_text(
        text, 
        reply_markup=get_back_to_group_keyboard(group_id, group.account_id)
    )
    await callback.answer() 