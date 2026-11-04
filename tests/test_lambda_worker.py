from __future__ import annotations

from contextlib import nullcontext

from davdeploy import lambda_worker


def test_worker_wakeup_drains_a_bounded_durable_backlog(monkeypatch):
    claims = iter([True, True, True, False])

    class Service:
        def __init__(self, _db):
            pass

        def reconcile_cloud_execution_build(self, _build_id):
            return False

        def run_next_discovery_job(self):
            return next(claims)

        def run_next_generated_plan_run(self):
            return False

        def run_next_cloud_execution(self):
            return False

        def run_next_job(self):
            return False

    monkeypatch.setattr(lambda_worker, "SessionLocal", lambda: nullcontext(object()))
    monkeypatch.setattr(lambda_worker, "ProductService", Service)
    monkeypatch.setenv("DAVDEPLOY_WORKER_MAX_JOBS_PER_WAKEUP", "3")

    result = lambda_worker.handler({"Records": [{"body": '{"version":1}'}]}, None)

    assert result == {"records": 1, "processed": 3, "processed_jobs": 3}


def test_worker_wakeup_clamps_an_invalid_or_excessive_drain_limit(monkeypatch):
    calls = []

    class Service:
        def __init__(self, _db):
            pass

        def reconcile_cloud_execution_build(self, _build_id):
            return False

        def run_next_discovery_job(self):
            calls.append("discovery")
            return False

        def run_next_generated_plan_run(self):
            calls.append("nova")
            return False

        def run_next_cloud_execution(self):
            calls.append("cloud_execution")
            return False

        def run_next_job(self):
            calls.append("legacy")
            return False

    monkeypatch.setattr(lambda_worker, "SessionLocal", lambda: nullcontext(object()))
    monkeypatch.setattr(lambda_worker, "ProductService", Service)
    monkeypatch.setenv("DAVDEPLOY_WORKER_MAX_JOBS_PER_WAKEUP", "not-a-number")

    result = lambda_worker.handler({}, None)

    assert result == {"records": 0, "processed": 0, "processed_jobs": 0}
    assert calls == ["nova", "discovery", "cloud_execution", "legacy"]


def test_worker_ignores_a_malformed_wakeup_without_redriving_the_batch(monkeypatch):
    class Service:
        def __init__(self, _db):
            pass

        def reconcile_cloud_execution_build(self, _build_id):
            raise AssertionError("malformed input has no build id")

        def run_next_discovery_job(self):
            return False

        def run_next_generated_plan_run(self):
            return False

        def run_next_cloud_execution(self):
            return False

        def run_next_job(self):
            return False

    monkeypatch.setattr(lambda_worker, "SessionLocal", lambda: nullcontext(object()))
    monkeypatch.setattr(lambda_worker, "ProductService", Service)

    result = lambda_worker.handler({"Records": [{"body": "not-json"}]}, None)

    assert result == {"records": 1, "processed": 0, "processed_jobs": 0}


def test_worker_wakeup_drains_a_durable_nova_plan_request(monkeypatch):
    claims = iter([True, False])

    class Service:
        def __init__(self, _db):
            pass

        def reconcile_cloud_execution_build(self, _build_id):
            return False

        def run_next_generated_plan_run(self):
            return next(claims)

        def run_next_discovery_job(self):
            return False

        def run_next_cloud_execution(self):
            return False

        def run_next_job(self):
            return False

    monkeypatch.setattr(lambda_worker, "SessionLocal", lambda: nullcontext(object()))
    monkeypatch.setattr(lambda_worker, "ProductService", Service)
    monkeypatch.setenv("DAVDEPLOY_WORKER_MAX_JOBS_PER_WAKEUP", "1")

    result = lambda_worker.handler({"Records": [{"body": '{"version":1,"kind":"generated_plan_run"}'}]}, None)

    assert result == {"records": 1, "processed": 1, "processed_jobs": 1}


def test_worker_wakeup_services_each_queue_before_repeating_under_nova_backlog(monkeypatch):
    calls = []

    class Service:
        def __init__(self, _db):
            pass

        def reconcile_cloud_execution_build(self, _build_id):
            return False

        def run_next_generated_plan_run(self):
            calls.append("nova")
            return True

        def run_next_discovery_job(self):
            calls.append("discovery")
            return True

        def run_next_cloud_execution(self):
            calls.append("cloud_execution")
            return True

        def run_next_job(self):
            calls.append("legacy")
            return True

    monkeypatch.setattr(lambda_worker, "SessionLocal", lambda: nullcontext(object()))
    monkeypatch.setattr(lambda_worker, "ProductService", Service)
    monkeypatch.setenv("DAVDEPLOY_WORKER_MAX_JOBS_PER_WAKEUP", "1")

    result = lambda_worker.handler({}, None)

    assert result == {"records": 0, "processed": 4, "processed_jobs": 4}
    assert calls == ["nova", "discovery", "cloud_execution", "legacy"]
