from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from cloudblueprint.backend.database.models import (
    ArchitectureRecord,
    TerraformGenerationRecord,
)
from cloudblueprint.backend.generators.terraform.files import TerraformFile
from cloudblueprint.backend.models.architecture import InfrastructureArchitecture
from cloudblueprint.backend.models.relationships import Relationship
from cloudblueprint.backend.models.resource import Resource
from cloudblueprint.backend.services.validation_service import ValidationReport
from cloudblueprint.backend.validators.base import ValidationResult


class HealthResponse(BaseModel):
    status: str


ArchitectureRequest = InfrastructureArchitecture
ResourceRequest = Resource
RelationshipRequest = Relationship


class ArchitectureResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    resources: dict[str, Resource]
    relationships: list[Relationship]
    created_at: str
    updated_at: str

    @classmethod
    def from_record(cls, record: ArchitectureRecord) -> ArchitectureResponse:
        architecture = record.architecture
        return cls(
            id=architecture.id,
            name=architecture.name,
            resources=architecture.resources,
            relationships=architecture.relationships,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )


class ValidationReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    architecture_id: str
    is_valid: bool
    results: list[ValidationResult]

    @classmethod
    def from_report(cls, report: ValidationReport) -> ValidationReportResponse:
        return cls(
            architecture_id=report.architecture_id,
            is_valid=report.is_valid,
            results=report.results,
        )


class TerraformGenerationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    architecture_id: str
    files: list[TerraformFile]
    created_at: str

    @classmethod
    def from_record(cls, record: TerraformGenerationRecord) -> TerraformGenerationResponse:
        return cls(
            id=record.id,
            architecture_id=record.architecture_id,
            files=record.result.files,
            created_at=record.created_at,
        )

