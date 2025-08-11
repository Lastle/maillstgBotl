# handlers.py

from aiogram import types, Dispatcher
from utils.keyboards import main_menu, groups_menu
from services import (
    register_new_account, register_new_group,
    perform_mailing, get_analytics, is_authorized
)
from db import get_accounts, get_groups, get_logs
from database.models import init_db

def register_handlers(dp: Dispatcher):
    init_db()

    @dp.message_handler(commands=['start'])
    async def cmd_start(msg: types.Message):
        await msg.answer("Добро пожаловать! Выберите действие:", reply_markup=main_menu())

    # --- ДОБАВИТЬ АККАУНТ ---
    @dp.message_handler(lambda m: m.text == "➕ Добавить аккаунт")
    async def acc_start(msg: types.Message):
        await msg.answer("Введите: TG_ID PHONE NAME TOKEN SESSION_PATH РОЛЬ (через пробел, роль user/operator/admin)")

    @dp.message_handler(lambda m: len(m.text.split()) == 6 and not m.text.startswith('/'))
    async def handle_acc(msg: types.Message):
        tg_id, phone, name, token, session_path, role = msg.text.split()
        ok, result = register_new_account(tg_id, phone, name, token, session_path, role)
        await msg.answer(result, reply_markup=main_menu())

    # --- ДОБАВИТЬ ГРУППУ ---
    @dp.message_handler(lambda m: m.text == "➕ Добавить группу")
    async def add_grp(msg: types.Message):
        await msg.answer("Введите: GROUP_ID TITLE [SEGMENT] (через пробел)")

    @dp.message_handler(lambda m: len(m.text.split()) >= 2 and m.text.split()[0].isdigit())
    async def handle_grp(msg: types.Message):
        group_id, title, *segment = msg.text.split()
        segment = " ".join(segment) if segment else ''
        ok, result = register_new_group(group_id, title, segment)
        await msg.answer(result, reply_markup=main_menu())

    # --- СПИСОК АККАУНТОВ ---
    @dp.message_handler(lambda m: m.text == "📋 Список аккаунтов")
    async def acc_list(msg: types.Message):
        accs = get_accounts()
        if not accs:
            await msg.answer("Аккаунтов нет.")
        else:
            text = "\n".join(
                f"{a.tg_id} {a.phone} {a.name} {a.role}" for a in accs)
            await msg.answer(f"Аккаунты:\n{text}")

    # --- СПИСОК ГРУПП ---
    @dp.message_handler(lambda m: m.text == "📋 Список групп")
    async def grp_list(msg: types.Message):
        grps = get_groups()
        if not grps:
            await msg.answer("Групп нет.")
        else:
            text = "\n".join(f"{g.group_id} {g.title} [{g.segment}]" for g in grps)
            await msg.answer(f"Группы:\n{text}")

    # --- РАССЫЛКА ---
    @dp.message_handler(lambda m: m.text == "📤 Рассылка")
    async def mailing(msg: types.Message):
        await msg.answer("Введите сообщение для рассылки, рассылка будет от вашего аккаунта, если он авторизован:")

    @dp.message_handler(lambda m: len(m.text) > 5 and not m.text.startswith('/'))
    async def process_mailing(msg: types.Message):
        if not is_authorized(str(msg.from_user.id)):
            await msg.answer("Вы не авторизованы для рассылки!")
            return
        ok, results = perform_mailing(msg.text, str(msg.from_user.id))
        if not ok:
            await msg.answer(results)
            return
        success = sum(1 for _, status in results if status == 'success')
        fails = sum(1 for _, status in results if status != 'success')
        await msg.answer(f"Рассылка завершена!\nУспешно: {success}\nОшибок: {fails}")

    # --- АНАЛИТИКА ---
    @dp.message_handler(lambda m: m.text == "📊 Аналитика")
    async def analytics(msg: types.Message):
        a = get_analytics()
        await msg.answer(f"Аккаунтов: {a['accounts_count']}\nГрупп: {a['groups_count']}")

    # --- ЛОГИ ---
    @dp.message_handler(lambda m: m.text == "🗒 Логи")
    async def logs(msg: types.Message):
        logs = get_logs()
        if not logs:
            await msg.answer("Логов нет.")
        else:
            text = "\n".join(
                f"[{l.timestamp:%H:%M %d/%m}] {l.group_id} {l.text[:20]}..: {l.status}"
                for l in logs)
            await msg.answer(f"Логи:\n{text}")
