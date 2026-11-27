from __future__ import annotations

import re

from davdeploy.nova_contract_generation import normalize_generated_resource_ids

RESOURCE_ID = re.compile(r"^[a-z][a-z0-9-]{0,23}$")


def test_malformed_resource_id_and_every_declared_reference_are_rewritten():
    original = {
        "resources": [
            {"resource_id": "Primary_Database", "depends_on": [], "arguments": {}},
            {
                "resource_id": "api",
                "depends_on": ["Primary_Database"],
                "arguments": {
                    "database": {
                        "kind": "resource_reference",
                        "resource_id": "Primary_Database",
                        "output_name": "endpoint",
                        "value_type": "string",
                    }
                },
            },
        ],
        "health_assertions": [
            {
                "target_resource_id": "Primary_Database",
                "source_resource_id": "Primary_Database",
            }
        ],
        "cost_assumptions": [{"resource_id": "Primary_Database"}],
    }

    normalized = normalize_generated_resource_ids(original)
    canonical = normalized["resources"][0]["resource_id"]

    assert canonical == "primary-database"
    assert RESOURCE_ID.fullmatch(canonical)
    assert normalized["resources"][1]["depends_on"] == [canonical]
    assert normalized["resources"][1]["arguments"]["database"]["resource_id"] == canonical
    assert normalized["health_assertions"][0]["target_resource_id"] == canonical
    assert normalized["health_assertions"][0]["source_resource_id"] == canonical
    assert normalized["cost_assumptions"][0]["resource_id"] == canonical
    assert original["resources"][0]["resource_id"] == "Primary_Database"


def test_valid_ids_are_returned_unchanged():
    output = {"resources": [{"resource_id": "db-primary"}]}

    assert normalize_generated_resource_ids(output) is output


def test_slug_collisions_get_stable_unique_hash_suffixes_independent_of_order():
    first = "API_Server"
    second = "api-server"
    forward = {"resources": [{"resource_id": first}, {"resource_id": second}]}
    reverse = {"resources": [{"resource_id": second}, {"resource_id": first}]}

    forward_map = {
        source: normalized["resource_id"]
        for source, normalized in zip(
            (first, second), normalize_generated_resource_ids(forward)["resources"], strict=True
        )
    }
    reverse_map = {
        source: normalized["resource_id"]
        for source, normalized in zip(
            (second, first), normalize_generated_resource_ids(reverse)["resources"], strict=True
        )
    }

    assert forward_map == reverse_map
    assert len(set(forward_map.values())) == 2
    assert all(RESOURCE_ID.fullmatch(value) for value in forward_map.values())


def test_normalized_id_collision_with_existing_valid_id_gets_hash_suffix():
    normalized = normalize_generated_resource_ids(
        {"resources": [{"resource_id": "API"}, {"resource_id": "api"}]}
    )
    first, second = [item["resource_id"] for item in normalized["resources"]]

    assert second == "api"
    assert first.startswith("api-")
    assert RESOURCE_ID.fullmatch(first)
    assert first != second


def test_duplicate_source_ids_fail_closed_without_guessing_reference_targets():
    output = {
        "resources": [
            {"resource_id": "Invalid_ID"},
            {"resource_id": "Invalid_ID"},
        ],
        "health_assertions": [{"target_resource_id": "Invalid_ID"}],
    }

    assert normalize_generated_resource_ids(output) is output
    assert output["resources"][0]["resource_id"] == "Invalid_ID"
    assert output["health_assertions"][0]["target_resource_id"] == "Invalid_ID"


def test_secret_like_or_oversized_source_ids_fail_closed():
    for source_id in ("Password Secret", "API token", "123456789012", "x" * 65):
        output = {"resources": [{"resource_id": source_id}]}
        assert normalize_generated_resource_ids(output) is output


def test_malformed_output_shape_is_left_for_strict_schema_validation():
    output = {"resources": [{"resource_id": {"untrusted": "object"}}]}

    assert normalize_generated_resource_ids(output) is output
