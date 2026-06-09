from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
import logging
from .db import get_db
from .models import Пользователь, ТЭЦ, Дом
from .schemas import (
    РегистрацияRequest, ЛогинRequest, ТокенResponse, ПользовательResponse,
    ТЭЦCreate, ТЭЦUpdate, ТЭЦResponse,
    ДомCreate, ДомUpdate, ДомResponse
)
from .auth import (
    hash_password, verify_password, create_access_token, create_refresh_token,
    set_tokens_cookies, clear_tokens_cookies, set_access_token_cookie,
    get_token_from_request, refresh_access_token
)
from .dependencies import get_current_user
from .utils import (
    MAX_CHPS_DEFAULT, MAX_CHPS_ADMIN,
    MAX_HOUSES_PER_CHP_DEFAULT, MAX_HOUSES_PER_CHP_ADMIN,
    get_max_chps_for_user, get_max_houses_for_user,
    get_chp_position, get_house_position, get_houses_by_chp,
    calculate_chp_status, check_chp_limit_for_user, check_houses_per_chp_limit,
    is_chp_name_unique_for_user, is_house_name_unique_for_user,
    validate_temperature, get_next_available_chp_number,
    recalc_house_positions_for_chp, get_all_chp_ids
)

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post(
    "/api/register",
    response_model=ПользовательResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "Неверные данные"},
        409: {"description": "Пользователь уже существует"}
    }
)
def register(
    user_data: РегистрацияRequest,
    db: Session = Depends(get_db)
):
    logger.info(f"Начало регистрации: {user_data.Логин}")
    try:
        existing = db.query(Пользователь).filter(
            Пользователь.Логин == user_data.Логин
        ).first()
        if existing:
            logger.warning(f"Пользователь уже существует: {user_data.Логин}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Пользователь с таким логином уже существует"
            )
        
        hashed_password = hash_password(user_data.Пароль)
        new_user = Пользователь(
            Логин=user_data.Логин,
            Хэш_пароля=hashed_password,
            Роль="user"
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        logger.info(f"Регистрация успешна: {user_data.Логин}")
        return new_user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка регистрации: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Внутренняя ошибка сервера: {str(e)}"
        )

@router.post(
    "/api/login",
    response_model=ТокенResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"description": "Неверный логин или пароль"}
    }
)
def login(
    response: Response,
    login_data: ЛогинRequest,
    db: Session = Depends(get_db)
):
    logger.info(f"Начало входа: {login_data.Логин}")
    try:
        user = db.query(Пользователь).filter(
            Пользователь.Логин == login_data.Логин
        ).first()
        if not user:
            logger.warning(f"Пользователь не найден: {login_data.Логин}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный логин или пароль"
            )        
        
        password_valid = verify_password(login_data.Пароль, user.Хэш_пароля)
        if not password_valid:
            logger.warning(f"Неверный пароль для пользователя {login_data.Логин}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный логин или пароль"
            )
        
        access_token = create_access_token(user.ID, user.Логин)
        refresh_token = create_refresh_token(user.ID, user.Логин)
        set_tokens_cookies(response, access_token, refresh_token)
        logger.info(f"Вход успешен: {login_data.Логин}")
        return ТокенResponse(
            access_token=access_token,
            username=user.Логин
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Критическая ошибка при входе: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Внутренняя ошибка сервера: {str(e)}"
        )

@router.post("/api/refresh", status_code=status.HTTP_200_OK)
def refresh_token(
    response: Response,
    request: Request,
    db: Session = Depends(get_db)
):
    logger.info("Начало обновления токена")
    try:
        refresh_token_value = get_token_from_request(request, "refresh")
        if not refresh_token_value:
            logger.warning("Refresh token не предоставлен")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token не предоставлен"
            )
        
        new_access_token = refresh_access_token(refresh_token_value)
        if not new_access_token:
            logger.warning("Неверный или истёкший refresh token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный или истёкший refresh token"
            )
        
        set_access_token_cookie(response, new_access_token)
        logger.info("Токен успешно обновлён")
        return {"message": "Токен успешно обновлён"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка обновления токена: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Внутренняя ошибка сервера: {str(e)}"
        )

