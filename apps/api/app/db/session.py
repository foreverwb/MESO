from __future__ import annotations

from collections.abc import Iterator
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

import app.db.models  # noqa: F401
from app.core.settings import settings
from app.db.base import Base


DEFAULT_DATABASE_FILENAME = "app.db"

_default_engine: Engine | None = None
_default_session_factory: sessionmaker[Session] | None = None


def build_database_url(database_path: Path | None = None) -> str:
    database_url = os.getenv("MESO_DATABASE_URL")
    if database_path is None and database_url:
        return database_url

    resolved_path = Path(
        database_path
        or os.getenv("MESO_DB_PATH", str(settings.data_dir / DEFAULT_DATABASE_FILENAME)),
    ).expanduser()
    return f"sqlite:///{resolved_path.resolve()}"


def create_engine_from_url(
    database_url: str | None = None,
    *,
    echo: bool = False,
) -> Engine:
    resolved_url = database_url or build_database_url()
    _ensure_sqlite_parent_dir(resolved_url)
    return create_engine(
        resolved_url,
        echo=echo,
        future=True,
        connect_args=_sqlite_connect_args(resolved_url),
    )


def create_session_factory(
    engine: Engine | None = None,
    *,
    database_url: str | None = None,
) -> sessionmaker[Session]:
    bound_engine = engine or create_engine_from_url(database_url)
    return sessionmaker(
        bind=bound_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )


def get_engine() -> Engine:
    global _default_engine
    if _default_engine is None:
        _default_engine = create_engine_from_url()
    return _default_engine


def get_session_factory() -> sessionmaker[Session]:
    global _default_session_factory
    if _default_session_factory is None:
        _default_session_factory = create_session_factory(get_engine())
    return _default_session_factory


def get_db_session() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def init_db(engine: Engine | None = None) -> None:
    Base.metadata.create_all(bind=engine or get_engine())


def _sqlite_connect_args(database_url: str) -> dict[str, bool]:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def _ensure_sqlite_parent_dir(database_url: str) -> None:
    sqlite_prefix = "sqlite:///"
    if not database_url.startswith(sqlite_prefix):
        return

    database_path = Path(database_url.removeprefix(sqlite_prefix))
    database_path.parent.mkdir(parents=True, exist_ok=True)
