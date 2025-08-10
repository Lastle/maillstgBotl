from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from utils.keyboards import get_main_menu_keyboard, get_night_mode_keyboard, get_back_keyboard, get_mailings_list_keyboard, get_mailing_details_keyboard
from services.night_mode import get_night_mode_status, enable_night_mode, disable_night_mode
from services.mailing_service import mailing_service
from database.database import get_async_db
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
    print(f"🔍 Обработчик списка рассылок вызван")
    try:
        mailings = await mailing_service.get_all_mailings()
        print(f"📋 Получено рассылок: {len(mailings)}")
        
        if not mailings:
            text = "📋 Список рассылок\n\nРассылок пока нет."
        else:
            text = f"📋 Список рассылок ({len(mailings)}):\n\n"
            for i, mailing in enumerate(mailings, 1):
                text += f"{i}. {mailing['status']}\n"
                text += f"   Аккаунт: {mailing['account_name']}\n"
                text += f"   Группа: {mailing['group_title']}\n"
                text += f"   Тип: {mailing['mailing_type']}\n"
                text += f"   Интервал: {mailing['min_interval']}-{mailing['max_interval']} мин\n"
                text += f"   Создана: {mailing['created_at']}\n\n"
        
        await callback.message.edit_text(
            text, 
            reply_markup=get_mailings_list_keyboard(mailings)
        )
        await callback.answer()
        
    except Exception as e:
        print(f"❌ Ошибка в show_mailings_list: {e}")
        await callback.answer("❌ Ошибка при получении списка рассылок")



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