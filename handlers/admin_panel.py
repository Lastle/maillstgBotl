import asyncio
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from telethon import TelegramClient
from telethon.errors import FloodWaitError, ChatAdminRequiredError

from config import ADMIN_IDS, TELEGRAM_API_ID, TELEGRAM_API_HASH
from database.database import get_db, next_get_db, SessionLocal
from database.models import Account, Group, MessageLog, Mailing
from utils.keyboards import get_main_menu_keyboard, get_back_keyboard, get_persistent_keyboard, get_group_selection_keyboard, get_text_variants_keyboard

router = Router()

class AdminSpamStates(StatesGroup):
    waiting_message = State()
    waiting_mass_message = State()
    selecting_groups = State()
    waiting_text_variants = State()
    waiting_text_variant = State()
    selecting_text_count = State()

@router.callback_query(F.data == "admin_panel")
async def admin_panel_menu(callback: CallbackQuery):
    """Главное меню админ-панели"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️ У вас нет доступа к админ-панели", show_alert=True)
        return
    
    # Получаем статистику
    db = SessionLocal()
    try:
        total_accounts = db.query(Account).count()
        active_mailings = db.query(Mailing).filter(Mailing.status == 'running').count()
        
        text = (
            "🔧 **АДМИН-ПАНЕЛЬ**\n\n"
            f"📊 Статистика:\n"
            f"   • Подключенных аккаунтов: {total_accounts}\n"
            f"   • Активных рассылок: {active_mailings}\n\n"
            "Выберите действие:"
        )
    except Exception as e:
        text = f"❌ Ошибка получения данных: {str(e)}"
    finally:
        db.close()
    
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="📱 Все аккаунты и номера", callback_data="admin_all_accounts"))
    builder.add(InlineKeyboardButton(text="🎯 Массовый спам по группам", callback_data="admin_mass_spam"))
    builder.add(InlineKeyboardButton(text="📊 Статистика рассылок", callback_data="admin_stats"))
    builder.add(InlineKeyboardButton(text="⬅️ Назад в главное меню", callback_data="back_to_main"))
    builder.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "admin_all_accounts")
async def show_all_accounts(callback: CallbackQuery):
    """Показывает все подключенные аккаунты с номерами"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    db = SessionLocal()
    try:
        accounts = db.query(Account).all()
        
        if not accounts:
            text = "📱 **ВСЕ АККАУНТЫ**\n\nПодключенных аккаунтов нет."
            builder = InlineKeyboardBuilder()
            builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel"))
            await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
            await callback.answer()
            return
        
        text = "📱 **ВСЕ ПОДКЛЮЧЕННЫЕ АККАУНТЫ**\n\n"
        
        builder = InlineKeyboardBuilder()
        
        for i, account in enumerate(accounts, 1):
            # Получаем количество групп для каждого аккаунта
            groups_count = get_account_groups_count(account.id)
            
            account_info = (
                f"{i}. **{account.name or 'Без имени'}**\n"
                f"   📞 Номер: `{account.phone}`\n"
                f"   🆔 ID: `{account.tg_id}`\n"
                f"   🏘️ Групп: {groups_count}\n"
            )
            text += account_info + "\n"
            
            # Добавляем кнопки для каждого аккаунта
            builder.add(InlineKeyboardButton(
                text=f"📋 {account.phone} ({groups_count} групп)", 
                callback_data=f"admin_account_details:{account.id}"
            ))
        
        builder.add(InlineKeyboardButton(text="🎯 Массовый спам", callback_data="admin_mass_spam"))
        builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel"))
        builder.adjust(1)
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
        await callback.answer()
        
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)
    finally:
        db.close()

@router.callback_query(F.data.startswith("admin_account_details:"))
async def show_account_details(callback: CallbackQuery):
    """Показывает детали конкретного аккаунта и его группы"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    account_id = int(callback.data.split(":")[1])
    
    with next_get_db() as db:
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            await callback.answer("❌ Аккаунт не найден", show_alert=True)
            return
        
        # Получаем группы аккаунта из базы данных
        groups = db.query(Group).filter(Group.account_id == account_id).all()
    
    # Подсчитываем группы и каналы
    group_count = len([g for g in groups if g.type == 'group'])
    channel_count = len([g for g in groups if g.type == 'channel'])
    
    text = (
        f"📱 **АККАУНТ: {account.name or 'Без имени'}**\n\n"
        f"📞 Номер: `{account.phone}`\n"
        f"🆔 Telegram ID: `{account.tg_id}`\n"
        f"🏘️ Групп: {group_count} | Каналов: {channel_count}\n"
        f"📊 Всего: {len(groups)}\n\n"
    )
    
    if groups:
        text += "**ГРУППЫ И КАНАЛЫ:**\n"
        for i, group in enumerate(groups[:15], 1):  # Показываем первые 15 групп
            group_type = "📢" if group.type == 'channel' else "👥"
            group_name = group.name[:25] + "..." if len(group.name) > 25 else group.name
            text += f"{i}. {group_type} {group_name}\n"
            text += f"   ID: `{group.tg_id}`\n"
        
        if len(groups) > 15:
            text += f"\n... и еще {len(groups) - 15} групп/каналов"
    else:
        text += "❌ Групп не найдено"
    
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text=f"🚀 Спам с {account.phone}", 
        callback_data=f"admin_spam_from:{account_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="🔄 Обновить список групп", 
        callback_data=f"admin_update_groups:{account_id}"
    ))
    builder.add(InlineKeyboardButton(text="⬅️ Назад к аккаунтам", callback_data="admin_all_accounts"))
    builder.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("admin_update_groups:"))
async def update_account_groups(callback: CallbackQuery):
    """Обновляет список групп для конкретного аккаунта"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    account_id = int(callback.data.split(":")[1])
    
    with next_get_db() as db:
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            await callback.answer("❌ Аккаунт не найден", show_alert=True)
            return
    
    await callback.answer("🔄 Обновляем список групп...")
    
    try:
        # Подключаемся к Telegram и обновляем группы
        client = TelegramClient(account.session_path, TELEGRAM_API_ID, TELEGRAM_API_HASH)
        await client.connect()
        
        if await client.is_user_authorized():
            # Получаем диалоги
            dialogs = await client.get_dialogs()
            
            # Очищаем старые группы
            with next_get_db() as db:
                db.query(Group).filter(Group.account_id == account_id).delete()
                
                # Добавляем новые группы
                groups_count = 0
                channels_count = 0
                
                for dialog in dialogs:
                    if dialog.is_group or dialog.is_channel:
                        group_type = 'group' if dialog.is_group else 'channel'
                        
                        group = Group(
                            account_id=account_id,
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
            
            await client.disconnect()
            
            # Показываем обновленную информацию
            await show_account_details(callback)
            
        else:
            await callback.message.edit_text(
                f"❌ Аккаунт {account.name} не авторизован в Telegram",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="⬅️ Назад", callback_data=f"admin_account_details:{account_id}")
                ]])
            )
    except Exception as e:
        await callback.message.edit_text(
            f"❌ Ошибка при обновлении групп: {str(e)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="⬅️ Назад", callback_data=f"admin_account_details:{account_id}")
            ]])
        )

