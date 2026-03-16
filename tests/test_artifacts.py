"""Tests for artifact tracking."""

import pytest

from cortexbot.memory.artifacts import extract_artifacts_from_status


class TestExtractArtifacts:
    """Test artifact extraction from status blocks."""

    def test_extracts_doc_artifacts(self) -> None:
        """Recognize design docs and impl guides."""
        paths = ["docs/plans/2026-03-15-design.md"]
        result = extract_artifacts_from_status(paths, phase="design")
        assert len(result) == 1
        assert result[0]["type"] == "design_doc"

    def test_extracts_pr_artifact(self) -> None:
        """Recognize PR URLs."""
        paths = ["https://github.com/org/repo/pull/42"]
        result = extract_artifacts_from_status(paths, phase="merge")
        assert len(result) == 1
        assert result[0]["type"] == "pr"

    def test_extracts_generic_artifacts(self) -> None:
        """Non-recognized paths are tracked as generic files."""
        paths = ["src/cortexbot/new_file.py"]
        result = extract_artifacts_from_status(paths, phase="implement")
        assert len(result) == 1
        assert result[0]["type"] == "file"

    def test_empty_list(self) -> None:
        result = extract_artifacts_from_status([], phase="design")
        assert result == []

    def test_extracts_impl_guide(self) -> None:
        """Recognize impl guides."""
        paths = ["docs/plans/2026-03-15-impl-guide.md"]
        result = extract_artifacts_from_status(paths, phase="plan")
        assert len(result) == 1
        assert result[0]["type"] == "impl_guide"

    def test_extracts_screenshot(self) -> None:
        """Recognize screenshot images."""
        paths = ["screenshots/test_result.png"]
        result = extract_artifacts_from_status(paths, phase="test")
        assert len(result) == 1
        assert result[0]["type"] == "screenshot"

    def test_extracts_diff(self) -> None:
        """Recognize diff/patch files."""
        paths = ["changes.diff"]
        result = extract_artifacts_from_status(paths, phase="merge")
        assert len(result) == 1
        assert result[0]["type"] == "diff"
