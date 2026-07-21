from __future__ import annotations

from cloudblueprint.backend.models.architecture import InfrastructureArchitecture
from cloudblueprint.backend.models.relationships import Relationship, RelationshipType
from cloudblueprint.backend.models.resource import Resource, ResourceType
from cloudblueprint.backend.validators.base import Severity
from cloudblueprint.backend.validators.database import RdsPrivateSubnetRule
from cloudblueprint.backend.validators.dependency import ExplicitDependsOnCycleRule
from cloudblueprint.backend.validators.engine import ValidationEngine


def test_valid_example_has_no_blocking_validation_results(
    valid_architecture: InfrastructureArchitecture,
) -> None:
    engine = ValidationEngine()
    results = engine.validate(valid_architecture)

    assert results == []
    assert engine.has_blocking_errors(results) is False


def test_invalid_example_triggers_expected_rules(
    invalid_architecture: InfrastructureArchitecture,
) -> None:
    engine = ValidationEngine()
    results = engine.validate(invalid_architecture)
    rule_ids = {result.rule_id for result in results}

    assert {
        "REF001",
        "NET001",
        "NET002",
        "NET003",
        "NET004",
        "CMP001",
        "CMP002",
        "LB001",
        "DB001",
        "DB002",
        "DEP001",
    }.issubset(rule_ids)
    assert engine.has_blocking_errors(results) is True


def test_rds_requires_two_private_subnets_in_distinct_availability_zones() -> None:
    vpc = Resource(id="vpc", name="VPC", type=ResourceType.VPC)
    subnet = Resource(
        id="private_a",
        name="Private A",
        type=ResourceType.PRIVATE_SUBNET,
        properties={"availability_zone": "us-east-1a"},
    )
    database = Resource(id="db", name="DB", type=ResourceType.RDS_DATABASE)
    architecture = InfrastructureArchitecture(
        id="db-test",
        name="DB Test",
        resources={"vpc": vpc, "private_a": subnet, "db": database},
        relationships=[
            Relationship(source_id="private_a", target_id="vpc", type=RelationshipType.BELONGS_TO),
            Relationship(source_id="db", target_id="private_a", type=RelationshipType.BELONGS_TO),
        ],
    )

    results = ValidationEngine(rules=[RdsPrivateSubnetRule()]).validate(architecture)

    assert len(results) == 1
    assert results[0].rule_id == "DB001"
    assert results[0].severity == Severity.ERROR


def test_dependency_cycle_rule_ignores_non_depends_on_cycles() -> None:
    resource_a = Resource(id="a", name="A", type=ResourceType.VPC)
    resource_b = Resource(id="b", name="B", type=ResourceType.VPC)
    architecture = InfrastructureArchitecture(
        id="non-dep-cycle",
        name="Non Dependency Cycle",
        resources={"a": resource_a, "b": resource_b},
        relationships=[
            Relationship(source_id="a", target_id="b", type=RelationshipType.CONNECTS_TO),
            Relationship(source_id="b", target_id="a", type=RelationshipType.CONNECTS_TO),
        ],
    )

    results = ValidationEngine(rules=[ExplicitDependsOnCycleRule()]).validate(architecture)

    assert results == []


def test_public_subnet_requires_internet_gateway() -> None:
    from cloudblueprint.backend.validators.networking import PublicSubnetRequiresInternetGatewayRule
    vpc = Resource(id="vpc", name="VPC", type=ResourceType.VPC)
    subnet = Resource(
        id="public_a",
        name="Public A",
        type=ResourceType.PUBLIC_SUBNET,
        properties={"availability_zone": "us-east-1a"},
    )
    architecture = InfrastructureArchitecture(
        id="net-test",
        name="NET Test",
        resources={"vpc": vpc, "public_a": subnet},
        relationships=[
            Relationship(source_id="public_a", target_id="vpc", type=RelationshipType.BELONGS_TO),
        ],
    )

    results = ValidationEngine(rules=[PublicSubnetRequiresInternetGatewayRule()]).validate(architecture)

    assert len(results) == 1
    assert results[0].rule_id == "NET005"
    assert results[0].severity == Severity.ERROR


def test_subnet_belongs_to_vpc_rule() -> None:
    from cloudblueprint.backend.validators.networking import SubnetBelongsToVpcRule
    subnet = Resource(
        id="subnet_a",
        name="Subnet A",
        type=ResourceType.PUBLIC_SUBNET,
        properties={"cidr_block": "10.0.1.0/24"},
    )
    architecture = InfrastructureArchitecture(
        id="subnet-test",
        name="Subnet Test",
        resources={"subnet_a": subnet},
        relationships=[],
    )

    results = ValidationEngine(rules=[SubnetBelongsToVpcRule()]).validate(architecture)

    assert len(results) == 1
    assert results[0].rule_id == "NET001"
    assert results[0].severity == Severity.ERROR



