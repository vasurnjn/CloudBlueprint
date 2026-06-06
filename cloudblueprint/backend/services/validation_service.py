from __future__ import annotations

from dataclasses import dataclass

from cloudblueprint.backend.database.repository import SQLiteArchitectureRepository
from cloudblueprint.backend.services.exceptions import NotFoundError
from cloudblueprint.backend.validators.base import ValidationResult
from cloudblueprint.backend.validators.engine import ValidationEngine


@dataclass(frozen=True)
class ValidationReport:
    architecture_id: str
    is_valid: bool
    results: list[ValidationResult]


class ValidationService:
    def __init__(
        self,
        architecture_repository: SQLiteArchitectureRepository,
        validation_engine: ValidationEngine | None = None,
    ) -> None:
        self.architecture_repository = architecture_repository
        self.validation_engine = validation_engine or ValidationEngine()

    def validate_architecture(self, architecture_id: str) -> ValidationReport:
        record = self.architecture_repository.get(architecture_id)
        if record is None:
            raise NotFoundError(f"architecture '{architecture_id}' was not found")

        results = self.validation_engine.validate(record.architecture)
        return ValidationReport(
            architecture_id=architecture_id,
            is_valid=not self.validation_engine.has_blocking_errors(results),
            results=results,
        )

