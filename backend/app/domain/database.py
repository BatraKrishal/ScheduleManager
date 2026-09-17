from __future__ import annotations

import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.domain.models import Base

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    try:
        import psycopg2  # check if driver available
        DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/primavera"
    except ImportError:
        DATABASE_URL = "sqlite:///./primavera.db"

# SQLite test compatibility
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Create tables if they do not already exist."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
