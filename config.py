import os
from dotenv import load_dotenv

load_dotenv()

# Основные настройки бота
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(",")))

# Настройки Telegram API (нужно получить на https://my.telegram.org)
TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID", 29966891))
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "b7e61c7e93cc485090cfbc4c5f2a1d80")

# Настройки базы данных PostgreSQL
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:1463@localhost:5432/tgmaill")
SYNC_DATABASE_URL = os.getenv("SYNC_DATABASE_URL", "postgresql+asyncpg://postgres:1463@localhost:5432/tgmaill")

# Настройки рассылки
DEFAULT_MIN_INTERVAL = 5  # минут
DEFAULT_MAX_INTERVAL = 15  # минут
MAX_HISTORY_ITEMS = 10  # количество записей в истории

# Настройки ночного режима
DEFAULT_NIGHT_START = 21  # час начала ночного режима
DEFAULT_NIGHT_END = 5     # час окончания ночного режима
NIGHT_MODE_MULTIPLIER = 2  # множитель для ночного режима

# Настройки сообщений
MAX_TEXT_LENGTH = 100  # максимальная длина текста в истории
MAX_PHOTO_SIZE = 10 * 1024 * 1024  # 10MB

# Таймауты
AUTH_TIMEOUT = 300  # 5 минут на авторизацию
MESSAGE_TIMEOUT = 30  # 30 секунд между сообщениями 