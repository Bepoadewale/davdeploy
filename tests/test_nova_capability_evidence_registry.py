from __future__ import annotations

import re
from pathlib import Path

from davdeploy.certification_factory import certification_scenarios
from davdeploy.module_catalogue import known_modules

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md"
BINDING_DOC = ROOT / "docs/product/NOVA_CATALOGUE_ROOT_BINDING.md"
ARCHITECTURE_HEADING = "## Architecture catalogue: all 26 entries"
IMPLEMENTATION_HEADING = "## Terraform implementation registry: all 30 roots"
GAPS_HEADING = "## Explicit coverage gaps"


def _table_rows(path: Path, start: str, end: str) -> list[list[str]]:
    document = path.read_text(encoding="utf-8")
    section = document.split(start, maxsplit=1)[1].split(end, maxsplit=1)[0]
    rows = []
    for line in section.splitlines():
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if cells and cells[0].startswith("`"):
            rows.append(cells)
    return rows


def _identifiers(cell: str) -> set[str]:
    return set(re.findall(r"`([^`]+)`", cell))


def _architecture_rows() -> list[list[str]]:
    return _table_rows(MATRIX, ARCHITECTURE_HEADING, IMPLEMENTATION_HEADING)


def _implementation_rows() -> list[list[str]]:
    return _table_rows(MATRIX, IMPLEMENTATION_HEADING, GAPS_HEADING)


def test_architecture_rows_match_catalogue_and_certification_scenarios() -> None:
    rows = _architecture_rows()
    architecture_ids = {row[0].strip("`") for row in rows}
    scenario_ids = {scenario.identifier for scenario in certification_scenarios()}
    scenarios_by_module = {
        module_id: {
            scenario.identifier
            for scenario in certification_scenarios()
            if module_id in scenario.modules
        }
        for module_id in architecture_ids
    }

    assert len(rows) == 26
    assert len(architecture_ids) == len(rows)
    assert architecture_ids == set(known_modules())

    for row in rows:
        module_id = row[0].strip("`")
        scenario_references = _identifiers(row[1])
        assert scenario_references <= scenario_ids
        assert scenario_references == scenarios_by_module[module_id]


def test_implementation_registry_covers_roots_and_support_modules() -> None:
    rows = _implementation_rows()
    implementation_ids = {row[0].strip("`") for row in rows}
    relative_paths = {row[1].strip("`") for row in rows}
    modules_directory = ROOT / "infrastructure/terraform/modules"
    actual_module_directories = {
        path.name for path in modules_directory.iterdir() if (path / "main.tf").is_file()
    }
    support_rows = _table_rows(
        BINDING_DOC,
        "## Terraform module directories outside the workload registry",
        "## Acceptance",
    )
    support_paths = {row[0].strip("`") for row in support_rows}
    support_directory_names = {
        path.removeprefix("modules/") for path in support_paths
    }
    registered_directory_names = {
        path.removeprefix("modules/") for path in relative_paths
    }

    assert len(rows) == 30
    assert len(implementation_ids) == len(rows)
    assert len(relative_paths) == len(rows)
    assert registered_directory_names.isdisjoint(support_directory_names)
    assert registered_directory_names | support_directory_names == actual_module_directories
    for relative_path in relative_paths:
        assert relative_path.startswith("modules/")
        assert (ROOT / "infrastructure/terraform" / relative_path / "main.tf").is_file()


def test_candidate_module_and_root_references_are_known_and_symmetric() -> None:
    architecture_rows = _architecture_rows()
    implementation_rows = _implementation_rows()
    architecture_ids = {row[0].strip("`") for row in architecture_rows}
    implementation_ids = {row[0].strip("`") for row in implementation_rows}
    scenario_ids = {scenario.identifier for scenario in certification_scenarios()}

    architecture_to_roots: dict[str, set[str]] = {}
    for row in architecture_rows:
        module_id = row[0].strip("`")
        candidates = _identifiers(row[2])
        assert candidates <= implementation_ids
        architecture_to_roots[module_id] = candidates

    root_to_architecture: dict[str, set[str]] = {}
    for row in implementation_rows:
        root_id = row[0].strip("`")
        references = _identifiers(row[2])
        architecture_candidates = references & architecture_ids
        scenario_references = references & scenario_ids
        assert references == architecture_candidates | scenario_references
        root_to_architecture[root_id] = architecture_candidates

    assert {
        (module_id, root_id)
        for module_id, roots in architecture_to_roots.items()
        for root_id in roots
    } == {
        (module_id, root_id)
        for root_id, modules in root_to_architecture.items()
        for module_id in modules
    }
