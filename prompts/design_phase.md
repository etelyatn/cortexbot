# CortexBot — Design Phase

You are working on project **{{project_name}}** on branch `{{branch}}`.

## Task
**{{title}}**

## Instructions

Create a design document for this task. Research the codebase, understand the requirements, and write a comprehensive design document.

Save the design document to `docs/plans/` with an appropriate filename.

{{phase_history}}

## Autonomy
{{autonomy_rules}}

{{error_context}}

## Completion

You MUST end your response with exactly one of these JSON status blocks on its own line (no markdown code fences):

{"status": "complete", "summary": "<what you did>", "artifacts": ["docs/plans/your-design-doc.md"]}
{"status": "escalate", "reason": "<why you cannot proceed>"}
{"status": "blocked", "reason": "<what you need from the user>"}
