from typing import Dict, Any
from database.models import NightMode
from database.database import get_db, next_get_db
from config import DEFAULT_NIGHT_START, DEFAULT_NIGHT_END, NIGHT_MODE_MULTIPLIER

def get_night_mode_settings() -> Dict[str, Any]:
    """Получает настройки ночного режима"""
    with next_get_db() as db:
        night_mode = db.query(NightMode).first()
        
        if not night_mode:
            # Создаем настройки по умолчанию
            night_mode = NightMode(
                enabled=False,
                start_hour=DEFAULT_NIGHT_START,
                end_hour=DEFAULT_NIGHT_END
            )
            db.add(night_mode)
            db.commit()
        
        return {
            "is_enabled": night_mode.enabled,
            "start_hour": night_mode.start_hour,
            "end_hour": night_mode.end_hour,
            "multiplier": getattr(night_mode, 'multiplier', NIGHT_MODE_MULTIPLIER)
        }

def enable_night_mode() -> Dict[str, Any]:
    """Включает ночной режим"""
    with next_get_db() as db:
        night_mode = db.query(NightMode).first()
        
        if not night_mode:
            night_mode = NightMode(
                enabled=True,
                start_hour=DEFAULT_NIGHT_START,
                end_hour=DEFAULT_NIGHT_END
            )
            db.add(night_mode)
        else:
            night_mode.enabled = True
        
        db.commit()
        return get_night_mode_settings()

def disable_night_mode() -> Dict[str, Any]:
    """Выключает ночной режим"""
    with next_get_db() as db:
        night_mode = db.query(NightMode).first()
        if night_mode:
            night_mode.enabled = False
            db.commit()
            return get_night_mode_settings()
        return {"error": "Настройки ночного режима не найдены"}

def update_night_mode_settings(start_hour: int, end_hour: int) -> Dict[str, Any]:
    """Обновляет настройки ночного режима"""
    if not (0 <= start_hour <= 23 and 0 <= end_hour <= 23):
        return {"success": False, "error": "Часы должны быть от 0 до 23"}
    
    with next_get_db() as db:
        night_mode = db.query(NightMode).first()
        
        if not night_mode:
            night_mode = NightMode()
            db.add(night_mode)
        
        night_mode.start_hour = start_hour
        night_mode.end_hour = end_hour
        
        db.commit()
    
    return {
        "success": True, 
        "message": f"Настройки обновлены: {start_hour}:00 - {end_hour}:00"
    }

def get_night_mode_status() -> str:
    """Получает статус ночного режима в виде строки"""
    settings = get_night_mode_settings()
    
    if not settings["is_enabled"]:
        return "🌙 Ночной режим: 🔴 ВЫКЛ"
    
    return f"🌙 Ночной режим: 🟢 ВКЛ ({settings['start_hour']}:00 - {settings['end_hour']}:00, x{settings['multiplier']})" 