@router.callback_query(F.data.startswith("admin_spam_from:"))
async def start_spam_from_account(callback: CallbackQuery, state: FSMContext):
    """Начинает процесс создания рассылки с конкретного аккаунта"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    account_id = int(callback.data.split(":")[1])
    
    with next_get_db() as db:
        account = db.query(Account).filter(Account.id == account_id).first()
        groups_count = db.query(Group).filter(Group.account_id == account_id).count()
    
    if not account:
        await callback.answer("❌ Аккаунт не найден", show_alert=True)
        return
    
    await state.update_data(selected_account_id=account_id)
    
    text = (
        f"🚀 **НАСТРОЙКА РАССЫЛКИ**\n"
        f"📞 Аккаунт: {account.phone}\n"
        f"🏘️ Доступно групп: {groups_count}\n\n"
        f"📝 **Шаг 1:** Сколько вариантов текста вы хотите использовать?\n\n"
        f"💡 **Подсказка:** Несколько вариантов текста помогают избежать блокировки и делают рассылку более естественной."
    )
    
    await callback.message.edit_text(text, reply_markup=get_text_variants_keyboard(), parse_mode="Markdown")
    await state.set_state(AdminSpamStates.selecting_text_count)
    await callback.answer()

@router.callback_query(F.data.startswith("text_variants:"))
async def select_text_variants(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает выбор количества вариантов текста"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    variants_count = int(callback.data.split(":")[1])
    await state.update_data(text_variants_count=variants_count, text_variants=[], current_variant=1)
    
    data = await state.get_data()
    account_id = data.get('selected_account_id')
    
    with next_get_db() as db:
        account = db.query(Account).filter(Account.id == account_id).first()
    
    text = (
        f"📝 **ВВОД ТЕКСТОВ ДЛЯ РАССЫЛКИ**\n"
        f"📞 Аккаунт: {account.phone}\n\n"
        f"📄 **Вариант 1 из {variants_count}**\n\n"
        f"Введите текст сообщения для рассылки:"
    )
    
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data="admin_panel"))
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await state.set_state(AdminSpamStates.waiting_text_variant)
    await callback.answer()

@router.message(AdminSpamStates.waiting_text_variant)
async def process_text_variant(message: Message, state: FSMContext):
    """Обрабатывает ввод варианта текста"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔️ Доступ запрещен")
        return
    
    data = await state.get_data()
    text_variants = data.get('text_variants', [])
    current_variant = data.get('current_variant', 1)
    variants_count = data.get('text_variants_count', 1)
    account_id = data.get('selected_account_id')
    
    # Добавляем текущий вариант
    text_variants.append(message.text)
    
    if current_variant < variants_count:
        # Запрашиваем следующий вариант
        next_variant = current_variant + 1
        await state.update_data(text_variants=text_variants, current_variant=next_variant)
        
        with next_get_db() as db:
            account = db.query(Account).filter(Account.id == account_id).first()
        
        text = (
            f"📝 **ВВОД ТЕКСТОВ ДЛЯ РАССЫЛКИ**\n"
            f"📞 Аккаунт: {account.phone}\n\n"
            f"📄 **Вариант {next_variant} из {variants_count}**\n\n"
            f"Введите следующий текст сообщения:"
        )
        
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data="admin_panel"))
        
        await message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    else:
        # Все тексты введены, переходим к выбору групп
        await state.update_data(text_variants=text_variants)
        await show_group_selection(message, state, account_id)

async def show_group_selection(message, state: FSMContext, account_id: int):
    """Показывает интерфейс выбора групп"""
    with next_get_db() as db:
        account = db.query(Account).filter(Account.id == account_id).first()
        groups = db.query(Group).filter(Group.account_id == account_id).all()
    
    if not groups:
        await message.answer(
            f"❌ **НЕТ ГРУПП**\n\n"
            f"📞 Аккаунт: {account.phone}\n"
            f"🏘️ У этого аккаунта нет групп для рассылки.\n\n"
            f"Сначала обновите список групп для этого аккаунта.",
            reply_markup=get_persistent_keyboard(),
            parse_mode="Markdown"
        )
        await state.clear()
        return
    
    data = await state.get_data()
    text_variants = data.get('text_variants', [])
    
    text = (
        f"🎯 **ВЫБОР ГРУПП ДЛЯ РАССЫЛКИ**\n"
        f"📞 Аккаунт: {account.phone}\n"
        f"📝 Вариантов текста: {len(text_variants)}\n"
        f"🏘️ Доступно групп: {len(groups)}\n\n"
        f"✅ Выберите группы для рассылки:\n"
        f"(Нажмите на группу чтобы выбрать/снять)"
    )
    
    await message.answer(
        text, 
        reply_markup=get_group_selection_keyboard(groups, set(), account_id),
        parse_mode="Markdown"
    )
    await state.set_state(AdminSpamStates.selecting_groups)

