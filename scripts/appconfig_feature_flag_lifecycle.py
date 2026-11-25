"""Verify an exact, test-owned AWS AppConfig feature-flag rollout."""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

import boto3
from botocore.exceptions import ClientError


class LifecycleCheckError(RuntimeError):
    """Raised when the exact AppConfig test manifest is not satisfied."""


NOT_FOUND_CODES = frozenset(
    {
        "ResourceNotFoundException",
        "ResourceNotFound",
        "DeploymentNotFoundException",
    }
)
TERMINAL_DEPLOYMENT_STATES = frozenset(
    {"COMPLETE", "ROLLED_BACK", "REVERTED", "FAILED"}
)


def verify_account(sts: Any, expected_account_id: str) -> None:
    actual_account_id = sts.get_caller_identity().get("Account")
    if actual_account_id != expected_account_id:
        raise LifecycleCheckError("AWS caller account mismatch")


def _tags_for_resource(client: Any, arn: str, *, test_id: str) -> None:
    tags = client.list_tags_for_resource(ResourceArn=arn).get("Tags")
    if not isinstance(tags, dict):
        raise LifecycleCheckError("AppConfig resource tags are missing")
    if (
        tags.get("Product") != "davdeploy"
        or tags.get("Purpose") != "temporary-appconfig-feature-flag-validation"
        or tags.get("TestId") != test_id
    ):
        raise LifecycleCheckError("AppConfig ownership tags do not match the exact test")


def _deployment(client: Any, *, application_id: str, environment_id: str, number: int) -> dict[str, Any]:
    result = client.get_deployment(
        ApplicationId=application_id,
        EnvironmentId=environment_id,
        DeploymentNumber=number,
    )
    deployment = result.get("Deployment")
    if not isinstance(deployment, dict):
        raise LifecycleCheckError("exact AppConfig deployment metadata is missing")
    return deployment


def _verify_resources(
    *,
    appconfig: Any,
    application_id: str,
    environment_id: str,
    profile_id: str,
    strategy_id: str,
    deployment_number: int,
    expected_name: str,
    test_id: str,
) -> dict[str, Any]:
    application = appconfig.get_application(ApplicationId=application_id).get("Application")
    environment = appconfig.get_environment(
        ApplicationId=application_id, EnvironmentId=environment_id
    ).get("Environment")
    profile = appconfig.get_configuration_profile(
        ApplicationId=application_id, ConfigurationProfileId=profile_id
    ).get("ConfigurationProfile")
    strategy = appconfig.get_deployment_strategy(
        DeploymentStrategyId=strategy_id
    ).get("DeploymentStrategy")
    deployment = _deployment(
        appconfig,
        application_id=application_id,
        environment_id=environment_id,
        number=deployment_number,
    )
    if not all(isinstance(item, dict) for item in (application, environment, profile, strategy)):
        raise LifecycleCheckError("AppConfig resource metadata is incomplete")

    if application.get("Name") != expected_name or application.get("Id") != application_id:
        raise LifecycleCheckError("application does not match the exact test name")
    if environment.get("Name") != "production" or environment.get("ApplicationId") != application_id:
        raise LifecycleCheckError("environment is not bound to the exact test application")
    if (
        profile.get("Name") != f"{expected_name}-flags"
        or profile.get("ApplicationId") != application_id
        or profile.get("LocationUri") != "hosted"
        or profile.get("Type") != "AWS.AppConfig.FeatureFlags"
    ):
        raise LifecycleCheckError("profile is not the expected hosted feature-flag profile")
    if (
        strategy.get("Name") != f"{expected_name}-linear"
        or strategy.get("GrowthFactor") != 50.0
        or strategy.get("GrowthType") != "LINEAR"
        or strategy.get("DeploymentDurationInMinutes") != 1
        or strategy.get("FinalBakeTimeInMinutes") != 1
        or strategy.get("ReplicateTo") != "NONE"
    ):
        raise LifecycleCheckError("deployment strategy does not match the bounded test profile")
    if (
        deployment.get("ApplicationId") != application_id
        or deployment.get("EnvironmentId") != environment_id
        or deployment.get("ConfigurationProfileId") != profile_id
        or deployment.get("DeploymentStrategyId") != strategy_id
        or deployment.get("DeploymentNumber") != deployment_number
    ):
        raise LifecycleCheckError("deployment is not bound to the exact test resources")

    for item in (application, environment, profile, strategy):
        arn = item.get("Arn")
        if not isinstance(arn, str):
            raise LifecycleCheckError("AppConfig resource ARN is missing")
        _tags_for_resource(appconfig, arn, test_id=test_id)
    return deployment


