---
description: Run Audit B — LLM harness audit of every Anthropic API call site.
---
Read docs/handoff/00-OSPRA-MASTER-HANDOFF.md first. Then, using the harness-reviewer subagent on every file that calls the Anthropic API or assembles prompts:

1. Dump the FULL prompt + raw response for 3 recent product/niche analyses (from logs or by running the pipeline in a dry mode). Report what data actually reached the model.
2. Find exception handlers that swallow API/data failures and pass empty or partial data downstream. List each with a proposed loud-failure replacement.
3. Record the model + max_tokens + effort config for every analysis endpoint. Flag analysis on small models and labeling on expensive ones.
4. Check every system prompt for: data-source manifest requirement, "DATA UNAVAILABLE over inference" clause, confidence field.
5. Identify one-shot calls that should be multi-step loops; propose the loop shape and whether the Anthropic server-side web_search tool applies.
6. Propose a golden set: 5 products with known-good analyses, and how the eval would run on every prompt/model change.

Append findings to OPEN_ISSUES.md under "HARNESS". Scope (optional): $ARGUMENTS
