from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import os

from utils.keyboards import (
    get_main_menu_keyboard, get_mailing_type_keyboard, 
    get_photo_attachment_keyboard, get_back_keyboard
)
from services.mailing_service import mailing_service
from database.models import Account, Group, Mailing
from database.database import get_db, next_get_db
from config import ADMIN_IDS, MAX_PHOTO_SIZE

router = Router()

class MailingSetup(StatesGroup):
    waiting_text = State()
    waiting_min_interval = State()
    waiting_max_interval = State()
    waiting_photo_choice = State()
    waiting_photo = State()

@router.callback_query(F.data.startswith("start_mailing_all:"))
async def start_mailing_all(callback: CallbackQuery):
    """Начинает рассылку во все группы аккаунта"""
    account_id = int(callback.data.split(":")[1])
    await start_mailing_setup(callback, account_id, False)

async def start_mailing_setup(callback: CallbackQuery, account_id: int = None, broadcast_all: bool = False):
    """Настройка рассылки"""
    await callback.message.edit_text(
        "📧 Настройка рассылки\n\n"
        "Выберите режим отправки:",
        reply_markup=get_mailing_type_keyboard()
    )
    
    # Сохраняем данные в контексте
    await callback.answer()
    return

@router.callback_query(F.data.startswith("mailing_type:"))
async def process_mailing_type(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора типа рассылки"""
    mailing_type = callback.data.split(":")[1]
    
    await state.update_data(mailing_type=mailing_type)
    
    await callback.message.edit_text(
        "📝 Пришлите текст рассылки, потом спрошу границы интервала:",
        reply_markup=get_back_keyboard()
    )
    await state.set_state(MailingSetup.waiting_text)
    await callback.answer()

@router.message(MailingSetup.waiting_text)
async def process_mailing_text(message: Message, state: FSMContext):
    """Обработка текста рассылки"""
    text = message.text.strip()
    
    if not text:
        await message.answer("❌ Текст не может быть пустым. Попробуйте снова:")
        return
    
    await state.update_data(text=text)
    
    data = await state.get_data()
    mailing_type = data.get("mailing_type")
    
    if mailing_type == "fixed":
        await message.answer("⏰ Введите интервал в минутах:")
        await state.set_state(MailingSetup.waiting_min_interval)
    else:  # random
        await message.answer("⏰ Минимальный интервал (мин):")
        await state.set_state(MailingSetup.waiting_min_interval)

@router.message(MailingSetup.waiting_min_interval)
async def process_min_interval(message: Message, state: FSMContext):
    """Обработка минимального интервала"""
    try:
        min_interval = int(message.text)
        if min_interval <= 0:
            await message.answer("❌ Интервал должен быть больше 0. Попробуйте снова:")
            return
        
        await state.update_data(min_interval=min_interval)
        
        data = await state.get_data()
        mailing_type = data.get("mailing_type")
        
        if mailing_type == "fixed":
            # Для фиксированного интервала используем тот же интервал
            await state.update_data(max_interval=min_interval)
            await message.answer(
                "📷 Хотите прикрепить фото к сообщению?",
                reply_markup=get_photo_attachment_keyboard()
            )
            await state.set_state(MailingSetup.waiting_photo_choice)
        else:  # random
            await message.answer("⏰ Максимальный интервал (мин):")
            await state.set_state(MailingSetup.waiting_max_interval)
            
    except ValueError:
        await message.answer("❌ Введите число. Попробуйте снова:")
    except Exception as e:
        await message.answer("❌ Произошла ошибка. Попробуйте начать заново.")
        await state.clear()

@router.message(MailingSetup.waiting_max_interval)
async def process_max_interval(message: Message, state: FSMContext):
    """Обработка максимального интервала"""
    try:
        max_interval = int(message.text)
        if max_interval <= 0:
            await message.answer("❌ Интервал должен быть больше 0. Попробуйте снова:")
            return
        
        data = await state.get_data()
        min_interval = data.get("min_interval")
        
        if max_interval < min_interval:
            await message.answer("❌ Максимальный интервал должен быть больше минимального. Попробуйте снова:")
            return
        
        await state.update_data(max_interval=max_interval)
        
        await message.answer(
            "📷 Хотите прикрепить фото к сообщению?",
            reply_markup=get_photo_attachment_keyboard()
        )
        await state.set_state(MailingSetup.waiting_photo_choice)
            
    except ValueError:
        await message.answer("❌ Введите число. Попробуйте снова:")
    except Exception as e:
        await message.answer("❌ Произошла ошибка. Попробуйте начать заново.")
        await state.clear()



@router.callback_query(F.data.startswith("photo_attachment:"))
async def process_photo_attachment(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора прикрепления фото"""
    attachment_type = callback.data.split(":")[1]
    
    if attachment_type == "text_only":
        await state.update_data(photo_path=None, mailing_type="text")
        await start_mailing(callback, state)
        return  # Важно! Прерываем выполнение, чтобы не вызывать callback.answer()
    elif attachment_type == "only_photo":
        await callback.message.edit_text(
            "📷 Отправьте фото:",
            reply_markup=get_back_keyboard()
        )
        await state.set_state(MailingSetup.waiting_photo)
        await state.update_data(photo_type="only_photo")
    elif attachment_type == "with_text":
        await callback.message.edit_text(
            "📷 Отправьте фото:",
            reply_markup=get_back_keyboard()
        )
        await state.set_state(MailingSetup.waiting_photo)
        await state.update_data(photo_type="with_text")
    
    await callback.answer()

@router.message(MailingSetup.waiting_photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    """Обработка загруженного фото"""
    photo = message.photo[-1]  # Берем самое большое фото
    
    if photo.file_size > MAX_PHOTO_SIZE:
        await message.answer(f"❌ Фото слишком большое. Максимальный размер: {MAX_PHOTO_SIZE // (1024*1024)}MB")
        return
    
    # Создаем папку для фото если её нет
    os.makedirs("photos", exist_ok=True)
    
    # Сохраняем фото
    photo_path = f"photos/{photo.file_id}.jpg"
    await message.bot.download(photo, photo_path)
    
    data = await state.get_data()
    photo_type = data.get("photo_type")
    
    if photo_type == "only_photo":
        await state.update_data(photo_path=photo_path, mailing_type="photo")
    else:  # with_text
        await state.update_data(photo_path=photo_path, mailing_type="photo_with_text")
    
    await start_mailing(message, state)

async def start_mailing(callback_or_message, state: FSMContext):
    """Запускает рассылку"""
    data = await state.get_data()
    
    text = data.get("text")
    mailing_type = data.get("mailing_type")
    min_interval = data.get("min_interval")
    max_interval = data.get("max_interval")
    photo_path = data.get("photo_path")
    
    # Определяем тип интервала
    interval_type = "fixed" if min_interval == max_interval else "random"
    
    # Запускаем рассылку
    result = await mailing_service.start_broadcast_all(
        text=text,
        mailing_type=mailing_type,
        interval_type=interval_type,
        min_interval=min_interval,
        max_interval=max_interval,
        photo_path=photo_path
    )
    
    if result["success"]:
        interval_text = f"каждые {min_interval} мин" if interval_type == "fixed" else f"случайно каждые {min_interval}-{max_interval} мин"
        
        # Получаем информацию о ночном режиме
        from services.night_mode import get_night_mode_settings
        night_settings = get_night_mode_settings()
        night_info = ""
        if night_settings["is_enabled"]:
            night_info = f"\n🌙 Ночной режим: ВКЛ ({night_settings['start_hour']}:00-{night_settings['end_hour']}:00, x{night_settings['multiplier']})"
        
        # Проверяем тип объекта для правильного ответа
        if hasattr(callback_or_message, 'message'):
            # Это callback_query - редактируем сообщение
            await callback_or_message.message.edit_text(
                f"✅ {result['message']}\n\n"
                f"📝 Тип рассылки: {mailing_type}\n"
                f"⏰ Интервал: {interval_text}\n"
                f"🔄 Рассылка работает в фоновом режиме\n"
                f"📊 Следите за историей рассылок{night_info}",
                reply_markup=get_main_menu_keyboard()
            )
        else:
            # Это message - отправляем новое сообщение
            await callback_or_message.answer(
                f"✅ {result['message']}\n\n"
                f"📝 Тип рассылки: {mailing_type}\n"
                f"⏰ Интервал: {interval_text}\n"
                f"🔄 Рассылка работает в фоновом режиме\n"
                f"📊 Следите за историей рассылок{night_info}",
                reply_markup=get_main_menu_keyboard()
            )
    else:
        await callback_or_message.answer(
            f"❌ {result['error']}",
            reply_markup=get_main_menu_keyboard()
        )
    
    await state.clear()

@router.callback_query(F.data.startswith("stop_mailing_all:"))
async def stop_mailing_all(callback: CallbackQuery):
    """Останавливает рассылку аккаунта"""
    account_id = int(callback.data.split(":")[1])
    
    with next_get_db() as db:
        active_mailings = db.query(Mailing).filter(
            Mailing.account_id == account_id,
            Mailing.is_active == True
        ).all()
        
        stopped_count = 0
        for mailing in active_mailings:
            result = await mailing_service.stop_mailing(mailing.id)
            if result["success"]:
                stopped_count += 1
    
    await callback.answer(f"Остановлено {stopped_count} рассылок")
    
    # Возвращаемся в меню аккаунта
    from handlers.accounts import account_menu
    await account_menu(callback) 