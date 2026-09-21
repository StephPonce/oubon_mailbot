---
description: "Implement one feature from the feature spec (F1–F8) with tests, migration, and ledger review. Usage — /ship-feature F2"
---
Feature to ship: $ARGUMENTS

1. Read docs/handoff/02-OSPRA-FEATURE-SPEC.md and the section for this feature; read 01-OUBON-PRODUCT-SPEC.md if the feature touches the fit gate, and 07-AGENTIC-PLAYBOOK.md Part 1 if it executes actions autonomously.
2. Plan first: list files to touch, new models, migrations, Celery jobs, endpoints, and tests. Show the plan and wait for my go.
3. Implement following existing repo patterns. Every action or prediction the feature produces must write to or read from the F1 ledger; if it does neither, stop and tell me.
4. Loud failures only — no swallowed exceptions, no empty-data fallthrough.
5. Add tests per endpoint/job; add a reversible migration for any model change.
6. Run the ledger-guardian subagent on the diff if any ledger table is touched. Run the harness-reviewer if any LLM call was added or changed.
7. Finish with: what shipped, how to verify it manually, what's still open.
