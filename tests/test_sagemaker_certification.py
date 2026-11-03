from pathlib import Path


def test_sagemaker_endpoint_module_requires_a_model_artifact():
    module = (
        Path(__file__).resolve().parents[1]
        / "infrastructure"
        / "terraform"
        / "modules"
        / "sagemaker-endpoint"
        / "main.tf"
    ).read_text()
    assert 'variable "model_data_url"' in module
    assert "model_data_url = var.model_data_url" in module


def test_sagemaker_certification_has_an_owned_artifact_and_live_probe_boundary():
    root = (
        Path(__file__).resolve().parents[1]
        / "infrastructure"
        / "terraform"
        / "module-validation"
        / "sagemaker"
        / "main.tf"
    ).read_text()
    script = (Path(__file__).resolve().parents[1] / "scripts" / "certify_sagemaker_endpoint.py").read_text()
    assert "force_destroy = true" in root
    assert 'sse_algorithm = "AES256"' in root
    assert 'identifiers = ["sagemaker.amazonaws.com"]' in root
    assert '"sagemaker-runtime",' in script
    assert '"raw-in-base64-out",' in script
    assert "DAVDEPLOY_DISPOSABLE_CERTIFICATION" in script
