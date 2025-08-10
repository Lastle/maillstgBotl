from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from utils.keyboards import get_main_menu_keyboard, get_account_menu_keyboard, get_back_keyboard, get_cancel_keyboard
from services.auth_service import auth_service
from services.mailing_service import mailing_service
from database.models import Account, Group, Mailing
from database.database import get_db
from config import ADMIN_IDS

router = Router()

class AccountAuth(StatesGroup):
    waiting_phone = State()
    waiting_code = State()
    waiting_password = State()

@router.callback_query(F.data == "add_account")
async def add_account_start(callback: CallbackQuery, state: FSMContext):
    """Начинает процесс добавления аккаунта"""
    await callback.message.edit_text(
        "📱 Добавление аккаунта\n\n"
        "Введите номер телефона аккаунта в формате:\n"
        "+79000000000",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AccountAuth.waiting_phone)
    await callback.answer()

@router.callback_query(F.data == "cancel_operation")
async def cancel_operation(callback: CallbackQuery, state: FSMContext):
    """Отменяет текущую операцию"""
    await state.clear()
    welcome_text = f"👋 Добро пожаловать, {callback.from_user.first_name}!\n\nОперация отменена. Выберите действие:"
    await callback.message.edit_text(welcome_text, reply_markup=get_main_menu_keyboard())
    await callback.answer("Операция отменена")


@router.message(AccountAuth.waiting_phone)
async def process_phone(message: Message, state: FSMContext):
    """Обработка номера телефона"""
    phone = message.text.strip()
    
    # Используем глобальные API credentials
    from config import TELEGRAM_API_ID, TELEGRAM_API_HASH
    
    # Отправляем код подтверждения с глобальными API credentials
    result = await auth_service.start_auth(message.from_user.id, phone, TELEGRAM_API_ID, TELEGRAM_API_HASH)
    
    if result["success"]:
        await message.answer(result["message"], reply_markup=get_cancel_keyboard())
        await state.set_state(AccountAuth.waiting_code)
    else:
        error_msg = result.get("error", "Неизвестная ошибка")
        await message.answer(f"❌ {error_msg}\n\nПопробуйте снова:", reply_markup=get_cancel_keyboard())
        await state.set_state(AccountAuth.waiting_phone)

@router.message(AccountAuth.waiting_code)
async def process_code(message: Message, state: FSMContext):
    """Обработка кода подтверждения"""
    code = message.text.strip()
    
    result = await auth_service.verify_code(message.from_user.id, code)
    
    if result["success"]:
        await message.answer(result["message"], reply_markup=get_main_menu_keyboard())
        await state.clear()
    else:
        # Проверяем, есть ли ключ "message" в результате
        if "message" in result and "пароль" in result["message"].lower():
            await message.answer(result["message"], reply_markup=get_cancel_keyboard())
            await state.set_state(AccountAuth.waiting_password)
        else:
            error_msg = result.get("error", "Неизвестная ошибка")
            
            # Если код истек или нужно начать заново, перенаправляем на начало
            if any(keyword in error_msg.lower() for keyword in ["истек", "заново", "сброшена", "ограничил"]):
                from aiogram.utils.keyboard import InlineKeyboardBuilder
                builder = InlineKeyboardBuilder()
                builder.add(InlineKeyboardButton(text="🔄 Начать заново", callback_data="add_account"))
                builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_operation"))
                builder.adjust(1)
                
                await message.answer(f"❌ {error_msg}\n\nНачните процесс добавления аккаунта заново:", reply_markup=builder.as_markup())
                await state.clear()
            else:
                await message.answer(f"❌ {error_msg}\n\nПопробуйте снова:", reply_markup=get_cancel_keyboard())
                await state.set_state(AccountAuth.waiting_code)

@router.message(AccountAuth.waiting_password)
async def process_password(message: Message, state: FSMContext):
    """Обработка пароля двухфакторной аутентификации"""
    password = message.text.strip()
    
    result = await auth_service.verify_password(message.from_user.id, password)
    
    if result["success"]:
        await message.answer(result["message"], reply_markup=get_main_menu_keyboard())
        await state.clear()
    else:
        error_msg = result.get("error", "Неизвестная ошибка")
        
        # Если есть серьезная ошибка, перенаправляем на начало
        if any(keyword in error_msg.lower() for keyword in ["ограничил", "заново", "сброшена"]):
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            builder = InlineKeyboardBuilder()
            builder.add(InlineKeyboardButton(text="🔄 Начать заново", callback_data="add_account"))
            builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_operation"))
            builder.adjust(1)
            
            await message.answer(f"❌ {error_msg}\n\nНачните процесс добавления аккаунта заново:", reply_markup=builder.as_markup())
            await state.clear()
        else:
            await message.answer(f"❌ {error_msg}\n\nПопробуйте снова:", reply_markup=get_cancel_keyboard())
            await state.set_state(AccountAuth.waiting_password)

