from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TerraformExpression:
    """A Terraform expression that should not be quoted during rendering."""

    value: str


@dataclass
class TerraformBlock:
    block_type: str
    labels: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)
    nested_blocks: list[TerraformBlock] = field(default_factory=list)

    def render(self, indent_level: int = 0) -> str:
        indent = "  " * indent_level
        labels = "".join(f" {json.dumps(label)}" for label in self.labels)
        lines = [f"{indent}{self.block_type}{labels} {{"]
        if self.attributes:
            max_key_len = max(len(key) for key in self.attributes.keys())
            for key, value in self.attributes.items():
                rendered = render_value(value, indent_level + 1)
                padding = " " * (max_key_len - len(key))
                lines.append(f"{indent}  {key}{padding} = {rendered}")
        for block in self.nested_blocks:
            lines.append(block.render(indent_level + 1))
        lines.append(f"{indent}}}")
        return "\n".join(lines)


def ref(expression: str) -> TerraformExpression:
    return TerraformExpression(expression)


def render_blocks(blocks: list[TerraformBlock]) -> str:
    if not blocks:
        return ""
    return "\n\n".join(block.render() for block in blocks) + "\n"


def render_value(value: Any, indent_level: int = 0) -> str:
    if isinstance(value, TerraformExpression):
        return value.value
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return _render_list(value, indent_level)
    if isinstance(value, dict):
        return _render_map(value, indent_level)
    raise TypeError(f"unsupported Terraform value type: {type(value).__name__}")


def _render_list(values: list[Any], indent_level: int) -> str:
    if not values:
        return "[]"
    rendered_values = [render_value(value, indent_level) for value in values]
    if all("\n" not in rendered for rendered in rendered_values):
        return f"[{', '.join(rendered_values)}]"

    indent = "  " * indent_level
    child_indent = "  " * (indent_level + 1)
    lines = ["["]
    for rendered in rendered_values:
        lines.append(f"{child_indent}{rendered},")
    lines.append(f"{indent}]")
    return "\n".join(lines)


def _render_map(values: dict[str, Any], indent_level: int) -> str:
    if not values:
        return "{}"
    indent = "  " * indent_level
    child_indent = "  " * (indent_level + 1)
    lines = ["{"]
    max_key_len = max(len(_render_map_key(key)) for key in values.keys())
    for key, value in values.items():
        k_str = _render_map_key(key)
        padding = " " * (max_key_len - len(k_str))
        lines.append(f"{child_indent}{k_str}{padding} = {render_value(value, indent_level + 1)}")
    lines.append(f"{indent}}}")
    return "\n".join(lines)


def _render_map_key(key: str) -> str:
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
        return key
    return json.dumps(key)

