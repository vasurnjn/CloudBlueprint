from __future__ import annotations

from cloudblueprint.backend.models.architecture import InfrastructureArchitecture
from cloudblueprint.backend.models.graph import InfrastructureGraph
from cloudblueprint.backend.models.relationships import RelationshipType
from cloudblueprint.backend.models.resource import ResourceType
from cloudblueprint.backend.validators.base import Severity, ValidationResult, ValidationRule


class Ec2BelongsToSubnetRule(ValidationRule):
    rule_id = "CMP001"
    name = "EC2 belongs to subnet"
    description = "Every EC2 instance must belong to a subnet."
    severity = Severity.ERROR
    recommendation = "Add a BELONGS_TO relationship from the EC2 instance to a public or private subnet."

    def validate(
        self,
        architecture: InfrastructureArchitecture,
        graph: InfrastructureGraph,
    ) -> list[ValidationResult]:
        results: list[ValidationResult] = []
        for resource in architecture.resources.values():
            if resource.type != ResourceType.EC2_INSTANCE:
                continue
            subnets = [
                parent
                for parent in graph.get_parents(resource.id, RelationshipType.BELONGS_TO)
                if parent.type in {ResourceType.PUBLIC_SUBNET, ResourceType.PRIVATE_SUBNET}
            ]
            if not subnets:
                results.append(self.result(resource_id=resource.id))
        return results


class Ec2SecurityGroupRule(ValidationRule):
    rule_id = "CMP002"
    name = "EC2 uses Security Group"
    description = "EC2 instances should have at least one associated Security Group."
    severity = Severity.WARNING
    recommendation = "Add a USES_SECURITY_GROUP relationship from the EC2 instance to a Security Group."

    def validate(
        self,
        architecture: InfrastructureArchitecture,
        graph: InfrastructureGraph,
    ) -> list[ValidationResult]:
        results: list[ValidationResult] = []
        for resource in architecture.resources.values():
            if resource.type != ResourceType.EC2_INSTANCE:
                continue
            security_groups = [
                parent
                for parent in graph.get_parents(resource.id, RelationshipType.USES_SECURITY_GROUP)
                if parent.type == ResourceType.SECURITY_GROUP
            ]
            if not security_groups:
                results.append(self.result(resource_id=resource.id))
        return results

