"""Artifact tracking — classify and record artifacts from phase output."""

from __future__ import annotations


def extract_artifacts_from_status(
    paths: list[str], phase: str
) -> list[dict[str, str]]:
    """Classify artifact paths from a status block.

    Args:
        paths: List of file paths or URLs from status block
        phase: Phase that produced these artifacts

    Returns:
        List of dicts with type, path, phase
    """
    results = []
    for path in paths:
        artifact_type = _classify(path, phase)
        results.append({"type": artifact_type, "path": path, "phase": phase})
    return results


def _classify(path: str, phase: str) -> str:
    """Classify an artifact path into a type."""
    lower = path.lower()

    if "github.com" in lower and "/pull/" in lower:
        return "pr"
    if lower.endswith((".png", ".jpg", ".jpeg", ".bmp")):
        return "screenshot"
    if phase == "design" and lower.endswith(".md"):
        return "design_doc"
    if phase == "plan" and lower.endswith(".md"):
        return "impl_guide"
    if lower.endswith((".diff", ".patch")):
        return "diff"

    return "file"