def _read_enabled_flag(
    *,
    appconfigdata: Any,
    application_id: str,
    environment_id: str,
    profile_id: str,
    flag_name: str,
    configuration_token: str | None,
) -> tuple[str, bool | None]:
    if configuration_token is None:
        session = appconfigdata.start_configuration_session(
            ApplicationIdentifier=application_id,
            EnvironmentIdentifier=environment_id,
            ConfigurationProfileIdentifier=profile_id,
            RequiredMinimumPollIntervalInSeconds=15,
        )
        configuration_token = session.get("InitialConfigurationToken")
    if not isinstance(configuration_token, str):
        raise LifecycleCheckError("AppConfig Data session token is missing")

    response = appconfigdata.get_latest_configuration(
        ConfigurationToken=configuration_token
    )
    next_token = response.get("NextPollConfigurationToken")
    if not isinstance(next_token, str):
        raise LifecycleCheckError("AppConfig Data next-poll token is missing")
    body = response.get("Configuration")
    raw = body.read() if hasattr(body, "read") else body
    if raw in (None, b"", ""):
        return next_token, None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    if not isinstance(raw, str):
        raise LifecycleCheckError("AppConfig Data returned an unsupported body")
    try:
        configuration = json.loads(raw)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise LifecycleCheckError("AppConfig Data returned invalid feature-flag JSON") from exc
    flag = configuration.get(flag_name) if isinstance(configuration, dict) else None
    enabled = flag.get("enabled") if isinstance(flag, dict) else None
    if not isinstance(enabled, bool):
        raise LifecycleCheckError("AppConfig Data did not return the expected boolean flag")
    return next_token, enabled


def verify_flag_rollout(
    *,
    sts: Any,
    appconfig: Any,
    appconfigdata: Any,
    expected_account_id: str,
    test_id: str,
    application_id: str,
    environment_id: str,
    profile_id: str,
    strategy_id: str,
    deployment_number: int,
    expected_enabled: bool,
    expected_deployment_state: str,
    require_progressive_state: bool = False,
    timeout_seconds: int = 600,
    poll_interval_seconds: int = 15,
    sleep: Any = time.sleep,
) -> dict[str, Any]:
    if timeout_seconds < 1 or timeout_seconds > 900:
        raise LifecycleCheckError("rollout timeout is outside the 1-900 second bound")
    if poll_interval_seconds < 15 or poll_interval_seconds > 30:
        raise LifecycleCheckError("configuration polling interval is outside the 15-30 second bound")
    verify_account(sts, expected_account_id)
    expected_name = f"davdeploy-nova-ff-495-{test_id}"
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            deployment = _verify_resources(
                appconfig=appconfig,
                application_id=application_id,
                environment_id=environment_id,
                profile_id=profile_id,
                strategy_id=strategy_id,
                deployment_number=deployment_number,
                expected_name=expected_name,
                test_id=test_id,
            )
            break
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code not in NOT_FOUND_CODES or time.monotonic() >= deadline:
                raise
            sleep(poll_interval_seconds)
    initial_state = deployment.get("State")
    if require_progressive_state and initial_state not in {"DEPLOYING", "BAKING"}:
        raise LifecycleCheckError("progressive deployment state was not observed")

    state = initial_state
    token = None
    last_enabled = None
    while time.monotonic() < deadline:
        token, observed = _read_enabled_flag(
            appconfigdata=appconfigdata,
            application_id=application_id,
            environment_id=environment_id,
            profile_id=profile_id,
            flag_name="nova_demo",
            configuration_token=token,
        )
        if observed is not None:
            last_enabled = observed
        deployment = _deployment(
            appconfig,
            application_id=application_id,
            environment_id=environment_id,
            number=deployment_number,
        )
        state = deployment.get("State")
        if state in {"ROLLED_BACK", "REVERTED", "FAILED"} and state != expected_deployment_state:
            raise LifecycleCheckError("AppConfig deployment ended before expected verification")
        if state == expected_deployment_state and last_enabled is expected_enabled:
            return {
                "status": "verified",
                "account_id": expected_account_id,
                "test_id": test_id,
                "application_id": application_id,
                "environment_id": environment_id,
                "configuration_profile_id": profile_id,
                "deployment_strategy_id": strategy_id,
                "deployment_number": deployment_number,
                "deployment_state": state,
                "progressive_state_observed": initial_state in {"DEPLOYING", "BAKING"},
                "flag_name": "nova_demo",
                "flag_enabled": last_enabled,
            }
        sleep(poll_interval_seconds)
    raise LifecycleCheckError(
        f"AppConfig rollout did not reach the expected state; last deployment state: {state}"
    )


