from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from cloudblueprint.backend.database.connection import (
    connect,
    initialize_database,
    resolve_database_path,
)
from cloudblueprint.backend.database.models import (
    ArchitectureRecord,
    TerraformGenerationRecord,
)
from cloudblueprint.backend.generators.terraform.files import TerraformGenerationResult
from cloudblueprint.backend.models.architecture import InfrastructureArchitecture


class DuplicateRecordError(Exception):
    """Raised when a repository create operation would overwrite an existing row."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteArchitectureRepository:
    def __init__(self, database_path: str | Path | None = None) -> None:
        self.database_path = resolve_database_path(database_path)
        initialize_database(self.database_path)

    def create(self, architecture: InfrastructureArchitecture) -> ArchitectureRecord:
        now = _utc_now()
        document_json = architecture.model_dump_json()
        try:
            with connect(self.database_path) as connection:
                connection.execute(
                    """
                    INSERT INTO architectures (id, name, document_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (architecture.id, architecture.name, document_json, now, now),
                )
        except sqlite3.IntegrityError as error:
            raise DuplicateRecordError(f"architecture '{architecture.id}' already exists") from error

        return ArchitectureRecord(
            id=architecture.id,
            name=architecture.name,
            architecture=architecture,
            created_at=now,
            updated_at=now,
        )

    def list(self) -> list[ArchitectureRecord]:
        with connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT id, name, document_json, created_at, updated_at
                FROM architectures
                ORDER BY created_at ASC, id ASC
                """
            ).fetchall()
        return [self._record_from_row(row) for row in rows]

    def get(self, architecture_id: str) -> ArchitectureRecord | None:
        with connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT id, name, document_json, created_at, updated_at
                FROM architectures
                WHERE id = ?
                """,
                (architecture_id,),
            ).fetchone()
        if row is None:
            return None
        return self._record_from_row(row)

    def update(self, architecture: InfrastructureArchitecture) -> ArchitectureRecord | None:
        updated_at = _utc_now()
        document_json = architecture.model_dump_json()
        with connect(self.database_path) as connection:
            cursor = connection.execute(
                """
                UPDATE architectures
                SET name = ?, document_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (architecture.name, document_json, updated_at, architecture.id),
            )
        if cursor.rowcount == 0:
            return None
        return self.get(architecture.id)

    def upsert(self, architecture: InfrastructureArchitecture) -> tuple[ArchitectureRecord, bool]:
        existing = self.get(architecture.id)
        if existing is None:
            return self.create(architecture), True

        updated = self.update(architecture)
        if updated is None:
            return self.create(architecture), True
        return updated, False

    def delete(self, architecture_id: str) -> bool:
        with connect(self.database_path) as connection:
            cursor = connection.execute(
                "DELETE FROM architectures WHERE id = ?",
                (architecture_id,),
            )
        return cursor.rowcount > 0

    @staticmethod
    def _record_from_row(row: sqlite3.Row) -> ArchitectureRecord:
        architecture = InfrastructureArchitecture.model_validate_json(row["document_json"])
        return ArchitectureRecord(
            id=row["id"],
            name=row["name"],
            architecture=architecture,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


class SQLiteTerraformGenerationRepository:
    def __init__(self, database_path: str | Path | None = None) -> None:
        self.database_path = resolve_database_path(database_path)
        initialize_database(self.database_path)

    def create(
        self,
        architecture_id: str,
        result: TerraformGenerationResult,
    ) -> TerraformGenerationRecord:
        generation_id = str(uuid4())
        created_at = _utc_now()
        files_json = result.model_dump_json()
        with connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO terraform_generations (id, architecture_id, files_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (generation_id, architecture_id, files_json, created_at),
            )
        return TerraformGenerationRecord(
            id=generation_id,
            architecture_id=architecture_id,
            result=result,
            created_at=created_at,
        )

    def get_latest_for_architecture(
        self,
        architecture_id: str,
    ) -> TerraformGenerationRecord | None:
        with connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT id, architecture_id, files_json, created_at
                FROM terraform_generations
                WHERE architecture_id = ?
                ORDER BY created_at DESC, rowid DESC
                LIMIT 1
                """,
                (architecture_id,),
            ).fetchone()
        if row is None:
            return None
        return self._record_from_row(row)

    @staticmethod
    def _record_from_row(row: sqlite3.Row) -> TerraformGenerationRecord:
        result = TerraformGenerationResult.model_validate_json(row["files_json"])
        return TerraformGenerationRecord(
            id=row["id"],
            architecture_id=row["architecture_id"],
            result=result,
            created_at=row["created_at"],
        )
