"""Session rotation — execute sessions only."""

DEFAULT_EXECUTE_THRESHOLD = 100


def should_rotate(action: str, event_count: int, threshold: int = DEFAULT_EXECUTE_THRESHOLD) -> bool:
    """Only rotate execute sessions (includes fix-review, fix-tests)."""
    if action not in ("execute", "implement", "fix-review", "fix-tests"):
        return False
    return event_count >= threshold
