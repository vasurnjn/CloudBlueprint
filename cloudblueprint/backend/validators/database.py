from __future__ import annotations

from cloudblueprint.backend.models.architecture import InfrastructureArchitecture
from cloudblueprint.backend.models.graph import InfrastructureGraph
from cloudblueprint.backend.models.relationships import RelationshipType
from cloudblueprint.backend.models.resource import ResourceType
from cloudblueprint.backend.validators.base import Severity, ValidationResult, ValidationRule


class RdsPrivateSubnetRule(ValidationRule):
    rule_id = "DB001"
    name = "RDS belongs to private subnets"
    description = "RDS databases must belong to private subnets."
    severity = Severity.ERROR
    recommendation = (
        "Add BELONGS_TO relationships from the RDS database to at least two "
        "PRIVATE_SUBNET resources in distinct Availability Zones."
    )

    def validate(
        self,
        architecture: InfrastructureArchitecture,
        graph: InfrastructureGraph,
    ) -> list[ValidationResult]:
        results: list[ValidationResult] = []
        for database in architecture.resources.values():
            if database.type != ResourceType.RDS_DATABASE:
                continue
            private_subnets = [
                parent
                for parent in graph.get_parents(database.id, RelationshipType.BELONGS_TO)
                if parent.type == ResourceType.PRIVATE_SUBNET
            ]
            availability_zones = {
                str(subnet.properties.get("availability_zone"))
                for subnet in private_subnets
                if subnet.properties.get("availability_zone")
            }
            if len(private_subnets) < 2:
                results.append(
                    self.result(
                        resource_id=database.id,
                        description=(
                            f"RDS database '{database.id}' must belong to at least "
                            "two private subnets so a DB subnet group can be generated."
                        ),
                    )
                )
            elif len(availability_zones) < 2:
                results.append(
                    self.result(
                        resource_id=database.id,
                        description=(
                            f"RDS database '{database.id}' private subnets must be "
                            "in at least two distinct Availability Zones."
                        ),
                    )
                )
        return results


class RdsPublicExposureRule(ValidationRule):
    rule_id = "DB002"
    name = "RDS is not publicly exposed"
    description = "RDS databases should not be directly publicly accessible by default."
    severity = Severity.WARNING
    recommendation = "Set publicly_accessible to false and place the RDS database in private subnets."

    def validate(
        self,
        architecture: InfrastructureArchitecture,
        graph: InfrastructureGraph,
    ) -> list[ValidationResult]:
        del graph
        results: list[ValidationResult] = []
        for database in architecture.resources.values():
            if database.type != ResourceType.RDS_DATABASE:
                continue
            if database.properties.get("publicly_accessible") is True:
                results.append(self.result(resource_id=database.id))
        return results

