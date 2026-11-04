from __future__ import annotations

import pytest
from davdeploy import db
from davdeploy.models import Base
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError


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
    monkeypatch.setenv(
        "DAVDEPLOY_DATABASE_SECRET_ARN", "arn:aws:secretsmanager:us-east-1:123:secret:db"
    )
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
        assert (
            connection.execute(text("SELECT MAX(version) FROM schema_migrations")).scalar_one()
            == 30
        )
    columns = {
        column["name"] for column in inspect(engine).get_columns("cloud_execution_module_instances")
    }
    assert "runner_build_id" in columns
    indexes = {
        index["name"] for index in inspect(engine).get_indexes("cloud_execution_module_instances")
    }
    assert "uq_cloud_execution_module_runner_build_id" in indexes
    engine.dispose()


def test_cloud_execution_worker_lease_migration_upgrades_version_23_idempotently():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY)"))
        connection.execute(text("INSERT INTO schema_migrations(version) VALUES (23)"))
        connection.execute(text("CREATE TABLE cloud_execution_runs (id VARCHAR(36) PRIMARY KEY)"))

    db.run_migrations(engine)
    db.run_migrations(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("cloud_execution_runs")}
    assert {
        "worker_claim_version",
        "worker_lease_token",
        "worker_lease_expires_at",
    } <= columns
    indexes = {index["name"] for index in inspect(engine).get_indexes("cloud_execution_runs")}
    assert "ix_cloud_execution_runs_worker_lease_expires_at" in indexes
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT MAX(version) FROM schema_migrations")).scalar_one()
            == 30
        )
    engine.dispose()


def test_module_runner_build_identity_migration_upgrades_version_24_idempotently():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY)"))
        connection.execute(text("INSERT INTO schema_migrations(version) VALUES (24)"))
        connection.execute(
            text(
                "CREATE TABLE cloud_execution_module_instances ("
                "id VARCHAR(36) PRIMARY KEY, runner_state VARCHAR(40))"
            )
        )

    db.run_migrations(engine)
    db.run_migrations(engine)

    columns = {
        column["name"] for column in inspect(engine).get_columns("cloud_execution_module_instances")
    }
    assert {"id", "runner_state", "runner_build_id"} <= columns
    assert inspect(engine).has_table("generated_plan_artifacts")
    assert inspect(engine).has_table("generated_plan_approvals")
    artifact_columns = {
        column["name"] for column in inspect(engine).get_columns("generated_plan_artifacts")
    }
    assert {"context_sha256", "manifest_sha256", "artifact_version_id"} <= artifact_columns
    indexes = {
        index["name"] for index in inspect(engine).get_indexes("cloud_execution_module_instances")
    }
    assert "uq_cloud_execution_module_runner_build_id" in indexes
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT MAX(version) FROM schema_migrations")).scalar_one()
            == 30
        )
        connection.execute(
            text(
                "INSERT INTO cloud_execution_module_instances(id, runner_build_id) "
                "VALUES ('first', 'project:build-1'), ('second', 'project:build-2')"
            )
        )
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO cloud_execution_module_instances(id, runner_build_id) "
                    "VALUES ('third', 'project:build-1')"
                )
            )
    engine.dispose()


def test_nova_plan_queue_migration_adds_persisted_request_and_lease_fields():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY)"))
        connection.execute(text("INSERT INTO schema_migrations(version) VALUES (27)"))
        connection.execute(text("CREATE TABLE organizations (id VARCHAR(36) PRIMARY KEY)"))
        connection.execute(text("INSERT INTO organizations(id) VALUES ('org-demo')"))
        connection.execute(
            text(
                "CREATE TABLE generated_plan_runs ("
                "id VARCHAR(36) PRIMARY KEY, organization_id VARCHAR(36), "
                "idempotency_key_sha256 VARCHAR(64), request_sha256 VARCHAR(64), state VARCHAR(40), "
                "preparation_lease_expires_at TIMESTAMP WITH TIME ZONE)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO generated_plan_runs "
                "(id, organization_id, idempotency_key_sha256, request_sha256, state) "
                "VALUES ('run-demo', 'org-demo', 'key-hash-demo', 'request-hash-demo', 'QUEUED')"
            )
        )
        connection.execute(text("CREATE TABLE generated_plan_artifacts (id TEXT PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE generated_plan_approvals (id TEXT PRIMARY KEY)"))

    db.run_migrations(engine)
    db.run_migrations(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("generated_plan_runs")}
    assert {"request_document", "preparation_lease_token", "runner_run_id"} <= columns
    assert inspect(engine).has_table("generated_plan_run_idempotency_keys")
    with engine.connect() as connection:
        binding = connection.execute(
            text(
                "SELECT organization_id, idempotency_key_sha256, request_sha256, run_id "
                "FROM generated_plan_run_idempotency_keys"
            )
        ).mappings().one()
        runner_run_id = connection.execute(
            text("SELECT runner_run_id FROM generated_plan_runs WHERE id = 'run-demo'")
        ).scalar_one()
        worker_cursor = connection.execute(
            text("SELECT next_queue_index FROM worker_dispatch_states WHERE id = 1")
        ).scalar_one()
    assert binding == {
        "organization_id": "org-demo",
        "idempotency_key_sha256": "key-hash-demo",
        "request_sha256": "request-hash-demo",
        "run_id": "run-demo",
    }
    assert runner_run_id == "run-demo"
    assert worker_cursor == 0
    indexes = {index["name"] for index in inspect(engine).get_indexes("generated_plan_runs")}
    assert "ix_generated_plan_run_preparation_lease" in indexes
    assert "uq_generated_plan_runs_runner_run_id" in indexes
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT MAX(version) FROM schema_migrations")).scalar_one()
            == 30
        )
    engine.dispose()
