from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime

class РегистрацияRequest(BaseModel):
    Логин: str = Field(..., min_length=3, max_length=50)
    Пароль: str = Field(..., min_length=4)
    Подтверждение_пароля: str    
    @validator('Логин')
    def validate_login(cls, v):
        if not v.strip():
            raise ValueError('Логин не может быть пустым')
        if ' ' in v:
            raise ValueError('Логин не может содержать пробелы')
        return v.strip()
    @validator('Пароль')
    def validate_password(cls, v):
        if not v.strip():
            raise ValueError('Пароль не может быть пустым')
        return v
    @validator('Подтверждение_пароля')
    def passwords_match(cls, v, values):
        if 'Пароль' in values and v != values['Пароль']:
            raise ValueError('Пароли не совпадают')
        return v

class ЛогинRequest(BaseModel):
    Логин: str
    Пароль: str
    @validator('Логин')
    def validate_login(cls, v):
        if not v or not v.strip():
            raise ValueError('Логин не может быть пустым')
        return v.strip()

class ТокенResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str

class ПользовательResponse(BaseModel):
    ID: int
    Логин: str
    Дата_создания: datetime
    Роль: Optional[str] = "user"
    class Config:
        from_attributes = True

class ТЭЦCreate(BaseModel):
    Название: str = Field(..., min_length=2, max_length=100)
    Мощность: int = Field(..., ge=100, le=1000)
    Расположение: str = Field(..., min_length=2, max_length=200)
    @validator('Название')
    def validate_name(cls, v):
        if not v or not v.strip():
            raise ValueError('Название не может быть пустым')
        forbidden = ['--', ';', 'DROP', 'DELETE', 'INSERT', 'UPDATE']
        upper_v = v.upper()
        for word in forbidden:
            if word in upper_v:
                raise ValueError(f'Название содержит недопустимые символы: {word}')
        return v.strip()

class ТЭЦUpdate(BaseModel):
    Название: Optional[str] = Field(None, min_length=2, max_length=100)
    Мощность: Optional[int] = Field(None, ge=100, le=1000)
    Расположение: Optional[str] = Field(None, min_length=2, max_length=200)

class ТЭЦResponse(BaseModel):
    ID: int
    Порядковый_номер: int
    Название: str
    Мощность: int
    Расположение: str
    Координата_X: int
    Координата_Y: int
    ID_пользователя: int
    Дата_создания: datetime
    Статус: Optional[str] = None
    Количество_домов: int = 0
    class Config:
        from_attributes = True

class ДомCreate(BaseModel):
    Название: str = Field(..., min_length=2, max_length=100)
    Тип: str = Field(..., pattern="^(apartment|private)$")
    ID_ТЭЦ: int
    Температура: int = Field(60, ge=40, le=95)
    @validator('Название')
    def validate_name(cls, v):
        if not v or not v.strip():
            raise ValueError('Название не может быть пустым')
        return v.strip()

class ДомUpdate(BaseModel):
    Название: Optional[str] = Field(None, min_length=2, max_length=100)
    ID_ТЭЦ: Optional[int] = None
    Температура: Optional[int] = Field(None, ge=40, le=95)

class ДомResponse(BaseModel):
    ID: int
    Название: str
    Тип: str
    ID_ТЭЦ: int
    Температура: int
    Координата_X: int
    Координата_Y: int
    Дата_создания: datetime
    Название_ТЭЦ: Optional[str] = None
    Статус_ТЭЦ: Optional[str] = None
    class Config:
        from_attributes = True

class MessageResponse(BaseModel):
    message: str
    detail: Optional[str] = None

class ErrorResponse(BaseModel):
    detail: str
    status_code: int