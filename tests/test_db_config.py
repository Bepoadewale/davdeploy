from __future__ import annotations

import pytest
from davdeploy import db
from davdeploy.models import Base
from sqlalchemy import create_engine, inspect, text


def test_hosted_mode_rejects_sqlite_database_url(monkeypatch):
    monkeypatch.delenv("DAVDEPLOY_DATABASE_SECRET_ARN", raising=False)
    monkeypatch.delenv("DAVDEPLOY_AURORA_CLUSTER_ARN", raising=False)
    monkeypatch.setenv("DAVDEPLOY_HOSTED_MODE", "true")
    monkeypatch.setenv("DAVDEPLOY_DATABASE_URL", "sqlite+pysqlite:////tmp/davdeploy.db")

    with pytest.raises(RuntimeError, match="durable PostgreSQL"):
        db.database_url()


def test_local_mode_keeps_sqlite_available(monkeypatch):
    monkeypatch.delenv("DAVDEPLOY_DATABASE_SECRET_ARN", raising=False)
    monkeypatch.delenv("DAVDEPLOY_AURORA_CLUSTER_ARN", raising=False)
    monkeypatch.setenv("DAVDEPLOY_HOSTED_MODE", "false")
    monkeypatch.setenv("DAVDEPLOY_DATABASE_URL", "sqlite+pysqlite:///./.local/test.db")

    assert db.database_url() == "sqlite+pysqlite:///./.local/test.db"


def test_database_url_uses_data_api_without_retrieving_database_password(monkeypatch):
    monkeypatch.setenv("DAVDEPLOY_AURORA_CLUSTER_ARN", "arn:aws:rds:us-east-1:123:cluster:db")
    monkeypatch.setenv("DAVDEPLOY_DATABASE_SECRET_ARN", "arn:aws:secretsmanager:us-east-1:123:secret:db")
    monkeypatch.setenv("DAVDEPLOY_DATABASE_NAME", "davdeploy")

    assert db.database_url() == "postgresql+auroradataapi://:@/davdeploy"


def test_execution_module_instance_migration_is_safe_for_existing_database():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    existing_tables = [
        table
        for table in Base.metadata.sorted_tables
        if table.name != "cloud_execution_module_instances"
    ]
    with engine.begin() as connection:
        Base.metadata.create_all(bind=connection, tables=existing_tables)
        connection.execute(text("CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY)"))
        connection.execute(text("INSERT INTO schema_migrations(version) VALUES (22)"))

    db.run_migrations(engine)
    db.run_migrations(engine)

    assert inspect(engine).has_table("cloud_execution_module_instances")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT MAX(version) FROM schema_migrations")).scalar_one() == 23
    engine.dispose()
