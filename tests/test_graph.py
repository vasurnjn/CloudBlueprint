from __future__ import annotations

from cloudblueprint.backend.models.architecture import InfrastructureArchitecture
from cloudblueprint.backend.models.graph import InfrastructureGraph
from cloudblueprint.backend.models.relationships import Relationship, RelationshipType
from cloudblueprint.backend.models.resource import Resource, ResourceType


def test_graph_retrieves_resources_and_relationships(valid_architecture: InfrastructureArchitecture) -> None:
    graph = InfrastructureGraph(valid_architecture)

    assert graph.get_resource("vpc_main").type == ResourceType.VPC
    assert len(graph.get_relationships("alb_public", RelationshipType.CONNECTS_TO)) == 2


def test_graph_finds_parents_and_children(valid_architecture: InfrastructureArchitecture) -> None:
    graph = InfrastructureGraph(valid_architecture)

    parents = graph.get_parents("private_subnet_a", RelationshipType.BELONGS_TO)
    children = graph.get_children("vpc_main", RelationshipType.BELONGS_TO)

    assert [parent.id for parent in parents] == ["vpc_main"]
    assert "private_subnet_a" in {child.id for child in children}


def test_graph_validates_missing_references(invalid_architecture: InfrastructureArchitecture) -> None:
    graph = InfrastructureGraph(invalid_architecture)

    issues = graph.validate_references()

    assert len(issues) == 1
    assert issues[0].missing_resource_id == "missing_ec2"
    assert issues[0].endpoint == "target"


def test_graph_detects_paths(valid_architecture: InfrastructureArchitecture) -> None:
    graph = InfrastructureGraph(valid_architecture)

    assert graph.has_path("ec2_app", "vpc_main") is True
    assert graph.has_path("alb_public", "ec2_app", RelationshipType.TARGETS) is True
    assert graph.has_path("vpc_main", "ec2_app") is False


def test_graph_detects_depends_on_cycles_only_when_requested(
    invalid_architecture: InfrastructureArchitecture,
) -> None:
    graph = InfrastructureGraph(invalid_architecture)

    cycles = graph.detect_cycles(RelationshipType.DEPENDS_ON)

    assert cycles
    assert {"ec2_bad", "alb_bad"}.issubset(set(cycles[0]))


def test_non_dependency_relationship_cycle_is_not_a_depends_on_cycle() -> None:
    resource_a = Resource(id="resource_a", name="A", type=ResourceType.VPC)
    resource_b = Resource(id="resource_b", name="B", type=ResourceType.VPC)
    architecture = InfrastructureArchitecture(
        id="cycle",
        name="Non Dependency Cycle",
        resources={"resource_a": resource_a, "resource_b": resource_b},
        relationships=[
            Relationship(
                source_id="resource_a",
                target_id="resource_b",
                type=RelationshipType.CONNECTS_TO,
            ),
            Relationship(
                source_id="resource_b",
                target_id="resource_a",
                type=RelationshipType.CONNECTS_TO,
            ),
        ],
    )
    graph = InfrastructureGraph(architecture)

    assert graph.detect_cycles(RelationshipType.DEPENDS_ON) == []
    assert graph.detect_cycles(RelationshipType.CONNECTS_TO)

