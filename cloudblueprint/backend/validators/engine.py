from __future__ import annotations

from collections.abc import Sequence

from cloudblueprint.backend.models.architecture import InfrastructureArchitecture
from cloudblueprint.backend.models.graph import InfrastructureGraph
from cloudblueprint.backend.validators.base import Severity, ValidationResult, ValidationRule
from cloudblueprint.backend.validators.compute import (
    Ec2BelongsToSubnetRule,
    Ec2SecurityGroupRule,
)
from cloudblueprint.backend.validators.database import (
    RdsPrivateSubnetRule,
    RdsPublicExposureRule,
)
from cloudblueprint.backend.validators.dependency import (
    ExplicitDependsOnCycleRule,
    ReferenceIntegrityRule,
)
from cloudblueprint.backend.validators.loadbalancing import LoadBalancerTargetsRule
from cloudblueprint.backend.validators.networking import (
    InternetFacingNetworkingRule,
    InternetGatewayAttachedToVpcRule,
    PublicSubnetRequiresInternetGatewayRule,
    SecurityGroupBelongsToVpcRule,
    SubnetBelongsToVpcRule,
)


def default_rules() -> list[ValidationRule]:
    return [
        SubnetBelongsToVpcRule(),
        InternetGatewayAttachedToVpcRule(),
        InternetFacingNetworkingRule(),
        SecurityGroupBelongsToVpcRule(),
        PublicSubnetRequiresInternetGatewayRule(),
        Ec2BelongsToSubnetRule(),
        Ec2SecurityGroupRule(),
        LoadBalancerTargetsRule(),
        RdsPrivateSubnetRule(),
        RdsPublicExposureRule(),
        ExplicitDependsOnCycleRule(),
    ]


class ValidationEngine:
    """Runs reference integrity checks and registered validation rules."""

    def __init__(self, rules: Sequence[ValidationRule] | None = None) -> None:
        self.reference_rule = ReferenceIntegrityRule()
        self.rules = list(rules) if rules is not None else default_rules()

    def validate(
        self,
        architecture: InfrastructureArchitecture,
        graph: InfrastructureGraph | None = None,
    ) -> list[ValidationResult]:
        graph = graph or InfrastructureGraph(architecture)
        results = self.reference_rule.validate(architecture, graph)
        for rule in self.rules:
            results.extend(rule.validate(architecture, graph))
        return results

    @staticmethod
    def has_blocking_errors(results: Sequence[ValidationResult]) -> bool:
        return any(
            result.severity in {Severity.ERROR, Severity.CRITICAL}
            for result in results
        )
