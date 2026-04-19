"""
SQLAlchemy engine, session factory, and Base declarative class.
Production-ready (Alembic-based migrations).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from config.db_config import settings
from logger import Database_logger as logger

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False}
    if "sqlite" in settings.DATABASE_URL.lower()
    else {},
    pool_pre_ping=True,
    echo=True,  #set True only for debugging
)


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


Base = declarative_base()


def get_db():
    """
    Provides a database session per request.
    Automatically closes after request ends.
    """
    db = SessionLocal()
    try:
        logger.info("Created new database session.")
        yield db
    finally:
        db.close()
        logger.info("Closed database session.")
