from davdeploy.domain import ProjectRequest
from pydantic import ValidationError


def test_project_request_accepts_a_customer_facing_name() -> None:
    request = ProjectRequest(name="French Pattern Cramming")

    assert request.name == "French Pattern Cramming"


def test_project_request_rejects_unsafe_or_blank_names() -> None:
    for name in ("  French Pattern Cramming", "French Pattern Cramming!", "a", "a" * 65):
        try:
            ProjectRequest(name=name)
        except ValidationError:
            continue
        raise AssertionError(f"Expected {name!r} to be rejected")
