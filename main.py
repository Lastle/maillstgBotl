import asyncio
import logging
import utils.keyboards
import services.night_mode
import services.mailing_service
import database.database
import database.models
import config
import handlers.mailing
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN, ADMIN_IDS
from database.database import init_db
from handlers.main import router as main_router
from handlers.accounts import router as accounts_router
from handlers.groups import router as groups_router
from handlers.mailing import router as mailing_router
from services.mailing_service import mailing_service

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

async def main():
    """Главная функция запуска бота"""
    
    # Проверяем токен
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не установлен в переменных окружения!")
        return
    
    # Проверяем админов
    if not ADMIN_IDS:
        logger.error("ADMIN_IDS не установлены в переменных окружения!")
        return
    
    # Инициализируем базу данных
    try:
        await init_db()
        logger.info("База данных инициализирована")
        
        # Очищаем старые рассылки
        await mailing_service.cleanup_old_mailings()
        logger.info("Старые рассылки очищены")
    except Exception as e:
        logger.error(f"Ошибка инициализации базы данных: {e}")
        return
    
    # Создаем бота и диспетчер
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Регистрируем роутеры
    dp.include_router(main_router)
    dp.include_router(accounts_router)
    dp.include_router(groups_router)
    dp.include_router(mailing_router)
    
    # Обработчик ошибок
    @dp.error()
    async def error_handler(event, **kwargs):
        exception = kwargs.get('exception')
        if exception:
            # Игнорируем ошибки "message is not modified"
            if "message is not modified" in str(exception):
                return
            
            # Игнорируем ошибки устаревших callback_query
            if "query is too old" in str(exception) or "query ID is invalid" in str(exception):
                return
            
            # Логируем остальные ошибки
            logger.error(f"Ошибка при обработке {event}: {exception}")
    
    # Запускаем бота
    try:
        logger.info("Бот запускается...")
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки")
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
    finally:
        # Очищаем ресурсы
        logger.info("Очистка ресурсов...")
        await mailing_service.cleanup()
        await bot.session.close()
        logger.info("Бот остановлен")

if __name__ == "__main__":
    asyncio.run(main()) 