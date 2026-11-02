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
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .core import settings
from .core.rate_limit import limiter
from .routers import profile, auth, cv, admin, companies, kb_documents, kb_conflicts, kb_review, copilot, jobs_hr, public_jobs
from .routers import applications as applications_router
from .routers import board as board_router
from .routers import screening as screening_router
from .routers import trust
from .routers import interviews as interviews_router
from .routers import job_drafts as job_drafts_router
from .routers import hiring_requests as hiring_requests_router
from .routers import reality_check as reality_check_router
from .routers import insights as insights_router
from .routers import onboarding as onboarding_router
from .routers import talent_pool as talent_pool_router
from .brain import fake_demo, ingestion
from .bridges import intake
from .hiring import analysis, cv_processing
from .hiring import retention
from .hiring import fake_demo as hiring_fake_demo
from .database import sql_models
from .database.database import SessionLocal
from .auth.security import get_password_hash
from .ai.config import load_config
from .ai.providers import get_provider
from .ai.types import AIOutputError, AIProviderError

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
    seed_admin()
    ingestion.fail_interrupted_jobs()
    cv_processing.fail_interrupted()
    analysis.recover_interrupted()
    intake.recover_interrupted()
    retention_task = retention.start_daily_task(app)
    yield
    if retention_task is not None:
        retention_task.cancel()


def _include_legacy_routers(app: FastAPI) -> None:
    from .routers import interview, payment, questions, stats, support

    app.include_router(profile.legacy_router)
    app.include_router(cv.legacy_router)
    app.include_router(admin.legacy_brain_router)
    for module in (interview, support, payment, stats, questions):
        app.include_router(module.router)


def create_app(legacy_b2c: bool | None = None) -> FastAPI:
    config = load_config()  # bad AI configuration must fail startup
    # Build each real provider now, so a bad setting or a missing SDK stops the start, not a later request.
    for provider in sorted({slot.provider for slot in config.slots.values()} - {"fake"}):
        get_provider(provider)
    origins = settings.allowed_origins()
    settings.max_upload_bytes()
    fake_demo.install()
    hiring_fake_demo.install()
    app = FastAPI(lifespan=lifespan)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    @app.exception_handler(AIProviderError)
    async def _ai_provider_error(_request, _exc):
        return JSONResponse(status_code=503, content={"detail": "The AI service is temporarily unavailable. Please try again."})

    @app.exception_handler(AIOutputError)
    async def _ai_output_error(_request, _exc):
        return JSONResponse(status_code=502, content={"detail": "The AI service returned an unusable response. Please try again."})

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
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
    app.include_router(companies.router)
    app.include_router(kb_documents.router)
    app.include_router(kb_conflicts.router)
    app.include_router(kb_review.router)
    app.include_router(copilot.router)
    app.include_router(jobs_hr.router)
    app.include_router(public_jobs.router)
    app.include_router(applications_router.router)
    app.include_router(board_router.router)
    app.include_router(screening_router.router)
    app.include_router(interviews_router.router)
    app.include_router(trust.router)
    app.include_router(trust.me_router)
    app.include_router(job_drafts_router.router)
    app.include_router(hiring_requests_router.router)
    app.include_router(reality_check_router.router)
    app.include_router(insights_router.router)
    app.include_router(onboarding_router.router)
    app.include_router(talent_pool_router.router)
    app.include_router(talent_pool_router.company_router)
    enabled = settings.flag("LEGACY_B2C_ENABLED") if legacy_b2c is None else legacy_b2c
    if enabled:
        _include_legacy_routers(app)
    return app


app = create_app()
