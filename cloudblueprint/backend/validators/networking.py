from __future__ import annotations

from cloudblueprint.backend.models.architecture import InfrastructureArchitecture
from cloudblueprint.backend.models.graph import InfrastructureGraph
from cloudblueprint.backend.models.relationships import RelationshipType
from cloudblueprint.backend.models.resource import Resource, ResourceType
from cloudblueprint.backend.validators.base import Severity, ValidationResult, ValidationRule


def _resources_of_type(
    architecture: InfrastructureArchitecture,
    *resource_types: ResourceType,
) -> list[Resource]:
    wanted = set(resource_types)
    return [resource for resource in architecture.resources.values() if resource.type in wanted]


class SubnetBelongsToVpcRule(ValidationRule):
    rule_id = "NET001"
    name = "Subnet belongs to VPC"
    description = "Every subnet must belong to a VPC."
    severity = Severity.ERROR
    recommendation = "Add a BELONGS_TO relationship from the subnet to a VPC."

    def validate(
        self,
        architecture: InfrastructureArchitecture,
        graph: InfrastructureGraph,
    ) -> list[ValidationResult]:
        results: list[ValidationResult] = []
        for subnet in _resources_of_type(
            architecture,
            ResourceType.PUBLIC_SUBNET,
            ResourceType.PRIVATE_SUBNET,
        ):
            vpcs = [
                parent
                for parent in graph.get_parents(subnet.id, RelationshipType.BELONGS_TO)
                if parent.type == ResourceType.VPC
            ]
            if not vpcs:
                results.append(self.result(resource_id=subnet.id))
        return results


class InternetGatewayAttachedToVpcRule(ValidationRule):
    rule_id = "NET002"
    name = "Internet Gateway attaches to VPC"
    description = "Every Internet Gateway must attach to a VPC."
    severity = Severity.ERROR
    recommendation = "Add an ATTACHES_TO relationship from the Internet Gateway to a VPC."

    def validate(
        self,
        architecture: InfrastructureArchitecture,
        graph: InfrastructureGraph,
    ) -> list[ValidationResult]:
        results: list[ValidationResult] = []
        for gateway in _resources_of_type(architecture, ResourceType.INTERNET_GATEWAY):
            vpcs = [
                parent
                for parent in graph.get_parents(gateway.id, RelationshipType.ATTACHES_TO)
                if parent.type == ResourceType.VPC
            ]
            if not vpcs:
                results.append(self.result(resource_id=gateway.id))
        return results


