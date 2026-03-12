"""
Database engine, session factory, and initialization helpers.

Uses SQLite by default with the DB file stored alongside the application.
"""

import os
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.models.models import Base

# Store the database in the project root
_DB_DIR = Path(__file__).resolve().parent.parent
_DB_PATH = _DB_DIR / "amazon_master.db"
_DB_URL = f"sqlite:///{_DB_PATH}"

engine = create_engine(_DB_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    """Create all tables if they don't already exist."""
    Base.metadata.create_all(bind=engine)


def get_session() -> Session:
    """Return a new SQLAlchemy session. Caller is responsible for closing it."""
    return SessionLocal()
