from __future__ import annotations

import json

import pytest

from scripts.parameter_config_lifecycle import (
    LifecycleCheckError,
    verify_account,
    verify_parameter_lifecycle,
)


class FakeSTS:
    def __init__(self, account_id: str) -> None:
        self.account_id = account_id

    def get_caller_identity(self) -> dict[str, str]:
        return {"Account": self.account_id}


class FakeSSM:
    def __init__(
        self,
        *,
        test_id: str = "20261125-a1b2c3",
        tag_test_id: str | None = None,
    ) -> None:
        self.name = f"/davdeploy/nova-parameter-config-493/{test_id}/synthetic"
        self.test_id = test_id
        self.tag_test_id = tag_test_id or test_id
        self.versions = {1: "synthetic-v1-only", 2: "synthetic-v2-only"}
        self.parameter = {
            "Name": self.name,
            "Type": "SecureString",
            "Tier": "Standard",
            "KeyId": "alias/aws/ssm",
            "Version": 2,
            "ARN": "arn:aws:ssm:us-east-1:654654474502:parameter/davdeploy/test",
        }

    def describe_parameters(self, *, ParameterFilters: list[dict[str, object]]) -> dict[str, object]:
        assert ParameterFilters == [
            {"Key": "Name", "Option": "Equals", "Values": [self.name]}
        ]
        return {"Parameters": [self.parameter]}

    def list_tags_for_resource(self, *, ResourceType: str, ResourceId: str) -> dict[str, object]:
        assert ResourceType == "Parameter"
        assert ResourceId == self.name
        return {
            "TagList": [
                {"Key": "ManagedBy", "Value": "terraform"},
                {"Key": "Product", "Value": "davdeploy"},
                {"Key": "Purpose", "Value": "nova-parameter-config-493-test"},
                {"Key": "TestId", "Value": self.tag_test_id},
            ]
        }

    def get_parameter(self, *, Name: str, WithDecryption: bool) -> dict[str, object]:
        assert WithDecryption is True
        name, _, version_text = Name.rpartition(":")
        version = int(version_text)
        assert name == self.name
        return {
            "Parameter": {
                "Name": self.name,
                "Type": "SecureString",
                "Version": version,
                "Value": self.versions[version],
            }
        }


class FakeKMS:
    def describe_key(self, *, KeyId: str) -> dict[str, object]:
        assert KeyId == "alias/aws/ssm"
        return {
            "KeyMetadata": {
                "KeyId": "key-1234",
                "Arn": "arn:aws:kms:us-east-1:654654474502:key/key-1234",
            }
        }

    def list_aliases(self, *, KeyId: str) -> dict[str, object]:
        assert KeyId == "key-1234"
        return {"Aliases": [{"AliasName": "alias/aws/ssm"}]}


def test_verify_parameter_lifecycle_reports_metadata_without_values():
    ssm = FakeSSM()
    result = verify_parameter_lifecycle(
        sts=FakeSTS("654654474502"),
        ssm=ssm,
        kms=FakeKMS(),
        expected_account_id="654654474502",
        name=ssm.name,
        test_id=ssm.test_id,
        expected_v1=ssm.versions[1],
        expected_v2=ssm.versions[2],
    )

    rendered = json.dumps(result)
    assert result["versions_verified"] == [1, 2]
    assert result["kms_key_arn"] == "arn:aws:kms:us-east-1:654654474502:key/key-1234"
    assert "synthetic-v1-only" not in rendered
    assert "synthetic-v2-only" not in rendered
    assert result["values_match"] is True


def test_verify_parameter_lifecycle_denies_wrong_account():
    with pytest.raises(LifecycleCheckError, match="account mismatch"):
        verify_account(FakeSTS("111122223333"), "654654474502")


def test_verify_parameter_lifecycle_denies_name_outside_test_path():
    ssm = FakeSSM()

    with pytest.raises(LifecycleCheckError, match="exact test parameter"):
        verify_parameter_lifecycle(
            sts=FakeSTS("654654474502"),
            ssm=ssm,
            kms=FakeKMS(),
            expected_account_id="654654474502",
            name="/davdeploy/another-test/parameter",
            test_id=ssm.test_id,
            expected_v1=ssm.versions[1],
            expected_v2=ssm.versions[2],
        )


def test_verify_parameter_lifecycle_denies_ownership_tag_mismatch():
    ssm = FakeSSM(tag_test_id="20261125-ffffff")

    with pytest.raises(LifecycleCheckError, match="ownership tags"):
        verify_parameter_lifecycle(
            sts=FakeSTS("654654474502"),
            ssm=ssm,
            kms=FakeKMS(),
            expected_account_id="654654474502",
            name=ssm.name,
            test_id="20261125-a1b2c3",
            expected_v1=ssm.versions[1],
            expected_v2=ssm.versions[2],
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("Type", "String", "type or tier"),
        ("Tier", "Advanced", "type or tier"),
        ("KeyId", "alias/other/key", "KMS key"),
        ("Version", 3, "exactly two"),
    ],
)
def test_verify_parameter_lifecycle_denies_unsafe_metadata(field, value, message):
    ssm = FakeSSM()
    ssm.parameter[field] = value

    with pytest.raises(LifecycleCheckError, match=message):
        verify_parameter_lifecycle(
            sts=FakeSTS("654654474502"),
            ssm=ssm,
            kms=FakeKMS(),
            expected_account_id="654654474502",
            name=ssm.name,
            test_id=ssm.test_id,
            expected_v1=ssm.versions[1],
            expected_v2=ssm.versions[2],
        )


def test_verify_parameter_lifecycle_does_not_include_mismatched_value_in_error():
    ssm = FakeSSM()
    secret_like_value = "synthetic-should-not-appear"

    with pytest.raises(LifecycleCheckError) as exc_info:
        verify_parameter_lifecycle(
            sts=FakeSTS("654654474502"),
            ssm=ssm,
            kms=FakeKMS(),
            expected_account_id="654654474502",
            name=ssm.name,
            test_id=ssm.test_id,
            expected_v1=secret_like_value,
            expected_v2=ssm.versions[2],
        )

    assert secret_like_value not in str(exc_info.value)
