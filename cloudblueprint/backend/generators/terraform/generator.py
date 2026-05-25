from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Any

from cloudblueprint.backend.generators.terraform.blocks import (
    TerraformBlock,
    TerraformExpression,
    ref,
    render_blocks,
)
from cloudblueprint.backend.generators.terraform.files import (
    TerraformFile,
    TerraformGenerationResult,
)
from cloudblueprint.backend.generators.terraform.naming import TerraformNameRegistry
from cloudblueprint.backend.models.architecture import InfrastructureArchitecture
from cloudblueprint.backend.models.graph import InfrastructureGraph
from cloudblueprint.backend.models.relationships import RelationshipType
from cloudblueprint.backend.models.resource import Resource, ResourceType
from cloudblueprint.backend.validators.base import ValidationResult
from cloudblueprint.backend.validators.engine import ValidationEngine


class TerraformGenerationError(Exception):
    def __init__(self, message: str, validation_results: list[ValidationResult]) -> None:
        super().__init__(message)
        self.validation_results = validation_results


class TerraformGenerator:
    def __init__(self, validation_engine: ValidationEngine | None = None) -> None:
        self.validation_engine = validation_engine or ValidationEngine()

    def generate(
        self,
        architecture: InfrastructureArchitecture,
        *,
        write_to: str | Path | None = None,
    ) -> TerraformGenerationResult:
        graph = InfrastructureGraph(architecture)
        validation_results = self.validation_engine.validate(architecture, graph)
        if self.validation_engine.has_blocking_errors(validation_results):
            raise TerraformGenerationError(
                "Terraform generation blocked because the architecture has ERROR or CRITICAL validation results.",
                validation_results,
            )

        registry = TerraformNameRegistry(architecture.resources.keys())
        blocks_by_file: OrderedDict[str, list[TerraformBlock]] = OrderedDict(
            [
                ("provider.tf", self._provider_blocks()),
                ("variables.tf", self._variable_blocks(architecture)),
                ("network.tf", []),
                ("compute.tf", []),
                ("database.tf", []),
                ("storage.tf", []),
                ("outputs.tf", []),
            ]
        )

        for resource in architecture.resources.values():
            if resource.type == ResourceType.VPC:
                blocks_by_file["network.tf"].append(self._vpc_block(resource, registry))
            elif resource.type in {ResourceType.PUBLIC_SUBNET, ResourceType.PRIVATE_SUBNET}:
                blocks_by_file["network.tf"].append(self._subnet_block(resource, graph, registry))
            elif resource.type == ResourceType.INTERNET_GATEWAY:
                blocks_by_file["network.tf"].append(
                    self._internet_gateway_block(resource, graph, registry)
                )
            elif resource.type == ResourceType.SECURITY_GROUP:
                blocks_by_file["network.tf"].append(
                    self._security_group_block(resource, graph, registry)
                )
            elif resource.type == ResourceType.EC2_INSTANCE:
                blocks_by_file["compute.tf"].append(self._ec2_block(resource, graph, registry))
            elif resource.type == ResourceType.APPLICATION_LOAD_BALANCER:
                blocks_by_file["compute.tf"].extend(
                    self._load_balancer_blocks(resource, graph, registry)
                )
            elif resource.type == ResourceType.RDS_DATABASE:
                blocks_by_file["database.tf"].extend(
                    self._rds_blocks(resource, graph, registry)
                )
            elif resource.type == ResourceType.S3_BUCKET:
                blocks_by_file["storage.tf"].append(self._s3_bucket_block(resource, registry))

        # Generate routing table and associations for public subnets
        blocks_by_file["network.tf"].extend(
            self._generate_public_routing_blocks(graph, registry)
        )

        blocks_by_file["outputs.tf"].extend(self._output_blocks(architecture, registry))

        result = TerraformGenerationResult(
            files=[
                TerraformFile(filename=filename, content=render_blocks(blocks))
                for filename, blocks in blocks_by_file.items()
            ]
        )
        if write_to is not None:
            result.write_to_directory(write_to)
        return result

    def _provider_blocks(self) -> list[TerraformBlock]:
        return [
            TerraformBlock(
                "terraform",
                nested_blocks=[
                    TerraformBlock(
                        "required_providers",
                        attributes={
                            "aws": {
                                "source": "hashicorp/aws",
                                "version": "~> 5.0",
                            }
                        },
                    )
                ],
            ),
            TerraformBlock(
                "provider",
                ["aws"],
                attributes={"region": ref("var.aws_region")},
            ),
        ]

    def _variable_blocks(self, architecture: InfrastructureArchitecture) -> list[TerraformBlock]:
        blocks = [
            TerraformBlock(
                "variable",
                ["aws_region"],
                attributes={
                    "description": "AWS region where resources will be created.",
                    "type": ref("string"),
                    "default": "us-east-1",
                },
            )
        ]
        if any(resource.type == ResourceType.RDS_DATABASE for resource in architecture.resources.values()):
            blocks.append(
                TerraformBlock(
                    "variable",
                    ["db_password"],
                    attributes={
                        "description": "Password for generated RDS database instances.",
                        "type": ref("string"),
                        "sensitive": True,
                    },
                )
            )
        if any(
            resource.type == ResourceType.EC2_INSTANCE and not resource.properties.get("ami")
            for resource in architecture.resources.values()
        ):
            blocks.append(
                TerraformBlock(
                    "variable",
                    ["ec2_ami"],
                    attributes={
                        "description": "AMI ID to use for EC2 instances without an explicit AMI.",
                        "type": ref("string"),
                    },
                )
            )
        return blocks

    def _vpc_block(self, resource: Resource, registry: TerraformNameRegistry) -> TerraformBlock:
        return self._resource_block(
            "aws_vpc",
            resource,
            registry,
            {
                "cidr_block": resource.properties.get("cidr_block", "10.0.0.0/16"),
                "enable_dns_support": resource.properties.get("enable_dns_support", True),
                "enable_dns_hostnames": resource.properties.get("enable_dns_hostnames", True),
                "tags": self._tags(resource),
            },
        )

    def _subnet_block(
        self,
        resource: Resource,
        graph: InfrastructureGraph,
        registry: TerraformNameRegistry,
    ) -> TerraformBlock:
        vpc = self._first_parent(resource, graph, RelationshipType.BELONGS_TO, ResourceType.VPC)
        attributes: dict[str, Any] = {
            "vpc_id": ref(registry.attribute("aws_vpc", vpc.id, "id")),
            "cidr_block": resource.properties.get("cidr_block", "10.0.0.0/24"),
            "map_public_ip_on_launch": resource.type == ResourceType.PUBLIC_SUBNET,
            "tags": self._tags(resource),
        }
        availability_zone = resource.properties.get("availability_zone")
        if availability_zone:
            attributes["availability_zone"] = availability_zone
        return self._resource_block("aws_subnet", resource, registry, attributes)

    def _internet_gateway_block(
        self,
        resource: Resource,
        graph: InfrastructureGraph,
        registry: TerraformNameRegistry,
    ) -> TerraformBlock:
        vpc = self._first_parent(resource, graph, RelationshipType.ATTACHES_TO, ResourceType.VPC)
        return self._resource_block(
            "aws_internet_gateway",
            resource,
            registry,
            {
                "vpc_id": ref(registry.attribute("aws_vpc", vpc.id, "id")),
                "tags": self._tags(resource),
            },
        )

    def _security_group_block(
        self,
        resource: Resource,
        graph: InfrastructureGraph,
        registry: TerraformNameRegistry,
    ) -> TerraformBlock:
        vpc = self._first_parent(resource, graph, RelationshipType.BELONGS_TO, ResourceType.VPC)
        sg_name = resource.properties.get("name", resource.id.replace("_", "-"))
        if sg_name.startswith("sg-"):
            sg_name = "sec-" + sg_name[3:]
        return self._resource_block(
            "aws_security_group",
            resource,
            registry,
            {
                "name": sg_name,
                "description": resource.properties.get("description", resource.name),
                "vpc_id": ref(registry.attribute("aws_vpc", vpc.id, "id")),
                "tags": self._tags(resource),
            },
            nested_blocks=[
                *self._security_group_rule_blocks(
                    "ingress",
                    resource.properties.get("ingress_rules", []),
                    registry,
                ),
                *self._security_group_rule_blocks(
                    "egress",
                    resource.properties.get(
                        "egress_rules",
                        [
                            {
                                "from_port": 0,
                                "to_port": 0,
                                "protocol": "-1",
                                "cidr_blocks": ["0.0.0.0/0"],
                            }
                        ],
                    ),
                    registry,
                ),
            ],
        )

    def _ec2_block(
        self,
        resource: Resource,
        graph: InfrastructureGraph,
        registry: TerraformNameRegistry,
    ) -> TerraformBlock:
        subnet = self._first_parent(
            resource,
            graph,
            RelationshipType.BELONGS_TO,
            ResourceType.PUBLIC_SUBNET,
            ResourceType.PRIVATE_SUBNET,
        )
        security_groups = self._parents(
            resource,
            graph,
            RelationshipType.USES_SECURITY_GROUP,
            ResourceType.SECURITY_GROUP,
        )
        attributes: dict[str, Any] = {
            "ami": resource.properties.get("ami") or ref("var.ec2_ami"),
            "instance_type": resource.properties.get("instance_type", "t3.micro"),
            "subnet_id": ref(registry.attribute("aws_subnet", subnet.id, "id")),
            "tags": self._tags(resource),
        }
        if security_groups:
            attributes["vpc_security_group_ids"] = [
                ref(registry.attribute("aws_security_group", security_group.id, "id"))
                for security_group in security_groups
            ]
        if "associate_public_ip_address" in resource.properties:
            attributes["associate_public_ip_address"] = bool(
                resource.properties["associate_public_ip_address"]
            )
        return self._resource_block("aws_instance", resource, registry, attributes)

    def _load_balancer_blocks(
        self,
        resource: Resource,
        graph: InfrastructureGraph,
        registry: TerraformNameRegistry,
    ) -> list[TerraformBlock]:
        subnets = self._parents(
            resource,
            graph,
            RelationshipType.CONNECTS_TO,
            ResourceType.PUBLIC_SUBNET,
            ResourceType.PRIVATE_SUBNET,
        )
        security_groups = self._parents(
            resource,
            graph,
            RelationshipType.USES_SECURITY_GROUP,
            ResourceType.SECURITY_GROUP,
        )
        vpc = self._vpc_for_subnet(subnets[0], graph)
        target_port = int(resource.properties.get("target_port", 80))
        protocol = str(resource.properties.get("protocol", "HTTP")).upper()

        lb_block = self._resource_block(
            "aws_lb",
            resource,
            registry,
            {
                "name": resource.properties.get("name", resource.id.replace("_", "-")),
                "internal": not self._is_internet_facing(resource),
                "load_balancer_type": "application",
                "subnets": [
                    ref(registry.attribute("aws_subnet", subnet.id, "id"))
                    for subnet in subnets
                ],
                **(
                    {
                        "security_groups": [
                            ref(registry.attribute("aws_security_group", security_group.id, "id"))
                            for security_group in security_groups
                        ]
                    }
                    if security_groups
                    else {}
                ),
                "tags": self._tags(resource),
            },
        )

        target_group = TerraformBlock(
            "resource",
            ["aws_lb_target_group", f"{registry.name_for(resource.id)}_tg"],
            attributes={
                "name": self._aws_name(resource.id, suffix="-tg", max_length=32),
                "port": target_port,
                "protocol": protocol,
                "target_type": "instance",
                "vpc_id": ref(registry.attribute("aws_vpc", vpc.id, "id")),
                "tags": self._tags(resource),
            },
            nested_blocks=[
                TerraformBlock(
                    "health_check",
                    attributes={
                        "path": resource.properties.get("health_check_path", "/"),
                        "protocol": protocol,
                        "matcher": resource.properties.get("health_check_matcher", "200-399"),
                    },
                )
            ],
        )

        attachments = []
        for target in self._parents(
            resource,
            graph,
            RelationshipType.TARGETS,
            ResourceType.EC2_INSTANCE,
        ):
            attachments.append(
                TerraformBlock(
                    "resource",
                    [
                        "aws_lb_target_group_attachment",
                        f"{registry.name_for(resource.id)}_{registry.name_for(target.id)}",
                    ],
                    attributes={
                        "target_group_arn": ref(
                            f"aws_lb_target_group.{registry.name_for(resource.id)}_tg.arn"
                        ),
                        "target_id": ref(registry.attribute("aws_instance", target.id, "id")),
                        "port": target_port,
                    },
                )
            )

        listener_port = int(resource.properties.get("listener_port", 80))
        listener = TerraformBlock(
            "resource",
            ["aws_lb_listener", f"{registry.name_for(resource.id)}_http"],
            attributes={
                "load_balancer_arn": ref(f"aws_lb.{registry.name_for(resource.id)}.arn"),
                "port": listener_port,
                "protocol": protocol,
            },
            nested_blocks=[
                TerraformBlock(
                    "default_action",
                    attributes={
                        "type": "forward",
                        "target_group_arn": ref(
                            f"aws_lb_target_group.{registry.name_for(resource.id)}_tg.arn"
                        ),
                    },
                )
            ],
        )

        return [lb_block, target_group, listener, *attachments]

    def _rds_blocks(
        self,
        resource: Resource,
        graph: InfrastructureGraph,
        registry: TerraformNameRegistry,
    ) -> list[TerraformBlock]:
        private_subnets = self._parents(
            resource,
            graph,
            RelationshipType.BELONGS_TO,
            ResourceType.PRIVATE_SUBNET,
        )
        security_groups = self._parents(
            resource,
            graph,
            RelationshipType.USES_SECURITY_GROUP,
            ResourceType.SECURITY_GROUP,
        )
        subnet_group = TerraformBlock(
            "resource",
            ["aws_db_subnet_group", f"{registry.name_for(resource.id)}_subnets"],
            attributes={
                "name": self._aws_name(resource.id, suffix="-subnets", max_length=255),
                "subnet_ids": [
                    ref(registry.attribute("aws_subnet", subnet.id, "id"))
                    for subnet in private_subnets
                ],
                "tags": self._tags(resource),
            },
        )

        attributes: dict[str, Any] = {
            "identifier": self._aws_name(resource.id, max_length=63),
            "allocated_storage": int(resource.properties.get("allocated_storage", 20)),
            "engine": resource.properties.get("engine", "postgres"),
            "instance_class": resource.properties.get("instance_class", "db.t3.micro"),
            "username": resource.properties.get("username", "admin"),
            "password": ref(resource.properties.get("password_expression", "var.db_password")),
            "db_subnet_group_name": ref(
                f"aws_db_subnet_group.{registry.name_for(resource.id)}_subnets.name"
            ),
            "publicly_accessible": bool(resource.properties.get("publicly_accessible", False)),
            "skip_final_snapshot": bool(resource.properties.get("skip_final_snapshot", True)),
            "tags": self._tags(resource),
        }
        if resource.properties.get("db_name"):
            attributes["db_name"] = resource.properties["db_name"]
        if security_groups:
            attributes["vpc_security_group_ids"] = [
                ref(registry.attribute("aws_security_group", security_group.id, "id"))
                for security_group in security_groups
            ]

        return [
            subnet_group,
            self._resource_block("aws_db_instance", resource, registry, attributes),
        ]

    def _s3_bucket_block(
        self,
        resource: Resource,
        registry: TerraformNameRegistry,
    ) -> TerraformBlock:
        attributes: dict[str, Any] = {"tags": self._tags(resource)}
        if resource.properties.get("bucket"):
            attributes["bucket"] = resource.properties["bucket"]
        else:
            attributes["bucket_prefix"] = resource.properties.get(
                "bucket_prefix",
                f"{resource.id.replace('_', '-')}-",
            )
        return self._resource_block("aws_s3_bucket", resource, registry, attributes)

    def _output_blocks(
        self,
        architecture: InfrastructureArchitecture,
        registry: TerraformNameRegistry,
    ) -> list[TerraformBlock]:
        outputs: list[TerraformBlock] = []
        type_mapping = {
            ResourceType.VPC: ("aws_vpc", "id", "vpc_id"),
            ResourceType.APPLICATION_LOAD_BALANCER: ("aws_lb", "dns_name", "alb_dns_name"),
            ResourceType.RDS_DATABASE: ("aws_db_instance", "endpoint", "rds_endpoint"),
            ResourceType.S3_BUCKET: ("aws_s3_bucket", "bucket", "s3_bucket_name"),
        }
        for resource in architecture.resources.values():
            mapping = type_mapping.get(resource.type)
            if mapping is None:
                continue
            terraform_type, attribute_name, suffix = mapping
            outputs.append(
                TerraformBlock(
                    "output",
                    [f"{registry.name_for(resource.id)}_{suffix}"],
                    attributes={
                        "value": ref(registry.attribute(terraform_type, resource.id, attribute_name))
                    },
                )
            )
        return outputs

    def _resource_block(
        self,
        terraform_type: str,
        resource: Resource,
        registry: TerraformNameRegistry,
        attributes: dict[str, Any],
        nested_blocks: list[TerraformBlock] | None = None,
    ) -> TerraformBlock:
        return TerraformBlock(
            "resource",
            [terraform_type, registry.name_for(resource.id)],
            attributes=attributes,
            nested_blocks=nested_blocks or [],
        )

    def _security_group_rule_blocks(
        self,
        block_type: str,
        rules: list[dict[str, Any]],
        registry: TerraformNameRegistry,
    ) -> list[TerraformBlock]:
        blocks: list[TerraformBlock] = []
        for rule in rules:
            attributes: dict[str, Any] = {
                "from_port": int(rule.get("from_port", 0)),
                "to_port": int(rule.get("to_port", 0)),
                "protocol": str(rule.get("protocol", "-1")),
            }
            if rule.get("description"):
                attributes["description"] = str(rule["description"])
            if rule.get("cidr_blocks"):
                attributes["cidr_blocks"] = list(rule["cidr_blocks"])
            if rule.get("security_group_id"):
                attributes["security_groups"] = [
                    ref(registry.attribute("aws_security_group", str(rule["security_group_id"]), "id"))
                ]
            blocks.append(TerraformBlock(block_type, attributes=attributes))
        return blocks

    def _parents(
        self,
        resource: Resource,
        graph: InfrastructureGraph,
        relationship_type: RelationshipType,
        *resource_types: ResourceType,
    ) -> list[Resource]:
        allowed = set(resource_types)
        return [
            parent
            for parent in graph.get_parents(resource.id, relationship_type)
            if parent.type in allowed
        ]

    def _first_parent(
        self,
        resource: Resource,
        graph: InfrastructureGraph,
        relationship_type: RelationshipType,
        *resource_types: ResourceType,
    ) -> Resource:
        parents = self._parents(resource, graph, relationship_type, *resource_types)
        if not parents:
            allowed = ", ".join(resource_type.value for resource_type in resource_types)
            raise TerraformGenerationError(
                f"Resource '{resource.id}' does not have a required {relationship_type.value} parent of type {allowed}.",
                [],
            )
        return parents[0]

    def _vpc_for_subnet(
        self,
        subnet: Resource,
        graph: InfrastructureGraph,
    ) -> Resource:
        return self._first_parent(subnet, graph, RelationshipType.BELONGS_TO, ResourceType.VPC)

    def _tags(self, resource: Resource) -> dict[str, str]:
        return {"Name": resource.name, **resource.tags}

    @staticmethod
    def _is_internet_facing(resource: Resource) -> bool:
        if "internet_facing" in resource.properties:
            return bool(resource.properties["internet_facing"])
        return resource.properties.get("scheme", "internet-facing") == "internet-facing"

    @staticmethod
    def _aws_name(resource_id: str, *, suffix: str = "", max_length: int) -> str:
        base = resource_id.replace("_", "-").lower()
        value = f"{base}{suffix}"
        if len(value) <= max_length:
            return value
        if suffix and len(suffix) < max_length:
            return f"{base[: max_length - len(suffix)]}{suffix}"
        return value[:max_length]

    def _generate_public_routing_blocks(
        self,
        graph: InfrastructureGraph,
        registry: TerraformNameRegistry,
    ) -> list[TerraformBlock]:
        blocks = []
        vpcs = [r for r in graph.all_resources() if r.type == ResourceType.VPC]
        for vpc in vpcs:
            igws = [
                child
                for child in graph.get_children(vpc.id, RelationshipType.ATTACHES_TO)
                if child.type == ResourceType.INTERNET_GATEWAY
            ]
            if not igws:
                continue
            igw = igws[0]

            public_subnets = [
                child
                for child in graph.get_children(vpc.id, RelationshipType.BELONGS_TO)
                if child.type == ResourceType.PUBLIC_SUBNET
            ]
            if not public_subnets:
                continue

            rt_name = f"{registry.name_for(vpc.id)}_public"
            route_table = TerraformBlock(
                "resource",
                ["aws_route_table", rt_name],
                attributes={
                    "vpc_id": ref(registry.attribute("aws_vpc", vpc.id, "id")),
                    "tags": {"Name": f"{vpc.name}-public"},
                },
                nested_blocks=[
                    TerraformBlock(
                        "route",
                        attributes={
                            "cidr_block": "0.0.0.0/0",
                            "gateway_id": ref(registry.attribute("aws_internet_gateway", igw.id, "id")),
                        }
                    )
                ]
            )
            blocks.append(route_table)

            for subnet in public_subnets:
                assoc_name = f"{registry.name_for(subnet.id)}_public"
                association = TerraformBlock(
                    "resource",
                    ["aws_route_table_association", assoc_name],
                    attributes={
                        "subnet_id": ref(registry.attribute("aws_subnet", subnet.id, "id")),
                        "route_table_id": ref(f"aws_route_table.{rt_name}.id"),
                    }
                )
                blocks.append(association)
        return blocks

