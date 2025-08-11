from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from utils.keyboards import get_main_menu_keyboard, get_night_mode_keyboard, get_back_keyboard, get_mailings_list_keyboard, get_mailing_details_keyboard
from services.night_mode import get_night_mode_status, enable_night_mode, disable_night_mode
from services.mailing_service import mailing_service
from database.database import get_db, next_get_db
from sqlalchemy import delete
from database.models import Mailing, MailingHistory
from config import ADMIN_IDS

router = Router()

class NightModeSettings(StatesGroup):
    waiting_start_hour = State()
    waiting_end_hour = State()

@router.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔️ У вас нет доступа к этому боту.")
        return
    
    welcome_text = f"👋 Добро пожаловать, {message.from_user.first_name}!\n\nВыберите действие:"
    await message.answer(welcome_text, reply_markup=get_main_menu_keyboard())

@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
    """Возврат в главное меню"""
    welcome_text = f"👋 Добро пожаловать, {callback.from_user.first_name}!\n\nВыберите действие:"
    await callback.message.edit_text(welcome_text, reply_markup=get_main_menu_keyboard())
    await callback.answer()

@router.callback_query(F.data == "night_mode")
async def night_mode_menu(callback: CallbackQuery):
    """Меню ночного режима"""
    status = get_night_mode_status()
    text = f"🌙 Ночной режим\n\n{status}\n\nВыберите действие:"
    await callback.message.edit_text(text, reply_markup=get_night_mode_keyboard())
    await callback.answer()

@router.callback_query(F.data.startswith("night_mode:"))
async def night_mode_actions(callback: CallbackQuery, state: FSMContext):
    """Действия с ночным режимом"""
    action = callback.data.split(":")[1]
    
    if action == "enable":
        result = enable_night_mode()
        await callback.answer(result["message"])
        await night_mode_menu(callback)
    
    elif action == "disable":
        result = disable_night_mode()
        await callback.answer(result["message"])
        await night_mode_menu(callback)
    
    elif action == "settings":
        await callback.message.edit_text(
            "⚙️ Настройки ночного режима\n\n"
            "Введите час начала ночного режима (0-23):",
            reply_markup=get_back_keyboard()
        )
        await state.set_state(NightModeSettings.waiting_start_hour)
        await callback.answer()

@router.message(NightModeSettings.waiting_start_hour)
async def process_start_hour(message: Message, state: FSMContext):
    """Обработка часа начала ночного режима"""
    try:
        start_hour = int(message.text)
        if not (0 <= start_hour <= 23):
            await message.answer("❌ Часы должны быть от 0 до 23. Попробуйте снова:")
            return
        
        await state.update_data(start_hour=start_hour)
        await message.answer("Введите час окончания ночного режима (0-23):")
        await state.set_state(NightModeSettings.waiting_end_hour)
        
    except ValueError:
        await message.answer("❌ Введите число от 0 до 23:")

@router.message(NightModeSettings.waiting_end_hour)
async def process_end_hour(message: Message, state: FSMContext):
    """Обработка часа окончания ночного режима"""
    try:
        end_hour = int(message.text)
        if not (0 <= end_hour <= 23):
            await message.answer("❌ Часы должны быть от 0 до 23. Попробуйте снова:")
            return
        
        data = await state.get_data()
        start_hour = data["start_hour"]
        
        from services.night_mode import update_night_mode_settings
        result = update_night_mode_settings(start_hour, end_hour)
        
        await message.answer(result["message"], reply_markup=get_main_menu_keyboard())
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Введите число от 0 до 23:")

@router.callback_query(F.data == "mailing_history")
async def show_mailing_history(callback: CallbackQuery):
    """Показывает историю рассылок"""
    history = await mailing_service.get_mailing_history()
    
    if not history:
        text = "📋 История рассылки\n\nИстория пуста."
    else:
        text = "📋 История рассылок:\n\n"
        for i, item in enumerate(history, 1):
            text += f"{i}. {item['sent_at']}\n"
            text += f"   Текст: {item['text']}\n"
            text += f"   Аккаунт: {item['account_name']}\n"
            text += f"   Группа: {item['group_title']}\n\n"
    
    await callback.message.edit_text(text, reply_markup=get_back_keyboard())
    await callback.answer()

@router.callback_query(F.data == "mailings_list")
async def show_mailings_list(callback: CallbackQuery):
    """Показывает список всех рассылок"""
    try:
        # Используем базу данных напрямую вместо сервиса
        with next_get_db() as db:
            from database.models import Mailing, Account
            mailings = db.query(Mailing).join(Account).all()
        
        if not mailings:
            text = "📋 Список рассылок\n\nРассылок пока нет."
        else:
            text = f"📋 Список рассылок ({len(mailings)}):\n\n"
            for i, mailing in enumerate(mailings, 1):
                status_emoji = "✅" if mailing.is_active else "❌"
                text += f"{i}. {status_emoji} ID: {mailing.id}\n"
                text += f"   Аккаунт: {mailing.account.phone}\n"
                text += f"   Создано: {mailing.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        
        await callback.message.edit_text(text, reply_markup=get_back_keyboard())
        await callback.answer()
        
    except Exception as e:
        await callback.message.edit_text(
            "❌ Ошибка при получении списка рассылок\n\n"
            "Попробуйте позже или обратитесь к администратору.",
            reply_markup=get_back_keyboard()
        )
        await callback.answer()



