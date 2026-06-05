from __future__ import annotations

from dataclasses import dataclass

from cloudblueprint.backend.generators.terraform.files import TerraformGenerationResult
from cloudblueprint.backend.models.architecture import InfrastructureArchitecture


@dataclass(frozen=True)
class ArchitectureRecord:
    id: str
    name: str
    architecture: InfrastructureArchitecture
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class TerraformGenerationRecord:
    id: str
    architecture_id: str
    result: TerraformGenerationResult
    created_at: str