@router.post("/api/logout", status_code=status.HTTP_200_OK)
def logout(response: Response):
    clear_tokens_cookies(response)
    return {"message": "Успешный выход из системы"}

@router.get(
    "/api/me",
    response_model=ПользовательResponse,
    status_code=status.HTTP_200_OK
)
def get_current_user_info(
    current_user: Пользователь = Depends(get_current_user)
):
    return current_user

@router.get(
    "/api/chps",
    response_model=List[ТЭЦResponse],
    status_code=status.HTTP_200_OK
)
def get_all_chps(
    db: Session = Depends(get_db),
    current_user: Пользователь = Depends(get_current_user)
):
    logger.info(f"Запрос списка ТЭЦ от пользователя: {current_user.Логин}")
    try:
        chps = db.query(ТЭЦ).filter(ТЭЦ.ID_пользователя == current_user.ID).order_by(ТЭЦ.Порядковый_номер).all()
        result = []
        for chp in chps:
            chp_status = calculate_chp_status(chp.ID, db)
            houses_count = db.query(Дом).filter(Дом.ID_ТЭЦ == chp.ID).count()
            result.append(ТЭЦResponse(
                ID=chp.ID,
                Порядковый_номер=chp.Порядковый_номер,
                Название=chp.Название,
                Мощность=chp.Мощность,
                Расположение=chp.Расположение,
                Координата_X=chp.Координата_X,
                Координата_Y=chp.Координата_Y,
                ID_пользователя=chp.ID_пользователя,
                Дата_создания=chp.Дата_создания,
                Статус=chp_status,
                Количество_домов=houses_count
            ))
        return result
    except Exception as e:
        logger.error(f"Ошибка при получении списка ТЭЦ: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Внутренняя ошибка сервера: {str(e)}"
        )

