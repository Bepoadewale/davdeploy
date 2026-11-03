from hashlib import sha256

from davdeploy.composed_deployment import collect_observations, destroy_verified, lifecycle_ready
from davdeploy.domain import ArchitectureModule
from davdeploy.universal_execution import LifecycleEvidence, compile_universal_execution_plan


def test_composed_deployment_requires_all_module_health_and_cleanup():
    digest = sha256(b"plan").hexdigest()
    modules = [ArchitectureModule(identifier="api", display_name="API", purpose="api", stage="test", services=["Lambda"])]
    plan = compile_universal_execution_plan(modules, workspace_id="w", project_id="p", plan_digest=digest)
    evidence = (LifecycleEvidence("api", "observe", "HEALTHY", (("url", "https://example.test"),)), LifecycleEvidence("api", "verify_cleanup", "ABSENT"))
    assert lifecycle_ready(plan, evidence)
    assert destroy_verified(plan, evidence)
    assert collect_observations(plan, evidence)[0].outputs == (("url", "https://example.test"),)


def test_conflicting_module_evidence_fails_closed():
    digest = sha256(b"plan").hexdigest()
    modules = [
        ArchitectureModule(
            identifier="api", display_name="API", purpose="api", stage="test", services=["Lambda"]
        )
    ]
    plan = compile_universal_execution_plan(
        modules, workspace_id="w", project_id="p", plan_digest=digest
    )
    evidence = (
        LifecycleEvidence("api", "observe", "HEALTHY", (("url", "https://example.test"),)),
        LifecycleEvidence("api", "observe", "FAILED"),
        LifecycleEvidence("api", "verify_cleanup", "ABSENT"),
        LifecycleEvidence("api", "verify_cleanup", "FAILED"),
    )
    assert not lifecycle_ready(plan, evidence)
    assert not destroy_verified(plan, evidence)
    assert collect_observations(plan, evidence)[0].health == "UNKNOWN"
