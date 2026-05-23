from __future__ import annotations

from cloudblueprint.backend.models.architecture import InfrastructureArchitecture
from cloudblueprint.backend.models.graph import InfrastructureGraph
from cloudblueprint.backend.models.relationships import RelationshipType
from cloudblueprint.backend.validators.base import Severity, ValidationResult, ValidationRule


class ReferenceIntegrityRule(ValidationRule):
    rule_id = "REF001"
    name = "Relationship references must exist"
    description = "Relationship endpoints must refer to existing resources."
    severity = Severity.ERROR
    recommendation = "Update the relationship to reference an existing resource, or create the missing resource."

    def validate(
        self,
        architecture: InfrastructureArchitecture,
        graph: InfrastructureGraph,
    ) -> list[ValidationResult]:
        del architecture
        results: list[ValidationResult] = []
        for issue in graph.validate_references():
            relationship = issue.relationship
            results.append(
                self.result(
                    resource_id=issue.missing_resource_id,
                    description=(
                        f"Relationship {relationship.source_id} "
                        f"{relationship.type.value} {relationship.target_id} "
                        f"references missing {issue.endpoint} resource "
                        f"'{issue.missing_resource_id}'."
                    ),
                )
            )
        return results


class ExplicitDependsOnCycleRule(ValidationRule):
    rule_id = "DEP001"
    name = "Explicit dependency cycle"
    description = "Explicit DEPENDS_ON relationships must not form cycles."
    severity = Severity.ERROR
    recommendation = "Remove or reverse one of the DEPENDS_ON relationships in the cycle."

    def validate(
        self,
        architecture: InfrastructureArchitecture,
        graph: InfrastructureGraph,
    ) -> list[ValidationResult]:
        del architecture
        results: list[ValidationResult] = []
        for cycle in graph.detect_cycles(RelationshipType.DEPENDS_ON):
            cycle_text = " -> ".join(cycle)
            results.append(
                self.result(
                    resource_id=cycle[0] if cycle else None,
                    description=f"Explicit DEPENDS_ON cycle detected: {cycle_text}.",
                )
            )
        return results