@router.get(
    "/api/chps/{chp_id}",
    response_model=ТЭЦResponse,
    status_code=status.HTTP_200_OK
)
def get_chp_by_id(
    chp_id: int,
    db: Session = Depends(get_db),
    current_user: Пользователь = Depends(get_current_user)
):
    logger.info(f"Запрос ТЭЦ ID={chp_id} от пользователя: {current_user.Логин}")
    try:
        chp = db.query(ТЭЦ).filter(
            ТЭЦ.ID == chp_id,
            ТЭЦ.ID_пользователя == current_user.ID
        ).first()
        if not chp:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ТЭЦ не найдена"
            )
        
        chp_status = calculate_chp_status(chp.ID, db)
        houses_count = db.query(Дом).filter(Дом.ID_ТЭЦ == chp.ID).count()
        return ТЭЦResponse(
            ID=chp.ID,
            Порядковый_номер=chp.Порядковый_номер,
            Название=chp.Название,
            Мощность=chp.Мощность,
            Расположение=chp.Расположение,
            Координата_X=chp.Координата_X,
            Координата_Y=chp.Координата_Y,
            ID_пользователя=chp.ID_пользователя,
            Дата_создания=chp.Дата_создания,
            Статус=chp_status,
            Количество_домов=houses_count
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при получении ТЭЦ ID={chp_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Внутренняя ошибка сервера: {str(e)}"
        )

@router.post(
    "/api/chps",
    response_model=ТЭЦResponse,
    status_code=status.HTTP_201_CREATED
)
def create_chp(
    chp_data: ТЭЦCreate,
    db: Session = Depends(get_db),
    current_user: Пользователь = Depends(get_current_user)
):
    logger.info(f"Создание новой ТЭЦ пользователем: {current_user.Логин} (роль: {current_user.Роль})")
    try:
        current_chp_count = db.query(ТЭЦ).filter(ТЭЦ.ID_пользователя == current_user.ID).count()
        max_chps = get_max_chps_for_user(current_user.Роль)
        logger.info(f"У пользователя {current_user.Логин} сейчас {current_chp_count} ТЭЦ, максимум {max_chps}")
        if current_chp_count >= max_chps:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Нельзя добавить больше {max_chps} ТЭЦ."
            )
        if not is_chp_name_unique_for_user(db, chp_data.Название, current_user.ID):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="ТЭЦ с таким названием уже существует у вас"
            )
        new_number = get_next_available_chp_number(db, current_user.ID, current_user.Роль)
        if new_number is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Не удалось найти свободный порядковый номер для ТЭЦ. Максимум: {max_chps}"
            )
        
        logger.info(f"Назначен порядковый номер: {new_number}")
        x, y = get_chp_position(new_number)
        new_chp = ТЭЦ(
            Порядковый_номер=new_number,
            Название=chp_data.Название,
            Мощность=chp_data.Мощность,
            Расположение=chp_data.Расположение,
            Координата_X=x,
            Координата_Y=y,
            ID_пользователя=current_user.ID
        )
        db.add(new_chp)
        db.commit()
        db.refresh(new_chp)
        chp_status = calculate_chp_status(new_chp.ID, db)
        houses_count = db.query(Дом).filter(Дом.ID_ТЭЦ == new_chp.ID).count()
        logger.info(f"ТЭЦ успешно создана: {new_chp.Название} (номер {new_number})")
        return ТЭЦResponse(
            ID=new_chp.ID,
            Порядковый_номер=new_chp.Порядковый_номер,
            Название=new_chp.Название,
            Мощность=new_chp.Мощность,
            Расположение=new_chp.Расположение,
            Координата_X=new_chp.Координата_X,
            Координата_Y=new_chp.Координата_Y,
            ID_пользователя=new_chp.ID_пользователя,
            Дата_создания=new_chp.Дата_создания,
            Статус=chp_status,
            Количество_домов=houses_count
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при создании ТЭЦ: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Внутренняя ошибка сервера: {str(e)}"
        )

@router.put(
    "/api/chps/{chp_id}",
    response_model=ТЭЦResponse,
    status_code=status.HTTP_200_OK
)
def update_chp(
    chp_id: int,
    chp_data: ТЭЦUpdate,
    db: Session = Depends(get_db),
    current_user: Пользователь = Depends(get_current_user)
):
    logger.info(f"Обновление ТЭЦ ID={chp_id} пользователем: {current_user.Логин}")
    try:
        chp = db.query(ТЭЦ).filter(
            ТЭЦ.ID == chp_id,
            ТЭЦ.ID_пользователя == current_user.ID
        ).first()
        if not chp:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ТЭЦ не найдена"
            )
        
        if chp_data.Название and chp_data.Название != chp.Название:
            if not is_chp_name_unique_for_user(db, chp_data.Название, current_user.ID, chp_id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="ТЭЦ с таким названием уже существует у вас"
                )
            chp.Название = chp_data.Название
        
        if chp_data.Мощность is not None:
            chp.Мощность = chp_data.Мощность
        
        if chp_data.Расположение is not None:
            chp.Расположение = chp_data.Расположение
        
        db.commit()
        db.refresh(chp)
        
        chp_status = calculate_chp_status(chp.ID, db)
        houses_count = db.query(Дом).filter(Дом.ID_ТЭЦ == chp.ID).count()
        return ТЭЦResponse(
            ID=chp.ID,
            Порядковый_номер=chp.Порядковый_номер,
            Название=chp.Название,
            Мощность=chp.Мощность,
            Расположение=chp.Расположение,
            Координата_X=chp.Координата_X,
            Координата_Y=chp.Координата_Y,
            ID_пользователя=chp.ID_пользователя,
            Дата_создания=chp.Дата_создания,
            Статус=chp_status,
            Количество_домов=houses_count
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при обновлении ТЭЦ ID={chp_id}: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Внутренняя ошибка сервера: {str(e)}"
        )

