# CortexBot — Plan Phase

You are working on project **{{project_name}}** on branch `{{branch}}`.

## Task
**{{title}}**

## Design Document
Read the design document at: `{{design_doc_path}}`

## Instructions

Create an implementation guide based on the design document. Break the work into specific, actionable steps.

Save the implementation guide to `docs/plans/` with an appropriate filename.

{{phase_history}}

## Autonomy
{{autonomy_rules}}

{{error_context}}

## Completion

You MUST end your response with exactly one of these JSON status blocks on its own line (no markdown code fences):

{"status": "complete", "summary": "<what you did>", "artifacts": ["docs/plans/your-impl-guide.md"]}
{"status": "escalate", "reason": "<why you cannot proceed>"}
{"status": "blocked", "reason": "<what you need from the user>"}
