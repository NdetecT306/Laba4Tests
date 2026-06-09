from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional
from .db import get_db
from .models import Пользователь
from .auth import get_token_from_request, decode_token, refresh_access_token, set_access_token_cookie
import logging

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)

async def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Пользователь:
    token = get_token_from_request(request, "access")
    if not token and credentials:
        token = credentials.credentials
    
    if not token:
        logger.warning("Токен не предоставлен")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = decode_token(token)
    if payload is None:
        refresh_token = get_token_from_request(request, "refresh")
        if refresh_token:
            new_access_token = refresh_access_token(refresh_token)
            if new_access_token:
                set_access_token_cookie(request, new_access_token)
                payload = decode_token(new_access_token)
    
    if payload is None:
        logger.warning("Неверный или истёкший токен")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный или истёкший токен",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный формат токена",
        )
    
    try:
        user_id_int = int(user_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный формат ID пользователя",
        )
    
    # Пытаемся получить пользователя из БД
    try:
        user = db.query(Пользователь).filter(Пользователь.ID == user_id_int).first()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Пользователь не найден",
            )
        return user
    except Exception as e:
        logger.error(f"Ошибка БД при получении пользователя: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ошибка авторизации",
        )

async def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[Пользователь]:
    try:
        return await get_current_user(request, db, credentials)
    except HTTPException:
        return None