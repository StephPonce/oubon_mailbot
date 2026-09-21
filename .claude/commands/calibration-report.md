---
description: Generate the weekly calibration report from the ledger (grades vs outcomes) and interpret it.
---
Window (optional, default last 28 days): $ARGUMENTS

1. Query grade_snapshots joined to product_outcomes (and proxy outcomes for undeployed products) for the window.
2. Compute Spearman rank correlation of grade vs order velocity and grade vs proxy score; report n, the correlation, and a per-factor breakdown of which factors correlated best and worst.
3. List the 5 biggest misses (high grade, poor outcome) and 5 biggest surprises (low grade, strong outcome) with their source manifests — were sources missing at prediction time?
4. State plainly whether the ≥ 0.4 launch-gate threshold is met. If not, propose weight adjustments and note that any change requires a before/after comparison — never tune to flatter a favorite.
5. Write the report to docs/calibration/YYYY-MM-DD.md and print a 6-line summary.
