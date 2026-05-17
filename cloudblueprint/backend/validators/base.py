from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum

from pydantic import BaseModel, ConfigDict

from cloudblueprint.backend.models.architecture import InfrastructureArchitecture
from cloudblueprint.backend.models.graph import InfrastructureGraph


class Severity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    rule_name: str
    severity: Severity
    resource_id: str | None
    description: str
    recommendation: str


class ValidationRule(ABC):
    rule_id: str
    name: str
    description: str
    severity: Severity
    recommendation: str

    def result(
        self,
        *,
        resource_id: str | None,
        description: str | None = None,
        recommendation: str | None = None,
        severity: Severity | None = None,
    ) -> ValidationResult:
        return ValidationResult(
            rule_id=self.rule_id,
            rule_name=self.name,
            severity=severity or self.severity,
            resource_id=resource_id,
            description=description or self.description,
            recommendation=recommendation or self.recommendation,
        )

    @abstractmethod
    def validate(
        self,
        architecture: InfrastructureArchitecture,
        graph: InfrastructureGraph,
    ) -> list[ValidationResult]:
        raise NotImplementedError

