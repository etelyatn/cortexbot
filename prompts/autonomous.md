## Autonomous Mode Rules

- Proceed to the next phase automatically after completing the current one
- On errors: retry up to 3 times with error context. If the same error occurs twice consecutively, escalate immediately
- On ambiguity: make your best judgment, document your reasoning, and continue
- Only stop for: exhausted retries, broken build, or need for external input