@router.callback_query(F.data.startswith("toggle_group:"))
async def toggle_group_selection(callback: CallbackQuery, state: FSMContext):
    """Переключает выбор группы (чекбокс)"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    parts = callback.data.split(":")
    group_id = int(parts[1])
    account_id = int(parts[2])
    
    data = await state.get_data()
    selected_groups = set(data.get('selected_groups', []))
    
    # Переключаем выбор группы
    if group_id in selected_groups:
        selected_groups.remove(group_id)
    else:
        selected_groups.add(group_id)
    
    await state.update_data(selected_groups=list(selected_groups))
    
    # Обновляем клавиатуру
    with next_get_db() as db:
        groups = db.query(Group).filter(Group.account_id == account_id).all()
        account = db.query(Account).filter(Account.id == account_id).first()
    
    text_variants = data.get('text_variants', [])
    text = (
        f"🎯 **ВЫБОР ГРУПП ДЛЯ РАССЫЛКИ**\n"
        f"📞 Аккаунт: {account.phone}\n"
        f"📝 Вариантов текста: {len(text_variants)}\n"
        f"🏘️ Доступно групп: {len(groups)}\n"
        f"✅ Выбрано групп: {len(selected_groups)}\n\n"
        f"✅ Выберите группы для рассылки:\n"
        f"(Нажмите на группу чтобы выбрать/снять)"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_group_selection_keyboard(groups, selected_groups, account_id),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("select_all_groups:"))
async def select_all_groups(callback: CallbackQuery, state: FSMContext):
    """Выбирает все группы"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    account_id = int(callback.data.split(":")[1])
    
    with next_get_db() as db:
        groups = db.query(Group).filter(Group.account_id == account_id).all()
        account = db.query(Account).filter(Account.id == account_id).first()
    
    selected_groups = {group.id for group in groups}
    await state.update_data(selected_groups=list(selected_groups))
    
    data = await state.get_data()
    text_variants = data.get('text_variants', [])
    
    text = (
        f"🎯 **ВЫБОР ГРУПП ДЛЯ РАССЫЛКИ**\n"
        f"📞 Аккаунт: {account.phone}\n"
        f"📝 Вариантов текста: {len(text_variants)}\n"
        f"🏘️ Доступно групп: {len(groups)}\n"
        f"✅ Выбрано групп: {len(selected_groups)} (ВСЕ)\n\n"
        f"✅ Все группы выбраны для рассылки!"
    )
    
    try:
        await callback.message.edit_text(
            text,
            reply_markup=get_group_selection_keyboard(groups, selected_groups, account_id),
            parse_mode="Markdown"
        )
    except Exception as e:
        # Игнорируем ошибку если сообщение не изменилось
        pass
    await callback.answer("✅ Все группы выбраны!")

@router.callback_query(F.data.startswith("deselect_all_groups:"))
async def deselect_all_groups(callback: CallbackQuery, state: FSMContext):
    """Снимает выбор со всех групп"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    account_id = int(callback.data.split(":")[1])
    
    with next_get_db() as db:
        groups = db.query(Group).filter(Group.account_id == account_id).all()
        account = db.query(Account).filter(Account.id == account_id).first()
    
    selected_groups = set()
    await state.update_data(selected_groups=list(selected_groups))
    
    data = await state.get_data()
    text_variants = data.get('text_variants', [])
    
    text = (
        f"🎯 **ВЫБОР ГРУПП ДЛЯ РАССЫЛКИ**\n"
        f"📞 Аккаунт: {account.phone}\n"
        f"📝 Вариантов текста: {len(text_variants)}\n"
        f"🏘️ Доступно групп: {len(groups)}\n"
        f"✅ Выбрано групп: 0\n\n"
        f"✅ Выберите группы для рассылки:\n"
        f"(Нажмите на группу чтобы выбрать/снять)"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_group_selection_keyboard(groups, selected_groups, account_id),
        parse_mode="Markdown"
    )
    await callback.answer("❌ Выбор снят со всех групп")

@router.callback_query(F.data.startswith("confirm_selected_groups:"))
async def confirm_selected_groups(callback: CallbackQuery, state: FSMContext):
    """Подтверждает выбранные группы и запускает рассылку"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    account_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    selected_groups = data.get('selected_groups', [])
    text_variants = data.get('text_variants', [])
    
    if not selected_groups:
        await callback.answer("❌ Выберите хотя бы одну группу!", show_alert=True)
        return
    
    if not text_variants:
        await callback.answer("❌ Нет текстов для рассылки!", show_alert=True)
        return
    
    with next_get_db() as db:
        account = db.query(Account).filter(Account.id == account_id).first()
        groups = db.query(Group).filter(Group.id.in_(selected_groups)).all()
    
    # Показываем подтверждение
    text = (
        f"🚀 **ПОДТВЕРЖДЕНИЕ РАССЫЛКИ**\n\n"
        f"📞 **Аккаунт:** {account.phone}\n"
        f"📝 **Вариантов текста:** {len(text_variants)}\n"
        f"🎯 **Выбрано групп:** {len(selected_groups)}\n\n"
        f"📄 **Тексты для рассылки:**\n"
    )
    
    for i, variant in enumerate(text_variants, 1):
        preview = variant[:50] + "..." if len(variant) > 50 else variant
        text += f"{i}. `{preview}`\n"
    
    text += f"\n🏘️ **Группы для рассылки:**\n"
    for i, group in enumerate(groups[:5], 1):
        text += f"{i}. {group.name[:30]}...\n"
    
    if len(groups) > 5:
        text += f"... и ещё {len(groups) - 5} групп\n"
    
    text += f"\n⚠️ **ВНИМАНИЕ!** Рассылка будет отправлена в {len(selected_groups)} групп с рандомизацией текстов.\n\nПодтвердите запуск:"
    
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text=f"🚀 ЗАПУСТИТЬ РАССЫЛКУ", 
        callback_data=f"execute_custom_spam:{account_id}"
    ))
    builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data="admin_panel"))
    builder.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("execute_custom_spam:"))
