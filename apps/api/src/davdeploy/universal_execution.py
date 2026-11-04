"""Provider-neutral, deterministic lifecycle contracts for composed workloads.

This is intentionally a compiler boundary.  It turns a selected internal module
graph into immutable lifecycle work, but never accepts free-form commands or
credentials from a model or browser.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol

from davdeploy.domain import ArchitectureModule
from davdeploy.module_ports import module_ports, validate_module_outputs

LIFECYCLE_OPERATIONS = ("plan", "apply", "observe", "rollback", "destroy", "verify_cleanup")
FORWARD_OPERATIONS = ("plan", "apply", "observe")
REVERSE_OPERATIONS = ("rollback", "destroy", "verify_cleanup")
TERMINAL_EVIDENCE_STATES = {
    "plan": frozenset({"SUCCEEDED", "PLAN_READY_FOR_REVIEW", "DESTROY_PLAN_READY_FOR_REVIEW"}),
    "apply": frozenset({"SUCCEEDED", "SUCCEEDED_AWAITING_OBSERVATION"}),
    "observe": frozenset({"HEALTHY"}),
    "rollback": frozenset({"ROLLED_BACK", "DESTROYED_VERIFIED"}),
    "destroy": frozenset({"SUCCEEDED", "DESTROYED_VERIFIED"}),
    "verify_cleanup": frozenset({"ABSENT", "CLEANUP_VERIFIED"}),
}
_MODULE_ID_PATTERN = re.compile(r"[a-z][a-z0-9-]{0,99}\Z")
_PORT_NAME_PATTERN = re.compile(r"[a-z][a-z0-9_]{0,99}\Z")
_PLAN_DIGEST_PATTERN = re.compile(r"[a-f0-9]{64}\Z")
_DISPATCH_OPERATIONS = frozenset(
    (*LIFECYCLE_OPERATIONS, "destroy_plan", "build-push-image", "build_artifact")
)
_REVERSE_DISPATCH_OPERATIONS = frozenset((*REVERSE_OPERATIONS, "destroy_plan"))
_DISPATCH_SUCCESS_STATES = {
    "plan": frozenset({"PLAN_READY_FOR_REVIEW", "DESTROY_PLAN_READY_FOR_REVIEW"}),
    "destroy_plan": frozenset({"DESTROY_PLAN_READY_FOR_REVIEW"}),
    "build_artifact": frozenset({"ARTIFACT_READY"}),
    "apply": frozenset({"SUCCEEDED_AWAITING_OBSERVATION", "HEALTHY"}),
    "observe": frozenset({"HEALTHY"}),
    "rollback": frozenset({"ROLLED_BACK", "DESTROYED_VERIFIED"}),
    "destroy": frozenset({"DESTROYED_VERIFIED"}),
    "verify_cleanup": frozenset({"CLEANUP_VERIFIED", "DESTROYED_VERIFIED"}),
}


@dataclass(frozen=True)
class ModuleLifecycle:
    module_id: str
    instance_id: str
    dependencies: tuple[str, ...]
    input_bindings: tuple[tuple[str, str, str], ...] = ()
    operations: tuple[str, ...] = LIFECYCLE_OPERATIONS
    resource_tags: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class UniversalExecutionPlan:
    plan_digest: str
    modules: tuple[ModuleLifecycle, ...]
    estimated_monthly_cost_state: str
    immutable: bool = True


@dataclass(frozen=True)
class LifecycleEvidence:
    module_id: str
    operation: str
    state: str
    outputs: tuple[tuple[str, str], ...] = ()
    instance_id: str | None = None


class LifecycleExecutor(Protocol):
    def run(
        self, plan: UniversalExecutionPlan, operation: str
    ) -> tuple[LifecycleEvidence, ...]: ...


def ordered_modules(plan: UniversalExecutionPlan, operation: str) -> tuple[ModuleLifecycle, ...]:
    """Return a stable dependency order for one bounded lifecycle operation.

    Apply-like work executes dependencies before their consumers. Cleanup-like
    work reverses that order. This contract deliberately contains no commands,
    credentials, or provider SDK calls.
    """
    if operation not in LIFECYCLE_OPERATIONS:
        raise ValueError(f"unsupported lifecycle operation: {operation}")
    by_id = {module.instance_id: module for module in plan.modules}
    remaining = {module.instance_id: set(module.dependencies) for module in plan.modules}
    ordered: list[ModuleLifecycle] = []
    while remaining:
        ready = sorted(
            identifier for identifier, dependencies in remaining.items() if not dependencies
        )
        if not ready:
            raise ValueError("module graph contains a dependency cycle")
        for identifier in ready:
            ordered.append(by_id[identifier])
            del remaining[identifier]
        completed = set(ready)
        for dependencies in remaining.values():
            dependencies.difference_update(completed)
    if operation in REVERSE_OPERATIONS:
        ordered.reverse()
    return tuple(ordered)


def lifecycle_work(plan: UniversalExecutionPlan, operation: str) -> tuple[dict[str, object], ...]:
    """Serialize only typed lifecycle work for a durable execution runner."""
    return tuple(
        {
            "module_id": module.module_id,
            "instance_id": module.instance_id,
            "operation": operation,
            "dependencies": list(module.dependencies),
            "input_bindings": [
                {
                    "input_name": input_name,
                    "source_instance_id": source_instance_id,
                    "source_output": source_output,
                }
                for input_name, source_instance_id, source_output in module.input_bindings
            ],
            "resource_tags": dict(module.resource_tags),
        }
        for module in ordered_modules(plan, operation)
    )


def validate_lifecycle_work_graph(value: object) -> tuple[dict[str, object], ...]:
    """Validate the serialized dependency graph before renderer resolution.

    The database and queue are durable boundaries, but their contents still
    need complete graph validation before any runner is selected. This checks
    identity, references, cycles, operation consistency and the dependency
    order required by forward or cleanup work. It does not authorize a module;
    the fixed renderer registry performs that separate check.
    """
    if not isinstance(value, list) or not value:
        raise ValueError("universal lifecycle work is required")

    accepted: list[dict[str, object]] = []
    seen: set[str] = set()
    graph: dict[str, tuple[str, ...]] = {}
    operations: set[str] = set()
    for item in value:
        if not isinstance(item, Mapping):
            raise TypeError("universal lifecycle work item must be an object")
        module_id = item.get("module_id")
        instance_id = item.get("instance_id", module_id)
        operation = item.get("operation")
        dependencies = item.get("dependencies")
        input_bindings = item.get("input_bindings", [])
        resource_tags = item.get("resource_tags")
        if not isinstance(module_id, str) or not _MODULE_ID_PATTERN.fullmatch(module_id):
            raise ValueError("universal lifecycle work item has an invalid module identifier")
        if not isinstance(instance_id, str) or not _MODULE_ID_PATTERN.fullmatch(instance_id):
            raise ValueError("universal lifecycle work item has an invalid instance identifier")
        if instance_id in seen:
            raise ValueError("universal lifecycle work contains duplicate instance identifiers")
        if not isinstance(operation, str) or operation not in _DISPATCH_OPERATIONS:
            raise ValueError("universal lifecycle work has an unsupported operation")
        if not isinstance(dependencies, list) or not all(
            isinstance(dependency, str) and _MODULE_ID_PATTERN.fullmatch(dependency)
            for dependency in dependencies
        ):
            raise ValueError("universal lifecycle work has invalid dependencies")
        if len(dependencies) != len(set(dependencies)):
            raise ValueError(f"module {module_id} contains duplicate dependencies")
        if not isinstance(input_bindings, list):
            raise TypeError("universal lifecycle work has invalid input bindings")
        accepted_bindings: list[dict[str, str]] = []
        bound_inputs: set[str] = set()
        for binding in input_bindings:
            if not isinstance(binding, Mapping) or set(binding) != {
                "input_name",
                "source_instance_id",
                "source_output",
            }:
                raise ValueError("universal lifecycle input binding must contain references only")
            input_name = binding["input_name"]
            source_instance_id = binding["source_instance_id"]
            source_output = binding["source_output"]
            if (
                not isinstance(input_name, str)
                or not _PORT_NAME_PATTERN.fullmatch(input_name)
                or not isinstance(source_instance_id, str)
                or not _MODULE_ID_PATTERN.fullmatch(source_instance_id)
                or not isinstance(source_output, str)
                or not _PORT_NAME_PATTERN.fullmatch(source_output)
            ):
                raise ValueError("universal lifecycle input binding has an invalid reference")
            if input_name in bound_inputs:
                raise ValueError("universal lifecycle input binding repeats a destination input")
            if source_instance_id not in dependencies:
                raise ValueError("input binding source must be a declared module dependency")
            bound_inputs.add(input_name)
            accepted_bindings.append(
                {
                    "input_name": input_name,
                    "source_instance_id": source_instance_id,
                    "source_output": source_output,
                }
            )
        if instance_id in dependencies:
            raise ValueError(f"module instance {instance_id} cannot depend on itself")
        if not isinstance(resource_tags, Mapping) or not all(
            isinstance(key, str) and isinstance(tag_value, str)
            for key, tag_value in resource_tags.items()
        ):
            raise ValueError("universal lifecycle work has invalid resource tags")
        seen.add(instance_id)
        graph[instance_id] = tuple(dependencies)
        operations.add(operation)
        accepted.append(
            {
                "module_id": module_id,
                "instance_id": instance_id,
                "operation": operation,
                "dependencies": list(dependencies),
                "input_bindings": accepted_bindings,
                "resource_tags": dict(resource_tags),
            }
        )

    if len(operations) != 1:
        raise ValueError("universal lifecycle work must use one operation")
    operation = next(iter(operations))
    for instance_id, dependencies in graph.items():
        missing = set(dependencies) - seen
        if missing:
            raise ValueError(
                f"module instance {instance_id} depends on missing modules or instances: {sorted(missing)}"
            )

    # A complete dependency walk also rejects cycles, including those hidden
    # by an otherwise plausible submitted ordering.
    pending = {module_id: set(dependencies) for module_id, dependencies in graph.items()}
    emitted: list[str] = []
    while pending:
        ready = sorted(module_id for module_id, deps in pending.items() if not deps)
        if not ready:
            raise ValueError("module graph contains a dependency cycle")
        emitted.extend(ready)
        completed = set(ready)
        for module_id in ready:
            del pending[module_id]
        for deps in pending.values():
            deps.difference_update(completed)

    submitted_order = [str(item["instance_id"]) for item in accepted]
    positions = {instance_id: index for index, instance_id in enumerate(submitted_order)}
    reverse = operation in _REVERSE_DISPATCH_OPERATIONS
    for instance_id, dependencies in graph.items():
        for dependency in dependencies:
            correctly_ordered = (
                positions[dependency] > positions[instance_id]
                if reverse
                else positions[dependency] < positions[instance_id]
            )
            if not correctly_ordered:
                raise ValueError(
                    f"module graph is not dependency-ordered for {operation}: {instance_id}"
                )
    return tuple(accepted)


def next_dispatchable_work_item(
    value: object, module_states: Mapping[str, str]
) -> dict[str, object] | None:
    """Select the first undispatched node whose lifecycle prerequisites succeeded.

    This deliberately returns one node so the caller can attach a unique runner
    build identity before any later dependency wave is submitted. Input bindings
    remain references here; callers must resolve them through a renderer-specific
    contract before dispatch.
    """
    work = validate_lifecycle_work_graph(value)
    operation = str(work[0]["operation"])
    success_states = _DISPATCH_SUCCESS_STATES.get(operation)
    if success_states is None:
        return None
    known_instances = {str(item["instance_id"]) for item in work}
    if set(module_states) - known_instances or any(
        not isinstance(state, str) for state in module_states.values()
    ):
        raise ValueError("module state map does not match the validated lifecycle graph")

    dependencies_by_instance = {
        str(item["instance_id"]): tuple(str(dep) for dep in item["dependencies"]) for item in work
    }
    reverse = operation in _REVERSE_DISPATCH_OPERATIONS
    for item in work:
        instance_id = str(item["instance_id"])
        state = module_states.get(instance_id, "NOT_DISPATCHED")
        if state not in {"NOT_DISPATCHED", "QUEUED"}:
            continue
        if reverse:
            prerequisites = tuple(
                candidate
                for candidate, dependencies in dependencies_by_instance.items()
                if instance_id in dependencies
            )
        else:
            prerequisites = dependencies_by_instance[instance_id]
        if all(module_states.get(source) in success_states for source in prerequisites):
            return item
    return None


def lifecycle_evidence_complete(
    plan: UniversalExecutionPlan,
    operation: str,
    evidence: Iterable[LifecycleEvidence],
) -> bool:
    """Require one operation-appropriate terminal record for every graph node.

    A module's successful health check cannot stand in for its plan or apply,
    and a successful delete request is not cleanup proof until absence is
    independently observed. Duplicate records are ambiguous because this
    contract has no attempt ordering, so callers must pass the current
    per-module outcome set rather than an event history.
    """
    expected = {module.instance_id for module in ordered_modules(plan, operation)}
    terminal_states = TERMINAL_EVIDENCE_STATES[operation]
    outcomes: dict[str, list[str]] = {module_id: [] for module_id in expected}
    for item in evidence:
        instance_id = item.instance_id or item.module_id
        if item.operation == operation and instance_id in outcomes:
            outcomes[instance_id].append(item.state)
    return all(len(states) == 1 and states[0] in terminal_states for states in outcomes.values())


def resolve_module_inputs(
    plan: UniversalExecutionPlan,
    instance_id: str,
    module_outputs: Mapping[str, object],
    module_states: Mapping[str, str],
) -> dict[str, str]:
    """Resolve declared input references from successful dependency outcomes.

    This function returns only values that the source module explicitly
    declared as outputs. A secret port resolves to a secret reference ARN; it
    never reads the referenced secret contents.
    """
    modules = {module.instance_id: module for module in plan.modules}
    consumer = modules.get(instance_id)
    if consumer is None:
        raise ValueError("module instance is outside the execution graph")
    resolved: dict[str, str] = {}
    successful_states = {"SUCCEEDED_AWAITING_OBSERVATION", "HEALTHY"}
    for input_name, source_instance_id, source_output in consumer.input_bindings:
        if source_instance_id not in consumer.dependencies:
            raise ValueError("input binding source is not a declared dependency")
        if module_states.get(source_instance_id) not in successful_states:
            raise ValueError("input binding source has not completed successfully")
        source = modules[source_instance_id]
        source_contracts = {item.name: item for item in module_ports(source.module_id).outputs}
        port_contract = source_contracts.get(source_output)
        if port_contract is None:
            raise ValueError("input binding references an undeclared source output")
        source_values = validate_module_outputs(
            source.module_id, module_outputs.get(source_instance_id)
        )
        if source_values is None or source_output not in source_values:
            raise ValueError("input binding source output is not available")
        resolved[input_name] = source_values[source_output]
    return resolved


def resolve_lifecycle_work_inputs(
    work: object,
    instance_id: str,
    module_outputs: Mapping[str, object],
    module_states: Mapping[str, str],
    *,
    plan_digest: str,
) -> dict[str, str]:
    """Resolve typed references from the durable, serialized worker graph."""
    accepted = validate_lifecycle_work_graph(work)
    modules = tuple(
        ModuleLifecycle(
            module_id=str(item["module_id"]),
            instance_id=str(item["instance_id"]),
            dependencies=tuple(str(value) for value in item["dependencies"]),
            input_bindings=tuple(
                (
                    str(binding["input_name"]),
                    str(binding["source_instance_id"]),
                    str(binding["source_output"]),
                )
                for binding in item["input_bindings"]
            ),
            operations=(str(item["operation"]),),
            resource_tags=tuple(
                sorted((str(key), str(value)) for key, value in item["resource_tags"].items())
            ),
        )
        for item in accepted
    )
    plan = UniversalExecutionPlan(
        plan_digest=plan_digest,
        modules=modules,
        estimated_monthly_cost_state="not_resolved_by_worker",
    )
    return resolve_module_inputs(plan, instance_id, module_outputs, module_states)


def compile_universal_execution_plan(
    modules: list[ArchitectureModule], *, workspace_id: str, project_id: str, plan_digest: str
) -> UniversalExecutionPlan:
    """Compile dependency-ordered internal modules into bounded lifecycle work."""
    if not modules:
        raise ValueError("module graph must contain at least one module")
    if not workspace_id.strip() or not project_id.strip():
        raise ValueError("workspace and project identifiers are required")
    if not _PLAN_DIGEST_PATTERN.fullmatch(plan_digest):
        raise ValueError("plan digest must be a lowercase SHA-256 hex digest")
    type_counts: dict[str, int] = {}
    for module in modules:
        if not _MODULE_ID_PATTERN.fullmatch(module.identifier):
            raise ValueError("module graph contains an invalid module identifier")
        type_counts[module.identifier] = type_counts.get(module.identifier, 0) + 1

    instance_ids: list[str] = []
    for module in modules:
        instance_id = module.instance_id or module.identifier
        if type_counts[module.identifier] > 1 and module.instance_id is None:
            raise ValueError(
                f"module type {module.identifier} requires explicit instance identifiers when repeated"
            )
        if not _MODULE_ID_PATTERN.fullmatch(instance_id):
            raise ValueError("module graph contains an invalid instance identifier")
        instance_ids.append(instance_id)
        if len(module.depends_on) != len(set(module.depends_on)):
            raise ValueError(f"module {module.identifier} contains duplicate dependencies")
    if len(set(instance_ids)) != len(instance_ids):
        raise ValueError("module graph contains duplicate instance identifiers")
    instances_by_type: dict[str, list[str]] = {}
    for module, instance_id in zip(modules, instance_ids, strict=True):
        instances_by_type.setdefault(module.identifier, []).append(instance_id)
    known_instances = set(instance_ids)

    result: list[ModuleLifecycle] = []
    for module, instance_id in zip(modules, instance_ids, strict=True):
        dependencies: list[str] = []
        for dependency in module.depends_on:
            if dependency in known_instances:
                dependencies.append(dependency)
                continue
            matching_instances = instances_by_type.get(dependency, [])
            if len(matching_instances) == 1:
                dependencies.append(matching_instances[0])
                continue
            if len(matching_instances) > 1:
                raise ValueError(
                    f"module {module.identifier} has an ambiguous dependency on repeated module type {dependency}; use an instance identifier"
                )
            raise ValueError(
                f"module {module.identifier} depends on unknown module or instance: {dependency}"
            )
        if instance_id in dependencies:
            raise ValueError(f"module instance {instance_id} cannot depend on itself")
        if len(dependencies) != len(set(dependencies)):
            raise ValueError(f"module instance {instance_id} contains duplicate dependencies")
        target_ports = {item.name: item for item in module_ports(module.identifier).inputs}
        bound_inputs: set[str] = set()
        compiled_bindings: list[tuple[str, str, str]] = []
        for binding in module.input_bindings:
            if not _PORT_NAME_PATTERN.fullmatch(binding.input_name):
                raise ValueError("module input binding has an invalid input name")
            if not _MODULE_ID_PATTERN.fullmatch(binding.source_instance_id):
                raise ValueError("module input binding has an invalid source instance identifier")
            if not _PORT_NAME_PATTERN.fullmatch(binding.source_output):
                raise ValueError("module input binding has an invalid output name")
            if binding.input_name in bound_inputs:
                raise ValueError(f"module instance {instance_id} binds an input more than once")
            if binding.source_instance_id not in known_instances:
                raise ValueError(
                    f"module instance {instance_id} binds from an unknown source instance"
                )
            if binding.source_instance_id not in dependencies:
                raise ValueError(
                    f"module instance {instance_id} input binding source must be declared as a dependency"
                )
            source_module = next(
                item
                for item, source_instance in zip(modules, instance_ids, strict=True)
                if source_instance == binding.source_instance_id
            )
            source_ports = {
                item.name: item for item in module_ports(source_module.identifier).outputs
            }
            target_port = target_ports.get(binding.input_name)
            source_port = source_ports.get(binding.source_output)
            if target_port is None:
                raise ValueError(
                    f"module instance {instance_id} has no declared input {binding.input_name}"
                )
            if source_port is None:
                raise ValueError(
                    f"module instance {binding.source_instance_id} has no declared output {binding.source_output}"
                )
            if target_port.value_type != source_port.value_type:
                raise ValueError(
                    f"module input {binding.input_name} type does not match source output {binding.source_output}"
                )
            if target_port.secret_reference_only != source_port.secret_reference_only:
                raise ValueError(
                    "module secret references must connect only to secret-reference inputs"
                )
            compiled_bindings.append(
                (binding.input_name, binding.source_instance_id, binding.source_output)
            )
            bound_inputs.add(binding.input_name)
        unknown = set(dependencies) - known_instances
        if unknown:
            raise ValueError(
                f"module instance {instance_id} depends on unknown instances: {sorted(unknown)}"
            )
        result.append(
            ModuleLifecycle(
                module_id=module.identifier,
                instance_id=instance_id,
                dependencies=tuple(dependencies),
                input_bindings=tuple(compiled_bindings),
                resource_tags=(
                    ("ManagedBy", "davdeploy"),
                    ("DavDeployWorkspace", workspace_id),
                    ("DavDeployProject", project_id),
                    ("DavDeployPlan", plan_digest),
                    ("DavDeployModuleInstance", instance_id),
                ),
            )
        )
    canonical = "|".join(
        f"{item.instance_id}:{item.module_id}:{','.join(item.dependencies)}:{item.input_bindings}"
        for item in result
    )
    expected = sha256(canonical.encode()).hexdigest()
    # The caller-provided digest remains the authoritative approved artifact.
    return UniversalExecutionPlan(
        plan_digest=plan_digest,
        modules=tuple(result),
        estimated_monthly_cost_state=f"evidence-required:{expected[:12]}",
    )


def verify_cleanup(evidence: tuple[LifecycleEvidence, ...], plan: UniversalExecutionPlan) -> bool:
    """Require an independent ABSENT observation for every composed module."""
    return lifecycle_evidence_complete(plan, "verify_cleanup", evidence)
