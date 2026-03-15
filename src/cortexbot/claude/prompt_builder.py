"""Prompt template builder with {{variable}} substitution."""

from __future__ import annotations

from pathlib import Path


def load_template(path: Path) -> str:
    """Load a prompt template from file.

    Args:
        path: Path to .md template file

    Returns:
        Template content as string

    Raises:
        FileNotFoundError: If template doesn't exist
    """
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    return path.read_text(encoding="utf-8")


def build_prompt(template: str, **variables: str) -> str:
    """Replace {{variable}} placeholders with values.

    Variables not provided are left as-is ({{var}}).

    Args:
        template: Template string with {{variable}} placeholders
        **variables: Variable name/value pairs

    Returns:
        Template with variables substituted
    """
    result = template
    for name, value in variables.items():
        result = result.replace(f"{{{{{name}}}}}", value)
    return result
