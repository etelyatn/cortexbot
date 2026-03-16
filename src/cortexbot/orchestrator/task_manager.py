"""Task state management and phase transitions."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

PHASES = ["design", "plan", "implement", "test", "merge"]


def next_phase(current: str) -> str | None:
    """Return the phase after current, or None if current is merge."""
    try:
        idx = PHASES.index(current)
    except ValueError:
        return None
    if idx + 1 >= len(PHASES):
        return None
    return PHASES[idx + 1]


def slugify(title: str, max_len: int = 50) -> str:
    """Convert title to URL-safe branch slug."""
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug[:max_len].rstrip("-")


@dataclass
class Artifact:
    """A tracked artifact (design doc, PR, screenshot, etc.)."""

    artifact_type: str
    path: str
    phase: str

    def to_dict(self) -> dict[str, str]:
        return {"type": self.artifact_type, "path": self.path, "phase": self.phase}

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> Artifact:
        return cls(
            artifact_type=data["type"], path=data["path"], phase=data["phase"]
        )


@dataclass
class PhaseRecord:
    """Record of a completed (or skipped/rolled-back) phase."""

    phase: str
    status: str  # completed | skipped | rolled_back
    summary: str | None = None
    artifacts: list[str] = field(default_factory=list)
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "status": self.status,
            "summary": self.summary,
            "artifacts": self.artifacts,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PhaseRecord:
        return cls(
            phase=data["phase"],
            status=data["status"],
            summary=data.get("summary"),
            artifacts=data.get("artifacts", []),
            timestamp=data.get("timestamp", ""),
        )


@dataclass
class TaskState:
    """Full task state, persisted as JSON."""

    thread_id: int
    title: str
    project: str
    branch: str
    current_phase: str
    current_phase_status: str  # pending | in_progress | interrupted | completed | done
    autonomy: str
    session_id: str | None
    session_event_count: int
    phase_history: list[PhaseRecord]
    artifacts: list[Artifact]
    budget_usd: float
    retry_count: int
    last_error: str | None
    subprocess_pid: int | None
    created_at: str
    updated_at: str

    @classmethod
    def create(
        cls,
        *,
        thread_id: int,
        title: str,
        project: str,
        budget_usd: float,
        autonomy: str = "supervised",
    ) -> TaskState:
        """Create a new task in its initial state."""
        now = datetime.now(timezone.utc).isoformat()
        return cls(
            thread_id=thread_id,
            title=title,
            project=project,
            branch=f"task/{thread_id}-{slugify(title)}",
            current_phase="design",
            current_phase_status="pending",
            autonomy=autonomy,
            session_id=None,
            session_event_count=0,
            phase_history=[],
            artifacts=[],
            budget_usd=budget_usd,
            retry_count=0,
            last_error=None,
            subprocess_pid=None,
            created_at=now,
            updated_at=now,
        )

    def advance_phase(
        self, summary: str | None = None, artifacts: list[str] | None = None
    ) -> None:
        """Record current phase as completed and advance to next.

        If already at merge, marks task as done.
        """
        self.phase_history.append(
            PhaseRecord(
                phase=self.current_phase,
                status="completed",
                summary=summary,
                artifacts=artifacts or [],
            )
        )

        nxt = next_phase(self.current_phase)
        if nxt is None:
            # Already at merge — task complete
            self.current_phase_status = "done"
        else:
            self.current_phase = nxt
            self.current_phase_status = "pending"

        self.retry_count = 0
        self.session_id = None
        self.session_event_count = 0
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def add_artifact(self, artifact_type: str, path: str, phase: str) -> None:
        """Track a new artifact."""
        self.artifacts.append(Artifact(artifact_type=artifact_type, path=path, phase=phase))
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def deduct_cost(self, cost_usd: float) -> None:
        """Deduct cost from remaining budget."""
        self.budget_usd = max(0.0, self.budget_usd - cost_usd)
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def add_budget(self, amount_usd: float) -> None:
        """Add budget to remaining balance."""
        self.budget_usd += amount_usd
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def calculate_phase_budget(self) -> float:
        """Calculate budget for the next phase.

        Formula per spec: 50% of remaining divided across remaining phase count.
        Last phase gets all remaining budget.
        """
        remaining_phases = len(PHASES) - PHASES.index(self.current_phase)
        if remaining_phases <= 1:
            return max(1.0, self.budget_usd)

        phase_budget = (self.budget_usd * 0.5) / remaining_phases
        return max(1.0, round(phase_budget, 2))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "thread_id": self.thread_id,
            "title": self.title,
            "project": self.project,
            "branch": self.branch,
            "current_phase": self.current_phase,
            "current_phase_status": self.current_phase_status,
            "autonomy": self.autonomy,
            "session_id": self.session_id,
            "session_event_count": self.session_event_count,
            "phase_history": [r.to_dict() for r in self.phase_history],
            "artifacts": [a.to_dict() for a in self.artifacts],
            "budget_usd": self.budget_usd,
            "retry_count": self.retry_count,
            "last_error": self.last_error,
            "subprocess_pid": self.subprocess_pid,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskState:
        """Deserialize from JSON-compatible dict."""
        return cls(
            thread_id=data["thread_id"],
            title=data["title"],
            project=data["project"],
            branch=data["branch"],
            current_phase=data["current_phase"],
            current_phase_status=data["current_phase_status"],
            autonomy=data["autonomy"],
            session_id=data.get("session_id"),
            session_event_count=data.get("session_event_count", 0),
            phase_history=[PhaseRecord.from_dict(r) for r in data.get("phase_history", [])],
            artifacts=[Artifact.from_dict(a) for a in data.get("artifacts", [])],
            budget_usd=data["budget_usd"],
            retry_count=data.get("retry_count", 0),
            last_error=data.get("last_error"),
            subprocess_pid=data.get("subprocess_pid"),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )
