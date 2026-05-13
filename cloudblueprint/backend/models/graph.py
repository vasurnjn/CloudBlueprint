from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from cloudblueprint.backend.models.architecture import InfrastructureArchitecture
from cloudblueprint.backend.models.relationships import Relationship, RelationshipType
from cloudblueprint.backend.models.resource import Resource


@dataclass(frozen=True)
class RelationshipReferenceIssue:
    relationship: Relationship
    missing_resource_id: str
    endpoint: str


class InfrastructureGraph:
    """Query helper around an infrastructure architecture's directed graph."""

    def __init__(self, architecture: InfrastructureArchitecture) -> None:
        self.architecture = architecture
        self._resources = architecture.resources
        self._relationships = list(architecture.relationships)
        self._outgoing: dict[str, list[Relationship]] = {}
        self._incoming: dict[str, list[Relationship]] = {}
        for relationship in self._relationships:
            self._outgoing.setdefault(relationship.source_id, []).append(relationship)
            self._incoming.setdefault(relationship.target_id, []).append(relationship)

    def get_resource(self, resource_id: str) -> Resource | None:
        return self._resources.get(resource_id)

    def all_resources(self) -> Iterable[Resource]:
        return self._resources.values()

    def get_relationships(
        self,
        resource_id: str | None = None,
        relationship_type: RelationshipType | None = None,
    ) -> list[Relationship]:
        relationships = self._relationships
        if resource_id is not None:
            relationships = [
                relationship
                for relationship in relationships
                if relationship.source_id == resource_id or relationship.target_id == resource_id
            ]
        if relationship_type is not None:
            relationships = [
                relationship
                for relationship in relationships
                if relationship.type == relationship_type
            ]
        return relationships

    def get_outgoing(
        self,
        resource_id: str,
        relationship_type: RelationshipType | None = None,
    ) -> list[Relationship]:
        relationships = list(self._outgoing.get(resource_id, []))
        if relationship_type is not None:
            relationships = [
                relationship
                for relationship in relationships
                if relationship.type == relationship_type
            ]
        return relationships

    def get_incoming(
        self,
        resource_id: str,
        relationship_type: RelationshipType | None = None,
    ) -> list[Relationship]:
        relationships = list(self._incoming.get(resource_id, []))
        if relationship_type is not None:
            relationships = [
                relationship
                for relationship in relationships
                if relationship.type == relationship_type
            ]
        return relationships

    def get_parents(
        self,
        resource_id: str,
        relationship_type: RelationshipType | None = None,
    ) -> list[Resource]:
        parents: list[Resource] = []
        for relationship in self.get_outgoing(resource_id, relationship_type):
            resource = self.get_resource(relationship.target_id)
            if resource is not None:
                parents.append(resource)
        return parents

    def get_children(
        self,
        resource_id: str,
        relationship_type: RelationshipType | None = None,
    ) -> list[Resource]:
        children: list[Resource] = []
        for relationship in self.get_incoming(resource_id, relationship_type):
            resource = self.get_resource(relationship.source_id)
            if resource is not None:
                children.append(resource)
        return children

    def validate_references(self) -> list[RelationshipReferenceIssue]:
        issues: list[RelationshipReferenceIssue] = []
        for relationship in self._relationships:
            if relationship.source_id not in self._resources:
                issues.append(
                    RelationshipReferenceIssue(
                        relationship=relationship,
                        missing_resource_id=relationship.source_id,
                        endpoint="source",
                    )
                )
            if relationship.target_id not in self._resources:
                issues.append(
                    RelationshipReferenceIssue(
                        relationship=relationship,
                        missing_resource_id=relationship.target_id,
                        endpoint="target",
                    )
                )
        return issues

    def has_path(
        self,
        source_id: str,
        target_id: str,
        relationship_type: RelationshipType | None = None,
    ) -> bool:
        if source_id not in self._resources or target_id not in self._resources:
            return False
        if source_id == target_id:
            return True

        visited: set[str] = set()
        stack = [source_id]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            for relationship in self.get_outgoing(current, relationship_type):
                if relationship.target_id == target_id:
                    return True
                if relationship.target_id not in visited:
                    stack.append(relationship.target_id)
        return False

    def detect_cycles(
        self,
        relationship_type: RelationshipType | None = None,
    ) -> list[list[str]]:
        adjacency: dict[str, list[str]] = {resource_id: [] for resource_id in self._resources}
        for relationship in self._relationships:
            if relationship_type is not None and relationship.type != relationship_type:
                continue
            if relationship.source_id in self._resources and relationship.target_id in self._resources:
                adjacency.setdefault(relationship.source_id, []).append(relationship.target_id)

        visiting: set[str] = set()
        visited: set[str] = set()
        stack: list[str] = []
        cycles: list[list[str]] = []
        seen_signatures: set[tuple[str, ...]] = set()

        def normalized_cycle(cycle: list[str]) -> tuple[str, ...]:
            without_repeat = cycle[:-1] if cycle and cycle[0] == cycle[-1] else cycle
            rotations = [
                tuple(without_repeat[index:] + without_repeat[:index])
                for index in range(len(without_repeat))
            ]
            return min(rotations)

        def visit(node: str) -> None:
            visiting.add(node)
            stack.append(node)
            for neighbor in adjacency.get(node, []):
                if neighbor in visiting:
                    start_index = stack.index(neighbor)
                    cycle = stack[start_index:] + [neighbor]
                    signature = normalized_cycle(cycle)
                    if signature not in seen_signatures:
                        seen_signatures.add(signature)
                        cycles.append(cycle)
                elif neighbor not in visited:
                    visit(neighbor)
            stack.pop()
            visiting.remove(node)
            visited.add(node)

        for resource_id in adjacency:
            if resource_id not in visited:
                visit(resource_id)

        return cycles

