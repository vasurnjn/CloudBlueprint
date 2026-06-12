from __future__ import annotations

import pytest

from cloudblueprint.backend.database.repository import (
    SQLiteArchitectureRepository,
    SQLiteTerraformGenerationRepository,
)
from cloudblueprint.backend.models.architecture import InfrastructureArchitecture
from cloudblueprint.backend.models.relationships import Relationship, RelationshipType
from cloudblueprint.backend.models.resource import Resource, ResourceType
from cloudblueprint.backend.services.architecture_service import ArchitectureService
from cloudblueprint.backend.services.exceptions import BadRequestError, ConflictError
from cloudblueprint.backend.services.terraform_service import TerraformService
from cloudblueprint.backend.services.validation_service import ValidationService


def test_architecture_service_persists_across_instances(tmp_path) -> None:
    database_path = tmp_path / "service.sqlite"
    architecture = InfrastructureArchitecture(id="arch", name="Architecture")

    first_service = ArchitectureService(SQLiteArchitectureRepository(database_path))
    first_service.create_architecture(architecture)

    second_service = ArchitectureService(SQLiteArchitectureRepository(database_path))
    loaded = second_service.get_architecture("arch")

    assert loaded.architecture == architecture


def test_resource_operations_update_persisted_architecture(tmp_path) -> None:
    service = ArchitectureService(
        SQLiteArchitectureRepository(tmp_path / "resources.sqlite")
    )
    service.create_architecture(
        InfrastructureArchitecture(id="arch", name="Architecture")
    )

    vpc = Resource(id="vpc", name="VPC", type=ResourceType.VPC)
    service.add_resource("arch", vpc)

    renamed_vpc = Resource(id="vpc", name="Renamed VPC", type=ResourceType.VPC)
    updated = service.update_resource("arch", "vpc", renamed_vpc)

    assert updated.architecture.resources["vpc"].name == "Renamed VPC"

    with pytest.raises(ConflictError):
        service.add_resource("arch", renamed_vpc)

    service.delete_resource("arch", "vpc")

    assert service.get_architecture("arch").architecture.resources == {}


def test_relationship_operations_update_persisted_architecture(tmp_path) -> None:
    service = ArchitectureService(
        SQLiteArchitectureRepository(tmp_path / "relationships.sqlite")
    )
    architecture = InfrastructureArchitecture(
        id="arch",
        name="Architecture",
        resources={
            "vpc": Resource(id="vpc", name="VPC", type=ResourceType.VPC),
            "subnet": Resource(
                id="subnet",
                name="Subnet",
                type=ResourceType.PUBLIC_SUBNET,
            ),
        },
    )
    service.create_architecture(architecture)

    relationship = Relationship(
        source_id="subnet",
        target_id="vpc",
        type=RelationshipType.BELONGS_TO,
    )
    updated = service.add_relationship("arch", relationship)

    assert updated.architecture.relationships == [relationship]

    with pytest.raises(ConflictError):
        service.add_relationship("arch", relationship)

    with pytest.raises(BadRequestError):
        service.add_relationship(
            "arch",
            Relationship(
                source_id="missing",
                target_id="vpc",
                type=RelationshipType.BELONGS_TO,
            ),
        )

    service.delete_relationship("arch", relationship)

    assert service.get_architecture("arch").architecture.relationships == []


def test_validation_and_terraform_services_use_persistence(
    tmp_path,
    valid_architecture: InfrastructureArchitecture,
) -> None:
    database_path = tmp_path / "workflow.sqlite"
    architecture_repository = SQLiteArchitectureRepository(database_path)
    architecture_service = ArchitectureService(architecture_repository)
    validation_service = ValidationService(architecture_repository)
    terraform_service = TerraformService(
        architecture_repository,
        SQLiteTerraformGenerationRepository(database_path),
    )

    architecture_service.create_architecture(valid_architecture)

    validation_report = validation_service.validate_architecture(valid_architecture.id)
    generation_record = terraform_service.generate_terraform(valid_architecture.id)
    latest_generation = terraform_service.get_latest_terraform(valid_architecture.id)

    assert validation_report.is_valid is True
    assert generation_record.id == latest_generation.id
    assert "network.tf" in generation_record.result.as_dict()

