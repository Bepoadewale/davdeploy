import pytest
from davdeploy import lambda_migrate


def test_migration_lambda_reports_completion(monkeypatch):
    calls = []
    monkeypatch.setattr(lambda_migrate, "run_migrations", lambda: calls.append("migrated"))

    assert lambda_migrate.handler({}, None) == {"status": "migrations-complete"}
    assert calls == ["migrated"]


def test_migration_lambda_surfaces_a_failed_migration_for_release_rollback(monkeypatch):
    def fail():
        raise RuntimeError("migration failed")

    monkeypatch.setattr(lambda_migrate, "run_migrations", fail)

    with pytest.raises(RuntimeError, match="migration failed"):
        lambda_migrate.handler({}, None)
