from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class TerraformFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str
    content: str


class TerraformGenerationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    files: list[TerraformFile] = Field(default_factory=list)

    def as_dict(self) -> dict[str, str]:
        return {file.filename: file.content for file in self.files}

    def write_to_directory(self, output_directory: str | Path) -> list[Path]:
        output_path = Path(output_directory)
        output_path.mkdir(parents=True, exist_ok=True)

        written_files: list[Path] = []
        for terraform_file in self.files:
            file_path = output_path / terraform_file.filename
            file_path.write_text(terraform_file.content, encoding="utf-8")
            written_files.append(file_path)
        return written_files

