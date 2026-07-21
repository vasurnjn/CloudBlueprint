from __future__ import annotations

import os
import sqlite3
from pathlib import Path


DATABASE_PATH_ENV_VAR = "CLOUDBLUEPRINT_DB_PATH"
DEFAULT_DATABASE_PATH = Path("cloudblueprint.sqlite3")


def resolve_database_path(database_path: str | Path | None = None) -> str:
    if database_path is not None:
        return str(database_path)
    configured_path = os.environ.get(DATABASE_PATH_ENV_VAR)
    if configured_path:
        return configured_path
    return str(DEFAULT_DATABASE_PATH)


def connect(database_path: str | Path) -> sqlite3.Connection:
    path = str(database_path)
    if path != ":memory:" and not path.startswith("file:"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(database_path: str | Path) -> None:
    with connect(database_path) as connection:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS architectures (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                document_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS terraform_generations (
                id TEXT PRIMARY KEY,
                architecture_id TEXT NOT NULL,
                files_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (architecture_id)
                    REFERENCES architectures(id)
                    ON DELETE CASCADE
            )
            """
        )

