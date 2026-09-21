---
description: Run Audit A — grading/intelligence integrity audit. Produces OPEN_ISSUES.md.
---
Read docs/handoff/00-OSPRA-MASTER-HANDOFF.md and docs/handoff/02-OSPRA-FEATURE-SPEC.md first. Then execute Audit A end to end. Scope (optional): $ARGUMENTS

1. GRADE INTEGRITY — trace the 0–10 scoring pipeline end to end; list every factor, weight, and data source. Hunt mocked/hardcoded/fallback values: grep for mock, placeholder, TODO, FIXME, HACK, dummy, sample.
2. GRADE LOGGING — do daily grades + factor breakdowns persist anywhere? If not, spec the F1 tables and write path.
3. PROFIT CALCULATOR — list every cost assumption; mark live-data vs hardcoded constant.
4. SELF-LEARNING — is there any code path writing real outcomes back into scoring, or is it design-only?
5. PRODUCTION TRUTH — diff local env vs Render config; CJ credential status; vars set locally but missing in prod.
6. Write OPEN_ISSUES.md ranked (a) blocks validation (b) blocks SaaS (c) cosmetic. For each: file path, effort estimate, and flag any "looks functional but isn't" case.

Do not fix anything during the audit. Use the ledger-guardian and harness-reviewer subagents for the relevant sections. Finish with a 10-line executive summary.
