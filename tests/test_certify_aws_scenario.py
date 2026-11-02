from pathlib import Path

from davdeploy.certification_factory import certification_scenarios


def test_each_certification_scenario_has_an_explicit_runner_boundary():
    script = Path(__file__).resolve().parents[1] / "scripts" / "certify_aws_scenario.py"
    text = script.read_text()
    for scenario in certification_scenarios():
        assert f'"{scenario.identifier}"' in text
    assert "DAVDEPLOY_DISPOSABLE_CERTIFICATION" in text
    assert "AWS_PROFILE" in text