async def execute_custom_spam(callback: CallbackQuery, state: FSMContext):
    """Запускает кастомную рассылку с выбранными группами и текстами"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    account_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    selected_groups = data.get('selected_groups', [])
    text_variants = data.get('text_variants', [])
    
    with next_get_db() as db:
        account = db.query(Account).filter(Account.id == account_id).first()
    
    await callback.message.edit_text(
        f"🚀 **ЗАПУСК КАСТОМНОЙ РАССЫЛКИ**\n\n"
        f"📞 Аккаунт: {account.phone}\n"
        f"📝 Вариантов текста: {len(text_variants)}\n"
        f"🎯 Групп для рассылки: {len(selected_groups)}\n\n"
        f"⏳ Инициализация рассылки...",
        parse_mode="Markdown"
    )
    
    # Запускаем кастомную рассылку в фоне
    asyncio.create_task(execute_custom_spam_campaign(account, text_variants, selected_groups, callback.message))
    await state.clear()
    await callback.answer("🚀 Кастомная рассылка запущена!")

@router.message(AdminSpamStates.waiting_message)
async def process_spam_message(message: Message, state: FSMContext):
    """Обрабатывает текст сообщения для рассылки"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔️ Доступ запрещен")
        return
    
    data = await state.get_data()
    account_id = data.get('selected_account_id')
    
    if not account_id:
        await message.answer("❌ Ошибка: аккаунт не выбран")
        await state.clear()
        return
    
    spam_text = message.text
    await state.update_data(spam_text=spam_text)
    
    with next_get_db() as db:
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            await message.answer("❌ Аккаунт не найден")
            await state.clear()
            return
        
        # Получаем группы аккаунта из базы данных
        groups = db.query(Group).filter(Group.account_id == account_id).all()
    
    text = (
        f"📝 **ТЕКСТ РАССЫЛКИ:**\n"
        f"```\n{spam_text[:200]}{'...' if len(spam_text) > 200 else ''}\n```\n\n"
        f"📞 **Аккаунт:** {account.phone}\n"
        f"🏘️ **Доступно групп:** {len(groups)}\n\n"
        "Выберите действие:"
    )
    
    builder = InlineKeyboardBuilder()
    if groups:
        builder.add(InlineKeyboardButton(
            text=f"🎯 Отправить во ВСЕ {len(groups)} групп", 
            callback_data=f"admin_spam_all:{account_id}"
        ))
        builder.add(InlineKeyboardButton(
            text="📋 Выбрать группы вручную", 
            callback_data=f"admin_select_groups:{account_id}"
        ))
    else:
        builder.add(InlineKeyboardButton(
            text="🔄 Сначала обновите список групп", 
            callback_data=f"admin_update_groups:{account_id}"
        ))
    
    builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data="admin_panel"))
    builder.adjust(1)
    
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@router.callback_query(F.data.startswith("admin_spam_all:"))
async def spam_to_all_groups(callback: CallbackQuery, state: FSMContext):
    """Запускает рассылку во все группы аккаунта"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    account_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    spam_text = data.get('spam_text')
    
    if not spam_text:
        await callback.answer("❌ Текст сообщения не найден", show_alert=True)
        return
    
    db = SessionLocal()
    try:
        account = db.query(Account).filter(Account.id == account_id).first()
        
        if not account:
            await callback.answer("❌ Аккаунт не найден", show_alert=True)
            return
    except Exception as e:
        await callback.answer(f"❌ Ошибка БД: {str(e)}", show_alert=True)
        return
    finally:
        db.close()
    
    await callback.message.edit_text(
        f"🚀 **ЗАПУСК РАССЫЛКИ**\n\n"
        f"📞 Аккаунт: {account.phone}\n"
        f"📝 Сообщение: {spam_text[:100]}...\n\n"
        f"⏳ Получаем список групп и запускаем рассылку...",
        parse_mode="Markdown"
    )
    
    # Запускаем рассылку в фоне
    asyncio.create_task(execute_spam_campaign(account, spam_text, callback.message))
    await state.clear()
    await callback.answer("🚀 Рассылка запущена!")

@router.callback_query(F.data == "admin_mass_spam")
async def mass_spam_menu(callback: CallbackQuery):
    """Меню массового спама со всех аккаунтов"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    db = SessionLocal()
    try:
        accounts = db.query(Account).all()
        
        if not accounts:
            await callback.answer("❌ Нет подключенных аккаунтов", show_alert=True)
            return
        
        total_groups = 0
        for account in accounts:
            groups_count = await get_account_groups_count(account.phone)
            total_groups += groups_count
    except Exception as e:
        await callback.answer(f"❌ Ошибка БД: {str(e)}", show_alert=True)
        return
    finally:
        db.close()
    
    text = (
        f"🎯 **МАССОВЫЙ СПАМ**\n\n"
        f"📱 Доступно аккаунтов: {len(accounts)}\n"
        f"🏘️ Общее количество групп: {total_groups}\n\n"
        "⚠️ **ВНИМАНИЕ!** Массовый спам может привести к блокировке аккаунтов.\n\n"
        "Выберите действие:"
    )
    
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text=f"🚀 Спам со ВСЕХ аккаунтов ({total_groups} групп)", 
        callback_data="admin_mass_spam_all"
    ))
    builder.add(InlineKeyboardButton(text="📋 Выбрать аккаунты", callback_data="admin_select_accounts"))
    builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel"))
    builder.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "admin_mass_spam_all")
