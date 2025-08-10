from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Dict

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню"""
    builder = InlineKeyboardBuilder()
    
    # Управление аккаунтами
    builder.add(InlineKeyboardButton(
        text="➕ Добавить аккаунт", 
        callback_data="add_account"
    ))
    builder.add(InlineKeyboardButton(
        text="👤 Мои аккаунты", 
        callback_data="my_accounts"
    ))
    
    # Рассылки
    builder.add(InlineKeyboardButton(
        text="📧 Рассылка во все аккаунты", 
        callback_data="broadcast_all"
    ))
    builder.add(InlineKeyboardButton(
        text="⏹ Остановить все рассылки", 
        callback_data="stop_broadcast_all"
    ))
    builder.add(InlineKeyboardButton(
        text="📋 Список рассылок", 
        callback_data="mailings_list"
    ))
    
    # Настройки
    builder.add(InlineKeyboardButton(
        text="🌙 Ночной режим", 
        callback_data="night_mode"
    ))
    
    # Располагаем кнопки по одной в ряду для лучшей читаемости
    builder.adjust(1, 1, 1, 1, 1, 1)
    return builder.as_markup()

def get_account_menu_keyboard(account_id: int) -> InlineKeyboardMarkup:
    """Меню аккаунта"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="📋 Список групп", 
        callback_data=f"account_groups:{account_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="🚀 Начать рассылку во все группы", 
        callback_data=f"start_mailing_all:{account_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="⏹ Остановить общую рассылку", 
        callback_data=f"stop_mailing_all:{account_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="🔄 Обновить информацию о группах", 
        callback_data=f"update_groups:{account_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="❌ Удалить этот аккаунт", 
        callback_data=f"delete_account:{account_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="⬅️ Назад к аккаунтам", 
        callback_data="my_accounts"
    ))
    
    builder.adjust(1, 1, 1, 1, 1, 1)
    return builder.as_markup()

def get_account_groups_keyboard(groups: List[Dict], account_id: int) -> InlineKeyboardMarkup:
    """Клавиатура со списком групп аккаунта"""
    keyboard = InlineKeyboardBuilder()
    
    for group in groups:
        # Создаем текст кнопки
        status_icon = "🟢" if group['is_private'] else "🔴"
        button_text = f"{status_icon} {group['title']}"
        keyboard.button(
            text=button_text, 
            callback_data=f"group_menu:{group['id']}"
        )
    
    # Навигация
    keyboard.button(text="🔄 Обновить группы", callback_data=f"update_groups:{account_id}")
    keyboard.button(text="⬅️ К аккаунту", callback_data=f"account_menu:{account_id}")
    keyboard.button(text="🏠 Главное меню", callback_data="back_to_main")
    
    # Располагаем кнопки: по 2 в ряду для групп, 1 для навигации
    group_rows = (len(groups) + 1) // 2  # Округляем вверх
    adjust_pattern = [2] * group_rows + [1, 1, 1]
    keyboard.adjust(*adjust_pattern)
    return keyboard.as_markup()

def get_group_menu_keyboard(group_id: int, account_id: int, has_active_mailing: bool = False) -> InlineKeyboardMarkup:
    """Меню группы"""
    builder = InlineKeyboardBuilder()
    
    # Кнопка статуса рассылки
    if has_active_mailing:
        builder.add(InlineKeyboardButton(
            text="🟢 Рассылка активна", 
            callback_data=f"mailing_status:{group_id}"
        ))
    else:
        builder.add(InlineKeyboardButton(
            text="🔴 Рассылка неактивна", 
            callback_data=f"mailing_status:{group_id}"
        ))
    
    builder.add(InlineKeyboardButton(
        text="📝 Текст и Интервал рассылки", 
        callback_data=f"group_mailing_settings:{group_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="▶️ Начать/возобновить рассылку", 
        callback_data=f"start_group_mailing:{group_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="⏹ Остановить рассылку", 
        callback_data=f"stop_group_mailing:{group_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="❌ Удалить группу", 
        callback_data=f"delete_group:{group_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="⬅️ Назад к группам", 
        callback_data=f"account_groups:{account_id}"
    ))
    
    builder.adjust(1, 1, 1, 1, 1, 1)
    return builder.as_markup()

def get_mailing_type_keyboard() -> InlineKeyboardMarkup:
    """Выбор типа рассылки"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="⏰ Интервал во все группы", 
        callback_data="mailing_type:fixed"
    ))
    builder.add(InlineKeyboardButton(
        text="🎲 Разный интервал (25-35)", 
        callback_data="mailing_type:random"
    ))
    
    builder.adjust(1, 1)
    return builder.as_markup()

def get_photo_attachment_keyboard() -> InlineKeyboardMarkup:
    """Выбор прикрепления фото"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="✅ Да, прикрепить фото", 
        callback_data="photo_attachment:with_text"
    ))
    builder.add(InlineKeyboardButton(
        text="📷 Только изображение", 
        callback_data="photo_attachment:only_photo"
    ))
    builder.add(InlineKeyboardButton(
        text="❌ Нет, только текст", 
        callback_data="photo_attachment:text_only"
    ))
    
    builder.adjust(1, 1, 1)
    return builder.as_markup()

