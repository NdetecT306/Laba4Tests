import sys
sys.path.append('.')
from server.db import SessionLocal
from server.models import Пользователь
from server.auth import hash_password

db = SessionLocal()
admin = db.query(Пользователь).filter(Пользователь.Логин == 'admin').first()
if admin:
    admin.Роль = 'admin'
    print(f"Пользователь admin назначен администратором")
else:
    new_admin = Пользователь(
        Логин='admin',
        Хэш_пароля=hash_password('admin123'),
        Роль='admin'
    )
    db.add(new_admin)
    print(f"Администратор admin создан с паролем admin123")
db.commit()
db.close()
