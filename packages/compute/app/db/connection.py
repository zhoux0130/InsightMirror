from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import Generator

from app.config import settings

# SQLAlchemy 2.1 起 postgresql:// 默认改用 psycopg(3)；本项目装的是 psycopg2，这里显式指定驱动。
_url = settings.database_url
if _url.startswith("postgresql://"):
    _url = "postgresql+psycopg2://" + _url[len("postgresql://"):]

engine = create_engine(
    _url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@contextmanager
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
