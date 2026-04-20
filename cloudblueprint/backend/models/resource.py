from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ResourceType(str, Enum):
    VPC = "VPC"
    PUBLIC_SUBNET = "PUBLIC_SUBNET"
    PRIVATE_SUBNET = "PRIVATE_SUBNET"
    SECURITY_GROUP = "SECURITY_GROUP"
    INTERNET_GATEWAY = "INTERNET_GATEWAY"
    EC2_INSTANCE = "EC2_INSTANCE"
    APPLICATION_LOAD_BALANCER = "APPLICATION_LOAD_BALANCER"
    RDS_DATABASE = "RDS_DATABASE"
    S3_BUCKET = "S3_BUCKET"


class Resource(BaseModel):
    """A supported AWS infrastructure resource in a CloudBlueprint design."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    type: ResourceType
    properties: dict[str, Any] = Field(default_factory=dict)
    tags: dict[str, str] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def id_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("resource id must not be blank")
        return normalized

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("resource name must not be blank")
        return normalized