def _resource_exists(client: Any, method: str, **kwargs: Any) -> bool:
    try:
        getattr(client, method)(**kwargs)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in NOT_FOUND_CODES:
            return False
        raise LifecycleCheckError("AWS absence check failed for a non-not-found response") from exc
    return True


def verify_resources_absent(
    *,
    sts: Any,
    appconfig: Any,
    expected_account_id: str,
    test_id: str,
    application_id: str,
    environment_id: str,
    profile_id: str,
    strategy_id: str,
    deployment_number: int,
) -> dict[str, Any]:
    verify_account(sts, expected_account_id)
    checks = {
        "application": _resource_exists(
            appconfig, "get_application", ApplicationId=application_id
        ),
        "environment": _resource_exists(
            appconfig,
            "get_environment",
            ApplicationId=application_id,
            EnvironmentId=environment_id,
        ),
        "configuration_profile": _resource_exists(
            appconfig,
            "get_configuration_profile",
            ApplicationId=application_id,
            ConfigurationProfileId=profile_id,
        ),
        "deployment_strategy": _resource_exists(
            appconfig, "get_deployment_strategy", DeploymentStrategyId=strategy_id
        ),
        "deployment_history": _resource_exists(
            appconfig,
            "get_deployment",
            ApplicationId=application_id,
            EnvironmentId=environment_id,
            DeploymentNumber=deployment_number,
        ),
    }
    if any(checks.values()):
        raise LifecycleCheckError("one or more exact AppConfig test resources remain")
    return {
        "status": "absent",
        "account_id": expected_account_id,
        "test_id": test_id,
        "application_absent": True,
        "environment_absent": True,
        "configuration_profile_absent": True,
        "deployment_strategy_absent": True,
        "deployment_history_absent": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("present", "absent"), required=True)
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--test-id", required=True)
    parser.add_argument("--application-id", required=True)
    parser.add_argument("--environment-id", required=True)
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--strategy-id", required=True)
    parser.add_argument("--deployment-number", required=True, type=int)
    parser.add_argument("--expected-enabled", choices=("true", "false"))
    parser.add_argument("--expected-deployment-state", default="COMPLETE")
    parser.add_argument("--require-progressive-state", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--poll-interval-seconds", type=int, default=15)
    parser.add_argument("--profile")
    args = parser.parse_args(argv)
    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    sts = session.client("sts")
    appconfig = session.client("appconfig")
    try:
        if args.phase == "absent":
            result = verify_resources_absent(
                sts=sts,
                appconfig=appconfig,
                expected_account_id=args.account_id,
                test_id=args.test_id,
                application_id=args.application_id,
                environment_id=args.environment_id,
                profile_id=args.profile_id,
                strategy_id=args.strategy_id,
                deployment_number=args.deployment_number,
            )
        else:
            if args.expected_enabled is None:
                raise LifecycleCheckError("present phase requires --expected-enabled")
            appconfigdata = session.client("appconfigdata")
            result = verify_flag_rollout(
                sts=sts,
                appconfig=appconfig,
                appconfigdata=appconfigdata,
                expected_account_id=args.account_id,
                test_id=args.test_id,
                application_id=args.application_id,
                environment_id=args.environment_id,
                profile_id=args.profile_id,
                strategy_id=args.strategy_id,
                deployment_number=args.deployment_number,
                expected_enabled=args.expected_enabled == "true",
                expected_deployment_state=args.expected_deployment_state,
                require_progressive_state=args.require_progressive_state,
                timeout_seconds=args.timeout_seconds,
                poll_interval_seconds=args.poll_interval_seconds,
            )
    except LifecycleCheckError as exc:
        print(json.dumps({"status": "failed", "reason": str(exc)}))
        return 1
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "unknown")
        print(json.dumps({"status": "failed", "aws_error_code": code}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
