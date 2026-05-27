from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


engine: Engine | None = None
SessionLocal: sessionmaker[Session] | None = None


def init_engine(database_url: str) -> Engine:
    global engine
    global SessionLocal

    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}

    engine = create_engine(database_url, connect_args=connect_args, future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return engine


def init_db() -> None:
    """Jalankan Alembic migrations hingga revision terbaru (upgrade head).

    Dipanggil otomatis saat bot startup sehingga schema selalu up-to-date
    tanpa perlu menjalankan `alembic upgrade head` secara manual.
    """
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    if engine is None:
        raise RuntimeError("Engine has not been initialized. Call init_engine first.")

    project_root = Path(__file__).resolve().parents[2]
    alembic_cfg = Config(str(project_root / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(project_root / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", str(engine.url))
    command.upgrade(alembic_cfg, "head")


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    if SessionLocal is None:
        raise RuntimeError("Session factory has not been initialized. Call init_engine first.")

    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

