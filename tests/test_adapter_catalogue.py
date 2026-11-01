from __future__ import annotations

import pytest
from davdeploy.adapter_catalogue import adapter_catalogue, adapter_catalogue_entry


def test_catalogue_covers_major_workload_families_without_claiming_execution() -> None:
    entries = {entry.identifier: entry for entry in adapter_catalogue()}

    assert {
        "aws-static-edge",
        "aws-serverless-api",
        "aws-ecs-fargate",
        "aws-relational-data",
        "aws-event-backbone",
        "aws-ai-retrieval",
        "aws-managed-ml",
        "aws-gpu-inference",
    } <= entries.keys()
    assert entries["aws-app-runner"].stage == "pilot"
    assert entries["aws-ecs-fargate"].stage == "planning"
    assert entries["aws-ai-retrieval"].stage == "planning"
    assert entries["aws-managed-ml"].stage == "catalogued"


def test_catalogue_rejects_unknown_adapter_scope() -> None:
    with pytest.raises(ValueError, match="no governed adapter catalogue entry"):
        adapter_catalogue_entry("aws-arbitrary-admin-access")
