from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from config import Settings
from .base import Base
from .models import OrderModel, PaymentModel

_settings = Settings()
engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