@router.delete(
    "/api/chps/{chp_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_chp(
    chp_id: int,
    db: Session = Depends(get_db),
    current_user: Пользователь = Depends(get_current_user)
):
    logger.info(f"Удаление ТЭЦ ID={chp_id} пользователем: {current_user.Логин}")
    try:
        chp = db.query(ТЭЦ).filter(
            ТЭЦ.ID == chp_id,
            ТЭЦ.ID_пользователя == current_user.ID
        ).first()
        if not chp:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ТЭЦ не найдена"
            )
        
        db.delete(chp)
        db.commit()
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при удалении ТЭЦ ID={chp_id}: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Внутренняя ошибка сервера: {str(e)}"
        )

@router.get(
    "/api/users/chps/{chp_number}",
    response_model=ТЭЦResponse,
    status_code=status.HTTP_200_OK
)
def get_chp_by_number(
    chp_number: int,
    db: Session = Depends(get_db),
    current_user: Пользователь = Depends(get_current_user)
):
    if chp_number < 1 or chp_number > 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Порядковый номер должен быть от 1 до 4"
        )
    
    try:
        chp = db.query(ТЭЦ).filter(
            ТЭЦ.ID_пользователя == current_user.ID,
            ТЭЦ.Порядковый_номер == chp_number
        ).first()
        if not chp:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ТЭЦ с номером {chp_number} не найдена"
            )
        
        chp_status = calculate_chp_status(chp.ID, db)
        houses_count = db.query(Дом).filter(Дом.ID_ТЭЦ == chp.ID).count()
        return ТЭЦResponse(
            ID=chp.ID,
            Порядковый_номер=chp.Порядковый_номер,
            Название=chp.Название,
            Мощность=chp.Мощность,
            Расположение=chp.Расположение,
            Координата_X=chp.Координата_X,
            Координата_Y=chp.Координата_Y,
            ID_пользователя=chp.ID_пользователя,
            Дата_создания=chp.Дата_создания,
            Статус=chp_status,
            Количество_домов=houses_count
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при получении ТЭЦ по номеру {chp_number}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Внутренняя ошибка сервера: {str(e)}"
        )

@router.get(
    "/api/users/chps/{chp_number}/houses",
    response_model=List[ДомResponse],
    status_code=status.HTTP_200_OK
)
def get_houses_by_chp_number(
    chp_number: int,
    db: Session = Depends(get_db),
    current_user: Пользователь = Depends(get_current_user)
):
    if chp_number < 1 or chp_number > 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Порядковый номер должен быть от 1 до 4"
        )
    
    try:
        chp = db.query(ТЭЦ).filter(
            ТЭЦ.ID_пользователя == current_user.ID,
            ТЭЦ.Порядковый_номер == chp_number
        ).first()
        if not chp:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ТЭЦ с номером {chp_number} не найдена"
            )
        
        houses = get_houses_by_chp(db, chp.ID)
        result = []
        for house in houses:
            result.append(ДомResponse(
                ID=house.ID,
                Название=house.Название,
                Тип=house.Тип,
                ID_ТЭЦ=house.ID_ТЭЦ,
                Температура=house.Температура,
                Координата_X=house.Координата_X,
                Координата_Y=house.Координата_Y,
                Дата_создания=house.Дата_создания,
                Название_ТЭЦ=chp.Название,
                Статус_ТЭЦ=calculate_chp_status(chp.ID, db)
            ))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при получении домов для ТЭЦ с номером {chp_number}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Внутренняя ошибка сервера: {str(e)}"
        )

