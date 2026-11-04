from pathlib import Path

RUNTIME = Path("infrastructure/terraform/app-runner-runtime/main.tf")
VARIABLES = Path("infrastructure/terraform/app-runner-runtime/variables.tf")


def test_nova_runtime_is_opt_in_and_restricted_to_nova_2_lite():
    runtime = RUNTIME.read_text(encoding="utf-8")
    variables = VARIABLES.read_text(encoding="utf-8")
    assert 'variable "enable_nova_model"' in variables
    assert 'default     = false' in variables
    assert 'default     = "us.amazon.nova-2-lite-v1:0"' in variables
    assert runtime.count('["bedrock:InvokeModel"]') == 2
    assert "foundation-model/amazon.nova-2-lite-v1:0" in runtime
    assert "inference-profile/${var.nova_model_id}" in runtime
    assert 'variable = "bedrock:InferenceProfileArn"' in runtime
    assert "InvokeNova2LiteOnlyThroughProfile" in runtime
    assert 'DAVDEPLOY_MODEL_FALLBACK          = "disabled"' in runtime
    assert "DAVDEPLOY_MODEL_MAX_ATTEMPTS" not in runtime


def test_nova_configuration_contains_no_static_aws_credentials():
    configuration = "\n".join(
        [
            Path(".env.example").read_text(encoding="utf-8"),
            RUNTIME.read_text(encoding="utf-8"),
        ]
    )
    assert "AWS_ACCESS_KEY_ID" not in configuration
    assert "AWS_SECRET_ACCESS_KEY" not in configuration
