from __future__ import annotations

from cloudblueprint.backend.models.architecture import InfrastructureArchitecture
from cloudblueprint.backend.models.graph import InfrastructureGraph
from cloudblueprint.backend.models.relationships import RelationshipType
from cloudblueprint.backend.models.resource import ResourceType
from cloudblueprint.backend.validators.base import Severity, ValidationResult, ValidationRule


class LoadBalancerTargetsRule(ValidationRule):
    rule_id = "LB001"
    name = "Load Balancer has valid backend targets"
    description = "Application Load Balancers must target at least one EC2 instance."
    severity = Severity.ERROR
    recommendation = "Add a TARGETS relationship from the load balancer to one or more EC2 instances."

    def validate(
        self,
        architecture: InfrastructureArchitecture,
        graph: InfrastructureGraph,
    ) -> list[ValidationResult]:
        results: list[ValidationResult] = []
        for resource in architecture.resources.values():
            if resource.type != ResourceType.APPLICATION_LOAD_BALANCER:
                continue
            targets = [
                parent
                for parent in graph.get_parents(resource.id, RelationshipType.TARGETS)
                if parent.type == ResourceType.EC2_INSTANCE
            ]
            if not targets:
                results.append(self.result(resource_id=resource.id))
        return results