@router.get(
    "/api/users/chps/mapping",
    status_code=status.HTTP_200_OK
)
def get_chps_mapping(
    db: Session = Depends(get_db),
    current_user: Пользователь = Depends(get_current_user)
):
    try:
        chps = db.query(ТЭЦ).filter(
            ТЭЦ.ID_пользователя == current_user.ID
        ).order_by(ТЭЦ.Порядковый_номер).all()
        
        mapping = {
            chp.Порядковый_номер: {
                "id": chp.ID,
                "name": chp.Название,
                "houses_count": db.query(Дом).filter(Дом.ID_ТЭЦ == chp.ID).count()
            }
            for chp in chps
        }
        
        for i in range(1, 5):
            if i not in mapping:
                mapping[i] = None
        
        return mapping
    except Exception as e:
        logger.error(f"Ошибка при получении маппинга ТЭЦ: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Внутренняя ошибка сервера: {str(e)}"
        )

@router.get(
    "/api/houses",
    response_model=List[ДомResponse],
    status_code=status.HTTP_200_OK
)
def get_all_houses(
    db: Session = Depends(get_db),
    current_user: Пользователь = Depends(get_current_user)
):
    logger.info(f"Запрос списка домов от пользователя: {current_user.Логин}")
    try:
        houses = db.query(Дом).join(ТЭЦ).filter(
            ТЭЦ.ID_пользователя == current_user.ID
        ).order_by(Дом.ID).all()
        
        chps = db.query(ТЭЦ).filter(ТЭЦ.ID_пользователя == current_user.ID).all()
        chp_dict = {chp.ID: chp for chp in chps}
        
        result = []
        for house in houses:
            chp = chp_dict.get(house.ID_ТЭЦ)
            chp_status = calculate_chp_status(house.ID_ТЭЦ, db) if chp else None
            result.append(ДомResponse(
                ID=house.ID,
                Название=house.Название,
                Тип=house.Тип,
                ID_ТЭЦ=house.ID_ТЭЦ,
                Температура=house.Температура,
                Координата_X=house.Координата_X,
                Координата_Y=house.Координата_Y,
                Дата_создания=house.Дата_создания,
                Название_ТЭЦ=chp.Название if chp else None,
                Статус_ТЭЦ=chp_status
            ))
        return result
    except Exception as e:
        logger.error(f"Ошибка при получении списка домов: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Внутренняя ошибка сервера: {str(e)}"
        )

@router.get(
    "/api/houses/{house_id}",
    response_model=ДомResponse,
    status_code=status.HTTP_200_OK
)
def get_house_by_id(
    house_id: int,
    db: Session = Depends(get_db),
    current_user: Пользователь = Depends(get_current_user)
):
    logger.info(f"Запрос дома ID={house_id} от пользователя: {current_user.Логин}")
    try:
        house = db.query(Дом).join(ТЭЦ).filter(
            Дом.ID == house_id,
            ТЭЦ.ID_пользователя == current_user.ID
        ).first()
        if not house:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Дом не найден"
            )
        
        chp = db.query(ТЭЦ).filter(ТЭЦ.ID == house.ID_ТЭЦ).first()
        chp_status = calculate_chp_status(house.ID_ТЭЦ, db) if chp else None
        return ДомResponse(
            ID=house.ID,
            Название=house.Название,
            Тип=house.Тип,
            ID_ТЭЦ=house.ID_ТЭЦ,
            Температура=house.Температура,
            Координата_X=house.Координата_X,
            Координата_Y=house.Координата_Y,
            Дата_создания=house.Дата_создания,
            Название_ТЭЦ=chp.Название if chp else None,
            Статус_ТЭЦ=chp_status
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при получении дома ID={house_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Внутренняя ошибка сервера: {str(e)}"
        )

@router.post(
    "/api/houses",
    response_model=ДомResponse,
    status_code=status.HTTP_201_CREATED
)
def create_house(
    house_data: ДомCreate,
    db: Session = Depends(get_db),
    current_user: Пользователь = Depends(get_current_user)
):
    logger.info(f"Создание нового дома пользователем: {current_user.Логин} (роль: {current_user.Роль})")
    try:
        chp = db.query(ТЭЦ).filter(
            ТЭЦ.ID == house_data.ID_ТЭЦ,
            ТЭЦ.ID_пользователя == current_user.ID
        ).first()
        if not chp:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Указанная ТЭЦ не найдена"
            )
        
        if not check_houses_per_chp_limit(db, house_data.ID_ТЭЦ, current_user.Роль):
            max_houses = get_max_houses_for_user(current_user.Роль)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"У ТЭЦ не может быть больше {max_houses} домов. Ваша роль: {current_user.Роль}"
            )
        
        if not is_house_name_unique_for_user(db, house_data.Название, current_user.ID):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Дом с таким названием уже существует у вас"
            )
        
        existing_houses = get_houses_by_chp(db, house_data.ID_ТЭЦ)
        house_index = len(existing_houses)
        x, y = get_house_position(chp.Координата_X, chp.Координата_Y, house_index)
        temp = validate_temperature(house_data.Температура)
        
        new_house = Дом(
            Название=house_data.Название,
            Тип=house_data.Тип,
            ID_ТЭЦ=house_data.ID_ТЭЦ,
            Температура=temp,
            Координата_X=x,
            Координата_Y=y
        )
        db.add(new_house)
        db.commit()
        db.refresh(new_house)
        
        chp_status = calculate_chp_status(chp.ID, db)
        return ДомResponse(
            ID=new_house.ID,
            Название=new_house.Название,
            Тип=new_house.Тип,
            ID_ТЭЦ=new_house.ID_ТЭЦ,
            Температура=new_house.Температура,
            Координата_X=new_house.Координата_X,
            Координата_Y=new_house.Координата_Y,
            Дата_создания=new_house.Дата_создания,
            Название_ТЭЦ=chp.Название,
            Статус_ТЭЦ=chp_status
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при создании дома: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Внутренняя ошибка сервера: {str(e)}"
        )

