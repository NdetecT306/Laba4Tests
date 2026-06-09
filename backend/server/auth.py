from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi import HTTPException, status, Response, Request
from typing import Optional, Dict, Any
import os
import logging
from dotenv import load_dotenv

try:
    from argon2 import PasswordHasher
    from argon2.exceptions import VerificationError, InvalidHash
    ARGON2_AVAILABLE = True
except ImportError as e:
    ARGON2_AVAILABLE = False
    error_msg = (
        "Argon2 не установлен.\n"
    )
    print(error_msg)
    raise RuntimeError("Argon2 is required for password hashing.")

load_dotenv()
logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    error_msg = (
        "JWT_SECRET_KEY не установлен в переменных окружения.\n"
    )
    print(error_msg)
    raise RuntimeError("JWT_SECRET_KEY is required")

if len(SECRET_KEY) < 32:
    logger.warning(f"JWT_SECRET_KEY слишком короткий.")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

ph = PasswordHasher(
    time_cost=2,      
    memory_cost=102400,  
    parallelism=8,    
    hash_len=32,      
    salt_len=16,     
)

def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Пароль не может быть пустым")
    if len(password) < 4:
        raise ValueError("Пароль слишком короткий (минимум 4 символа)")
    return ph.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    logger.info("Проверка пароля")
    if not plain_password or not hashed_password:
        logger.warning("Пустой пароль или хеш")
        return False
    try:
        ph.verify(hashed_password, plain_password)
        if ph.check_needs_rehash(hashed_password):
            logger.info("Хеш пароля устарел, требуется обновление")
        logger.info("Пароль верный")
        return True
    except VerificationError:
        logger.warning("Пароль неверный")
        return False
    except InvalidHash as e:
        logger.error(f"Неверный формат хеша: {e}")
        return False
    except Exception as e:
        logger.error(f"Ошибка при проверке пароля: {e}")
        return False


def create_access_token(user_id: int, username: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(user_id: int, username: str) -> str:
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh"
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        exp = payload.get("exp")
        if exp and datetime.utcfromtimestamp(exp) < datetime.utcnow():
            logger.warning("Токен истек")
            return None
        return payload  
    except JWTError as e:
        logger.warning(f"Ошибка декодирования: {e}")
        return None

def refresh_access_token(refresh_token: str) -> Optional[str]:
    payload = decode_token(refresh_token)
    if not payload:
        logger.warning("Недействительный refresh токен")
        return None
    if payload.get("type") != "refresh":
        logger.warning("Неверный тип токена для обновления")
        return None
    user_id = payload.get("sub")
    username = payload.get("username")
    if not user_id or not username:
        logger.warning("Отсутствуют обязательные поля в токене")
        return None
    try:
        user_id_int = int(user_id)
    except (ValueError, TypeError):
        logger.warning("Неверный формат user_id")
        return None
    logger.info(f"Обновление access токена для пользователя {username}")
    return create_access_token(user_id_int, username)

def get_token_from_request(request: Request, token_type: str = "access") -> Optional[str]:
    cookie_name = f"{token_type}_token"
    token = request.cookies.get(cookie_name)
    if token:
        logger.debug(f"Токен {token_type} получен из cookies")
    return token

def set_tokens_cookies(response: Response, access_token: str, refresh_token: str):
    is_production = os.getenv("ENVIRONMENT", "development") == "production"
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,         
        secure=is_production,   
        samesite="Lax",         
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/"
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=is_production,
        samesite="Lax",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path="/api/refresh"     
    )
    logger.info("Токены установлены в cookies")

def clear_tokens_cookies(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/api/refresh")
    logger.info("Токены удалены из cookies")

def set_access_token_cookie(response: Response, token: str):
    is_production = os.getenv("ENVIRONMENT", "development") == "production"
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=is_production,
        samesite="Lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/"
    )
    logger.debug("Access токен обновлен в cookies")

def get_current_user_id_from_token(request: Request) -> Optional[int]:
    token = get_token_from_request(request, "access")
    if not token:
        return None
    payload = decode_token(token)
    if not payload:
        return None
    try:
        user_id = int(payload.get("sub"))
        return user_id
    except (ValueError, TypeError):
        logger.warning("Не удалось извлечь пользователя из токена")
        return None