def get_night_mode_keyboard() -> InlineKeyboardMarkup:
    """Меню ночного режима"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(
        text="🌙 Включить ночной режим", 
        callback_data="night_mode:enable"
    ))
    builder.add(InlineKeyboardButton(
        text="☀️ Выключить ночной режим", 
        callback_data="night_mode:disable"
    ))
    builder.add(InlineKeyboardButton(
        text="⚙️ Настройки ночного режима", 
        callback_data="night_mode:settings"
    ))
    builder.add(InlineKeyboardButton(
        text="⬅️ Назад", 
        callback_data="back_to_main"
    ))
    
    builder.adjust(1, 1, 1, 1)
    return builder.as_markup()

def get_back_keyboard():
    """Клавиатура с кнопкой назад"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="⬅️ Назад", callback_data="back_to_main")
    return keyboard.as_markup()

def get_cancel_keyboard():
    """Клавиатура с кнопкой отмены"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="❌ Отмена", callback_data="cancel_operation")
    return keyboard.as_markup()

def get_back_cancel_keyboard() -> InlineKeyboardMarkup:
    """Кнопки назад и отмена"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="⬅️ Назад", 
        callback_data="back_to_main"
    ))
    builder.add(InlineKeyboardButton(
        text="❌ Отмена", 
        callback_data="cancel_operation"
    ))
    builder.adjust(2)
    return builder.as_markup()

def get_back_to_accounts_keyboard():
    """Клавиатура с кнопкой назад к аккаунтам"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="⬅️ К аккаунтам", callback_data="accounts")
    return keyboard.as_markup()

def get_back_to_account_keyboard(account_id: int) -> InlineKeyboardMarkup:
    """Кнопка назад к конкретному аккаунту"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="⬅️ Назад к аккаунту", 
        callback_data=f"account_menu:{account_id}"
    ))
    return builder.as_markup()

def get_back_to_groups_keyboard():
    """Клавиатура с кнопкой назад к группам"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="⬅️ К группам", callback_data="groups")
    return keyboard.as_markup()

def get_mailings_list_keyboard(mailings: List[Dict]) -> InlineKeyboardMarkup:
    """Клавиатура со списком рассылок"""
    keyboard = InlineKeyboardBuilder()
    
    # Показываем рассылки в более читаемом формате
    for i, mailing in enumerate(mailings, 1):
        status_icon = "🟢" if mailing['is_active'] else "🔴"
        
        # Берем только номер телефона (последние 4 цифры)
        phone = mailing['account_name']
        if phone.startswith('+'):
            phone_short = phone[-4:]  # последние 4 цифры
        else:
            phone_short = phone[-4:] if len(phone) > 4 else phone
        
        # Сокращаем название группы
        group_name = mailing['group_title']
        if len(group_name) > 12:
            group_short = group_name[:12] + "..."
        else:
            group_short = group_name
        
        button_text = f"{i}. {status_icon} {phone_short} → {group_short}"
        keyboard.button(
            text=button_text, 
            callback_data=f"mailing_details:{mailing['id']}"
        )
    
    # Навигация
    keyboard.button(text="🏠 Главное меню", callback_data="back_to_main")
    
    # Располагаем кнопки: по 2 в ряду для рассылок, 1 для навигации
    mailing_rows = (len(mailings) + 1) // 2  # Округляем вверх
    adjust_pattern = [2] * mailing_rows + [1]
    keyboard.adjust(*adjust_pattern)
    return keyboard.as_markup()

def get_mailing_details_keyboard(mailing_id: int, is_active: bool) -> InlineKeyboardMarkup:
    """Клавиатура с деталями рассылки"""
    keyboard = InlineKeyboardBuilder()
    
    # Основные действия
    if is_active:
        keyboard.button(text="⏹️ Стоп", callback_data=f"stop_mailing:{mailing_id}")
    else:
        keyboard.button(text="▶️ Старт", callback_data=f"start_mailing:{mailing_id}")
    
    # Дополнительные действия
    keyboard.button(text="🗑️ Удалить", callback_data=f"delete_mailing:{mailing_id}")
    
    # Навигация
    keyboard.button(text="📋 Список", callback_data="mailings_list")
    keyboard.button(text="🏠 Меню", callback_data="back_to_main")
    
    # Располагаем кнопки по 2 в ряду
    keyboard.adjust(2, 2, 1)
    return keyboard.as_markup() 

def get_back_to_group_keyboard(group_id: int, account_id: int) -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой назад к конкретной группе"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="⬅️ К группе", callback_data=f"group_menu:{group_id}")
    keyboard.button(text="📋 К списку групп", callback_data=f"account_groups:{account_id}")
    keyboard.button(text="🏠 Главное меню", callback_data="back_to_main")
    return keyboard.as_markup() 