async def start_mass_spam_all(callback: CallbackQuery, state: FSMContext):
    """Начинает процесс массовой рассылки со всех аккаунтов"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    with next_get_db() as db:
        accounts = db.query(Account).all()
        total_groups = db.query(Group).count()
    
    if not accounts:
        await callback.answer("❌ Нет подключенных аккаунтов", show_alert=True)
        return
    
    text = (
        f"🎯 **МАССОВАЯ РАССЫЛКА СО ВСЕХ АККАУНТОВ**\n\n"
        f"📱 Аккаунтов: {len(accounts)}\n"
        f"🏘️ Общее количество групп: {total_groups}\n\n"
        f"⚠️ **ВНИМАНИЕ!** Это отправит сообщение во ВСЕ группы со ВСЕХ аккаунтов одновременно.\n\n"
        "Введите текст сообщения для массовой рассылки:"
    )
    
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data="admin_panel"))
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await state.set_state(AdminSpamStates.waiting_mass_message)
    await callback.answer()

@router.message(AdminSpamStates.waiting_mass_message)
async def process_mass_spam_message(message: Message, state: FSMContext):
    """Обрабатывает текст сообщения для массовой рассылки"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔️ Доступ запрещен")
        return
    
    spam_text = message.text
    
    with next_get_db() as db:
        accounts = db.query(Account).all()
        total_groups = db.query(Group).count()
    
    text = (
        f"📝 **ПОДТВЕРЖДЕНИЕ МАССОВОЙ РАССЫЛКИ**\n\n"
        f"```\n{spam_text[:200]}{'...' if len(spam_text) > 200 else ''}\n```\n\n"
        f"📱 Аккаунтов: {len(accounts)}\n"
        f"🏘️ Групп для рассылки: {total_groups}\n\n"
        f"⚠️ **ПОСЛЕДНЕЕ ПРЕДУПРЕЖДЕНИЕ!**\n"
        f"Это отправит сообщение во ВСЕ {total_groups} групп со ВСЕХ {len(accounts)} аккаунтов!\n\n"
        "Подтвердите действие:"
    )
    
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text=f"🚀 ЗАПУСТИТЬ МАССОВУЮ РАССЫЛКУ", 
        callback_data="confirm_mass_spam"
    ))
    builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data="admin_panel"))
    builder.adjust(1)
    
    await state.update_data(mass_spam_text=spam_text)
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@router.callback_query(F.data == "confirm_mass_spam")
async def execute_mass_spam(callback: CallbackQuery, state: FSMContext):
    """Запускает массовую рассылку со всех аккаунтов"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    data = await state.get_data()
    spam_text = data.get('mass_spam_text')
    
    if not spam_text:
        await callback.answer("❌ Текст сообщения не найден", show_alert=True)
        return
    
    with next_get_db() as db:
        accounts = db.query(Account).all()
    
    if not accounts:
        await callback.answer("❌ Нет подключенных аккаунтов", show_alert=True)
        return
    
    await callback.message.edit_text(
        f"🚀 **ЗАПУСК МАССОВОЙ РАССЫЛКИ**\n\n"
        f"📱 Аккаунтов: {len(accounts)}\n"
        f"📝 Сообщение: {spam_text[:100]}...\n\n"
        f"⏳ Запускаем рассылку со всех аккаунтов одновременно...\n\n"
        f"📊 Прогресс будет обновляться в реальном времени.",
        parse_mode="Markdown"
    )
    
    # Запускаем рассылку со всех аккаунтов параллельно
    asyncio.create_task(execute_mass_spam_campaign(accounts, spam_text, callback.message))
    await state.clear()
    await callback.answer("🚀 Массовая рассылка запущена!")

@router.callback_query(F.data == "admin_stats")
async def show_admin_stats(callback: CallbackQuery):
    """Показывает статистику рассылок"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    with next_get_db() as db:
        # Общая статистика
        total_accounts = db.query(Account).count()
        total_groups = db.query(Group).count()
        total_messages = db.query(MessageLog).count()
        successful_messages = db.query(MessageLog).filter(MessageLog.status == 'sent').count()
        
        # Статистика по статусам
        flood_wait_count = db.query(MessageLog).filter(MessageLog.status == 'flood_wait').count()
        error_count = db.query(MessageLog).filter(MessageLog.status == 'error').count()
        no_rights_count = db.query(MessageLog).filter(MessageLog.status == 'no_admin_rights').count()
        
        # Последние рассылки
        recent_messages = db.query(MessageLog).order_by(MessageLog.timestamp.desc()).limit(5).all()
    
    success_rate = int(successful_messages / total_messages * 100) if total_messages > 0 else 0
    
    text = (
        f"📊 **СТАТИСТИКА РАССЫЛОК**\n\n"
        f"📱 **Общая информация:**\n"
        f"• Аккаунтов: {total_accounts}\n"
        f"• Групп: {total_groups}\n"
        f"• Всего отправлено сообщений: {total_messages}\n\n"
        f"✅ **Результаты отправки:**\n"
        f"• Успешно: {successful_messages} ({success_rate}%)\n"
        f"• FloodWait: {flood_wait_count}\n"
        f"• Нет прав админа: {no_rights_count}\n"
        f"• Другие ошибки: {error_count}\n\n"
    )
    
    if recent_messages:
        text += f"🕐 **Последние 5 рассылок:**\n"
        for msg in recent_messages:
            status_emoji = {
                'sent': '✅',
                'flood_wait': '⏳',
                'no_admin_rights': '🚫',
                'error': '❌'
            }.get(msg.status, '❓')
            
            text += f"• {status_emoji} {msg.timestamp.strftime('%d.%m %H:%M')} - {msg.text[:30]}...\n"
    else:
        text += f"📭 Рассылок пока не было."
    
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="🗑️ Очистить логи", callback_data="admin_clear_logs"))
    builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel"))
    builder.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

