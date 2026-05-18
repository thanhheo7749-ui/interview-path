# Copyright (c) 2026 SpeakCV Team
# This project is licensed under the MIT License.
# See the LICENSE file in the project root for more information.

import os
import sys

# Force UTF-8 encoding for standard output to avoid UnicodeEncodeError on Windows
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pathlib import Path
from sqlalchemy import inspect, text

from .routers import profile, auth, cv, admin, interview, support, payment, jobs, stats, questions
from .database import sql_models          
from .database.database import engine, SessionLocal
from .auth.security import get_password_hash

# Load root project .env first, then local .env overrides
_resolved = Path(__file__).resolve()
_root_candidate = _resolved.parents[2] / ".env"
if _root_candidate.exists():
    load_dotenv(_root_candidate)
load_dotenv(override=True)  # local src/backend/.env overrides

sql_models.Base.metadata.create_all(bind=engine)


def ensure_profile_master_cv_column():
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("user_profiles")}

    with engine.begin() as connection:
        if "master_cv_text" not in columns:
            connection.execute(text("ALTER TABLE user_profiles ADD COLUMN master_cv_text TEXT NULL"))
            print("[MIGRATE] Added user_profiles.master_cv_text column")
        if "master_cv_structured" not in columns:
            connection.execute(text("ALTER TABLE user_profiles ADD COLUMN master_cv_structured JSON NULL"))
            print("[MIGRATE] Added user_profiles.master_cv_structured column")

        if "master_cv_text" not in columns or "master_cv_structured" not in columns:
            return


def seed_admin():
    """Create admin account if it doesn't exist, or reset password + role if it does."""
    admin_email = os.getenv("ADMIN_EMAIL", "admin@gmail.com")
    admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
    admin_name = os.getenv("ADMIN_NAME", "Admin")

    db = SessionLocal()
    try:
        existing = db.query(sql_models.User).filter(sql_models.User.email == admin_email).first()
        if not existing:
            new_admin = sql_models.User(
                email=admin_email,
                full_name=admin_name,
                hashed_password=get_password_hash(admin_password),
                role="admin"
            )
            db.add(new_admin)
            db.commit()
            print(f"[SEED] Admin account created: {admin_email}")
        else:
            # Always ensure admin has correct role, name, and password
            changed = False
            if existing.role != "admin":
                existing.role = "admin"
                changed = True
            # Reset password to env value (fixes Google OAuth random password issue)
            existing.hashed_password = get_password_hash(admin_password)
            existing.full_name = admin_name
            changed = True
            if changed:
                db.commit()
                print(f"[SEED] Admin account reset for: {admin_email}")
            else:
                print(f"[SEED] Admin account already exists: {admin_email}")
    finally:
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_profile_master_cv_column()
    seed_admin()
    yield

app = FastAPI(lifespan=lifespan)

default_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:8001",
    "http://127.0.0.1:8001",
]

configured_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "").split(",")
    if origin.strip()
]
origins = list(dict.fromkeys(default_origins + configured_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,       
    allow_credentials=True,      
    allow_methods=["*"],       
    allow_headers=["*"],
    expose_headers=["X-AI-Response-Text"]
)

app.include_router(profile.router)
app.include_router(auth.router)
app.include_router(cv.router)
app.include_router(admin.router)
app.include_router(interview.router)
app.include_router(support.router)
app.include_router(payment.router)
app.include_router(jobs.router)
app.include_router(stats.router)
app.include_router(questions.router)
