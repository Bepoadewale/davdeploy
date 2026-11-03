from hashlib import sha256

import pytest
from davdeploy.certification_factory import certification_scenarios, scenario_for_module
from davdeploy.domain import ArchitectureModule
from davdeploy.universal_execution import (
    LifecycleEvidence,
    compile_universal_execution_plan,
    lifecycle_evidence_complete,
    lifecycle_work,
    ordered_modules,
    verify_cleanup,
)


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


def test_compiler_rejects_empty_graph_and_invalid_scope_or_digest():
    digest = sha256(b"approved").hexdigest()
    with pytest.raises(ValueError, match="at least one module"):
        compile_universal_execution_plan([], workspace_id="w", project_id="p", plan_digest=digest)
    with pytest.raises(ValueError, match="workspace and project"):
        compile_universal_execution_plan(
            [module("api")], workspace_id=" ", project_id="p", plan_digest=digest
        )
    for invalid_digest in ("g" * 64, digest.upper(), "short"):
        with pytest.raises(ValueError, match="lowercase SHA-256"):
            compile_universal_execution_plan(
                [module("api")],
                workspace_id="w",
                project_id="p",
                plan_digest=invalid_digest,
            )


@pytest.mark.parametrize(
    ("identifier", "dependencies", "message"),
    [
        ("API", [], "invalid module identifier"),
        ("", [], "invalid module identifier"),
        ("api", ["api"], "cannot depend on itself"),
        ("api", ["worker", "worker"], "duplicate dependencies"),
    ],
)
def test_compiler_rejects_invalid_module_and_dependency_identifiers(
    identifier, dependencies, message
):
    digest = sha256(b"approved").hexdigest()
    with pytest.raises(ValueError, match=message):
        compile_universal_execution_plan(
            [module(identifier, dependencies)],
            workspace_id="w",
            project_id="p",
            plan_digest=digest,
        )


def test_lifecycle_work_is_stable_and_reverses_for_cleanup():
    digest = sha256(b"approved").hexdigest()
    plan = compile_universal_execution_plan(
        [module("worker", ["api"]), module("api"), module("uploads", ["api"])],
        workspace_id="w",
        project_id="p",
        plan_digest=digest,
    )
    assert [item.module_id for item in ordered_modules(plan, "apply")] == ["api", "uploads", "worker"]
    assert [item.module_id for item in ordered_modules(plan, "destroy")] == ["worker", "uploads", "api"]
    assert [item["module_id"] for item in lifecycle_work(plan, "apply")] == ["api", "uploads", "worker"]
    assert lifecycle_evidence_complete(
        plan,
        "apply",
        tuple(LifecycleEvidence(item.module_id, "apply", "SUCCEEDED") for item in plan.modules),
    )


@pytest.mark.parametrize(
    ("operation", "state"),
    [
        ("plan", "PLAN_READY_FOR_REVIEW"),
        ("apply", "SUCCEEDED_AWAITING_OBSERVATION"),
        ("observe", "HEALTHY"),
        ("rollback", "ROLLED_BACK"),
        ("destroy", "DESTROYED_VERIFIED"),
        ("verify_cleanup", "CLEANUP_VERIFIED"),
    ],
)
def test_lifecycle_evidence_uses_operation_specific_terminal_states(operation, state):
    digest = sha256(b"approved").hexdigest()
    plan = compile_universal_execution_plan(
        [module("api")], workspace_id="workspace-1", project_id="project-1", plan_digest=digest
    )
    assert lifecycle_evidence_complete(
        plan, operation, (LifecycleEvidence("api", operation, state),)
    )


@pytest.mark.parametrize(
    ("operation", "wrong_state"),
    [
        ("plan", "HEALTHY"),
        ("apply", "PLAN_READY_FOR_REVIEW"),
        ("observe", "SUCCEEDED"),
        ("rollback", "HEALTHY"),
        ("destroy", "CLEANUP_VERIFIED"),
        ("verify_cleanup", "DESTROYED_VERIFIED"),
    ],
)
def test_lifecycle_evidence_rejects_wrong_operation_state(operation, wrong_state):
    digest = sha256(b"approved").hexdigest()
    plan = compile_universal_execution_plan(
        [module("api")], workspace_id="workspace-1", project_id="project-1", plan_digest=digest
    )
    assert not lifecycle_evidence_complete(
        plan, operation, (LifecycleEvidence("api", operation, wrong_state),)
    )


def test_lifecycle_evidence_requires_every_module_and_unambiguous_outcomes():
    digest = sha256(b"approved").hexdigest()
    plan = compile_universal_execution_plan(
        [module("api"), module("worker", ["api"])],
        workspace_id="workspace-1",
        project_id="project-1",
        plan_digest=digest,
    )
    assert not lifecycle_evidence_complete(
        plan, "observe", (LifecycleEvidence("api", "observe", "HEALTHY"),)
    )
    assert not lifecycle_evidence_complete(
        plan,
        "observe",
        (
            LifecycleEvidence("api", "observe", "HEALTHY"),
            LifecycleEvidence("worker", "observe", "HEALTHY"),
            LifecycleEvidence("worker", "observe", "FAILED"),
        ),
    )


def test_compiler_rejects_cycles_and_unknown_operations():
    digest = sha256(b"approved").hexdigest()
    plan = compile_universal_execution_plan(
        [module("api", ["worker"]), module("worker", ["api"])],
        workspace_id="w",
        project_id="p",
        plan_digest=digest,
    )
    try:
        ordered_modules(plan, "apply")
    except ValueError as error:
        assert "cycle" in str(error)
    else:
        raise AssertionError("dependency cycle accepted")
    try:
        ordered_modules(plan, "unbounded-shell")
    except ValueError as error:
        assert "unsupported" in str(error)
    else:
        raise AssertionError("unknown operation accepted")


def test_certification_factory_covers_eight_representative_workloads():
    scenarios = certification_scenarios()
    assert len(scenarios) == 8
    assert all(scenario.readiness and scenario.cleanup for scenario in scenarios)
    assert scenario_for_module("aws-managed-ml")[0].identifier == "machine-learning"
