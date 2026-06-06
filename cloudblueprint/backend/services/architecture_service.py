from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from cloudblueprint.backend.database.models import ArchitectureRecord
from cloudblueprint.backend.database.repository import (
    DuplicateRecordError,
    SQLiteArchitectureRepository,
)
from cloudblueprint.backend.models.architecture import InfrastructureArchitecture
from cloudblueprint.backend.models.relationships import Relationship
from cloudblueprint.backend.models.resource import Resource
from cloudblueprint.backend.services.exceptions import (
    BadRequestError,
    ConflictError,
    NotFoundError,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class ArchitectureService:
    def __init__(
        self,
        repository: SQLiteArchitectureRepository,
        *,
        examples_directory: str | Path | None = None,
    ) -> None:
        self.repository = repository
        self.examples_directory = (
            Path(examples_directory)
            if examples_directory is not None
            else PROJECT_ROOT / "examples"
        )

    def create_architecture(
        self,
        architecture: InfrastructureArchitecture,
    ) -> ArchitectureRecord:
        try:
            return self.repository.create(architecture)
        except DuplicateRecordError as error:
            raise ConflictError(f"architecture '{architecture.id}' already exists") from error

    def list_architectures(self) -> list[ArchitectureRecord]:
        return self.repository.list()

    def get_architecture(self, architecture_id: str) -> ArchitectureRecord:
        record = self.repository.get(architecture_id)
        if record is None:
            raise NotFoundError(f"architecture '{architecture_id}' was not found")
        return record

    def update_architecture(
        self,
        architecture_id: str,
        architecture: InfrastructureArchitecture,
    ) -> ArchitectureRecord:
        if architecture.id != architecture_id:
            raise BadRequestError("architecture id in the path must match the request body")

        updated = self.repository.update(architecture)
        if updated is None:
            raise NotFoundError(f"architecture '{architecture_id}' was not found")
        return updated

    def delete_architecture(self, architecture_id: str) -> None:
        if not self.repository.delete(architecture_id):
            raise NotFoundError(f"architecture '{architecture_id}' was not found")

    def add_resource(
        self,
        architecture_id: str,
        resource: Resource,
    ) -> ArchitectureRecord:
        architecture = self.get_architecture(architecture_id).architecture
        if resource.id in architecture.resources:
            raise ConflictError(f"resource '{resource.id}' already exists")

        architecture.add_resource(resource)
        return self._persist_existing(architecture)

    def update_resource(
        self,
        architecture_id: str,
        resource_id: str,
        resource: Resource,
    ) -> ArchitectureRecord:
        if resource.id != resource_id:
            raise BadRequestError("resource id in the path must match the request body")

        architecture = self.get_architecture(architecture_id).architecture
        if resource_id not in architecture.resources:
            raise NotFoundError(f"resource '{resource_id}' was not found")

        architecture.resources[resource_id] = resource
        return self._persist_existing(architecture)

    def delete_resource(self, architecture_id: str, resource_id: str) -> None:
        architecture = self.get_architecture(architecture_id).architecture
        if resource_id not in architecture.resources:
            raise NotFoundError(f"resource '{resource_id}' was not found")

        del architecture.resources[resource_id]
        architecture.relationships = [
            relationship
            for relationship in architecture.relationships
            if relationship.source_id != resource_id and relationship.target_id != resource_id
        ]
        self._persist_existing(architecture)

    def add_relationship(
        self,
        architecture_id: str,
        relationship: Relationship,
    ) -> ArchitectureRecord:
        architecture = self.get_architecture(architecture_id).architecture
        missing_ids = [
            resource_id
            for resource_id in (relationship.source_id, relationship.target_id)
            if resource_id not in architecture.resources
        ]
        if missing_ids:
            missing_text = ", ".join(sorted(set(missing_ids)))
            raise BadRequestError(f"relationship references missing resource(s): {missing_text}")
        if relationship in architecture.relationships:
            raise ConflictError(
                "relationship already exists: "
                f"{relationship.source_id} {relationship.type.value} {relationship.target_id}"
            )

        architecture.add_relationship(relationship)
        return self._persist_existing(architecture)

    def delete_relationship(
        self,
        architecture_id: str,
        relationship: Relationship,
    ) -> None:
        architecture = self.get_architecture(architecture_id).architecture
        try:
            architecture.relationships.remove(relationship)
        except ValueError as error:
            raise NotFoundError(
                "relationship was not found: "
                f"{relationship.source_id} {relationship.type.value} {relationship.target_id}"
            ) from error
        self._persist_existing(architecture)

    def load_example(self, example_name: str) -> tuple[ArchitectureRecord, bool]:
        if example_name not in {"valid", "invalid"}:
            raise BadRequestError("example name must be 'valid' or 'invalid'")

        path = self.examples_directory / f"{example_name}_architecture.json"
        try:
            architecture = InfrastructureArchitecture.model_validate_json(
                path.read_text(encoding="utf-8")
            )
        except FileNotFoundError as error:
            raise NotFoundError(f"example architecture '{example_name}' was not found") from error
        except ValidationError as error:
            raise BadRequestError(f"example architecture '{example_name}' is invalid") from error

        return self.repository.upsert(architecture)

    def _persist_existing(self, architecture: InfrastructureArchitecture) -> ArchitectureRecord:
        updated = self.repository.update(architecture)
        if updated is None:
            raise NotFoundError(f"architecture '{architecture.id}' was not found")
        return updated

