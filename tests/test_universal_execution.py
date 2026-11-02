from hashlib import sha256

from davdeploy.certification_factory import certification_scenarios, scenario_for_module
from davdeploy.domain import ArchitectureModule
from davdeploy.universal_execution import LifecycleEvidence, compile_universal_execution_plan, verify_cleanup


def module(identifier: str, depends_on: list[str] | None = None) -> ArchitectureModule:
    return ArchitectureModule(identifier=identifier, display_name=identifier, purpose="test", stage="test", services=["AWS"], depends_on=depends_on or [])


def test_compiled_plan_has_full_lifecycle_and_customer_scope_tags():
    digest = sha256(b"approved").hexdigest()
    plan = compile_universal_execution_plan([module("api"), module("worker", ["api"])], workspace_id="workspace-1", project_id="project-1", plan_digest=digest)
    assert plan.modules[1].dependencies == ("api",)
    assert plan.modules[0].operations == ("plan", "apply", "observe", "rollback", "destroy", "verify_cleanup")
    assert ("DavDeployPlan", digest) in plan.modules[0].resource_tags
    assert verify_cleanup(tuple(LifecycleEvidence(item.module_id, "verify_cleanup", "ABSENT") for item in plan.modules), plan)


def test_compiler_rejects_unknown_dependencies():
    digest = sha256(b"approved").hexdigest()
    try:
        compile_universal_execution_plan([module("api", ["missing"])], workspace_id="w", project_id="p", plan_digest=digest)
    except ValueError as error:
        assert "unknown modules" in str(error)
    else:
        raise AssertionError("unknown dependency accepted")


def test_certification_factory_covers_eight_representative_workloads():
    scenarios = certification_scenarios()
    assert len(scenarios) == 8
    assert all(scenario.readiness and scenario.cleanup for scenario in scenarios)
    assert scenario_for_module("aws-managed-ml")[0].identifier == "machine-learning"
