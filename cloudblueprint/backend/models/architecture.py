from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from cloudblueprint.backend.models.relationships import Relationship
from cloudblueprint.backend.models.resource import Resource


class InfrastructureArchitecture(BaseModel):
    """A complete serializable infrastructure design."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    resources: dict[str, Resource] = Field(default_factory=dict)
    relationships: list[Relationship] = Field(default_factory=list)

    @field_validator("id", "name")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("architecture id and name must not be blank")
        return normalized

    @model_validator(mode="after")
    def resource_keys_must_match_resource_ids(self) -> InfrastructureArchitecture:
        mismatched = [
            key
            for key, resource in self.resources.items()
            if key != resource.id
        ]
        if mismatched:
            joined = ", ".join(sorted(mismatched))
            raise ValueError(f"resource dictionary keys must match resource ids: {joined}")
        return self

    def add_resource(self, resource: Resource) -> None:
        if resource.id in self.resources:
            raise ValueError(f"resource with id '{resource.id}' already exists")
        self.resources[resource.id] = resource

    def add_relationship(self, relationship: Relationship) -> None:
        self.relationships.append(relationship)

