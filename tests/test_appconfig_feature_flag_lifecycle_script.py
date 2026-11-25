from __future__ import annotations

import io
import json
from collections import deque

import pytest
from botocore.exceptions import ClientError

from scripts.appconfig_feature_flag_lifecycle import (
    LifecycleCheckError,
    verify_account,
    verify_flag_rollout,
    verify_resources_absent,
)

ACCOUNT_ID = "654654474502"
TEST_ID = "20261125-a1b2c3"
APP_ID = "abcd12"
ENV_ID = "efgh34"
PROFILE_ID = "ijkl56"
STRATEGY_ID = "mnop78"
APP_NAME = f"davdeploy-nova-ff-495-{TEST_ID}"


class FakeSTS:
    def __init__(self, account_id: str = ACCOUNT_ID) -> None:
        self.account_id = account_id

    def get_caller_identity(self) -> dict[str, str]:
        return {"Account": self.account_id}


class FakeAppConfig:
    def __init__(
        self,
        *,
        deployment_states: list[str] | None = None,
        tag_test_id: str = TEST_ID,
        app_name: str = APP_NAME,
        remains_present: bool = False,
        missing_deployments: int = 0,
    ) -> None:
        self.deployment_states = deque(deployment_states or ["COMPLETE"])
        self.last_state = self.deployment_states[-1]
        self.tag_test_id = tag_test_id
        self.app_name = app_name
        self.remains_present = remains_present
        self.missing_deployments = missing_deployments

    def _not_found(self, operation: str) -> None:
        raise ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "absent"}},
            operation,
        )

    def get_application(self, *, ApplicationId: str) -> dict[str, object]:
        if self.remains_present:
            return {"Application": {"Id": ApplicationId, "Name": self.app_name, "Arn": "arn:app"}}
        self._not_found("GetApplication")

    def get_environment(self, *, ApplicationId: str, EnvironmentId: str) -> dict[str, object]:
        if self.remains_present:
            return {
                "Environment": {
                    "ApplicationId": ApplicationId,
                    "EnvironmentId": EnvironmentId,
                    "Name": "production",
                    "Arn": "arn:environment",
                }
            }
        self._not_found("GetEnvironment")

    def get_configuration_profile(
        self, *, ApplicationId: str, ConfigurationProfileId: str
    ) -> dict[str, object]:
        if self.remains_present:
            return {
                "ConfigurationProfile": {
                    "ApplicationId": ApplicationId,
                    "ConfigurationProfileId": ConfigurationProfileId,
                    "LocationUri": "hosted",
                    "Name": f"{APP_NAME}-flags",
                    "Type": "AWS.AppConfig.FeatureFlags",
                    "Arn": "arn:profile",
                }
            }
        self._not_found("GetConfigurationProfile")

    def get_deployment_strategy(self, *, DeploymentStrategyId: str) -> dict[str, object]:
        if self.remains_present:
            return {
                "DeploymentStrategy": {
                    "Name": f"{APP_NAME}-linear",
                    "GrowthFactor": 50.0,
                    "GrowthType": "LINEAR",
                    "DeploymentDurationInMinutes": 1,
                    "FinalBakeTimeInMinutes": 1,
                    "ReplicateTo": "NONE",
                    "Arn": "arn:strategy",
                }
            }
        self._not_found("GetDeploymentStrategy")

    def get_deployment(
        self, *, ApplicationId: str, EnvironmentId: str, DeploymentNumber: int
    ) -> dict[str, object]:
        if self.missing_deployments:
            self.missing_deployments -= 1
            self._not_found("GetDeployment")
        if not self.remains_present:
            self._not_found("GetDeployment")
        if not self.deployment_states:
            state = self.last_state
        else:
            state = self.deployment_states.popleft()
            self.last_state = state
        return {
            "Deployment": {
                "ApplicationId": ApplicationId,
                "EnvironmentId": EnvironmentId,
                "ConfigurationProfileId": PROFILE_ID,
                "DeploymentStrategyId": STRATEGY_ID,
                "DeploymentNumber": DeploymentNumber,
                "State": state,
            }
        }

    def list_tags_for_resource(self, *, ResourceArn: str) -> dict[str, object]:
        return {
            "Tags": {
                "Product": "davdeploy",
                "Purpose": "temporary-appconfig-feature-flag-validation",
                "TestId": self.tag_test_id,
            }
        }


class FakeAppConfigData:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled
        self.seen_tokens: list[str] = []

    def start_configuration_session(self, **kwargs: object) -> dict[str, str]:
        assert kwargs["ApplicationIdentifier"] == APP_ID
        assert kwargs["EnvironmentIdentifier"] == ENV_ID
        assert kwargs["ConfigurationProfileIdentifier"] == PROFILE_ID
        assert kwargs["RequiredMinimumPollIntervalInSeconds"] == 15
        return {"InitialConfigurationToken": "do-not-print-initial-token"}

    def get_latest_configuration(self, *, ConfigurationToken: str) -> dict[str, object]:
        self.seen_tokens.append(ConfigurationToken)
        content = json.dumps({"nova_demo": {"enabled": self.enabled}}).encode()
        return {
            "NextPollConfigurationToken": "do-not-print-next-token",
            "Configuration": io.BytesIO(content),
        }


def verify(*, enabled: bool, states: list[str] | None = None, progressive: bool = False):
    appconfig = FakeAppConfig(deployment_states=states, remains_present=True)
    data = FakeAppConfigData(enabled)
    result = verify_flag_rollout(
        sts=FakeSTS(),
        appconfig=appconfig,
        appconfigdata=data,
        expected_account_id=ACCOUNT_ID,
        test_id=TEST_ID,
        application_id=APP_ID,
        environment_id=ENV_ID,
        profile_id=PROFILE_ID,
        strategy_id=STRATEGY_ID,
        deployment_number=2,
        expected_enabled=enabled,
        expected_deployment_state=(states[-1] if states else "COMPLETE"),
        require_progressive_state=progressive,
        timeout_seconds=1,
        sleep=lambda _: None,
    )
    return result, data