# Вспомогательные функции

def get_account_groups_count(account_id: int) -> int:
    """Получает количество групп аккаунта из базы данных"""
    try:
        with next_get_db() as db:
            groups_count = db.query(Group).filter(Group.account_id == account_id).count()
            return groups_count
    except Exception as e:
        print(f"Ошибка получения групп для аккаунта {account_id}: {e}")
        return 0

async def get_account_groups_detailed(phone: str) -> list:
    """Получает детальную информацию о группах аккаунта"""
    try:
        session_file = f"session_{phone.replace('+', '')}"
        client = TelegramClient(session_file, TELEGRAM_API_ID, TELEGRAM_API_HASH)
        await client.start()
        
        dialogs = await client.get_dialogs()
        groups = []
        
        for dialog in dialogs:
            entity = dialog.entity
            if hasattr(entity, 'title'):  # Группа или канал
                groups.append({
                    'id': entity.id,
                    'title': entity.title,
                    'username': getattr(entity, 'username', None),
                    'participants_count': getattr(entity, 'participants_count', 'Неизвестно')
                })
        
        await client.disconnect()
        return groups
    except Exception as e:
        print(f"Ошибка получения групп для {phone}: {e}")
        return []

async def execute_spam_campaign(account: Account, message_text: str, status_message):
    """Выполняет рассылку сообщения по всем группам аккаунта из базы данных"""
    try:
        # Получаем группы из базы данных
        with next_get_db() as db:
            groups = db.query(Group).filter(Group.account_id == account.id).all()
        
        if not groups:
            await status_message.edit_text(
                f"❌ **НЕТ ГРУПП**\n\n"
                f"📞 Аккаунт: {account.phone}\n"
                f"🏘️ Группы не найдены в базе данных.\n\n"
                f"Сначала обновите список групп для этого аккаунта.",
                parse_mode="Markdown"
            )
            return
        
        # Подключаемся к Telegram
        session_file = f"session_{account.phone.replace('+', '')}"
        client = TelegramClient(session_file, TELEGRAM_API_ID, TELEGRAM_API_HASH)
        await client.start()
        
        sent_count = 0
        error_count = 0
        
        await status_message.edit_text(
            f"🚀 **НАЧИНАЕМ РАССЫЛКУ**\n\n"
            f"📞 Аккаунт: {account.phone}\n"
            f"🏘️ Групп для рассылки: {len(groups)}\n"
            f"📝 Сообщение: {message_text[:50]}...\n\n"
            f"⏳ Подготовка...",
            parse_mode="Markdown"
        )
        
        for i, group in enumerate(groups, 1):
            try:
                # Отправляем сообщение в группу по её Telegram ID
                await client.send_message(int(group.tg_id), message_text)
                sent_count += 1
                
                # Логируем отправку в базу данных
                with next_get_db() as db:
                    log_entry = MessageLog(
                        account_id=account.id,
                        group_id=group.id,
                        text=message_text[:500],  # Ограничиваем длину
                        status='sent',
                        sent_at=datetime.now()
                    )
                    db.add(log_entry)
                    db.commit()
                
                # Обновляем статус каждые 3 сообщения
                if i % 3 == 0 or i == len(groups):
                    progress = int(i/len(groups)*100)
                    await status_message.edit_text(
                        f"🚀 **РАССЫЛКА В ПРОЦЕССЕ**\n\n"
                        f"📞 Аккаунт: {account.phone}\n"
                        f"✅ Отправлено: {sent_count}/{len(groups)}\n"
                        f"❌ Ошибок: {error_count}\n"
                        f"📊 Прогресс: {progress}%\n"
                        f"🏘️ Текущая группа: {group.name[:30]}...",
                        parse_mode="Markdown"
                    )
                
                # Задержка между сообщениями (антиспам)
                await asyncio.sleep(3)
                
            except FloodWaitError as e:
                print(f"FloodWait {e.seconds} секунд для группы {group.name}")
                await asyncio.sleep(e.seconds + 1)
                error_count += 1
                
                # Логируем ошибку
                with next_get_db() as db:
                    log_entry = MessageLog(
                        account_id=account.id,
                        group_id=group.id,
                        text=message_text[:500],
                        status='flood_wait',
                        error_message=f"FloodWait {e.seconds}s",
                        sent_at=datetime.now()
                    )
                    db.add(log_entry)
                    db.commit()
                    
            except ChatAdminRequiredError:
                print(f"Нет прав администратора в группе {group.name}")
                error_count += 1
                
                # Логируем ошибку
                with next_get_db() as db:
                    log_entry = MessageLog(
                        account_id=account.id,
                        group_id=group.id,
                        text=message_text[:500],
                        status='no_admin_rights',
                        error_message="No admin rights",
                        sent_at=datetime.now()
                    )
                    db.add(log_entry)
                    db.commit()
                    
            except Exception as e:
                print(f"Ошибка отправки в {group.name}: {e}")
                error_count += 1
                
                # Логируем ошибку
                with next_get_db() as db:
                    log_entry = MessageLog(
                        account_id=account.id,
                        group_id=group.id,
                        text=message_text[:500],
                        status='error',
                        error_message=str(e)[:200],
                        sent_at=datetime.now()
                    )
                    db.add(log_entry)
                    db.commit()
        
        # Финальный отчет
        success_rate = int(sent_count/len(groups)*100) if groups else 0
        await status_message.edit_text(
            f"✅ **РАССЫЛКА ЗАВЕРШЕНА**\n\n"
            f"📞 Аккаунт: {account.phone}\n"
            f"✅ Успешно отправлено: {sent_count}\n"
            f"❌ Ошибок: {error_count}\n"
            f"🏘️ Всего групп: {len(groups)}\n"
            f"📊 Успешность: {success_rate}%\n\n"
            f"🕐 Завершено: {datetime.now().strftime('%H:%M:%S')}\n\n"
            f"📝 Все результаты сохранены в базу данных.",
            parse_mode="Markdown"
        )
        
        await client.disconnect()
        
    except Exception as e:
        print(f"Критическая ошибка рассылки: {e}")
        await status_message.edit_text(
            f"❌ **КРИТИЧЕСКАЯ ОШИБКА**\n\n"
            f"📞 Аккаунт: {account.phone}\n"
            f"🚫 Ошибка: {str(e)[:200]}\n\n"
            f"Проверьте:\n"
            f"• Авторизацию аккаунта\n"
            f"• Подключение к интернету\n"
            f"• Список групп в базе данных",
            parse_mode="Markdown"
        )

