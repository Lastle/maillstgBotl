# services.py

from db import (
    add_account, get_account_by_tg_id, get_accounts, 
    add_group, get_groups, log_message, get_logs
)
from config import ROLES
import os

def register_new_account(tg_id, phone, name, token, session_path, role='user'):
    # Базовая бизнес-валидация (tg_id, token не пусты, роль валидная)
    if not tg_id or not token:
        return False, "tg_id и token обязательны"
    if role not in ROLES:
        return False, "Некорректная роль"
    result = add_account(tg_id, phone, name, token, session_path, role)
    if result:
        return True, "Аккаунт успешно добавлен"
    return False, "Ошибка: аккаунт с таким tg_id уже существует"

def register_new_group(group_id, title, segment=None):
    # Базовая бизнес-валидация
    if not group_id:
        return False, "group_id обязателен"
    result = add_group(group_id, title, segment)
    if result:
        return True, "Группа успешно добавлена"
    return False, "Ошибка: группа с таким id уже существует"

def perform_mailing(msg_text, from_tg_id, groups=None):
    account = get_account_by_tg_id(from_tg_id)
    if not account:
        return False, "Аккаунт не найден"
    session_file = account.session_path
    # Тут реализована интеграция с Telethon: загружаем сессию, отправляем от нужного аккаунта
    if not os.path.exists(session_file):
        return False, "Session-файл не найден, аккаунт не авторизован"
    from telethon.sync import TelegramClient
    results = []
    client = TelegramClient(session_file, api_id=123456, api_hash='your_api_hash')
    client.start()
    groups = groups or get_groups()
    for grp in groups:
        try:
            client.send_message(int(grp.group_id), msg_text)
            log_message(account.id, grp.group_id, msg_text, 'success')
            results.append((grp.group_id, 'success'))
        except Exception as ex:
            log_message(account.id, grp.group_id, msg_text, f'fail: {ex}')
            results.append((grp.group_id, f'fail: {ex}'))
    client.disconnect()
    return True, results

def get_analytics():
    accounts = get_accounts()
    groups = get_groups()
    return dict(accounts_count=len(accounts), groups_count=len(groups))

def is_authorized(tg_id, min_role='user'):
    acc = get_account_by_tg_id(tg_id)
    if acc and ROLES.index(acc.role) >= ROLES.index(min_role):
        return True
    return False
