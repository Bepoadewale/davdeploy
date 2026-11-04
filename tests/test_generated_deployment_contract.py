from __future__ import annotations

import pytest
from pydantic import ValidationError

from davdeploy.generated_deployment_contract import GeneratedDeploymentProposal


def proposal(resources: list[dict[str, object]]) -> dict[str, object]:
    return {
        "contract_version": "1.0",
        "source_revision": "test-revision",
        "context_digest": "a" * 64,
        "resources": resources,
        "requirements": {"region": "us-east-1"},
    }


def resource(
    resource_id: str,
    name: str,
    *,
    arguments: dict[str, object] | None = None,
    depends_on: tuple[str, ...] = (),
    outputs: tuple[dict[str, object], ...] = (),
) -> dict[str, object]:
    return {
        "resource_id": resource_id,
        "resource_type": "aws_s3_bucket",
        "name": name,
        "arguments": arguments or {},
        "depends_on": depends_on,
        "outputs": outputs,
        "rationale": "Stores private application uploads.",
    }


def test_contract_accepts_a_typed_reference_and_infers_dependency() -> None:
    result = GeneratedDeploymentProposal.model_validate(
        proposal(
            [
                resource(
                    "uploads",
                    "uploads",
                    outputs=(
                        {"name": "bucket_name", "value_type": "resource_name"},
                    ),
                ),
                resource(
                    "api",
                    "api",
                    arguments={
                        "bucket": {
                            "kind": "resource_reference",
                            "resource_id": "uploads",
                            "output_name": "bucket_name",
                            "value_type": "resource_name",
                        }
                    },
                ),
            ]
        )
    )

    assert [item.resource_id for item in result.resources] == ["uploads", "api"]


@pytest.mark.parametrize(
    "resources",
    [
        [resource("same", "one"), resource("same", "two")],
        [resource("one", "same"), resource("two", "same")],
        [resource("one", "one", depends_on=("missing",))],
        [
            resource("one", "one", depends_on=("two",)),
            resource("two", "two", depends_on=("one",)),
        ],
        [
            resource(
                "api",
                "api",
                arguments={
                    "bucket": {
                        "kind": "resource_reference",
                        "resource_id": "missing",
                        "output_name": "bucket_name",
                        "value_type": "resource_name",
                    }
                },
            )
        ],
        [
            resource(
                "uploads",
                "uploads",
                outputs=({"name": "bucket_name", "value_type": "resource_name"},),
            ),
            resource(
                "api",
                "api",
                arguments={
                    "bucket": {
                        "kind": "resource_reference",
                        "resource_id": "uploads",
                        "output_name": "bucket_name",
                        "value_type": "aws_arn",
                    }
                },
            ),
        ],
        [resource("one", "one", arguments={"name": "file(unsafe)"})],
        [resource("one", "one", arguments={"user_data": "unsafe"})],
    ],
)
def test_contract_rejects_unsafe_or_invalid_graphs(
    resources: list[dict[str, object]],
) -> None:
    with pytest.raises(ValidationError):
        GeneratedDeploymentProposal.model_validate(proposal(resources))