class InternetFacingNetworkingRule(ValidationRule):
    rule_id = "NET003"
    name = "Internet-facing resources use public networking"
    description = "Internet-facing resources must use valid public networking configuration."
    severity = Severity.ERROR
    recommendation = (
        "Connect internet-facing load balancers to at least two public subnets "
        "in distinct Availability Zones, and place public EC2 instances in a public subnet."
    )

    def validate(
        self,
        architecture: InfrastructureArchitecture,
        graph: InfrastructureGraph,
    ) -> list[ValidationResult]:
        results: list[ValidationResult] = []
        results.extend(self._validate_load_balancers(architecture, graph))
        results.extend(self._validate_public_ec2_instances(architecture, graph))
        return results

    def _validate_load_balancers(
        self,
        architecture: InfrastructureArchitecture,
        graph: InfrastructureGraph,
    ) -> list[ValidationResult]:
        results: list[ValidationResult] = []
        for load_balancer in _resources_of_type(
            architecture,
            ResourceType.APPLICATION_LOAD_BALANCER,
        ):
            if not self._is_internet_facing(load_balancer):
                continue

            connected_subnets = graph.get_parents(
                load_balancer.id,
                RelationshipType.CONNECTS_TO,
            )
            public_subnets = [
                subnet
                for subnet in connected_subnets
                if subnet.type == ResourceType.PUBLIC_SUBNET
            ]
            invalid_subnets = [
                subnet
                for subnet in connected_subnets
                if subnet.type != ResourceType.PUBLIC_SUBNET
            ]

            availability_zones = {
                str(subnet.properties.get("availability_zone"))
                for subnet in public_subnets
                if subnet.properties.get("availability_zone")
            }
            if invalid_subnets:
                invalid_ids = ", ".join(sorted(subnet.id for subnet in invalid_subnets))
                results.append(
                    self.result(
                        resource_id=load_balancer.id,
                        description=(
                            f"Internet-facing load balancer '{load_balancer.id}' "
                            f"is connected to non-public subnet(s): {invalid_ids}."
                        ),
                    )
                )
            if len(public_subnets) < 2:
                results.append(
                    self.result(
                        resource_id=load_balancer.id,
                        description=(
                            f"Internet-facing load balancer '{load_balancer.id}' "
                            "must connect to at least two public subnets."
                        ),
                    )
                )
            elif len(availability_zones) < 2:
                results.append(
                    self.result(
                        resource_id=load_balancer.id,
                        description=(
                            f"Internet-facing load balancer '{load_balancer.id}' "
                            "must use public subnets in at least two distinct Availability Zones."
                        ),
                    )
                )
        return results

    def _validate_public_ec2_instances(
        self,
        architecture: InfrastructureArchitecture,
        graph: InfrastructureGraph,
    ) -> list[ValidationResult]:
        results: list[ValidationResult] = []
        for instance in _resources_of_type(architecture, ResourceType.EC2_INSTANCE):
            if instance.properties.get("associate_public_ip_address") is not True:
                continue
            subnets = graph.get_parents(instance.id, RelationshipType.BELONGS_TO)
            public_subnets = [
                subnet
                for subnet in subnets
                if subnet.type == ResourceType.PUBLIC_SUBNET
            ]
            if not public_subnets:
                results.append(
                    self.result(
                        resource_id=instance.id,
                        description=(
                            f"EC2 instance '{instance.id}' requests a public IP "
                            "but does not belong to a public subnet."
                        ),
                    )
                )
        return results

    @staticmethod
    def _is_internet_facing(resource: Resource) -> bool:
        if "internet_facing" in resource.properties:
            return bool(resource.properties["internet_facing"])
        return resource.properties.get("scheme", "internet-facing") == "internet-facing"


class SecurityGroupBelongsToVpcRule(ValidationRule):
    rule_id = "NET004"
    name = "Security Group belongs to VPC"
    description = "Every Security Group must belong to a VPC."
    severity = Severity.ERROR
    recommendation = "Add a BELONGS_TO relationship from the Security Group to a VPC."

    def validate(
        self,
        architecture: InfrastructureArchitecture,
        graph: InfrastructureGraph,
    ) -> list[ValidationResult]:
        results: list[ValidationResult] = []
        for security_group in _resources_of_type(architecture, ResourceType.SECURITY_GROUP):
            vpcs = [
                parent
                for parent in graph.get_parents(security_group.id, RelationshipType.BELONGS_TO)
                if parent.type == ResourceType.VPC
            ]
            if not vpcs:
                results.append(self.result(resource_id=security_group.id))
        return results


class PublicSubnetRequiresInternetGatewayRule(ValidationRule):
    rule_id = "NET005"
    name = "Public subnet requires Internet Gateway"
    description = "A VPC containing public subnets must have an Internet Gateway attached to it."
    severity = Severity.ERROR
    recommendation = "Add an Internet Gateway and attach it to the VPC (using an ATTACHES_TO relationship)."

    def validate(
        self,
        architecture: InfrastructureArchitecture,
        graph: InfrastructureGraph,
    ) -> list[ValidationResult]:
        results: list[ValidationResult] = []
        vpcs = _resources_of_type(architecture, ResourceType.VPC)
        for vpc in vpcs:
            public_subnets = [
                child
                for child in graph.get_children(vpc.id, RelationshipType.BELONGS_TO)
                if child.type == ResourceType.PUBLIC_SUBNET
            ]
            if not public_subnets:
                continue
            igws = [
                child
                for child in graph.get_children(vpc.id, RelationshipType.ATTACHES_TO)
                if child.type == ResourceType.INTERNET_GATEWAY
            ]
            if not igws:
                results.append(
                    self.result(
                        resource_id=vpc.id,
                        description=f"VPC '{vpc.id}' contains public subnet(s) but has no Internet Gateway attached.",
                    )
                )
        return results


