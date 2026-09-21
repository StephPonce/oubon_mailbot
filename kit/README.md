# OSPRA CLAUDE KIT — skills, subagents, commands, hooks
*Drop-in Claude Code customization for the three terminals. Formats follow current Claude Code conventions: project skills in `.claude/skills/<name>/SKILL.md`, subagents in `.claude/agents/*.md`, slash commands in `.claude/commands/*.md`, hooks in `.claude/settings.json`. Skills hot-reload; run `/reload-skills` if a session was already open.*

## Install — Ospra repo (Terminal 1)
```bash
mkdir -p .claude/skills .claude/agents .claude/commands docs/handoff
cp -r kit/skills/ospra-* kit/skills/oubon-brand .claude/skills/
cp kit/agents/*.md .claude/agents/
cp kit/commands/{audit-a,audit-b,ship-feature,calibration-report}.md .claude/commands/
cp kit/settings/ospra.settings.json .claude/settings.json   # merge if you already have one
cp 0*-*.md docs/handoff/                                     # the numbered handoff docs
git add .claude docs && git commit -m "claude kit: skills, agents, commands, hooks"
```
Then in Claude Code: `/reload-skills` → `/audit-a` → `/audit-b` → `/ship-feature F1`.

## Install — Oubon theme repo (Terminal 2)
```bash
mkdir -p .claude/skills .claude/commands design
cp -r kit/skills/oubon-brand .claude/skills/
cp kit/commands/build-section.md .claude/commands/
cp kit/settings/theme.settings.json .claude/settings.json
cp OUBON-DESIGN-BRIEF.md CLAUDE.md
cp oubon-homepage-*.html 04-OUBON-THEME-BUILD.md design/
```
Then: `/build-section tokens` → `/build-section hero-dimmer` → … in the order from file 04.

## Terminal 3 (Paperwell)
No kit needed beyond `oubon-brand` if you want the landing copy on-voice. Sonnet 5 is fine here.

## Claude.ai / Claude Desktop
The `.skill` files can be saved into your Claude profile (Save skill button) so Desktop planning sessions and chat use the same fit gate, product-intel loop, niche method, and brand rules as the pipeline. Same judgment everywhere — that's the point.

## What each piece does
| Piece | Type | Purpose |
|---|---|---|
| ospra-fit-gate | skill | Curation gate + scene/role assignment, JSON output (file 01, feature F2) |
| ospra-product-intel | skill | The research loop + grading rubric + honesty clause + F1-aligned output |
| ospra-listing-aeo | skill | Agent-ready listings; metafield deploy contract |
| ospra-ad-angles | skill | Hooks/scripts/budget caps/kill rules with compliance guardrails |
| ospra-support-email | skill | Hybrid quiet-hours flow, classification, privacy guardrails, escalation |
| ospra-niche-analysis | skill | Niche scorecard, weekly pulse, paper-trade protocol (F8) |
| oubon-brand | skill | Voice, naming, tokens, imagery, scenes — loads on any "Oubon" mention |
| ledger-guardian | subagent | Blocks anything that makes the ledger mutable or incomplete |
| harness-reviewer | subagent | Finds the six harness flaws at every LLM call site |
| /audit-a, /audit-b | commands | The Sprint-0 audits, one keystroke each |
| /ship-feature F# | command | Spec-driven feature build with ledger + harness review baked in |
| /calibration-report | command | Weekly grades-vs-outcomes report; the launch-gate check |
| /build-section | command | Theme section build loop with Liquid lookups + theme check |
| settings hooks | hooks | Auto-run tests / theme check after every edit (non-blocking) |

## Production reuse (the real payoff)
These same SKILL.md files are the specs for the Agent SDK agents in file 07 §2.2 — load them as skills in the production harness so pipeline-Claude and chat-Claude share one brain. Version them in git; run the golden-set eval before any change ships.
