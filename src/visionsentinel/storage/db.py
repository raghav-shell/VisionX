"""Engine and session factory. SQLite runs in WAL mode with foreign keys enforced."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base


def _migration_config(database_url: str):
    """Create Alembic configuration for the checked-out application bundle."""
    from alembic.config import Config

    root = Path(__file__).resolve().parents[3]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def upgrade_database(engine: Engine, database_url: str) -> None:
    """Upgrade a database transactionally, stamping pre-migration installations once.

    Versions before Alembic created the complete initial schema with ``create_all``.
    A populated database without Alembic metadata is therefore stamped at the
    initial revision; new databases execute the initial migration normally.
    """
    from alembic import command
    from sqlalchemy import inspect

    config = _migration_config(database_url)
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        inspector = inspect(connection)
        if not inspector.has_table("alembic_version") and inspector.has_table("users"):
            command.stamp(config, "0001_initial")
        else:
            command.upgrade(config, "head")


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30}, future=True)

        @event.listens_for(engine, "connect")
        def _pragmas(dbapi_conn, _record) -> None:  # pragma: no cover - driver callback
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA synchronous=NORMAL")
            cur.close()
        return engine
    return create_engine(url, future=True, pool_pre_ping=True)


class Database:
    def __init__(self, url: str) -> None:
        self.engine = make_engine(url)
        upgrade_database(self.engine, url)
        self._factory = sessionmaker(self.engine, expire_on_commit=False, future=True)

    @contextmanager
    def session(self) -> Iterator[Session]:
        s = self._factory()
        try:
            yield s
            s.commit()
        except BaseException:
            s.rollback()
            raise
        finally:
            s.close()

    def dispose(self) -> None:
        self.engine.dispose()
