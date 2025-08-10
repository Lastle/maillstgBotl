from typing import Dict, Any
from database.models import NightMode
from database.database import get_db
from config import DEFAULT_NIGHT_START, DEFAULT_NIGHT_END, NIGHT_MODE_MULTIPLIER

def get_night_mode_settings() -> Dict[str, Any]:
    """Получает настройки ночного режима"""
    with next(get_db()) as db:
        night_mode = db.query(NightMode).first()
        
        if not night_mode:
            # Создаем настройки по умолчанию
            night_mode = NightMode(
                is_enabled=False,
                start_hour=DEFAULT_NIGHT_START,
                end_hour=DEFAULT_NIGHT_END,
                multiplier=NIGHT_MODE_MULTIPLIER
            )
            db.add(night_mode)
            db.commit()
        
        return {
            "is_enabled": night_mode.is_enabled,
            "start_hour": night_mode.start_hour,
            "end_hour": night_mode.end_hour,
            "multiplier": night_mode.multiplier
        }

def enable_night_mode() -> Dict[str, Any]:
    """Включает ночной режим"""
    with next(get_db()) as db:
        night_mode = db.query(NightMode).first()
        
        if not night_mode:
            night_mode = NightMode(
                is_enabled=True,
                start_hour=DEFAULT_NIGHT_START,
                end_hour=DEFAULT_NIGHT_END,
                multiplier=NIGHT_MODE_MULTIPLIER
            )
            db.add(night_mode)
        else:
            night_mode.is_enabled = True
        
        db.commit()
    
    return {"success": True, "message": "Ночной режим включен"}

def disable_night_mode() -> Dict[str, Any]:
    """Выключает ночной режим"""
    with next(get_db()) as db:
        night_mode = db.query(NightMode).first()
        
        if night_mode:
            night_mode.is_enabled = False
            db.commit()
    
    return {"success": True, "message": "Ночной режим выключен"}

def update_night_mode_settings(start_hour: int, end_hour: int, multiplier: float = 2.0) -> Dict[str, Any]:
    """Обновляет настройки ночного режима"""
    if not (0 <= start_hour <= 23 and 0 <= end_hour <= 23):
        return {"success": False, "error": "Часы должны быть от 0 до 23"}
    
    if multiplier <= 0:
        return {"success": False, "error": "Множитель должен быть больше 0"}
    
    with next(get_db()) as db:
        night_mode = db.query(NightMode).first()
        
        if not night_mode:
            night_mode = NightMode()
            db.add(night_mode)
        
        night_mode.start_hour = start_hour
        night_mode.end_hour = end_hour
        night_mode.multiplier = multiplier
        
        db.commit()
    
    return {
        "success": True, 
        "message": f"Настройки обновлены: {start_hour}:00 - {end_hour}:00, множитель x{multiplier}"
    }

def get_night_mode_status() -> str:
    """Получает статус ночного режима в виде строки"""
    settings = get_night_mode_settings()
    
    if not settings["is_enabled"]:
        return "🌙 Ночной режим: 🔴 ВЫКЛ"
    
    return f"🌙 Ночной режим: 🟢 ВКЛ ({settings['start_hour']}:00 - {settings['end_hour']}:00, x{settings['multiplier']})" 