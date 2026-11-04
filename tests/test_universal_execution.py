from hashlib import sha256

import pytest
from davdeploy.certification_factory import certification_scenarios, scenario_for_module
from davdeploy.composed_deployment import dependency_dispatch_wave
from davdeploy.domain import ArchitectureModule
from davdeploy.universal_execution import (
    LifecycleEvidence,
    compile_universal_execution_plan,
    lifecycle_evidence_complete,
    lifecycle_work,
    ordered_modules,
    validate_lifecycle_work_graph,
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


def test_serialized_lifecycle_graph_accepts_forward_and_reverse_dependency_order():
    forward = [
        {"module_id": "api", "operation": "apply", "dependencies": [], "resource_tags": {}},
        {"module_id": "worker", "operation": "apply", "dependencies": ["api"], "resource_tags": {}},
    ]
    reverse = [
        {"module_id": "worker", "operation": "destroy", "dependencies": ["api"], "resource_tags": {}},
        {"module_id": "api", "operation": "destroy", "dependencies": [], "resource_tags": {}},
    ]
    assert [item["module_id"] for item in validate_lifecycle_work_graph(forward)] == [
        "api",
        "worker",
    ]
    assert [item["module_id"] for item in validate_lifecycle_work_graph(reverse)] == [
        "worker",
        "api",
    ]


@pytest.mark.parametrize(
    ("work", "message"),
    [
        ([], "required"),
        (
            [
                {"module_id": "api", "operation": "apply", "dependencies": [], "resource_tags": {}},
                {"module_id": "api", "operation": "apply", "dependencies": [], "resource_tags": {}},
            ],
            "duplicate module",
        ),
        (
            [{"module_id": "api", "operation": "apply", "dependencies": ["missing"], "resource_tags": {}}],
            "missing modules",
        ),
        (
            [
                {"module_id": "api", "operation": "apply", "dependencies": ["worker"], "resource_tags": {}},
                {"module_id": "worker", "operation": "apply", "dependencies": ["api"], "resource_tags": {}},
            ],
            "cycle",
        ),
        (
            [
                {"module_id": "worker", "operation": "apply", "dependencies": ["api"], "resource_tags": {}},
                {"module_id": "api", "operation": "apply", "dependencies": [], "resource_tags": {}},
            ],
            "not dependency-ordered",
        ),
        (
            [
                {"module_id": "api", "operation": "destroy", "dependencies": [], "resource_tags": {}},
                {"module_id": "worker", "operation": "destroy", "dependencies": ["api"], "resource_tags": {}},
            ],
            "not dependency-ordered",
        ),
        (
            [
                {"module_id": "api", "operation": "apply", "dependencies": [], "resource_tags": {}},
                {"module_id": "worker", "operation": "observe", "dependencies": ["api"], "resource_tags": {}},
            ],
            "one operation",
        ),
        (
            [{"module_id": "API", "operation": "apply", "dependencies": [], "resource_tags": {}}],
            "invalid module identifier",
        ),
    ],
)
def test_serialized_lifecycle_graph_rejects_invalid_or_unordered_work(work, message):
    with pytest.raises((TypeError, ValueError), match=message):
        validate_lifecycle_work_graph(work)


def test_dispatch_wave_starts_roots_and_independent_modules_only():
    digest = sha256(b"approved").hexdigest()
    plan = compile_universal_execution_plan(
        [module("api"), module("worker", ["api"]), module("uploads")],
        workspace_id="w",
        project_id="p",
        plan_digest=digest,
    )
    wave = dependency_dispatch_wave(
        plan,
        "apply",
        {"api": "NOT_DISPATCHED", "worker": "NOT_DISPATCHED", "uploads": "NOT_DISPATCHED"},
    )
    assert [item.module_id for item in wave] == ["api", "uploads"]

    next_wave = dependency_dispatch_wave(
        plan,
        "apply",
        {"api": "HEALTHY", "worker": "NOT_DISPATCHED", "uploads": "RUNNING"},
    )
    assert [item.module_id for item in next_wave] == ["worker"]


@pytest.mark.parametrize("blocked_state", ["FAILED", "RECONCILIATION_REQUIRED", "RUNNING"])
def test_dispatch_wave_blocks_dependents_until_prerequisite_is_terminal(blocked_state):
    digest = sha256(b"approved").hexdigest()
    plan = compile_universal_execution_plan(
        [module("api"), module("worker", ["api"])],
        workspace_id="w",
        project_id="p",
        plan_digest=digest,
    )
    wave = dependency_dispatch_wave(
        plan, "apply", {"api": blocked_state, "worker": "NOT_DISPATCHED"}
    )
    assert wave == ()


def test_cleanup_dispatch_wave_removes_dependents_before_dependencies():
    digest = sha256(b"approved").hexdigest()
    plan = compile_universal_execution_plan(
        [module("api"), module("worker", ["api"])],
        workspace_id="w",
        project_id="p",
        plan_digest=digest,
    )
    first_wave = dependency_dispatch_wave(
        plan, "destroy", {"api": "NOT_DISPATCHED", "worker": "NOT_DISPATCHED"}
    )
    assert [item.module_id for item in first_wave] == ["worker"]
    second_wave = dependency_dispatch_wave(
        plan, "destroy", {"api": "NOT_DISPATCHED", "worker": "DESTROYED_VERIFIED"}
    )
    assert [item.module_id for item in second_wave] == ["api"]


@pytest.mark.parametrize(
    ("states", "message"),
    [
        ({"api": "NOT_DISPATCHED"}, "do not match"),
        ({"api": "NOT_DISPATCHED", "worker": "NOT_DISPATCHED", "extra": "NOT_DISPATCHED"}, "do not match"),
        ({"api": "NOT_DISPATCHED", "worker": "UNKNOWN"}, "unknown lifecycle state"),
    ],
)
def test_dispatch_wave_rejects_incomplete_or_unknown_persisted_states(states, message):
    digest = sha256(b"approved").hexdigest()
    plan = compile_universal_execution_plan(
        [module("api"), module("worker", ["api"])],
        workspace_id="w",
        project_id="p",
        plan_digest=digest,
    )
    with pytest.raises(ValueError, match=message):
        dependency_dispatch_wave(plan, "apply", states)


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
