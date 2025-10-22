from __future__ import annotations

from collections.abc import Generator
from typing import Any

from sqlmodel import Session, SQLModel, create_engine

from ..models import db as _db_models  # noqa: F401 - ensure models register with metadata
from .config import get_settings


def create_engine_for_url(database_url: str):
    connect_args: dict[str, Any] = {}
    if database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    return create_engine(database_url, echo=False, connect_args=connect_args)


settings = get_settings()
engine = create_engine_for_url(settings.database_url)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def set_engine(new_engine) -> None:
    global engine
    engine = new_engine
