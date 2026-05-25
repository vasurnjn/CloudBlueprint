from __future__ import annotations

import re
from collections.abc import Iterable


def sanitize_terraform_name(identifier: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_]", "_", identifier.strip().lower())
    sanitized = re.sub(r"_+", "_", sanitized).strip("_")
    if not sanitized:
        sanitized = "resource"
    if sanitized[0].isdigit():
        sanitized = f"cb_{sanitized}"
    return sanitized


class TerraformNameRegistry:
    """Stable Terraform names for resource IDs, with collision handling."""

    def __init__(self, resource_ids: Iterable[str]) -> None:
        self._names: dict[str, str] = {}
        used: dict[str, int] = {}
        for resource_id in resource_ids:
            base_name = sanitize_terraform_name(resource_id)
            count = used.get(base_name, 0)
            used[base_name] = count + 1
            name = base_name if count == 0 else f"{base_name}_{count + 1}"
            self._names[resource_id] = name

    def name_for(self, resource_id: str) -> str:
        return self._names[resource_id]

    def address(self, terraform_type: str, resource_id: str) -> str:
        return f"{terraform_type}.{self.name_for(resource_id)}"

    def attribute(self, terraform_type: str, resource_id: str, attribute_name: str) -> str:
        return f"{self.address(terraform_type, resource_id)}.{attribute_name}"