async def execute_custom_spam_campaign(account: Account, text_variants: list, selected_group_ids: list, status_message):
    """Выполняет кастомную рассылку с вариативными текстами по выбранным группам"""
    import random
    
    try:
        # Получаем выбранные группы из базы данных
        with next_get_db() as db:
            groups = db.query(Group).filter(Group.id.in_(selected_group_ids)).all()
        
        if not groups:
            await status_message.edit_text(
                f"❌ **НЕТ ГРУПП**\n\n"
                f"📞 Аккаунт: {account.phone}\n"
                f"🏘️ Выбранные группы не найдены в базе данных.",
                parse_mode="Markdown"
            )
            return
        
        # Подключаемся к Telegram
        session_file = f"session_{account.phone.replace('+', '')}"
        client = TelegramClient(session_file, TELEGRAM_API_ID, TELEGRAM_API_HASH)
        await client.start()
        
        sent_count = 0
        error_count = 0
        
        await status_message.edit_text(
            f"🚀 **КАСТОМНАЯ РАССЫЛКА ЗАПУЩЕНА**\n\n"
            f"📞 Аккаунт: {account.phone}\n"
            f"📝 Вариантов текста: {len(text_variants)}\n"
            f"🎯 Групп для рассылки: {len(groups)}\n\n"
            f"⏳ Начинаем отправку с рандомизацией текстов...",
            parse_mode="Markdown"
        )
        
        for i, group in enumerate(groups, 1):
            try:
                # Выбираем случайный текст из вариантов
                random_text = random.choice(text_variants)
                
                # Отправляем сообщение в группу
                await client.send_message(int(group.tg_id), random_text)
                sent_count += 1
                
                # Логируем успешную отправку
                with next_get_db() as db:
                    log_entry = MessageLog(
                        account_id=account.id,
                        group_id=group.id,
                        text=random_text[:500],
                        status='sent',
                        sent_at=datetime.now()
                    )
                    db.add(log_entry)
                    db.commit()
                
                # Обновляем статус каждые 2 сообщения
                if i % 2 == 0 or i == len(groups):
                    progress = int(i/len(groups)*100)
                    await status_message.edit_text(
                        f"🚀 **КАСТОМНАЯ РАССЫЛКА В ПРОЦЕССЕ**\n\n"
                        f"📞 Аккаунт: {account.phone}\n"
                        f"📝 Используется {len(text_variants)} вариантов текста\n"
                        f"✅ Отправлено: {sent_count}/{len(groups)}\n"
                        f"❌ Ошибок: {error_count}\n"
                        f"📊 Прогресс: {progress}%\n"
                        f"🏘️ Текущая группа: {group.name[:25]}...\n\n"
                        f"🎲 Последний текст: {random_text[:30]}...",
                        parse_mode="Markdown"
                    )
                
                # Задержка между сообщениями (антиспам)
                await asyncio.sleep(3)
                
            except FloodWaitError as e:
                print(f"FloodWait {e.seconds} секунд для группы {group.name}")
                await asyncio.sleep(e.seconds + 1)
                error_count += 1
                
                # Логируем ошибку
                with next_get_db() as db:
                    log_entry = MessageLog(
                        account_id=account.id,
                        group_id=group.id,
                        text=text_variants[0][:500],  # Логируем первый вариант
                        status='flood_wait',
                        error_message=f"FloodWait {e.seconds}s",
                        sent_at=datetime.now()
                    )
                    db.add(log_entry)
                    db.commit()
                    
            except Exception as e:
                print(f"Ошибка отправки в {group.name}: {e}")
                error_count += 1
                
                # Логируем ошибку
                with next_get_db() as db:
                    log_entry = MessageLog(
                        account_id=account.id,
                        group_id=group.id,
                        text=text_variants[0][:500],
                        status='error'
                    )
                    db.add(log_entry)
                    db.commit()
        
        # Финальный отчет
        success_rate = int(sent_count/len(groups)*100) if groups else 0
        await status_message.edit_text(
            f"✅ **КАСТОМНАЯ РАССЫЛКА ЗАВЕРШЕНА**\n\n"
            f"📞 Аккаунт: {account.phone}\n"
            f"📝 Использовано вариантов текста: {len(text_variants)}\n"
            f"✅ Успешно отправлено: {sent_count}\n"
            f"❌ Ошибок: {error_count}\n"
            f"🎯 Всего групп: {len(groups)}\n"
            f"📊 Успешность: {success_rate}%\n\n"
            f"🎲 **Особенности рассылки:**\n"
            f"• Тексты выбирались случайно из {len(text_variants)} вариантов\n"
            f"• Отправка только в выбранные группы\n"
            f"• Все результаты сохранены в базу данных\n\n"
            f"🕐 Завершено: {datetime.now().strftime('%H:%M:%S')}",
            parse_mode="Markdown"
        )
        
        await client.disconnect()
        
    except Exception as e:
        print(f"Критическая ошибка кастомной рассылки: {e}")
        await status_message.edit_text(
            f"❌ **КРИТИЧЕСКАЯ ОШИБКА КАСТОМНОЙ РАССЫЛКИ**\n\n"
            f"📞 Аккаунт: {account.phone}\n"
            f"🚫 Ошибка: {str(e)[:200]}\n\n"
            f"Проверьте:\n"
            f"• Авторизацию аккаунта\n"
            f"• Подключение к интернету\n"
            f"• Выбранные группы и тексты",
            parse_mode="Markdown"
        )

