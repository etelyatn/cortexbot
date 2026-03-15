"""Tests for prompt template builder."""

from pathlib import Path

import pytest

from cortexbot.claude.prompt_builder import build_prompt, load_template


class TestLoadTemplate:
    """Test template file loading."""

    def test_load_existing_template(self, tmp_dir: Path) -> None:
        """Load template from file."""
        tmpl = tmp_dir / "test.md"
        tmpl.write_text("Hello {{name}}, welcome to {{project}}!")
        content = load_template(tmpl)
        assert "{{name}}" in content

    def test_load_missing_template_raises(self, tmp_dir: Path) -> None:
        """Missing template raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_template(tmp_dir / "nonexistent.md")


class TestBuildPrompt:
    """Test variable substitution in templates."""

    def test_simple_substitution(self) -> None:
        """Replace {{var}} with value."""
        template = "Project: {{project_name}}, Branch: {{branch}}"
        result = build_prompt(template, project_name="Sandbox", branch="task/123-test")
        assert result == "Project: Sandbox, Branch: task/123-test"

    def test_missing_variable_left_as_is(self) -> None:
        """Unreplaced variables remain as {{var}}."""
        template = "Hello {{name}}, your role is {{role}}"
        result = build_prompt(template, name="Alice")
        assert "Alice" in result
        assert "{{role}}" in result

    def test_multiline_template(self) -> None:
        """Variables replaced across multiple lines."""
        template = "# {{title}}\n\nBranch: {{branch}}\nPhase: {{current_phase}}"
        result = build_prompt(
            template, title="My Task", branch="task/1-my-task", current_phase="design"
        )
        assert "# My Task" in result
        assert "Branch: task/1-my-task" in result

    def test_repeated_variable(self) -> None:
        """Same variable used multiple times is replaced everywhere."""
        template = "{{name}} is great. {{name}} is awesome."
        result = build_prompt(template, name="CortexBot")
        assert result == "CortexBot is great. CortexBot is awesome."

    def test_empty_value(self) -> None:
        """Empty string value replaces variable."""
        template = "Context: {{error_context}}"
        result = build_prompt(template, error_context="")
        assert result == "Context: "
