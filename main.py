import os
import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from dotenv import load_dotenv

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

from utils.keyboards import (
    get_main_menu_keyboard,
    get_account_menu_keyboard,
    get_back_keyboard,
    get_cancel_keyboard,
    get_mailings_list_keyboard,
    get_night_mode_keyboard
    # ... остальные при необходимости
)

# Импортируем роутеры из handlers
from handlers import admin_panel, main as main_handler, accounts, groups, mailing

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")

logging.basicConfig(level=logging.INFO)
dp = Dispatcher(storage=MemoryStorage())

# =============================== RUN ================================
async def main():
    if not (BOT_TOKEN and API_ID and API_HASH):
        print('Проверьте .env!')
        return
    
    # Инициализируем базу данных
    from database.database import init_db_sync
    init_db_sync()
    
    # Подключаем роутеры
    dp.include_router(main_handler.router)
    dp.include_router(accounts.router)
    dp.include_router(groups.router)
    dp.include_router(mailing.router)
    dp.include_router(admin_panel.router)
    
    bot = Bot(token=BOT_TOKEN)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