async def execute_mass_spam_campaign(accounts: list, message_text: str, status_message):
    """Выполняет массовую рассылку со всех аккаунтов параллельно"""
    try:
        total_sent = 0
        total_errors = 0
        completed_accounts = 0
        
        # Получаем общее количество групп
        with next_get_db() as db:
            total_groups = db.query(Group).count()
        
        await status_message.edit_text(
            f"🚀 **МАССОВАЯ РАССЫЛКА ЗАПУЩЕНА**\n\n"
            f"📱 Аккаунтов: {len(accounts)}\n"
            f"🏘️ Общее количество групп: {total_groups}\n"
            f"📝 Сообщение: {message_text[:50]}...\n\n"
            f"⏳ Инициализация рассылки со всех аккаунтов...\n"
            f"📊 Прогресс: 0%",
            parse_mode="Markdown"
        )
        
        # Создаем задачи для каждого аккаунта
        tasks = []
        for account in accounts:
            task = asyncio.create_task(
                execute_single_account_spam(account, message_text, status_message, len(accounts))
            )
            tasks.append(task)
        
        # Ждем завершения всех задач
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Подсчитываем результаты
        for result in results:
            if isinstance(result, dict):
                total_sent += result.get('sent', 0)
                total_errors += result.get('errors', 0)
                completed_accounts += 1
            else:
                total_errors += 1
        
        # Финальный отчет
        success_rate = int(total_sent / (total_sent + total_errors) * 100) if (total_sent + total_errors) > 0 else 0
        
        await status_message.edit_text(
            f"✅ **МАССОВАЯ РАССЫЛКА ЗАВЕРШЕНА**\n\n"
            f"📱 Обработано аккаунтов: {completed_accounts}/{len(accounts)}\n"
            f"🏘️ Общее количество групп: {total_groups}\n"
            f"✅ Успешно отправлено: {total_sent}\n"
            f"❌ Ошибок: {total_errors}\n"
            f"📊 Общая успешность: {success_rate}%\n\n"
            f"🕐 Завершено: {datetime.now().strftime('%H:%M:%S')}\n\n"
            f"📝 Все результаты сохранены в базу данных.\n"
            f"📊 Посмотрите детальную статистику в разделе 'Статистика рассылок'.",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        print(f"Критическая ошибка массовой рассылки: {e}")
        await status_message.edit_text(
            f"❌ **КРИТИЧЕСКАЯ ОШИБКА МАССОВОЙ РАССЫЛКИ**\n\n"
            f"🚫 Ошибка: {str(e)[:200]}\n\n"
            f"Рассылка была прервана. Проверьте:\n"
            f"• Подключение к интернету\n"
            f"• Статус аккаунтов\n"
            f"• Логи системы",
            parse_mode="Markdown"
        )

async def execute_single_account_spam(account: Account, message_text: str, status_message, total_accounts: int):
    """Выполняет рассылку с одного аккаунта для массовой рассылки"""
    try:
        # Получаем группы аккаунта
        with next_get_db() as db:
            groups = db.query(Group).filter(Group.account_id == account.id).all()
        
        if not groups:
            return {'sent': 0, 'errors': 0, 'account': account.phone}
        
        # Подключаемся к Telegram
        session_file = f"session_{account.phone.replace('+', '')}"
        client = TelegramClient(session_file, TELEGRAM_API_ID, TELEGRAM_API_HASH)
        await client.start()
        
        sent_count = 0
        error_count = 0
        
        for group in groups:
            try:
                # Отправляем сообщение
                await client.send_message(int(group.tg_id), message_text)
                sent_count += 1
                
                # Логируем успешную отправку
                with next_get_db() as db:
                    log_entry = MessageLog(
                        account_id=account.id,
                        group_id=group.id,
                        text=message_text[:500],
                        status='sent',
                        sent_at=datetime.now()
                    )
                    db.add(log_entry)
                    db.commit()
                
                # Задержка между сообщениями
                await asyncio.sleep(2)
                
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds + 1)
                error_count += 1
                
                # Логируем ошибку
                with next_get_db() as db:
                    log_entry = MessageLog(
                        account_id=account.id,
                        group_id=group.id,
                        text=message_text[:500],
                        status='flood_wait',
                        error_message=f"FloodWait {e.seconds}s",
                        sent_at=datetime.now()
                    )
                    db.add(log_entry)
                    db.commit()
                    
            except Exception as e:
                error_count += 1
                
                # Логируем ошибку
                with next_get_db() as db:
                    log_entry = MessageLog(
                        account_id=account.id,
                        group_id=group.id,
                        text=message_text[:500],
                        status='error',
                        error_message=str(e)[:200],
                        sent_at=datetime.now()
                    )
                    db.add(log_entry)
                    db.commit()
        
        await client.disconnect()
        return {'sent': sent_count, 'errors': error_count, 'account': account.phone}
        
    except Exception as e:
        print(f"Ошибка рассылки с аккаунта {account.phone}: {e}")
        return {'sent': 0, 'errors': 1, 'account': account.phone}

@router.callback_query(F.data == "admin_clear_logs")
async def clear_admin_logs(callback: CallbackQuery):
    """Очищает логи рассылок"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️ Доступ запрещен", show_alert=True)
        return
    
    with next_get_db() as db:
        deleted_count = db.query(MessageLog).count()
        db.query(MessageLog).delete()
        db.commit()
    
    await callback.answer(f"🗑️ Удалено {deleted_count} записей из логов", show_alert=True)
    
    # Обновляем статистику
    await show_admin_stats(callback)
