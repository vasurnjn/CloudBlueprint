from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RelationshipType(str, Enum):
    BELONGS_TO = "BELONGS_TO"
    ATTACHES_TO = "ATTACHES_TO"
    CONNECTS_TO = "CONNECTS_TO"
    USES_SECURITY_GROUP = "USES_SECURITY_GROUP"
    ROUTES_TO = "ROUTES_TO"
    TARGETS = "TARGETS"
    DEPENDS_ON = "DEPENDS_ON"


class Relationship(BaseModel):
    """A typed directed edge between two infrastructure resources."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    type: RelationshipType

    @field_validator("source_id", "target_id")
    @classmethod
    def resource_reference_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("relationship resource references must not be blank")
        return normalized