@router.callback_query(F.data == "help")
async def show_help(callback: CallbackQuery):
    """Показывает справку по использованию бота"""
    help_text = (
        f"❓ **СПРАВКА ПО ИСПОЛЬЗОВАНИЮ БОТА**\n\n"
        f"🚀 **Быстрая рассылка** - Запуск рассылки с выбором аккаунта, текстов и групп\n"
        f"👤 **Мои аккаунты** - Просмотр подключенных аккаунтов и управление ими\n"
        f"📋 **История рассылок** - Просмотр всех выполненных рассылок\n"
        f"🔧 **Админ-панель** - Расширенные функции администратора\n"
        f"📊 **Статистика** - Детальная статистика по рассылкам\n\n"
        f"🎯 **КАК СОЗДАТЬ РАССЫЛКУ:**\n"
        f"1. Выберите 'Быстрая рассылка' или перейдите в аккаунт\n"
        f"2. Укажите количество вариантов текста (1-5)\n"
        f"3. Введите тексты для рассылки\n"
        f"4. Выберите группы с помощью чекбоксов ✅\n"
        f"5. Подтвердите и запустите рассылку\n\n"
        f"🎲 **ВАРИАТИВНОСТЬ ТЕКСТОВ:**\n"
        f"• Несколько текстов помогают избежать блокировки\n"
        f"• Тексты выбираются случайно для каждой группы\n"
        f"• Рекомендуется использовать 2-3 варианта\n\n"
        f"⚡ **ПОЛЕЗНЫЕ ФУНКЦИИ:**\n"
        f"• ✅ Выбрать все группы\n"
        f"• ❌ Снять выбор со всех групп\n"
        f"• 🔄 Обновить список групп\n"
        f"• 📊 Просмотр статистики в реальном времени\n\n"
        f"💡 **СОВЕТЫ:**\n"
        f"• Используйте задержки между сообщениями\n"
        f"• Проверяйте статистику после рассылки\n"
        f"• Обновляйте списки групп регулярно"
    )
    
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"))
    builder.add(InlineKeyboardButton(text="🚀 Быстрая рассылка", callback_data="quick_spam"))
    builder.adjust(2)
    
    await callback.message.edit_text(help_text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "main_menu")
async def back_to_main_menu(callback: CallbackQuery):
    """Возвращает в главное меню"""
    welcome_text = f"🏠 **ГЛАВНОЕ МЕНЮ**\n\n👋 Добро пожаловать, {callback.from_user.first_name}!\n\nВыберите действие:"
    await callback.message.edit_text(welcome_text, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "quick_spam")
