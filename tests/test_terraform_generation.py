from __future__ import annotations

import re
import pytest

from cloudblueprint.backend.generators.terraform.blocks import (
    TerraformBlock,
    ref,
    render_value,
)
from cloudblueprint.backend.generators.terraform.generator import (
    TerraformGenerationError,
    TerraformGenerator,
)
from cloudblueprint.backend.models.architecture import InfrastructureArchitecture


def assert_contains_normalized(content: str, expected: str) -> None:
    norm_content = re.sub(r'\s+', ' ', content).strip()
    norm_expected = re.sub(r'\s+', ' ', expected).strip()
    assert norm_expected in norm_content


def test_terraform_renderer_handles_core_value_types() -> None:
    block = TerraformBlock(
        "resource",
        ["aws_instance", "web"],
        attributes={
            "ami": "ami-123",
            "enabled": True,
            "count": 2,
            "subnet_id": ref("aws_subnet.public.id"),
            "tags": {"Name": "web"},
        },
    )
    rendered = block.render()

    assert 'resource "aws_instance" "web"' in rendered
    assert_contains_normalized(rendered, 'ami = "ami-123"')
    assert_contains_normalized(rendered, "enabled = true")
    assert_contains_normalized(rendered, "count = 2")
    assert_contains_normalized(rendered, "subnet_id = aws_subnet.public.id")
    assert_contains_normalized(rendered, 'Name = "web"')
    assert render_value([ref("aws_subnet.a.id"), ref("aws_subnet.b.id")]) == (
        "[aws_subnet.a.id, aws_subnet.b.id]"
    )


def test_valid_architecture_generates_expected_terraform(
    valid_architecture: InfrastructureArchitecture,
) -> None:
    result = TerraformGenerator().generate(valid_architecture)
    files = result.as_dict()

    assert set(files) == {
        "provider.tf",
        "variables.tf",
        "network.tf",
        "compute.tf",
        "database.tf",
        "storage.tf",
        "outputs.tf",
    }
    assert 'resource "aws_vpc" "vpc_main"' in files["network.tf"]
    assert_contains_normalized(files["network.tf"], "vpc_id = aws_vpc.vpc_main.id")
    assert_contains_normalized(files["network.tf"], "security_groups = [aws_security_group.sg_alb.id]")
    assert 'resource "aws_lb" "alb_public"' in files["compute.tf"]
    assert_contains_normalized(
        files["compute.tf"],
        "subnets = [aws_subnet.public_subnet_a.id, aws_subnet.public_subnet_b.id]"
    )
    assert_contains_normalized(files["compute.tf"], "target_id = aws_instance.ec2_app.id")
    assert 'resource "aws_db_subnet_group" "rds_primary_subnets"' in files["database.tf"]
    assert_contains_normalized(
        files["database.tf"],
        "subnet_ids = [aws_subnet.private_subnet_a.id, aws_subnet.private_subnet_b.id]"
    )
    assert_contains_normalized(files["database.tf"], "password = var.db_password")
    assert 'resource "aws_s3_bucket" "s3_assets"' in files["storage.tf"]


def test_invalid_architecture_is_blocked_from_terraform_generation(
    invalid_architecture: InfrastructureArchitecture,
) -> None:
    with pytest.raises(TerraformGenerationError) as error:
        TerraformGenerator().generate(invalid_architecture)

    rule_ids = {result.rule_id for result in error.value.validation_results}
    assert "REF001" in rule_ids
    assert "DEP001" in rule_ids


def test_terraform_generation_can_write_files(
    tmp_path,
    valid_architecture: InfrastructureArchitecture,
) -> None:
    result = TerraformGenerator().generate(valid_architecture, write_to=tmp_path)

    written_files = {path.name for path in tmp_path.iterdir()}

    assert written_files == {file.filename for file in result.files}
    assert (tmp_path / "network.tf").read_text(encoding="utf-8")


