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
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import inspect, text

from .core import settings
from .core.rate_limit import limiter
from .routers import profile, auth, cv, admin, interview, support, payment, jobs, stats, questions
from .database import sql_models
from .database.database import engine, SessionLocal
from .auth.security import get_password_hash

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
    """Create the admin account if configured and absent. Never modifies an existing user."""
    admin_email = os.environ.get("ADMIN_EMAIL", "").strip()
    admin_password = os.environ.get("ADMIN_PASSWORD", "")
    admin_name = os.environ.get("ADMIN_NAME", "").strip() or "Admin"
    if not admin_email or not admin_password:
        return

    db = SessionLocal()
    try:
        existing = db.query(sql_models.User).filter(sql_models.User.email == admin_email).first()
        if existing:
            return
        db.add(sql_models.User(
            email=admin_email,
            full_name=admin_name,
            hashed_password=get_password_hash(admin_password),
            role="admin",
        ))
        db.commit()
        print(f"[SEED] Admin account created: {admin_email}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_profile_master_cv_column()
    seed_admin()
    yield


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.csv_list("ALLOWED_ORIGINS"),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=[
            "X-AI-Response-Text",
            "X-Interview-Trace-Id",
            "X-Interview-Analysis",
            "X-Interview-Usage",
        ],
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
    return app


app = create_app()
