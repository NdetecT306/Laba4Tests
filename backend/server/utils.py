from typing import List, Tuple, Dict, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from .models import ТЭЦ, Дом

# Лимиты для обычного пользователя
MAX_CHPS_DEFAULT = 4
MAX_HOUSES_PER_CHP_DEFAULT = 5

# Лимиты для администратора
MAX_CHPS_ADMIN = 5
MAX_HOUSES_PER_CHP_ADMIN = 6

TEMP_MIN = 40
TEMP_MAX = 95
TEMP_NORMAL = 60

# Позиции для ТЭЦ (1-4 для всех, 5 только для админа)
CHP_POSITIONS = {
    1: (750, 100),      # Верхний правый
    2: (750, 550),      # Нижний правый
    3: (100, 550),      # Нижний левый
    4: (100, 100),      # Верхний левый
    5: (425, 325)       # Центр (для администратора)
}

def get_max_chps_for_user(user_role: str) -> int:
    """Возвращает максимальное количество ТЭЦ для пользователя в зависимости от роли"""
    if user_role == "admin":
        return MAX_CHPS_ADMIN
    return MAX_CHPS_DEFAULT

def get_max_houses_for_user(user_role: str) -> int:
    """Возвращает максимальное количество домов на ТЭЦ в зависимости от роли"""
    if user_role == "admin":
        return MAX_HOUSES_PER_CHP_ADMIN
    return MAX_HOUSES_PER_CHP_DEFAULT

def get_chp_position(chp_number: int) -> Tuple[int, int]:
    """Возвращает координаты для ТЭЦ по её порядковому номеру"""
    if chp_number not in CHP_POSITIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Номер ТЭЦ должен быть от 1 до {len(CHP_POSITIONS)}. Получено: {chp_number}"
        )
    return CHP_POSITIONS[chp_number]

def get_next_available_chp_number(db: Session, user_id: int, user_role: str) -> Optional[int]:
    """Возвращает следующий доступный порядковый номер для ТЭЦ с учётом роли"""
    existing_numbers = {chp[0] for chp in db.query(ТЭЦ.Порядковый_номер).filter(ТЭЦ.ID_пользователя == user_id).all()}
    max_chps = get_max_chps_for_user(user_role)
    for i in range(1, max_chps + 1):
        if i not in existing_numbers:
            return i
    return None

def is_chp_number_available_for_user(db: Session, user_id: int, chp_number: int) -> bool:
    return db.query(ТЭЦ).filter(
        ТЭЦ.ID_пользователя == user_id,
        ТЭЦ.Порядковый_номер == chp_number
    ).first() is None

def get_all_chp_ids(db: Session) -> List[int]:
    return [chp[0] for chp in db.query(ТЭЦ.ID).order_by(ТЭЦ.ID).all()]

def get_house_position(chp_x: int, chp_y: int, house_index: int) -> Tuple[int, int]:
    """Возвращает позицию дома относительно ТЭЦ"""
    if house_index >= MAX_HOUSES_PER_CHP_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Индекс дома не может быть больше {MAX_HOUSES_PER_CHP_ADMIN - 1}"
        )
    
    # Для центральной ТЭЦ (позиция 5) - другое расположение домов
    if chp_x == 425 and chp_y == 325:
        # Дома вокруг центральной ТЭЦ по кругу
        positions = [
            (425, 235),  # Вверх
            (425, 415),  # Вниз
            (335, 325),  # Влево
            (515, 325),  # Вправо
            (380, 280),  # Вверх-влево
            (470, 370)   # Вниз-вправо
        ]
        if house_index < len(positions):
            return positions[house_index]
        return (chp_x + 50, chp_y + 50 * (house_index + 1))
    
    # Для угловых ТЭЦ
    if chp_x == 750 and chp_y == 100:      # Верхний правый
        offset_x = -100
        offset_y = 35 + (house_index * 70)
    elif chp_x == 750 and chp_y == 550:    # Нижний правый
        offset_x = -100
        offset_y = -35 - (house_index * 70)
    elif chp_x == 100 and chp_y == 550:    # Нижний левый
        offset_x = 100
        offset_y = -35 - (house_index * 70)
    else:                                   # Верхний левый
        offset_x = 100
        offset_y = 35 + (house_index * 70)
    
    return (chp_x + offset_x, chp_y + offset_y)

def get_houses_by_chp(db: Session, chp_id: int) -> List[Дом]:
    return db.query(Дом).filter(Дом.ID_ТЭЦ == chp_id).order_by(Дом.ID).all()

def recalc_house_positions_for_chp(db: Session, chp_id: int):
    houses = get_houses_by_chp(db, chp_id)
    chp = db.query(ТЭЦ).filter(ТЭЦ.ID == chp_id).first()
    if not chp:
        return
    for index, house in enumerate(houses):
        new_x, new_y = get_house_position(chp.Координата_X, chp.Координата_Y, index)
        house.Координата_X = new_x
        house.Координата_Y = new_y
    db.commit()

def calculate_chp_status(chp_id: int, db: Session) -> str:
    houses = get_houses_by_chp(db, chp_id)
    if len(houses) == 0:
        return 'working'
    all_at_max = all(house.Температура == TEMP_MAX for house in houses)
    all_at_min = all(house.Температура == TEMP_MIN for house in houses)
    if all_at_max or all_at_min:
        return 'off'
    return 'working'

def get_all_chp_statuses(db: Session) -> Dict[int, str]:
    chps = db.query(ТЭЦ).all()
    return {chp.ID: calculate_chp_status(chp.ID, db) for chp in chps}

def check_chp_limit_for_user(db: Session, user_id: int, user_role: str) -> bool:
    """Проверка лимита ТЭЦ с учётом роли"""
    count = db.query(ТЭЦ).filter(ТЭЦ.ID_пользователя == user_id).count()
    max_chps = get_max_chps_for_user(user_role)
    return count < max_chps

def check_houses_per_chp_limit(db: Session, chp_id: int, user_role: str, exclude_house_id: Optional[int] = None) -> bool:
    """Проверка лимита домов на ТЭЦ с учётом роли владельца"""
    query = db.query(Дом).filter(Дом.ID_ТЭЦ == chp_id)
    if exclude_house_id:
        query = query.filter(Дом.ID != exclude_house_id)
    count = query.count()
    max_houses = get_max_houses_for_user(user_role)
    return count < max_houses

def is_chp_name_unique_for_user(db: Session, name: str, user_id: int, exclude_id: Optional[int] = None) -> bool:
    query = db.query(ТЭЦ).filter(
        ТЭЦ.Название == name,
        ТЭЦ.ID_пользователя == user_id
    )
    if exclude_id:
        query = query.filter(ТЭЦ.ID != exclude_id)
    return query.first() is None

def is_house_name_unique_for_user(db: Session, name: str, user_id: int, exclude_id: Optional[int] = None) -> bool:
    query = db.query(Дом).join(ТЭЦ).filter(
        Дом.Название == name,
        ТЭЦ.ID_пользователя == user_id
    )
    if exclude_id:
        query = query.filter(Дом.ID != exclude_id)
    return query.first() is None

def validate_temperature(temp: int) -> int:
    if temp < TEMP_MIN:
        return TEMP_MIN
    if temp > TEMP_MAX:
        return TEMP_MAX
    return temp

def get_temperature_status(temp: int) -> str:
    if temp < 60:
        return 'cold'
    elif temp <= 80:
        return 'normal'
    else:
        return 'hot'