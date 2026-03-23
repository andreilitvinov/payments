import os
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Use in-memory SQLite for tests (same schema as PostgreSQL)
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from config import Settings
from db.base import Base
from db.models import OrderModel, PaymentModel
from main import app

# Override settings for tests
@pytest.fixture(scope="session")
def settings():
    return Settings(database_url="sqlite:///:memory:")


@pytest.fixture(scope="function")
def engine(settings):
    _engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
        poolclass=StaticPool if "sqlite" in settings.database_url else None,
    )
    Base.metadata.create_all(_engine)
    return _engine


@pytest.fixture
def db_session(engine) -> Generator[Session, None, None]:
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client(db_session):
    from fastapi.testclient import TestClient
    from db.session import get_db
    def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
