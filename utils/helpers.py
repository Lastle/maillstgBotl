import random
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Tuple
from config import NIGHT_MODE_MULTIPLIER, DEFAULT_NIGHT_START, DEFAULT_NIGHT_END

def truncate_text(text: str, max_length: int = 100) -> str:
    """Обрезает текст до указанной длины"""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."

def format_time_ago(timestamp: datetime) -> str:
    """Форматирует время в формате 'X секунд/минут/часов назад'"""
    now = datetime.utcnow()
    diff = now - timestamp
    
    if diff.total_seconds() < 60:
        seconds = int(diff.total_seconds())
        return f"{seconds} секунд назад"
    elif diff.total_seconds() < 3600:
        minutes = int(diff.total_seconds() // 60)
        return f"{minutes} минут назад"
    else:
        hours = int(diff.total_seconds() // 3600)
        return f"{hours} часов назад"

def is_night_mode(start_hour: int = DEFAULT_NIGHT_START, end_hour: int = DEFAULT_NIGHT_END) -> bool:
    """Проверяет, активен ли ночной режим"""
    now = datetime.now()
    current_hour = now.hour
    
    if start_hour > end_hour:  # Ночной режим переходит через полночь
        return current_hour >= start_hour or current_hour <= end_hour
    else:
        return start_hour <= current_hour <= end_hour

def calculate_interval(min_interval: int, max_interval: int, 
                      night_mode_enabled: bool = False,
                      night_start: int = DEFAULT_NIGHT_START,
                      night_end: int = DEFAULT_NIGHT_END) -> int:
    """Вычисляет интервал с учетом ночного режима"""
    # Генерируем случайный интервал в заданном диапазоне
    interval = random.randint(min_interval, max_interval)
    
    # Если ночной режим включен и сейчас ночь, умножаем интервал
    if night_mode_enabled and is_night_mode(night_start, night_end):
        interval = int(interval * NIGHT_MODE_MULTIPLIER)
    
    return interval

def validate_phone(phone: str) -> bool:
    """Проверяет корректность номера телефона"""
    import re
    # Убираем все символы кроме цифр и +
    phone = re.sub(r'[^\d+]', '', phone)
    
    # Проверяем формат +7XXXXXXXXXX или +44XXXXXXXXXX
    pattern = r'^\+[1-9]\d{10,14}$'
    return bool(re.match(pattern, phone))

def validate_code(code: str) -> bool:
    """Проверяет корректность кода подтверждения"""
    return code.isdigit() and len(code) >= 4 and len(code) <= 6

async def wait_with_timeout(seconds: int) -> bool:
    """Ожидание с таймаутом"""
    try:
        await asyncio.sleep(seconds)
        return True
    except asyncio.CancelledError:
        return False

def format_group_info(title: str, member_count: int, group_type: str, is_private: bool) -> str:
    """Форматирует информацию о группе"""
    privacy = "приватная группа" if is_private else "публичная группа"
    return f"{title} ({privacy}, {member_count} участников, {group_type})"

def format_mailing_status(is_active: bool, started_at: Optional[datetime] = None) -> str:
    """Форматирует статус рассылки"""
    if not is_active:
        return "🔴 ВЫКЛ"
    
    if started_at:
        return f"🟢 ВКЛ (запущена {format_time_ago(started_at)})"
    
    return "🟢 ВКЛ" 