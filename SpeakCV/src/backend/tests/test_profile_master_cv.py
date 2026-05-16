from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.database import get_db
from app.database.sql_models import Base, User, UserProfile
from app.routers.profile import get_current_user, router


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

app = FastAPI()
app.include_router(router)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def override_get_current_user():
    db = TestingSessionLocal()
    try:
        return db.query(User).filter(User.email == "test@example.com").first()
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user
client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        user = User(
            email="test@example.com",
            full_name="Test User",
            hashed_password="hashed",
            role="user",
            credits=50,
            plan="free",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        profile = UserProfile(
            user_id=user.id,
            summary="Existing summary",
            master_cv_text="Senior backend engineer with Python and FastAPI experience.",
        )
        db.add(profile)
        db.commit()
    finally:
        db.close()



def test_get_my_profile_returns_master_cv_text_in_info():
    response = client.get("/api/my-profile")

    assert response.status_code == 200
    payload = response.json()
    assert payload["info"]["master_cv_text"] == "Senior backend engineer with Python and FastAPI experience."



def test_update_profile_saves_master_cv_text():
    response = client.put(
        "/api/my-profile",
        json={
            "master_cv_text": "Updated master CV content for profile storage.",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"message": "Profile updated successfully"}

    db = TestingSessionLocal()
    try:
        profile = db.query(UserProfile).join(User, UserProfile.user_id == User.id).filter(User.email == "test@example.com").first()
        assert profile.master_cv_text == "Updated master CV content for profile storage."
    finally:
        db.close()
