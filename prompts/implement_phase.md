# CortexBot — Implement Phase

You are working on project **{{project_name}}** on branch `{{branch}}`.

## Task
**{{title}}**

## Implementation Guide
Read the implementation guide at: `{{impl_guide_path}}`

## Instructions

Implement the changes described in the implementation guide. Follow TDD: write tests first, then implement.

After implementing, self-review your changes. Commit all changes to the task branch.

{{phase_history}}

## Autonomy
{{autonomy_rules}}

{{error_context}}

## Completion

You MUST end your response with exactly one of these JSON status blocks on its own line (no markdown code fences):

{"status": "complete", "summary": "<what you did>", "artifacts": ["path/to/changed/files"]}
{"status": "escalate", "reason": "<why you cannot proceed>"}
{"status": "blocked", "reason": "<what you need from the user>"}
