from app.auth.security import create_access_token
from app.database.sql_models import User


def make_user(db, email, role="user"):
    user = User(email=email, full_name=email.split("@")[0], hashed_password="not-a-real-hash", role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def auth_header(email):
    return {"Authorization": f"Bearer {create_access_token({'sub': email})}"}
