from __future__ import annotations

import pytest

from cloudblueprint.backend.models.architecture import InfrastructureArchitecture
from cloudblueprint.backend.models.relationships import Relationship, RelationshipType
from cloudblueprint.backend.models.resource import Resource, ResourceType


def test_resource_creation() -> None:
    resource = Resource(
        id="vpc_main",
        name="Main VPC",
        type=ResourceType.VPC,
        properties={"cidr_block": "10.0.0.0/16"},
        tags={"Environment": "test"},
    )

    assert resource.id == "vpc_main"
    assert resource.type == ResourceType.VPC
    assert resource.properties["cidr_block"] == "10.0.0.0/16"


def test_architecture_creation_and_relationship_handling() -> None:
    vpc = Resource(id="vpc", name="VPC", type=ResourceType.VPC)
    subnet = Resource(id="subnet", name="Subnet", type=ResourceType.PUBLIC_SUBNET)
    architecture = InfrastructureArchitecture(
        id="arch",
        name="Architecture",
        resources={"vpc": vpc, "subnet": subnet},
    )

    architecture.add_relationship(
        Relationship(
            source_id="subnet",
            target_id="vpc",
            type=RelationshipType.BELONGS_TO,
        )
    )

    assert len(architecture.resources) == 2
    assert architecture.relationships[0].source_id == "subnet"


def test_architecture_rejects_resource_key_mismatch() -> None:
    with pytest.raises(ValueError, match="resource dictionary keys must match"):
        InfrastructureArchitecture(
            id="arch",
            name="Architecture",
            resources={
                "wrong_key": Resource(
                    id="vpc",
                    name="VPC",
                    type=ResourceType.VPC,
                )
            },
        )


def test_duplicate_resource_add_is_rejected() -> None:
    resource = Resource(id="vpc", name="VPC", type=ResourceType.VPC)
    architecture = InfrastructureArchitecture(
        id="arch",
        name="Architecture",
        resources={"vpc": resource},
    )

    with pytest.raises(ValueError, match="already exists"):
        architecture.add_resource(resource)

