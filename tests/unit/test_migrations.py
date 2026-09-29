"""Database startup always upgrades through the versioned Alembic history."""

from __future__ import annotations

from sqlalchemy import inspect, text

from visionsentinel.storage import Database
from visionsentinel.storage.db import make_engine
from visionsentinel.storage.models import Base


def test_fresh_database_is_created_at_alembic_head(tmp_path):
    database = Database(f"sqlite:///{tmp_path / 'workspace.db'}")
    try:
        with database.engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0001_initial"
            tables = set(inspect(connection).get_table_names())
        assert {"users", "scans", "finding_state", "decisions", "jobs", "audit_events"} <= tables
    finally:
        database.dispose()


def test_existing_pre_alembic_schema_is_stamped_without_recreating_data(tmp_path):
    url = f"sqlite:///{tmp_path / 'legacy.db'}"
    engine = make_engine(url)
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()

    database = Database(url)
    try:
        with database.engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0001_initial"
    finally:
        database.dispose()
