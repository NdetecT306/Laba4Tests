import sys
import os
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Теперь импорты должны работать
from server.main import app
from server.db import get_db, Base
from server.models import Пользователь, ТЭЦ, Дом
from server.auth import hash_password, verify_password

# Тестовая БД SQLite (in-memory)
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session")
def db_engine():
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(db_engine) -> Generator[Session, None, None]:
    connection = db_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    def _get_test_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _get_test_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db_session):
    user = Пользователь(
        Логин="testuser",
        Хэш_пароля=hash_password("testpass123"),
        Роль="user"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_admin(db_session):
    admin = Пользователь(
        Логин="admin",
        Хэш_пароля=hash_password("adminpass123"),
        Роль="admin"
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


@pytest.fixture
def auth_headers_user(client, test_user):
    response = client.post("/api/login", json={
        "Логин": "testuser",
        "Пароль": "testpass123"
    })
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_admin(client, test_admin):
    response = client.post("/api/login", json={
        "Логин": "admin",
        "Пароль": "adminpass123"
    })
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_chp(db_session, test_user):
    chp = ТЭЦ(
        Порядковый_номер=1,
        Название="Тестовая ТЭЦ",
        Мощность=500,
        Расположение="Тестовое расположение",
        Координата_X=750,
        Координата_Y=100,
        ID_пользователя=test_user.ID
    )
    db_session.add(chp)
    db_session.commit()
    db_session.refresh(chp)
    return chp


@pytest.fixture
def test_house(db_session, test_chp):
    house = Дом(
        Название="Тестовый дом",
        Тип="apartment",
        ID_ТЭЦ=test_chp.ID,
        Температура=60,
        Координата_X=650,
        Координата_Y=135
    )
    db_session.add(house)
    db_session.commit()
    db_session.refresh(house)
    return house


# ==================== ТЕСТЫ АВТОРИЗАЦИИ ====================

class TestAuth:
    def test_register_success(self, client):
        response = client.post("/api/register", json={
            "Логин": "newuser",
            "Пароль": "newpass123",
            "Подтверждение_пароля": "newpass123"
        })
        assert response.status_code == 201
        data = response.json()
        assert data["Логин"] == "newuser"
        assert "ID" in data

    def test_register_duplicate_login(self, client, test_user):
        response = client.post("/api/register", json={
            "Логин": "testuser",
            "Пароль": "pass123",
            "Подтверждение_пароля": "pass123"
        })
        assert response.status_code == 409
        assert "уже существует" in response.json()["detail"]

    def test_register_password_mismatch(self, client):
        response = client.post("/api/register", json={
            "Логин": "newuser",
            "Пароль": "pass123",
            "Подтверждение_пароля": "pass456"
        })
        assert response.status_code == 422

    def test_register_short_password(self, client):
        response = client.post("/api/register", json={
            "Логин": "newuser",
            "Пароль": "123",
            "Подтверждение_пароля": "123"
        })
        assert response.status_code == 422

    def test_login_success(self, client, test_user):
        response = client.post("/api/login", json={
            "Логин": "testuser",
            "Пароль": "testpass123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["username"] == "testuser"

    def test_login_wrong_password(self, client, test_user):
        response = client.post("/api/login", json={
            "Логин": "testuser",
            "Пароль": "wrongpass"
        })
        assert response.status_code == 401

    def test_login_user_not_found(self, client):
        response = client.post("/api/login", json={
            "Логин": "nonexistent",
            "Пароль": "pass123"
        })
        assert response.status_code == 401

    def test_get_current_user(self, client, auth_headers_user):
        response = client.get("/api/me", headers=auth_headers_user)
        assert response.status_code == 200
        data = response.json()
        assert data["Логин"] == "testuser"
        assert data["Роль"] == "user"

    def test_logout(self, client, auth_headers_user):
        response = client.post("/api/logout", headers=auth_headers_user)
        assert response.status_code == 200


# ==================== ТЕСТЫ ТЭЦ ====================

class TestCHPs:
    def test_get_chps_empty(self, client, auth_headers_user):
        response = client.get("/api/chps", headers=auth_headers_user)
        assert response.status_code == 200
        assert response.json() == []

    def test_create_chp_success(self, client, auth_headers_user):
        response = client.post("/api/chps", headers=auth_headers_user, json={
            "Название": "Южная ТЭЦ",
            "Мощность": 750,
            "Расположение": "Южный район"
        })
        assert response.status_code == 201
        data = response.json()
        assert data["Название"] == "Южная ТЭЦ"
        assert data["Мощность"] == 750
        assert data["Порядковый_номер"] == 1

    def test_create_chp_exceeds_limit(self, client, auth_headers_user):
        # Создаем 4 ТЭЦ
        for i in range(4):
            client.post("/api/chps", headers=auth_headers_user, json={
                "Название": f"ТЭЦ {i+1}",
                "Мощность": 500,
                "Расположение": f"Район {i+1}"
            })
        
        response = client.post("/api/chps", headers=auth_headers_user, json={
            "Название": "Лишняя ТЭЦ",
            "Мощность": 500,
            "Расположение": "Лишний район"
        })
        assert response.status_code == 403

    def test_create_chp_duplicate_name(self, client, auth_headers_user, test_chp):
        response = client.post("/api/chps", headers=auth_headers_user, json={
            "Название": "Тестовая ТЭЦ",
            "Мощность": 500,
            "Расположение": "Другое место"
        })
        assert response.status_code == 409

    def test_get_chps_list(self, client, auth_headers_user, test_chp):
        response = client.get("/api/chps", headers=auth_headers_user)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["Название"] == "Тестовая ТЭЦ"

    def test_get_chp_by_id(self, client, auth_headers_user, test_chp):
        response = client.get(f"/api/chps/{test_chp.ID}", headers=auth_headers_user)
        assert response.status_code == 200
        data = response.json()
        assert data["ID"] == test_chp.ID

    def test_get_chp_not_found(self, client, auth_headers_user):
        response = client.get("/api/chps/9999", headers=auth_headers_user)
        assert response.status_code == 404

    def test_update_chp(self, client, auth_headers_user, test_chp):
        response = client.put(f"/api/chps/{test_chp.ID}", headers=auth_headers_user, json={
            "Название": "Обновленная ТЭЦ",
            "Мощность": 800
        })
        assert response.status_code == 200
        data = response.json()
        assert data["Название"] == "Обновленная ТЭЦ"
        assert data["Мощность"] == 800

    def test_delete_chp(self, client, auth_headers_user, test_chp):
        response = client.delete(f"/api/chps/{test_chp.ID}", headers=auth_headers_user)
        assert response.status_code == 204
        
        get_response = client.get(f"/api/chps/{test_chp.ID}", headers=auth_headers_user)
        assert get_response.status_code == 404

    def test_get_chp_by_number(self, client, auth_headers_user, test_chp):
        response = client.get("/api/users/chps/1", headers=auth_headers_user)
        assert response.status_code == 200
        data = response.json()
        assert data["Порядковый_номер"] == 1


    def test_admin_can_create_5_chps(self, client, auth_headers_admin):
        for i in range(5):
            response = client.post("/api/chps", headers=auth_headers_admin, json={
                "Название": f"Админ ТЭЦ {i+1}",
                "Мощность": 500,
                "Расположение": f"Район {i+1}"
            })
            assert response.status_code == 201
        
        response = client.post("/api/chps", headers=auth_headers_admin, json={
            "Название": "Шестая ТЭЦ",
            "Мощность": 500,
            "Расположение": "Шестой район"
        })
        assert response.status_code == 403


# ==================== ТЕСТЫ ДОМОВ ====================

class TestHouses:
    def test_create_house_success(self, client, auth_headers_user, test_chp):
        response = client.post("/api/houses", headers=auth_headers_user, json={
            "Название": "Жилой комплекс",
            "Тип": "apartment",
            "ID_ТЭЦ": test_chp.ID,
            "Температура": 65
        })
        assert response.status_code == 201
        data = response.json()
        assert data["Название"] == "Жилой комплекс"
        assert data["Тип"] == "apartment"

    def test_create_house_default_temperature(self, client, auth_headers_user, test_chp):
        response = client.post("/api/houses", headers=auth_headers_user, json={
            "Название": "Дом с дефолтной температурой",
            "Тип": "private",
            "ID_ТЭЦ": test_chp.ID
        })
        assert response.status_code == 201
        data = response.json()
        assert data["Температура"] == 60

    def test_create_house_exceeds_limit(self, client, auth_headers_user, test_chp):
        for i in range(5):
            client.post("/api/houses", headers=auth_headers_user, json={
                "Название": f"Дом {i+1}",
                "Тип": "apartment",
                "ID_ТЭЦ": test_chp.ID
            })
        
        response = client.post("/api/houses", headers=auth_headers_user, json={
            "Название": "Шестой дом",
            "Тип": "apartment",
            "ID_ТЭЦ": test_chp.ID
        })
        assert response.status_code == 403

    def test_create_house_duplicate_name(self, client, auth_headers_user, test_chp, test_house):
        response = client.post("/api/houses", headers=auth_headers_user, json={
            "Название": "Тестовый дом",
            "Тип": "apartment",
            "ID_ТЭЦ": test_chp.ID
        })
        assert response.status_code == 409

    def test_get_houses_list(self, client, auth_headers_user, test_house):
        response = client.get("/api/houses", headers=auth_headers_user)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    def test_get_house_by_id(self, client, auth_headers_user, test_house):
        response = client.get(f"/api/houses/{test_house.ID}", headers=auth_headers_user)
        assert response.status_code == 200
        data = response.json()
        assert data["ID"] == test_house.ID

    def test_get_houses_by_chp_id(self, client, auth_headers_user, test_chp, test_house):
        response = client.get(f"/api/chps/{test_chp.ID}/houses", headers=auth_headers_user)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    def test_update_house_temperature(self, client, auth_headers_user, test_house):
        response = client.put(f"/api/houses/{test_house.ID}", headers=auth_headers_user, json={
            "Температура": 75
        })
        assert response.status_code == 200
        data = response.json()
        assert data["Температура"] == 75

    def test_update_house_name(self, client, auth_headers_user, test_house):
        response = client.put(f"/api/houses/{test_house.ID}", headers=auth_headers_user, json={
            "Название": "Переименованный дом"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["Название"] == "Переименованный дом"

    def test_move_house_to_another_chp(self, client, auth_headers_user, test_chp, test_house):
        response = client.post("/api/chps", headers=auth_headers_user, json={
            "Название": "Вторая ТЭЦ",
            "Мощность": 600,
            "Расположение": "Северный район"
        })
        second_chp = response.json()
        
        response = client.put(f"/api/houses/{test_house.ID}", headers=auth_headers_user, json={
            "ID_ТЭЦ": second_chp["ID"]
        })
        assert response.status_code == 200
        data = response.json()
        assert data["ID_ТЭЦ"] == second_chp["ID"]

    def test_delete_house(self, client, auth_headers_user, test_house):
        response = client.delete(f"/api/houses/{test_house.ID}", headers=auth_headers_user)
        assert response.status_code == 204
        
        get_response = client.get(f"/api/houses/{test_house.ID}", headers=auth_headers_user)
        assert get_response.status_code == 404


# ==================== ТЕСТЫ ЛИМИТОВ И СТАТУСОВ ====================

class TestLimitsAndStatus:
    def test_status_endpoint(self, client, auth_headers_user, test_chp, test_house):
        response = client.get("/api/status", headers=auth_headers_user)
        assert response.status_code == 200
        data = response.json()
        assert "chps_status" in data
        assert data["total_chps"] == 1
        assert data["total_houses"] == 1
        assert data["max_chps"] == 4
        assert data["max_houses_per_chp"] == 5
        assert data["user_role"] == "user"

    def test_status_endpoint_admin(self, client, auth_headers_admin, test_admin):
        response = client.get("/api/status", headers=auth_headers_admin)
        assert response.status_code == 200
        data = response.json()
        assert data["max_chps"] == 5
        assert data["max_houses_per_chp"] == 6
        assert data["user_role"] == "admin"

    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_root_endpoint(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])