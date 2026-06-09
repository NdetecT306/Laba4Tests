from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .db import Base

class Пользователь(Base):
    __tablename__ = "Пользователи"
    ID = Column(Integer, primary_key=True, index=True)
    Логин = Column(String(50), unique=True, nullable=False, index=True)
    Хэш_пароля = Column("Хэш пароля", String(255), nullable=False)
    Дата_создания = Column("Дата создания", DateTime, server_default=func.now())
    Роль = Column(String(20), default="user", nullable=False)
    тэц = relationship("ТЭЦ", back_populates="пользователь", cascade="all, delete-orphan")

class ТЭЦ(Base):
    __tablename__ = "ТЭЦ"
    ID = Column(Integer, primary_key=True, index=True)
    Порядковый_номер = Column("Порядковый номер", Integer, nullable=False)
    Название = Column(String(100), nullable=False, index=True)
    Мощность = Column(Integer, nullable=False)
    Расположение = Column(String(200), nullable=False)
    Координата_X = Column("Координата X", Integer, nullable=False)
    Координата_Y = Column("Координата Y", Integer, nullable=False)
    ID_пользователя = Column("ID пользователя", Integer, ForeignKey("Пользователи.ID", ondelete="CASCADE"), nullable=False)
    Дата_создания = Column("Дата создания", DateTime, server_default=func.now())
    __table_args__ = (
        CheckConstraint('"Порядковый номер" >= 1', name='check_порядковый_номер'),
        CheckConstraint('"Мощность" >= 100 AND "Мощность" <= 1000', name='check_мощность'),
    )
    пользователь = relationship("Пользователь", back_populates="тэц")
    дома = relationship("Дом", back_populates="тэц", cascade="all, delete-orphan")

class Дом(Base):
    __tablename__ = "Дома"
    ID = Column(Integer, primary_key=True, index=True)
    Название = Column(String(100), nullable=False, index=True)
    Тип = Column(String(20), nullable=False)
    ID_ТЭЦ = Column("ID ТЭЦ", Integer, ForeignKey("ТЭЦ.ID", ondelete="CASCADE"), nullable=False)
    Температура = Column(Integer, nullable=False)
    Координата_X = Column("Координата X", Integer, nullable=False)
    Координата_Y = Column("Координата Y", Integer, nullable=False)
    Дата_создания = Column("Дата создания", DateTime, server_default=func.now())
    __table_args__ = (
        CheckConstraint('"Тип" IN (\'apartment\', \'private\')', name='check_тип'),
        CheckConstraint('"Температура" >= 40 AND "Температура" <= 95', name='check_температура'),
    )
    тэц = relationship("ТЭЦ", back_populates="дома")