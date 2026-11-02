from pathlib import Path

from davdeploy.module_implementations import module_implementations


def test_module_implementations_are_unique_disabled_and_backed_by_roots() -> None:
    implementations = module_implementations()
    identifiers = [implementation.identifier for implementation in implementations]

    assert len(implementations) == 30
    assert len(identifiers) == len(set(identifiers))
    assert all(not implementation.enabled for implementation in implementations)

    repository_root = Path(__file__).resolve().parents[1]
    for implementation in implementations:
        assert (repository_root / "infrastructure" / "terraform" / implementation.terraform_root / "main.tf").is_file()