def test_public_routing_and_alb_listener_generation(
    valid_architecture: InfrastructureArchitecture,
) -> None:
    result = TerraformGenerator().generate(valid_architecture)
    files = result.as_dict()

    # Verify Route Table & associations in network.tf
    assert 'resource "aws_route_table" "vpc_main_public"' in files["network.tf"]
    assert_contains_normalized(files["network.tf"], 'gateway_id = aws_internet_gateway.igw_main.id')
    assert_contains_normalized(files["network.tf"], 'cidr_block = "0.0.0.0/0"')
    assert 'resource "aws_route_table_association" "public_subnet_a_public"' in files["network.tf"]
    assert 'resource "aws_route_table_association" "public_subnet_b_public"' in files["network.tf"]
    assert_contains_normalized(files["network.tf"], 'route_table_id = aws_route_table.vpc_main_public.id')

    # Verify ALB Listener in compute.tf
    assert 'resource "aws_lb_listener" "alb_public_http"' in files["compute.tf"]
    assert_contains_normalized(files["compute.tf"], 'load_balancer_arn = aws_lb.alb_public.arn')
    assert_contains_normalized(files["compute.tf"], 'port = 80')
    assert_contains_normalized(files["compute.tf"], 'protocol = "HTTP"')
    assert_contains_normalized(files["compute.tf"], 'target_group_arn = aws_lb_target_group.alb_public_tg.arn')


def test_security_group_name_does_not_start_with_sg() -> None:
    from cloudblueprint.backend.models.architecture import Resource, Relationship
    from cloudblueprint.backend.models.graph import RelationshipType

    vpc = Resource(
        id="vpc_main",
        name="Main VPC",
        type="VPC",
        properties={"cidr_block": "10.0.0.0/16"},
        tags={},
    )
    
    # 1. Test name fallback from resource ID starting with sg_
    sg = Resource(
        id="sg_app",
        name="App Security Group",
        type="SECURITY_GROUP",
        properties={"description": "Test security group"},
        tags={},
    )

    arch = InfrastructureArchitecture(
        id="test-sg-naming",
        name="SG Naming Test",
        resources={
            "vpc_main": vpc,
            "sg_app": sg,
        },
        relationships=[
            Relationship(source_id="sg_app", target_id="vpc_main", type=RelationshipType.BELONGS_TO)
        ],
    )

    result = TerraformGenerator().generate(arch)
    network_tf = result.as_dict()["network.tf"]

    # Logical ID is still "sg_app"
    assert 'resource "aws_security_group" "sg_app"' in network_tf
    # Physical name is adjusted to "sec-app"
    assert_contains_normalized(network_tf, 'name = "sec-app"')

    # 2. Test explicit name property starting with sg-
    sg_custom = Resource(
        id="sg_custom",
        name="Custom Security Group",
        type="SECURITY_GROUP",
        properties={"name": "sg-custom-group", "description": "Custom"},
        tags={},
    )

    arch_custom = InfrastructureArchitecture(
        id="test-sg-naming-custom",
        name="SG Naming Test Custom",
        resources={
            "vpc_main": vpc,
            "sg_custom": sg_custom,
        },
        relationships=[
            Relationship(source_id="sg_custom", target_id="vpc_main", type=RelationshipType.BELONGS_TO)
        ],
    )

    result_custom = TerraformGenerator().generate(arch_custom)
    network_tf_custom = result_custom.as_dict()["network.tf"]
    assert_contains_normalized(network_tf_custom, 'name = "sec-custom-group"')


def test_terraform_renderer_consecutive_alignment_grouping() -> None:
    block = TerraformBlock(
        "resource",
        ["aws_instance", "web"],
        attributes={
            "ami": "ami-123",
            "instance_type": "t3.micro",
            "tags": {"Name": "web", "Tier": "app"},
            "vpc_security_group_ids": [ref("aws_security_group.sg.id")],
            "associate_public_ip_address": False,
        },
    )
    rendered = block.render()
    
    # 1. ami & instance_type are aligned to max length 13
    assert '  ami           = "ami-123"' in rendered
    assert '  instance_type = "t3.micro"' in rendered
    
    # 2. tags is not padded
    assert '  tags = {' in rendered
    
    # 3. vpc_security_group_ids & associate_public_ip_address are aligned to max length 27
    assert '  vpc_security_group_ids      = [aws_security_group.sg.id]' in rendered
    assert '  associate_public_ip_address = false' in rendered

