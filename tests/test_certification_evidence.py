from davdeploy.certification_evidence import CertificationEvidence, scenario_status


def test_certification_requires_readiness_rollback_and_cleanup_not_only_terraform():
    evidence = CertificationEvidence("web-application", True, True)
    assert scenario_status((evidence,))["web-application"] == "REQUIRES_WORKLOAD_EVIDENCE"
    complete = CertificationEvidence("web-application", True, True, True, True, True)
    assert scenario_status((complete,))["web-application"] == "CERTIFIED"