async def quick_spam_menu(callback: CallbackQuery):
    """Быстрое меню для рассылки"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️ У вас нет доступа к этой функции.", show_alert=True)
        return
    
    with next_get_db() as db:
        accounts = db.query(Account).all()
    
    if not accounts:
        await callback.message.edit_text(
            "❌ **НЕТ АККАУНТОВ**\n\n"
            "Сначала добавьте аккаунты через раздел 'Мои аккаунты'.",
            reply_markup=get_persistent_keyboard(),
            parse_mode="Markdown"
        )
        await callback.answer()
        return
    
    text = (
        f"🚀 **БЫСТРАЯ РАССЫЛКА**\n\n"
        f"📱 Доступно аккаунтов: {len(accounts)}\n\n"
        f"Выберите аккаунт для рассылки:"
    )
    
    builder = InlineKeyboardBuilder()
    for account in accounts:
        with next_get_db() as db:
            groups_count = db.query(Group).filter(Group.account_id == account.id).count()
        
        builder.add(InlineKeyboardButton(
            text=f"📱 {account.phone} ({groups_count} групп)",
            callback_data=f"admin_spam_from:{account.id}"
        ))
    
    builder.add(InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"))
    builder.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("mailing_details:"))
async def show_mailing_details(callback: CallbackQuery):
    """Показывает детали рассылки"""
    mailing_id = int(callback.data.split(":")[1])
    details = await mailing_service.get_mailing_details(mailing_id)
    
    if not details:
        await callback.answer("❌ Рассылка не найдена")
        return
    
    text = f"📋 Детали рассылки #{details['id']}\n\n"
    text += f"Статус: {details['status']}\n"
    text += f"Аккаунт: {details['account_name']}\n"
    text += f"Группа: {details['group_title']}\n"
    text += f"Тип: {details['mailing_type']}\n"
    text += f"Интервал: {details['min_interval']}-{details['max_interval']} мин\n"
    text += f"Отправлено сообщений: {details['sent_count']}\n"
    text += f"Создана: {details['created_at']}\n\n"
    text += f"Текст:\n{details['text']}"
    
    await callback.message.edit_text(
        text, 
        reply_markup=get_mailing_details_keyboard(mailing_id, details['is_active'])
    )
    await callback.answer()

@router.callback_query(F.data.startswith("stop_mailing:"))
async def stop_single_mailing(callback: CallbackQuery):
    """Останавливает конкретную рассылку"""
    mailing_id = int(callback.data.split(":")[1])
    result = await mailing_service.stop_mailing(mailing_id)
    await callback.answer(result["message"])
    
    # Обновляем детали рассылки
    await show_mailing_details(callback)

@router.callback_query(F.data.startswith("start_mailing:"))
async def start_single_mailing(callback: CallbackQuery):
    """Запускает конкретную рассылку"""
    mailing_id = int(callback.data.split(":")[1])
    result = await mailing_service.start_mailing(mailing_id)
    await callback.answer(result["message"])
    
    # Обновляем детали рассылки
    await show_mailing_details(callback)

@router.callback_query(F.data.startswith("delete_mailing:"))
async def delete_single_mailing(callback: CallbackQuery):
    """Удаляет конкретную рассылку"""
    mailing_id = int(callback.data.split(":")[1])
    
    try:
        async with get_async_db() as db:
            # Удаляем историю рассылки
            await db.execute(
                delete(MailingHistory).filter(MailingHistory.mailing_id == mailing_id)
            )
            
            # Удаляем рассылку
            await db.execute(
                delete(Mailing).filter(Mailing.id == mailing_id)
            )
            
            await db.commit()
        
        await callback.answer("✅ Рассылка удалена")
        # Возвращаемся в главное меню
        welcome_text = f"👋 Добро пожаловать, {callback.from_user.first_name}!\n\nВыберите действие:"
        await callback.message.edit_text(welcome_text, reply_markup=get_main_menu_keyboard())
        
    except Exception as e:
        print(f"❌ Ошибка при удалении рассылки: {e}")
        await callback.answer("❌ Ошибка при удалении рассылки")

@router.callback_query(F.data == "broadcast_all")
async def broadcast_all_menu(callback: CallbackQuery):
    """Меню рассылки во все аккаунты"""
    from handlers.mailing import start_mailing_setup
    await start_mailing_setup(callback, None, True)

@router.callback_query(F.data == "stop_broadcast_all")
async def stop_broadcast_all(callback: CallbackQuery):
    """Останавливает все рассылки"""
    result = await mailing_service.stop_broadcast_all()
    await callback.answer(result["message"])
    
    # Возвращаемся в главное меню только если сообщение изменилось
    try:
        welcome_text = f"👋 Добро пожаловать, {callback.from_user.first_name}!\n\nВыберите действие:"
        await callback.message.edit_text(welcome_text, reply_markup=get_main_menu_keyboard())
    except Exception as e:
        if "message is not modified" not in str(e):
            raise e 

@router.callback_query(F.data == "back")
async def back_handler(callback: CallbackQuery, state: FSMContext):
    """Универсальный обработчик кнопки 'Назад' / Universal 'Back' button handler"""
    # Очищаем состояние FSM
    await state.clear()
    
    # Возвращаемся в главное меню
    welcome_text = (
        f"👋 Добро пожаловать, {callback.from_user.first_name}!\n\n"
        f"Выберите действие:\n\n"
        f"👋 Welcome, {callback.from_user.first_name}!\n\n"
        f"Choose an action:"
    )
    await callback.message.edit_text(welcome_text, reply_markup=get_main_menu_keyboard())
    await callback.answer()

@router.callback_query(F.data == "accounts")
async def accounts_handler(callback: CallbackQuery):
    """Обработчик кнопки 'К аккаунтам' / 'To accounts' button handler"""
    # Перенаправляем к списку аккаунтов
    from handlers.accounts import my_accounts
    await my_accounts(callback)

@router.callback_query(F.data == "groups")
async def groups_handler(callback: CallbackQuery):
    """Обработчик кнопки 'К группам' / 'To groups' button handler"""
    # Возвращаемся в главное меню, так как нет общего списка групп
    welcome_text = (
        f"👋 Группы доступны через аккаунты\n\n"
        f"Выберите 'Мои аккаунты' для просмотра групп\n\n"
        f"👋 Groups are available through accounts\n\n"
        f"Select 'My accounts' to view groups"
    )
    await callback.message.edit_text(welcome_text, reply_markup=get_main_menu_keyboard())
    await callback.answer()