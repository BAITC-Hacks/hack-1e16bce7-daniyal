"""Opt-in integration check; all writes are isolated in a temporary schema."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url

from app.application.import_dataset import import_dataset
from app.infrastructure.database import Database
from app.infrastructure.dataset_loader import load_dataset
from app.infrastructure.models import Employee, ActivityHistory


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="Set TEST_DATABASE_URL for PostgreSQL checks")
def test_postgres_migrations_and_concurrent_import(monkeypatch):
    api_root = Path(__file__).resolve().parents[1]
    schema = "test_dataset_" + uuid4().hex
    url = make_url(os.environ["TEST_DATABASE_URL"])
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    isolated_url = url.update_query_dict({"options": f"-csearch_path={schema}"}).render_as_string(hide_password=False)
    monkeypatch.setenv("DATABASE_URL", isolated_url)
    config = Config(str(api_root / "alembic.ini"))
    database = Database(isolated_url)
    try:
        command.upgrade(config, "head")
        command.check(config)
        dataset = load_dataset(api_root.parents[1] / "dataset")
        def run_import(_):
            with database.sessions() as session:
                return import_dataset(session, dataset)["status"]
        with ThreadPoolExecutor(max_workers=2) as executor:
            assert sorted(executor.map(run_import, range(2))) == ["imported", "unchanged"]
        with database.sessions() as session:
            assert session.scalar(select(func.count()).select_from(Employee)) == 200
            assert session.scalar(select(func.count()).select_from(ActivityHistory)) == 2743
        command.downgrade(config, "base")
        command.upgrade(config, "head")
        command.check(config)
    finally:
        database.close()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
