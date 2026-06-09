import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import pytest
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from server.main import app
from server.db import get_db, Base

IS_CI = os.environ.get('CI') == 'true'
if IS_CI:
    SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    from server.db import get_db_engine
    engine = get_db_engine()
    
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

Base.metadata.create_all(bind=engine)

@pytest.fixture(scope="session")
def db_engine():
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

from server.auth import hash_password, verify_password

@pytest.fixture
def test_user(db_session):
    from server.models import Пользователь
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
    from server.models import Пользователь
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
    from server.models import ТЭЦ
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
    from server.models import Дом
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

    def test_login_success(self, client, test_user):
        response = client.post("/api/login", json={
            "Логин": "testuser",
            "Пароль": "testpass123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data

    def test_login_wrong_password(self, client, test_user):
        response = client.post("/api/login", json={
            "Логин": "testuser",
            "Пароль": "wrongpass"
        })
        assert response.status_code == 401

class TestCHPs:
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

    def test_get_chps_empty(self, client, auth_headers_user):
        response = client.get("/api/chps", headers=auth_headers_user)
        assert response.status_code == 200
        assert response.json() == []

    def test_create_chp_duplicate_name(self, client, auth_headers_user, test_chp):
        response = client.post("/api/chps", headers=auth_headers_user, json={
            "Название": "Тестовая ТЭЦ",
            "Мощность": 500,
            "Расположение": "Другое место"
        })
        assert response.status_code == 409

    def test_delete_chp(self, client, auth_headers_user, test_chp):
        response = client.delete(f"/api/chps/{test_chp.ID}", headers=auth_headers_user)
        assert response.status_code == 204

class TestHouses:
    def test_create_house_success(self, client, auth_headers_user, test_chp):
        response = client.post("/api/houses", headers=auth_headers_user, json={
            "Название": "Жилой комплекс",
            "Тип": "apartment",
            "ID_ТЭЦ": test_chp.ID,
            "Температура": 65
        })
        assert response.status_code == 201

    def test_get_houses_list(self, client, auth_headers_user, test_house):
        response = client.get("/api/houses", headers=auth_headers_user)
        assert response.status_code == 200

    def test_update_house_temperature(self, client, auth_headers_user, test_house):
        response = client.put(f"/api/houses/{test_house.ID}", headers=auth_headers_user, json={
            "Температура": 75
        })
        assert response.status_code == 200

    def test_delete_house(self, client, auth_headers_user, test_house):
        response = client.delete(f"/api/houses/{test_house.ID}", headers=auth_headers_user)
        assert response.status_code == 204

class TestStatus:
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
