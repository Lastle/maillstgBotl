# Настройка PostgreSQL для Telegram Bot

## 1. Создайте базу данных в pgAdmin:
- Откройте pgAdmin
- Подключитесь к серверу PostgreSQL
- Правый клик на "Databases" → "Create" → "Database..."
- Имя базы: `mailing_bot`
- Owner: `postgres`
- Нажмите "Save"

## 2. Обновите ваш .env файл:
```env
# Telegram Bot настройки
BOT_TOKEN=ваш_токен_бота
ADMIN_IDS=ваш_admin_id

# Telegram API настройки
TELEGRAM_API_ID=2040
TELEGRAM_API_HASH=b18441a1ff607e10a989891a5462e627

# PostgreSQL настройки (замените на ваши данные)
DATABASE_URL=postgresql+asyncpg://postgres:ваш_пароль@localhost:5432/mailing_bot
SYNC_DATABASE_URL=postgresql://postgres:ваш_пароль@localhost:5432/mailing_bot
```

## 3. Данные подключения:
- **Хост:** localhost
- **Порт:** 5432 (стандартный)
- **База:** mailing_bot
- **Пользователь:** postgres
- **Пароль:** ваш пароль от PostgreSQL

## 4. Запуск бота:
После настройки запустите: `python3 main.py` 