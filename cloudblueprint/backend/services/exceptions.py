from __future__ import annotations

from cloudblueprint.backend.validators.base import ValidationResult


class ServiceError(Exception):
    """Base class for API-facing service errors."""


class NotFoundError(ServiceError):
    """Raised when a requested domain object does not exist."""


class ConflictError(ServiceError):
    """Raised when a create operation conflicts with existing state."""


class BadRequestError(ServiceError):
    """Raised when a request is well-formed but invalid for the current state."""


class TerraformGenerationBlockedError(BadRequestError):
    def __init__(self, message: str, validation_results: list[ValidationResult]) -> None:
        super().__init__(message)
        self.validation_results = validation_results