@router.callback_query(F.data == "my_accounts")
async def show_accounts(callback: CallbackQuery):
    """Показывает список аккаунтов"""
    with next(get_db()) as db:
        accounts = db.query(Account).filter(Account.is_active == True).all()
    
    if not accounts:
        text = "👤 Мои аккаунты\n\nУ вас нет добавленных аккаунтов."
        await callback.message.edit_text(text, reply_markup=get_back_keyboard())
    else:
        text = "👤 Мои аккаунты:\n\n"
        for i, account in enumerate(accounts, 1):
            text += f"{i}. {account.name} ({account.phone})\n"
        
        # Создаем клавиатуру с кнопками для каждого аккаунта
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.types import InlineKeyboardButton
        
        builder = InlineKeyboardBuilder()
        for account in accounts:
            builder.add(InlineKeyboardButton(
                text=f"👤 {account.name}",
                callback_data=f"account_menu:{account.id}"
            ))
        builder.add(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="back_to_main"
        ))
        builder.adjust(1)
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
    
    await callback.answer()

@router.callback_query(F.data.startswith("account_menu:"))
async def account_menu(callback: CallbackQuery):
    """Меню конкретного аккаунта"""
    account_id = int(callback.data.split(":")[1])
    
    with next(get_db()) as db:
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            await callback.answer("❌ Аккаунт не найден")
            return
        

        # Получаем информацию о группах
        groups = db.query(Group).filter(Group.account_id == account_id).all()
        groups_text = f"У пользователя {len(groups)} групп." if groups else "У пользователя нет групп."
        
        # Получаем статус рассылки
        from database.models import Mailing
        active_mailings = db.query(Mailing).filter(
            Mailing.account_id == account_id,
            Mailing.is_active == True
        ).count()
        
        text = f"Меню для аккаунта {account.name}:\n\n"
        text += f"📊 Массовая рассылка: {'🟢 ВКЛ' if active_mailings > 0 else '🔴 ВЫКЛ'}\n"
        text += f"👤 Имя: {account.name}\n"
        text += f"📱 Номер: {account.phone}\n\n"
        text += f"📋 Список групп:\n{groups_text}"
    
    await callback.message.edit_text(text, reply_markup=get_account_menu_keyboard(account_id))
    await callback.answer()

@router.callback_query(F.data.startswith("delete_account:"))
async def delete_account(callback: CallbackQuery):
    """Удаляет аккаунт"""
    account_id = int(callback.data.split(":")[1])
    
    try:
        from services.mailing_service import mailing_service
        from database.database import get_async_db
        from sqlalchemy import select
        
        async with get_async_db() as db:
            # Получаем аккаунт
            account_result = await db.execute(
                select(Account).filter(Account.id == account_id)
            )
            account = account_result.scalar_one_or_none()
            
            if not account:
                await callback.answer("❌ Аккаунт не найден")
                return
            
            # Останавливаем все рассылки этого аккаунта
            from database.models import Mailing
            mailings_result = await db.execute(
                select(Mailing).filter(
                    Mailing.account_id == account_id,
                    Mailing.is_active == True
                )
            )
            active_mailings = mailings_result.scalars().all()
            
            for mailing in active_mailings:
                await mailing_service.stop_mailing(mailing.id)
            
            # Получаем группы аккаунта
            groups_result = await db.execute(
                select(Group).filter(Group.account_id == account_id)
            )
            groups = groups_result.scalars().all()
            
            # Удаляем в правильном порядке (сначала зависимые записи)
            for group in groups:
                # Удаляем историю рассылок для этой группы
                from database.models import MailingHistory
                await db.execute(
                    select(MailingHistory).filter(MailingHistory.group_id == group.id)
                )
                history_result = await db.execute(
                    select(MailingHistory).filter(MailingHistory.group_id == group.id)
                )
                history_records = history_result.scalars().all()
                for history in history_records:
                    await db.delete(history)
                
                # Удаляем рассылки для этой группы
                group_mailings_result = await db.execute(
                    select(Mailing).filter(Mailing.group_id == group.id)
                )
                group_mailings = group_mailings_result.scalars().all()
                for mailing in group_mailings:
                    await db.delete(mailing)
                
                # Теперь удаляем саму группу
                await db.delete(group)
            
            # Удаляем аккаунт
            await db.delete(account)
            await db.commit()
            
            await callback.answer("✅ Аккаунт удален")
        
        # Возвращаемся в главное меню
        welcome_text = f"👋 Добро пожаловать, {callback.from_user.first_name}!\n\nВыберите действие:"
        await callback.message.edit_text(welcome_text, reply_markup=get_main_menu_keyboard())
        
    except Exception as e:
        print(f"❌ Ошибка при удалении аккаунта: {e}")
        await callback.answer("❌ Ошибка при удалении аккаунта") 