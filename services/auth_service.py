import asyncio
from typing import Optional, Dict, Any
from telethon import TelegramClient
from telethon.errors import (
    PhoneCodeInvalidError, 
    SessionPasswordNeededError, 
    PhoneCodeExpiredError,
    FloodWaitError,
    AuthRestartError
)
from database.models import Account
from database.database import get_db
from utils.helpers import validate_phone, validate_code
from config import AUTH_TIMEOUT

class AuthService:
    """Сервис для авторизации аккаунтов"""
    
    def __init__(self):
        self.auth_sessions: Dict[int, Dict[str, Any]] = {}
    
    async def start_auth(self, user_id: int, phone: str, api_id: int, api_hash: str) -> Dict[str, Any]:
        """Начинает процесс авторизации"""
        if not validate_phone(phone):
            return {"success": False, "error": "Неверный формат номера телефона"}
        
        # Проверяем, не авторизован ли уже этот номер
        with next(get_db()) as db:
            existing_account = db.query(Account).filter(Account.phone == phone).first()
            if existing_account:
                return {"success": False, "error": "Этот аккаунт уже добавлен"}
        
        # Проверяем API credentials
        if not api_id or not api_hash:
            return {"success": False, "error": "API credentials не предоставлены"}
        
        # Создаем клиент Telegram (сессия только по номеру телефона)
        session_name = f"session_{phone.replace('+', '')}"
        client = TelegramClient(session_name, api_id=api_id, api_hash=api_hash)
        
        try:
            await client.connect()
            
            if not await client.is_user_authorized():
                # Отправляем код подтверждения
                await client.send_code_request(phone)
                
                # Сохраняем сессию
                self.auth_sessions[user_id] = {
                    "client": client,
                    "phone": phone,
                    "api_id": api_id,
                    "api_hash": api_hash,
                    "step": "waiting_code",
                    "started_at": asyncio.get_event_loop().time()
                }
                
                return {"success": True, "message": "Код отправлен! Введите его сюда:"}
            else:
                # Аккаунт уже авторизован
                me = await client.get_me()
                await client.disconnect()
                
                # Сохраняем в базу данных
                with next(get_db()) as db:
                    account = Account(
                        phone=phone,
                        name=me.first_name or me.username or phone,
                        api_id=api_id,
                        api_hash=api_hash
                    )
                    db.add(account)
                    db.commit()
                
                return {"success": True, "message": "Авторизация прошла успешно!"}
                
        except FloodWaitError as e:
            await client.disconnect()
            wait_time = e.seconds
            hours = wait_time // 3600
            minutes = (wait_time % 3600) // 60
            if hours > 0:
                time_str = f"{hours} ч. {minutes} мин."
            else:
                time_str = f"{minutes} мин."
            return {"success": False, "error": f"Telegram временно ограничил отправку кодов. Попробуйте через {time_str}"}
        except Exception as e:
            await client.disconnect()
            error_msg = str(e)
            if "flood" in error_msg.lower():
                return {"success": False, "error": "Слишком много попыток. Попробуйте позже."}
            return {"success": False, "error": f"Ошибка при отправке кода: {error_msg}"}
    
    async def verify_code(self, user_id: int, code: str) -> Dict[str, Any]:
        """Проверяет код подтверждения"""
        if user_id not in self.auth_sessions:
            return {"success": False, "error": "Сессия авторизации не найдена"}
        
        if not validate_code(code):
            return {"success": False, "error": "Неверный формат кода"}
        
        session = self.auth_sessions[user_id]
        client = session["client"]
        
        # Проверяем таймаут
        if asyncio.get_event_loop().time() - session["started_at"] > AUTH_TIMEOUT:
            await self.cleanup_session(user_id)
            return {"success": False, "error": "Время авторизации истекло"}
        
        try:
            # Пытаемся войти с кодом
            await client.sign_in(session["phone"], code)
            
            # Получаем информацию о пользователе
            me = await client.get_me()
            
            # Сохраняем в базу данных
            with next(get_db()) as db:
                account = Account(
                    phone=session["phone"],
                    name=me.first_name or me.username or session["phone"],
                    api_id=session["api_id"],
                    api_hash=session["api_hash"]
                )
                db.add(account)
                db.commit()
            
            # Очищаем сессию
            await self.cleanup_session(user_id)
            
            return {"success": True, "message": "Авторизация прошла успешно!"}
            
        except PhoneCodeInvalidError:
            return {"success": False, "error": "Неверный код подтверждения"}
        except PhoneCodeExpiredError:
            await self.cleanup_session(user_id)
            return {"success": False, "error": "Код подтверждения истек. Начните процесс заново."}
        except FloodWaitError as e:
            await self.cleanup_session(user_id)
            wait_time = e.seconds
            hours = wait_time // 3600
            minutes = (wait_time % 3600) // 60
            if hours > 0:
                time_str = f"{hours} ч. {minutes} мин."
            else:
                time_str = f"{minutes} мин."
            return {"success": False, "error": f"Telegram временно ограничил вход. Попробуйте через {time_str}"}
        except AuthRestartError:
            await self.cleanup_session(user_id)
            return {"success": False, "error": "Сессия авторизации сброшена. Начните процесс заново."}
        except SessionPasswordNeededError:
            # Нужен пароль двухфакторной аутентификации
            session["step"] = "waiting_password"
            return {"success": True, "message": "Введите пароль двухфакторной аутентификации:"}
        except Exception as e:
            await self.cleanup_session(user_id)
            error_msg = str(e)
            if "confirmation code has expired" in error_msg.lower():
                return {"success": False, "error": "Код подтверждения истек. Начните процесс заново."}
            elif "flood" in error_msg.lower():
                return {"success": False, "error": "Слишком много попыток входа. Попробуйте позже."}
            return {"success": False, "error": f"Ошибка при авторизации: {error_msg}"}
    
    async def verify_password(self, user_id: int, password: str) -> Dict[str, Any]:
        """Проверяет пароль двухфакторной аутентификации"""
        if user_id not in self.auth_sessions:
            return {"success": False, "error": "Сессия авторизации не найдена"}
        
        session = self.auth_sessions[user_id]
        client = session["client"]
        
        if session["step"] != "waiting_password":
            return {"success": False, "error": "Неверный шаг авторизации"}
        
        try:
            # Входим с паролем
            await client.sign_in(password=password)
            
            # Получаем информацию о пользователе
            me = await client.get_me()
            
            # Сохраняем в базу данных
            with next(get_db()) as db:
                account = Account(
                    phone=session["phone"],
                    name=me.first_name or me.username or session["phone"],
                    api_id=session["api_id"],
                    api_hash=session["api_hash"]
                )
                db.add(account)
                db.commit()
            
            # Очищаем сессию
            await self.cleanup_session(user_id)
            
            return {"success": True, "message": "Авторизация прошла успешно!"}
            
        except FloodWaitError as e:
            await self.cleanup_session(user_id)
            wait_time = e.seconds
            hours = wait_time // 3600
            minutes = (wait_time % 3600) // 60
            if hours > 0:
                time_str = f"{hours} ч. {minutes} мин."
            else:
                time_str = f"{minutes} мин."
            return {"success": False, "error": f"Telegram временно ограничил вход. Попробуйте через {time_str}"}
        except Exception as e:
            await self.cleanup_session(user_id)
            error_msg = str(e)
            if "password" in error_msg.lower():
                return {"success": False, "error": "Неверный пароль двухфакторной аутентификации"}
            elif "flood" in error_msg.lower():
                return {"success": False, "error": "Слишком много попыток входа. Попробуйте позже."}
            return {"success": False, "error": f"Ошибка: {error_msg}"}
    
    async def cleanup_session(self, user_id: int):
        """Очищает сессию авторизации"""
        if user_id in self.auth_sessions:
            session = self.auth_sessions[user_id]
            try:
                await session["client"].disconnect()
            except:
                pass
            del self.auth_sessions[user_id]
    
    def get_auth_status(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получает статус авторизации пользователя"""
        return self.auth_sessions.get(user_id)

# Глобальный экземпляр сервиса
auth_service = AuthService() 