@router.put(
    "/api/houses/{house_id}",
    response_model=ДомResponse,
    status_code=status.HTTP_200_OK
)
def update_house(
    house_id: int,
    house_data: ДомUpdate,
    db: Session = Depends(get_db),
    current_user: Пользователь = Depends(get_current_user)
):
    logger.info(f"Обновление дома ID={house_id} пользователем: {current_user.Логин}")
    try:
        house = db.query(Дом).join(ТЭЦ).filter(
            Дом.ID == house_id,
            ТЭЦ.ID_пользователя == current_user.ID
        ).first()
        if not house:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Дом не найден"
            )
        
        old_chp_id = house.ID_ТЭЦ
        
        if house_data.Название and house_data.Название != house.Название:
            if not is_house_name_unique_for_user(db, house_data.Название, current_user.ID, house_id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Дом с таким названием уже существует у вас"
                )
            house.Название = house_data.Название
        
        if house_data.ID_ТЭЦ is not None and house_data.ID_ТЭЦ != house.ID_ТЭЦ:
            new_chp = db.query(ТЭЦ).filter(
                ТЭЦ.ID == house_data.ID_ТЭЦ,
                ТЭЦ.ID_пользователя == current_user.ID
            ).first()
            if not new_chp:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Новая ТЭЦ не найдена"
                )
            
            if not check_houses_per_chp_limit(db, house_data.ID_ТЭЦ, current_user.Роль, house_id):
                max_houses = get_max_houses_for_user(current_user.Роль)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"У ТЭЦ не может быть больше {max_houses} домов. Ваша роль: {current_user.Роль}"
                )
            
            house.ID_ТЭЦ = house_data.ID_ТЭЦ
            houses_at_new_chp = get_houses_by_chp(db, house.ID_ТЭЦ)
            house_index = len(houses_at_new_chp) - 1
            new_x, new_y = get_house_position(new_chp.Координата_X, new_chp.Координата_Y, house_index)
            house.Координата_X = new_x
            house.Координата_Y = new_y
            recalc_house_positions_for_chp(db, old_chp_id)
        
        if house_data.Температура is not None:
            house.Температура = validate_temperature(house_data.Температура)
        
        db.commit()
        db.refresh(house)
        
        chp = db.query(ТЭЦ).filter(ТЭЦ.ID == house.ID_ТЭЦ).first()
        chp_status = calculate_chp_status(house.ID_ТЭЦ, db) if chp else None
        return ДомResponse(
            ID=house.ID,
            Название=house.Название,
            Тип=house.Тип,
            ID_ТЭЦ=house.ID_ТЭЦ,
            Температура=house.Температура,
            Координата_X=house.Координата_X,
            Координата_Y=house.Координата_Y,
            Дата_создания=house.Дата_создания,
            Название_ТЭЦ=chp.Название if chp else None,
            Статус_ТЭЦ=chp_status
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при обновлении дома ID={house_id}: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Внутренняя ошибка сервера: {str(e)}"
        )

