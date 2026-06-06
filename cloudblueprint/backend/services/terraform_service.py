from __future__ import annotations

from cloudblueprint.backend.database.models import TerraformGenerationRecord
from cloudblueprint.backend.database.repository import (
    SQLiteArchitectureRepository,
    SQLiteTerraformGenerationRepository,
)
from cloudblueprint.backend.generators.terraform.generator import (
    TerraformGenerationError,
    TerraformGenerator,
)
from cloudblueprint.backend.services.exceptions import (
    NotFoundError,
    TerraformGenerationBlockedError,
)


class TerraformService:
    def __init__(
        self,
        architecture_repository: SQLiteArchitectureRepository,
        terraform_repository: SQLiteTerraformGenerationRepository,
        terraform_generator: TerraformGenerator | None = None,
    ) -> None:
        self.architecture_repository = architecture_repository
        self.terraform_repository = terraform_repository
        self.terraform_generator = terraform_generator or TerraformGenerator()

    def generate_terraform(self, architecture_id: str) -> TerraformGenerationRecord:
        record = self.architecture_repository.get(architecture_id)
        if record is None:
            raise NotFoundError(f"architecture '{architecture_id}' was not found")

        try:
            result = self.terraform_generator.generate(record.architecture)
        except TerraformGenerationError as error:
            raise TerraformGenerationBlockedError(str(error), error.validation_results) from error

        return self.terraform_repository.create(architecture_id, result)

    def get_latest_terraform(self, architecture_id: str) -> TerraformGenerationRecord:
        if self.architecture_repository.get(architecture_id) is None:
            raise NotFoundError(f"architecture '{architecture_id}' was not found")

        record = self.terraform_repository.get_latest_for_architecture(architecture_id)
        if record is None:
            raise NotFoundError(
                f"no Terraform generation exists for architecture '{architecture_id}'"
            )
        return record
