from pathlib import Path


def test_image_build_evidence_uses_connection_scoped_ecr_read():
    script = Path("scripts/customer-workload-app-runner-pilot.sh").read_text()

    assert "aws ecr batch-get-image" in script
    assert "aws ecr describe-images" not in script
