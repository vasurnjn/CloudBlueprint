from __future__ import annotations

from cloudblueprint.backend.database.repository import (
    SQLiteArchitectureRepository,
    SQLiteTerraformGenerationRepository,
)
from cloudblueprint.backend.generators.terraform.files import (
    TerraformFile,
    TerraformGenerationResult,
)
from cloudblueprint.backend.models.architecture import InfrastructureArchitecture


def test_sqlite_architecture_repository_crud(
    tmp_path,
    valid_architecture: InfrastructureArchitecture,
) -> None:
    repository = SQLiteArchitectureRepository(tmp_path / "repository.sqlite")

    created = repository.create(valid_architecture)
    loaded = repository.get(valid_architecture.id)

    assert created.id == valid_architecture.id
    assert loaded is not None
    assert loaded.architecture == valid_architecture
    assert [record.id for record in repository.list()] == [valid_architecture.id]

    updated_architecture = valid_architecture.model_copy(update={"name": "Updated Architecture"})
    updated = repository.update(updated_architecture)

    assert updated is not None
    assert updated.name == "Updated Architecture"
    assert updated.created_at == created.created_at
    assert updated.updated_at >= created.updated_at

    assert repository.delete(valid_architecture.id) is True
    assert repository.get(valid_architecture.id) is None
    assert repository.delete(valid_architecture.id) is False


def test_sqlite_terraform_repository_stores_latest_generation(
    tmp_path,
    valid_architecture: InfrastructureArchitecture,
) -> None:
    database_path = tmp_path / "terraform.sqlite"
    architecture_repository = SQLiteArchitectureRepository(database_path)
    terraform_repository = SQLiteTerraformGenerationRepository(database_path)
    architecture_repository.create(valid_architecture)

    first = terraform_repository.create(
        valid_architecture.id,
        TerraformGenerationResult(
            files=[TerraformFile(filename="network.tf", content="first")]
        ),
    )
    second = terraform_repository.create(
        valid_architecture.id,
        TerraformGenerationResult(
            files=[TerraformFile(filename="network.tf", content="second")]
        ),
    )

    latest = terraform_repository.get_latest_for_architecture(valid_architecture.id)

    assert latest is not None
    assert latest.id == second.id
    assert latest.id != first.id
    assert latest.result.as_dict()["network.tf"] == "second"


def test_repositories_persist_across_instances(
    tmp_path,
    valid_architecture: InfrastructureArchitecture,
) -> None:
    database_path = tmp_path / "persistent.sqlite"
    first_architecture_repository = SQLiteArchitectureRepository(database_path)
    first_terraform_repository = SQLiteTerraformGenerationRepository(database_path)

    first_architecture_repository.create(valid_architecture)
    first_terraform_repository.create(
        valid_architecture.id,
        TerraformGenerationResult(
            files=[TerraformFile(filename="provider.tf", content="provider")]
        ),
    )

    second_architecture_repository = SQLiteArchitectureRepository(database_path)
    second_terraform_repository = SQLiteTerraformGenerationRepository(database_path)

    loaded_architecture = second_architecture_repository.get(valid_architecture.id)
    loaded_terraform = second_terraform_repository.get_latest_for_architecture(
        valid_architecture.id
    )

    assert loaded_architecture is not None
    assert loaded_architecture.architecture == valid_architecture
    assert loaded_terraform is not None
    assert loaded_terraform.result.as_dict()["provider.tf"] == "provider"

