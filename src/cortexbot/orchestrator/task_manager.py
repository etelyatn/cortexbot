"""V2 artifact-driven task state management."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class SessionRecord:
    session_id: str
    action: str
    started_at: str
    ended_at: Optional[str] = None
    exit_reason: str = ""
    tokens_used: int = 0

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "action": self.action,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "exit_reason": self.exit_reason,
            "tokens_used": self.tokens_used,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SessionRecord":
        return cls(**d)


@dataclass
class ReviewResult:
    passed: bool
    feedback_summary: str
    review_output_path: Optional[str] = None
    timestamp: str = ""

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "feedback_summary": self.feedback_summary,
            "review_output_path": self.review_output_path,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ReviewResult":
        return cls(**d)


@dataclass
class TestResult:
    passed: bool
    summary: str
    failed_tests: list[str] = field(default_factory=list)
    log_path: Optional[str] = None
    timestamp: str = ""

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "summary": self.summary,
            "failed_tests": self.failed_tests,
            "log_path": self.log_path,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TestResult":
        return cls(**d)


@dataclass
class TaskState:
    task_id: str
    project: str
    description: str

    # Artifact trail
    spec_path: Optional[str] = None
    plan_path: Optional[str] = None
    branch_name: Optional[str] = None
    implementation_complete: bool = False
    review_result: Optional[ReviewResult] = None
    test_result: Optional[TestResult] = None

    # Cycle tracking
    review_cycle: int = 0
    test_cycle: int = 0
    max_cycles: int = 3

    # Session management
    session_id: Optional[str] = None
    subprocess_pid: Optional[int] = None
    sessions: list[SessionRecord] = field(default_factory=list)

    # Token budget
    token_budget: int = 500_000
    tokens_used: int = 0

    # Telegram
    telegram_chat_id: int = 0
    telegram_thread_id: Optional[int] = None
    telegram_status_message_id: Optional[int] = None

    # Auto mode
    auto_mode: bool = False

    # Lifecycle
    status: str = "active"
    last_error: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""

    @property
    def review_passed(self) -> bool:
        return self.review_result is not None and self.review_result.passed

    @property
    def tests_passed(self) -> bool:
        return self.test_result is not None and self.test_result.passed

    @property
    def next_action(self) -> str:
        if self.status != "active":
            return "paused"
        if self.tokens_used >= self.token_budget:
            return "budget-exceeded"

        # Failure cycles — check before happy path
        if self.test_result and not self.test_result.passed:
            return "escalate" if self.test_cycle >= self.max_cycles else "fix-tests"
        if self.review_result and not self.review_result.passed:
            return "escalate" if self.review_cycle >= self.max_cycles else "fix-review"

        # Happy path
        if not self.spec_path:
            return "brainstorm"
        if not self.plan_path:
            return "plan"
        if not self.implementation_complete:
            return "implement"
        if not self.review_passed:
            return "review"
        if not self.tests_passed:
            return "test"
        return "finish"

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "project": self.project,
            "description": self.description,
            "spec_path": self.spec_path,
            "plan_path": self.plan_path,
            "branch_name": self.branch_name,
            "implementation_complete": self.implementation_complete,
            "review_result": self.review_result.to_dict() if self.review_result else None,
            "test_result": self.test_result.to_dict() if self.test_result else None,
            "review_cycle": self.review_cycle,
            "test_cycle": self.test_cycle,
            "max_cycles": self.max_cycles,
            "session_id": self.session_id,
            "subprocess_pid": self.subprocess_pid,
            "sessions": [s.to_dict() for s in self.sessions],
            "token_budget": self.token_budget,
            "tokens_used": self.tokens_used,
            "telegram_chat_id": self.telegram_chat_id,
            "telegram_thread_id": self.telegram_thread_id,
            "telegram_status_message_id": self.telegram_status_message_id,
            "auto_mode": self.auto_mode,
            "status": self.status,
            "last_error": self.last_error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TaskState":
        review = d.get("review_result")
        test = d.get("test_result")
        sessions = d.get("sessions", [])
        return cls(
            task_id=d["task_id"],
            project=d["project"],
            description=d["description"],
            spec_path=d.get("spec_path"),
            plan_path=d.get("plan_path"),
            branch_name=d.get("branch_name"),
            implementation_complete=d.get("implementation_complete", False),
            review_result=ReviewResult.from_dict(review) if review else None,
            test_result=TestResult.from_dict(test) if test else None,
            review_cycle=d.get("review_cycle", 0),
            test_cycle=d.get("test_cycle", 0),
            max_cycles=d.get("max_cycles", 3),
            session_id=d.get("session_id"),
            subprocess_pid=d.get("subprocess_pid"),
            sessions=[SessionRecord.from_dict(s) for s in sessions],
            token_budget=d.get("token_budget", 500_000),
            tokens_used=d.get("tokens_used", 0),
            telegram_chat_id=d.get("telegram_chat_id", 0),
            telegram_thread_id=d.get("telegram_thread_id"),
            telegram_status_message_id=d.get("telegram_status_message_id"),
            auto_mode=d.get("auto_mode", False),
            status=d.get("status", "active"),
            last_error=d.get("last_error"),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
        )
