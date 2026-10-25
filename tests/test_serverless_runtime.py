from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from botocore.exceptions import ClientError
from davdeploy import db, executor, lambda_cognito_link, main, policy, security
from davdeploy.domain import PolicyResult
from davdeploy.lambda_policy import handler as policy_handler
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


def test_database_url_requires_complete_data_api_configuration(monkeypatch):
    monkeypatch.setenv("DAVDEPLOY_AURORA_CLUSTER_ARN", "arn:cluster")
    monkeypatch.delenv("DAVDEPLOY_DATABASE_SECRET_ARN", raising=False)
    with pytest.raises(RuntimeError, match="both cluster and secret"):
        db.database_url()


def test_data_api_engine_uses_arn_connect_arguments(monkeypatch):
    captured = {}
    monkeypatch.setenv("DAVDEPLOY_AURORA_CLUSTER_ARN", "arn:cluster")
    monkeypatch.setenv("DAVDEPLOY_DATABASE_SECRET_ARN", "arn:secret")
    monkeypatch.setenv("DAVDEPLOY_DATABASE_NAME", "controlplane")

    def fake_create_engine(url, **kwargs):
        captured.update(url=url, **kwargs)
        return object()

    monkeypatch.setattr(db, "create_engine", fake_create_engine)
    db.make_engine()
    assert captured["url"] == "postgresql+auroradataapi://:@/controlplane"
    assert captured["connect_args"] == {
        "aurora_cluster_arn": "arn:cluster",
        "secret_arn": "arn:secret",
    }
    assert captured["pool_pre_ping"] is False


def test_aurora_readiness_retries_a_resuming_database(monkeypatch):
    attempts = []
    sleeps = []

    class DataApi:
        def execute_statement(self, **kwargs):
            attempts.append(kwargs)
            if len(attempts) < 3:
                raise ClientError(
                    {"Error": {"Code": "DatabaseResumingException", "Message": "resuming"}},
                    "ExecuteStatement",
                )

    monkeypatch.setenv("DAVDEPLOY_AURORA_CLUSTER_ARN", "arn:cluster")
    monkeypatch.setenv("DAVDEPLOY_DATABASE_SECRET_ARN", "arn:secret")
    guard = db.AuroraReadinessGuard()
    guard.ensure_ready(
        client=DataApi(),
        sleeper=sleeps.append,
        clock=lambda: 100.0,
        delays=(2.0, 3.0),
    )

    assert len(attempts) == 3
    assert sleeps == [2.0, 3.0]
    assert attempts[-1]["sql"] == "SELECT 1"


def test_aurora_readiness_exhaustion_is_a_controlled_503(monkeypatch):
    class DataApi:
        def execute_statement(self, **kwargs):
            raise ClientError(
                {"Error": {"Code": "DatabaseResumingException", "Message": "resuming"}},
                "ExecuteStatement",
            )

    monkeypatch.setenv("DAVDEPLOY_AURORA_CLUSTER_ARN", "arn:cluster")
    monkeypatch.setenv("DAVDEPLOY_DATABASE_SECRET_ARN", "arn:secret")
    guard = db.AuroraReadinessGuard()
    with pytest.raises(db.AuroraDatabaseUnavailable, match="retry shortly"):
        guard.ensure_ready(
            client=DataApi(),
            sleeper=lambda delay: None,
            clock=lambda: 100.0,
            delays=(0.0,),
        )

    monkeypatch.setattr(
        main,
        "ensure_aurora_ready",
        lambda: (_ for _ in ()).throw(
            db.AuroraDatabaseUnavailable("database is resuming; retry shortly")
        ),
    )
    response = TestClient(main.app).get("/api/v1/me")

    assert response.status_code == 503
    assert response.json() == {"detail": "database is resuming; retry shortly"}
    assert response.headers["retry-after"] == "10"
    assert response.headers["x-davdeploy-api-version"] == "v1"


def test_policy_lambda_preserves_approval_boundary():
    result = policy_handler(
        {
            "input": {
                "principal": {"subject": "u", "organization_id": "o"},
                "spec": {"environments": ["production"], "monthly_budget_usd": 100},
                "action": "DEPLOY",
            }
        },
        None,
    )
    assert result["result"]["result"] == PolicyResult.APPROVAL_REQUIRED


def test_policy_client_invokes_lambda_and_parses_decision(monkeypatch):
    class Lambda:
        def invoke(self, **kwargs):
            assert kwargs["FunctionName"] == "policy-arn"
            return {
                "Payload": io.BytesIO(
                    json.dumps(
                        {"result": {"result": "ALLOW", "reason": "tested"}}
                    ).encode()
                )
            }

    monkeypatch.setattr(policy.boto3, "client", lambda service: Lambda())
    client = policy.PolicyClient()
    client.function_arn = "policy-arn"
    decision = client._invoke_lambda({"safe": True})
    assert decision.result == PolicyResult.ALLOW


def test_cognito_linker_only_links_verified_google_identity(monkeypatch):
    calls = []

    class Cognito:
        def list_users(self, **kwargs):
            return {"Users": [{"Username": "native-user"}]}

        def admin_link_provider_for_user(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(lambda_cognito_link.boto3, "client", lambda service: Cognito())
    event = {
        "triggerSource": "PreSignUp_ExternalProvider",
        "userPoolId": "pool",
        "userName": "Google_123",
        "request": {
            "userAttributes": {
                "email": "Person@example.com",
                "email_verified": "true",
            }
        },
        "response": {},
    }
    result = lambda_cognito_link.handler(event, None)
    assert calls[0]["DestinationUser"]["ProviderAttributeValue"] == "native-user"
    assert result["response"]["autoConfirmUser"] is True


def test_cognito_access_token_client_id_is_accepted_as_audience(monkeypatch):
    verifier = security.JwksIdentityVerifier("https://example.test/jwks", "issuer", "client")
    verifier.client = type(
        "Client", (), {"get_signing_key_from_jwt": lambda self, token: type("Key", (), {"key": "key"})()}
    )()
    monkeypatch.setattr(
        security.jwt,
        "decode",
        lambda *args, **kwargs: {
            "sub": "subject",
            "exp": 9999999999,
            "client_id": "client",
            "token_use": "id",
            "email": "person@example.com",
            "email_verified": True,
        },
    )
    claims = verifier.verify_claims("token")
    assert claims.email == "person@example.com"
    assert claims.email_verified is True


def test_cognito_access_token_is_rejected_when_identity_token_is_required(monkeypatch):
    verifier = security.JwksIdentityVerifier(
        "https://example.test/jwks",
        "https://cognito-idp.us-east-1.amazonaws.com/pool",
        "client",
    )
    verifier.client = type(
        "Client",
        (),
        {
            "get_signing_key_from_jwt": lambda self, token: type(
                "Key", (), {"key": "key"}
            )()
        },
    )()
    monkeypatch.setattr(
        security.jwt,
        "decode",
        lambda *args, **kwargs: {
            "sub": "subject",
            "exp": 9999999999,
            "client_id": "client",
            "token_use": "access",
        },
    )
    with pytest.raises(security.HTTPException) as error:
        verifier.verify_claims("token")
    assert error.value.status_code == 401


def test_serverless_stack_has_no_nat_gateway_or_lambda_vpc_attachment():
    terraform = (ROOT / "infrastructure/terraform/serverless-control-plane/main.tf").read_text()
    assert 'resource "aws_nat_gateway"' not in terraform
    assert 'resource "aws_internet_gateway"' not in terraform
    assert "vpc_config" not in terraform
    assert "enable_http_endpoint            = true" in terraform


def test_serverless_stack_keeps_google_secret_out_of_terraform_state():
    terraform_root = ROOT / "infrastructure/terraform/serverless-control-plane"
    contract = "\n".join(path.read_text() for path in terraform_root.glob("*.tf"))
    assert "google_client_secret" not in contract
    assert "aws_cognito_identity_provider" not in contract


def test_serverless_stack_pins_an_orderable_aurora_postgresql_version():
    variables = (
        ROOT / "infrastructure/terraform/serverless-control-plane/variables.tf"
    ).read_text()
    assert 'default     = "16.15"' in variables
    assert 'default     = "16.6"' not in variables


def test_serverless_stack_selects_the_implemented_bedrock_gateway():
    terraform = (ROOT / "infrastructure/terraform/serverless-control-plane/main.tf").read_text()
    assert 'DAVDEPLOY_MODEL_PROVIDER="bedrock"' in terraform.replace(" ", "")
    assert "bedrock-nova" not in terraform


def test_serverless_stack_uses_network_independent_bounded_fixture_executor():
    terraform = (ROOT / "infrastructure/terraform/serverless-control-plane/main.tf").read_text()
    assert 'DAVDEPLOY_EXECUTOR_MODE="embedded_fixture"' in terraform.replace(" ", "")


def test_serverless_stack_delivers_minimal_worker_wakeups_through_sqs():
    terraform = (ROOT / "infrastructure/terraform/serverless-control-plane/main.tf").read_text()
    assert "DAVDEPLOY_WORKER_QUEUE_URL" in terraform
    assert '"sqs:SendMessage"' in terraform


def test_serverless_stack_allows_worker_to_decrypt_but_not_write_customer_results():
    terraform = (ROOT / "infrastructure/terraform/serverless-control-plane/main.tf").read_text()
    api_policy = terraform.split('resource "aws_iam_role_policy" "api"', 1)[1].split(
        'resource "aws_iam_role" "customer_executor"', 1
    )[0]
    assert 'Action   = ["kms:Decrypt"]' in api_policy
    assert "Resource = var.customer_execution_kms_key_arns" in api_policy
    assert "kms:Encrypt" not in api_policy
    assert "kms:GenerateDataKey" not in api_policy


def test_serverless_stack_scopes_invitation_email_to_the_verified_ses_identity():
    terraform = (ROOT / "infrastructure/terraform/serverless-control-plane/main.tf").read_text()
    assert 'Action   = ["ses:SendEmail"]' in terraform
    assert "Resource = var.ses_identity_arn" in terraform
    assert 'DAVDEPLOY_EMAIL_PROVIDER=var.ses_identity_arn==""?"disabled":"ses"' in terraform.replace(" ", "")
    assert "DAVDEPLOY_FRONTEND_ORIGIN" in terraform


def test_serverless_stack_scopes_release_migration_invocation():
    terraform = (ROOT / "infrastructure/terraform/serverless-control-plane/main.tf").read_text()
    assert 'name = "davdeploy-terraform-apply-github"' in terraform
    assert 'name = "invoke-davdeploy-release-migrations"' in terraform
    assert 'Action   = ["lambda:InvokeFunction"]' in terraform
    assert "Resource = aws_lambda_function.migrate.arn" in terraform


def test_embedded_fixture_executor_is_stateless_and_bounded(monkeypatch):
    monkeypatch.setenv("DAVDEPLOY_EXECUTOR_MODE", "embedded_fixture")
    adapter = executor.configured_executor()

    deployed = adapter.deploy("environment-1", "aws-lambda-api")
    destroyed = adapter.destroy("environment-1")

    assert deployed.state == "READY"
    assert deployed.detail["fixture"] == "bounded-embedded-executor"
    assert deployed.detail["outputs"][1]["name"] == "lambda_function_arn"
    assert deployed.detail["resources"][0]["resource_type"] == "lambda_function"
    assert "app_runner" not in str(deployed.detail)
    assert destroyed.state == "DESTROYED"
    assert destroyed.detail["cleanup_verified"] is True


@pytest.mark.parametrize(
    ("profile", "output_name", "resource_type"),
    [
        ("aws-lambda-api", "lambda_function_arn", "lambda_function"),
        ("aws-app-runner", "app_runner_service_arn", "apprunner_service"),
        ("aws-ecs-fargate", "ecs_service_arn", "ecs_service"),
        ("aws-eks-governed", "eks_cluster_arn", "eks_cluster"),
        ("future-provider", "simulated_resource_reference", "simulated_service"),
    ],
)
def test_embedded_fixture_reports_the_selected_resource_family(
    profile, output_name, resource_type
):
    deployed = executor.EmbeddedFixtureExecutor().deploy("environment-1", profile)

    assert deployed.detail["outputs"][1]["name"] == output_name
    assert deployed.detail["resources"][0]["resource_type"] == resource_type


def test_serverless_stack_authorizes_only_the_selected_nova_model_family():
    terraform = (ROOT / "infrastructure/terraform/serverless-control-plane/main.tf").read_text()
    assert "foundation-model/amazon.nova-2-lite-v1:0" in terraform
    assert "inference-profile/${var.nova_model_id}" in terraform
    assert "foundation-model/*" not in terraform


def test_serverless_stack_manages_logs_and_actionable_alarms():
    terraform = (ROOT / "infrastructure/terraform/serverless-control-plane/main.tf").read_text()
    assert 'resource "aws_cloudwatch_log_group" "lambda"' in terraform
    assert "retention_in_days = 14" in terraform
    assert 'resource "aws_sns_topic" "operations"' in terraform
    for alarm in (
        "api_errors",
        "worker_errors",
        "api_gateway_5xx",
        "worker_dead_letter",
        "database_capacity_high",
    ):
        assert f'resource "aws_cloudwatch_metric_alarm" "{alarm}"' in terraform


def test_serverless_stack_allows_only_preflight_without_jwt():
    terraform = (ROOT / "infrastructure/terraform/serverless-control-plane/main.tf").read_text()
    assert 'route_key = "OPTIONS /"' in terraform
    assert 'route_key = "OPTIONS /{proxy+}"' in terraform
    assert terraform.count('authorization_type = "JWT"') == 1
    assert terraform.count("authorizer_id      = aws_apigatewayv2_authorizer.cognito.id") == 1
