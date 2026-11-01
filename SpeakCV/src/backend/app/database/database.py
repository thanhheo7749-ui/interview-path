# Copyright (c) 2026 SpeakCV Team
# This project is licensed under the MIT License.
# See the LICENSE file in the project root for more information.

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import settings

SQLALCHEMY_DATABASE_URL = settings.database_url()

_engine_kwargs = {}
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
    if SQLALCHEMY_DATABASE_URL in {"sqlite://", "sqlite:///:memory:"}:
        _engine_kwargs["poolclass"] = StaticPool

engine = create_engine(SQLALCHEMY_DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