def test_verify_account_rejects_wrong_account():
    with pytest.raises(LifecycleCheckError, match="account mismatch"):
        verify_account(FakeSTS("111122223333"), ACCOUNT_ID)


def test_rollout_verifies_exact_feature_configuration_without_exposing_tokens():
    result, data = verify(enabled=True)

    rendered = json.dumps(result)
    assert result["flag_enabled"] is True
    assert result["deployment_state"] == "COMPLETE"
    assert "do-not-print" not in rendered
    # AppConfig Data tokens are intentionally passed back to AWS inside the
    # helper. The test checks they never appear in its returned evidence.
    assert data.seen_tokens


def test_rollout_observes_progressive_state_and_complete_flag():
    result, _ = verify(enabled=True, states=["DEPLOYING", "COMPLETE"], progressive=True)

    assert result["progressive_state_observed"] is True
    assert result["deployment_state"] == "COMPLETE"


def test_progressive_rollout_waits_for_new_deployment_to_appear():
    appconfig = FakeAppConfig(
        deployment_states=["DEPLOYING", "COMPLETE"],
        remains_present=True,
        missing_deployments=2,
    )
    sleeps: list[int] = []

    result = verify_flag_rollout(
        sts=FakeSTS(),
        appconfig=appconfig,
        appconfigdata=FakeAppConfigData(True),
        expected_account_id=ACCOUNT_ID,
        test_id=TEST_ID,
        application_id=APP_ID,
        environment_id=ENV_ID,
        profile_id=PROFILE_ID,
        strategy_id=STRATEGY_ID,
        deployment_number=2,
        expected_enabled=True,
        expected_deployment_state="COMPLETE",
        require_progressive_state=True,
        timeout_seconds=120,
        sleep=sleeps.append,
    )

    assert result["progressive_state_observed"] is True
    assert result["deployment_state"] == "COMPLETE"
    assert len(sleeps) == 2


def test_rollout_accepts_explicit_reverted_state_and_old_flag():
    appconfig = FakeAppConfig(deployment_states=["REVERTED"], remains_present=True)
    result = verify_flag_rollout(
        sts=FakeSTS(),
        appconfig=appconfig,
        appconfigdata=FakeAppConfigData(False),
        expected_account_id=ACCOUNT_ID,
        test_id=TEST_ID,
        application_id=APP_ID,
        environment_id=ENV_ID,
        profile_id=PROFILE_ID,
        strategy_id=STRATEGY_ID,
        deployment_number=2,
        expected_enabled=False,
        expected_deployment_state="REVERTED",
        timeout_seconds=1,
        sleep=lambda _: None,
    )

    assert result["deployment_state"] == "REVERTED"
    assert result["flag_enabled"] is False


def test_rollout_rejects_non_progressive_initial_state():
    appconfig = FakeAppConfig(deployment_states=["COMPLETE"], remains_present=True)
    with pytest.raises(LifecycleCheckError, match="progressive deployment state"):
        verify_flag_rollout(
            sts=FakeSTS(),
            appconfig=appconfig,
            appconfigdata=FakeAppConfigData(True),
            expected_account_id=ACCOUNT_ID,
            test_id=TEST_ID,
            application_id=APP_ID,
            environment_id=ENV_ID,
            profile_id=PROFILE_ID,
            strategy_id=STRATEGY_ID,
            deployment_number=2,
            expected_enabled=True,
            expected_deployment_state="COMPLETE",
            require_progressive_state=True,
            timeout_seconds=1,
            sleep=lambda _: None,
        )


def test_rollout_rejects_ownership_tag_mismatch():
    appconfig = FakeAppConfig(tag_test_id="20261125-ffffff", remains_present=True)
    with pytest.raises(LifecycleCheckError, match="ownership tags"):
        verify_flag_rollout(
            sts=FakeSTS(),
            appconfig=appconfig,
            appconfigdata=FakeAppConfigData(False),
            expected_account_id=ACCOUNT_ID,
            test_id=TEST_ID,
            application_id=APP_ID,
            environment_id=ENV_ID,
            profile_id=PROFILE_ID,
            strategy_id=STRATEGY_ID,
            deployment_number=1,
            expected_enabled=False,
            expected_deployment_state="COMPLETE",
            timeout_seconds=1,
            sleep=lambda _: None,
        )


def test_absence_check_confirms_exact_ids_not_found():
    result = verify_resources_absent(
        sts=FakeSTS(),
        appconfig=FakeAppConfig(),
        expected_account_id=ACCOUNT_ID,
        test_id=TEST_ID,
        application_id=APP_ID,
        environment_id=ENV_ID,
        profile_id=PROFILE_ID,
        strategy_id=STRATEGY_ID,
        deployment_number=2,
    )

    assert result["status"] == "absent"
    assert result["deployment_history_absent"] is True


def test_absence_check_fails_if_any_test_resource_remains():
    with pytest.raises(LifecycleCheckError, match="resources remain"):
        verify_resources_absent(
            sts=FakeSTS(),
            appconfig=FakeAppConfig(remains_present=True),
            expected_account_id=ACCOUNT_ID,
            test_id=TEST_ID,
            application_id=APP_ID,
            environment_id=ENV_ID,
            profile_id=PROFILE_ID,
            strategy_id=STRATEGY_ID,
            deployment_number=2,
        )
