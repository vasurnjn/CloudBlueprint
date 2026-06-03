from __future__ import annotations

from pathlib import Path

import pytest

from cloudblueprint.backend.models.architecture import InfrastructureArchitecture


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_example(name: str) -> InfrastructureArchitecture:
    path = PROJECT_ROOT / "examples" / name
    return InfrastructureArchitecture.model_validate_json(path.read_text(encoding="utf-8"))


@pytest.fixture
def valid_architecture() -> InfrastructureArchitecture:
    return load_example("valid_architecture.json")


@pytest.fixture
def invalid_architecture() -> InfrastructureArchitecture:
    return load_example("invalid_architecture.json")