@router.delete(
    "/api/houses/{house_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_house(
    house_id: int,
    db: Session = Depends(get_db),
    current_user: Пользователь = Depends(get_current_user)
):
    logger.info(f"Удаление дома ID={house_id} пользователем: {current_user.Логин}")
    try:
        house = db.query(Дом).join(ТЭЦ).filter(
            Дом.ID == house_id,
            ТЭЦ.ID_пользователя == current_user.ID
        ).first()
        if not house:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Дом не найден"
            )
        
        chp_id = house.ID_ТЭЦ
        db.delete(house)
        db.commit()
        recalc_house_positions_for_chp(db, chp_id)
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при удалении дома ID={house_id}: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Внутренняя ошибка сервера: {str(e)}"
        )

@router.get(
    "/api/chps/{chp_id}/houses",
    response_model=List[ДомResponse],
    status_code=status.HTTP_200_OK
)
def get_houses_by_chp_id(
    chp_id: int,
    db: Session = Depends(get_db),
    current_user: Пользователь = Depends(get_current_user)
):
    logger.info(f"Запрос домов ТЭЦ ID={chp_id} от пользователя: {current_user.Логин}")
    try:
        chp = db.query(ТЭЦ).filter(
            ТЭЦ.ID == chp_id,
            ТЭЦ.ID_пользователя == current_user.ID
        ).first()
        if not chp:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ТЭЦ не найдена"
            )
        
        houses = get_houses_by_chp(db, chp_id)
        result = []
        for house in houses:
            result.append(ДомResponse(
                ID=house.ID,
                Название=house.Название,
                Тип=house.Тип,
                ID_ТЭЦ=house.ID_ТЭЦ,
                Температура=house.Температура,
                Координата_X=house.Координата_X,
                Координата_Y=house.Координата_Y,
                Дата_создания=house.Дата_создания,
                Название_ТЭЦ=chp.Название,
                Статус_ТЭЦ=calculate_chp_status(chp.ID, db)
            ))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при получении домов для ТЭЦ ID={chp_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Внутренняя ошибка сервера: {str(e)}"
        )
@router.get("/api/status", status_code=status.HTTP_200_OK)
def get_system_status(
    db: Session = Depends(get_db),
    current_user: Пользователь = Depends(get_current_user)
):
    logger.info(f"Запрос статуса системы от пользователя: {current_user.Логин}")
    try:
        chps = db.query(ТЭЦ).filter(ТЭЦ.ID_пользователя == current_user.ID).all()
        statuses = {}
        for chp in chps:
            chp_stat = calculate_chp_status(chp.ID, db)
            statuses[chp.Порядковый_номер] = chp_stat
        
        total_houses = db.query(Дом).join(ТЭЦ).filter(
            ТЭЦ.ID_пользователя == current_user.ID
        ).count()
        
        result = {
            "chps_status": statuses,
            "total_chps": len(chps),
            "total_houses": total_houses,
            "max_chps": get_max_chps_for_user(current_user.Роль),
            "max_houses_per_chp": get_max_houses_for_user(current_user.Роль),
            "user_role": current_user.Роль,
            "timestamp": datetime.utcnow()
        }
        return result
    except Exception as e:
        logger.error(f"Ошибка при получении статуса системы: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Внутренняя ошибка сервера: {str(e)}"
        )