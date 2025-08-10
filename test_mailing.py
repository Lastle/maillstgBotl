# file: send_to_groups.py
import asyncio
import random
from typing import Set

from telethon import TelegramClient
from telethon.errors import FloodWaitError, RPCError

# 1) Ваши данные с https://my.telegram.org
api_id = 2040                 # int
api_hash = "b18441a1ff607e10a989891a5462e627"   # str

# Имя файла сессии — тот же, что вы уже создавали
SESSION_NAME = "session_959784691910.session"

# --- НАСТРОЙКИ ОТПРАВКИ ---

# Текст сообщения
MESSAGE_TEXT = (
    "Привет!\n"
    "Это просто проверка отправки в группы."
)

# Если хотите отправить ТОЛЬКО в выбранные группы — укажите usernames:
# (из вашего списка: ejdkdkkffnd, ChatPython, deribit, Chat_Python)
TARGET_USERNAMES: Set[str] = {
    # примеры:
    # "ejdkdkkffnd", "ChatPython", "deribit", "Chat_Python"
}

# Либо укажите названия чатов (title) — удобно, если нет usernames.
# ВНИМАНИЕ: названия могут повторяться у разных чатов (как у вас с "Python").
TARGET_TITLES: Set[str] = {
    # примеры:
    # "Чат Pythonic", "Python", "Deribit Chat"
}

# Если и TARGET_USERNAMES, и TARGET_TITLES пустые — отправим ВО ВСЕ группы из списка диалогов.

# Пауза между отправками (секунды) — помогает не словить лимиты
DELAY_RANGE = (3, 7)  # случайная пауза 3–7 сек

def _norm(s: str) -> str:
    return (s or "").strip().lower()

async def main():
    client = TelegramClient(SESSION_NAME, api_id, api_hash)
    await client.start()
    print("Загружаю диалоги...")

    # Приводим фильтры к нижнему регистру
    targets_by_username = {_norm(u) for u in TARGET_USERNAMES if u}
    targets_by_title = {_norm(t) for t in TARGET_TITLES if t}

    selected = []  # сюда соберём entity выбранных групп

    async for dialog in client.iter_dialogs():
        if not dialog.is_group:
            continue

        ent = dialog.entity
        title_norm = _norm(dialog.name)
        username_norm = _norm(getattr(ent, "username", ""))

        # Логика выбора:
        send_here = False
        if targets_by_username or targets_by_title:
            if username_norm and username_norm in targets_by_username:
                send_here = True
            if not send_here and title_norm in targets_by_title:
                send_here = True
        else:
            # Фильтры пустые -> отправляем во ВСЕ группы
            send_here = True

        if send_here:
            selected.append((dialog.name, ent))

    if not selected:
        print("Не нашёл ни одной подходящей группы по фильтрам.")
        await client.disconnect()
        return

    print(f"Групп для отправки: {len(selected)}")
    sent = 0
    skipped = 0
    for title, entity in selected:
        try:
            await client.send_message(entity, MESSAGE_TEXT, link_preview=False)
            sent += 1
            print(f"✓ Отправлено: {title}")
        except FloodWaitError as e:
            # При сильных лимитах Telegram может потребовать подождать дольше
            wait_s = int(e.seconds) + 5
            print(f"⏳ FloodWait: ждём {wait_s} сек (чат: {title})")
            await asyncio.sleep(wait_s)
            try:
                await client.send_message(entity, MESSAGE_TEXT, link_preview=False)
                sent += 1
                print(f"✓ Отправлено после ожидания: {title}")
            except RPCError as e2:
                skipped += 1
                print(f"✗ Ошибка после FloodWait в {title}: {e2}")
        except RPCError as e:
            skipped += 1
            print(f"✗ Ошибка отправки в {title}: {e}")

        # Пауза между чатами даже при успехе
        await asyncio.sleep(random.uniform(*DELAY_RANGE))

    print(f"\nГотово. Успешно: {sent}, пропущено: {skipped}")
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
