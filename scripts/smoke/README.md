# Smoke harnesses

These scripts used to live in `tests/` but they aren't pytest tests —
they're standalone smoke harnesses you run by hand against a local
backend / dev SQLite. Each had a module-level `pytest.skip(...)` to keep
the pytest runner from picking them up; moving them out of `tests/`
removes the noise from the pytest collection without losing the scripts
themselves.

## What's here

- `multi_store.py` — multi-store smoke flow (per-store DB, niche routing).
- `multi_store_system.py` — broader integration smoke covering
  multi-store + supplier hand-off.
- `saturation_system.py` — saturation/launch-readiness smoke; uses
  `./data/multi_store.db` and a stale `ProductIntelligenceEngine`
  signature, so expect to update the imports before re-running.
- `tier_system.py` — tier-gating smoke; needs a backend running at
  `localhost:8001` and the dev SQLite at `./oubon_store.db`.

## Run

From the repo root:

```bash
python scripts/smoke/multi_store_system.py
```

These are NOT part of CI. Treat them as scratchpads for local
investigation; rewrite them into real pytest tests if a piece becomes
worth gating CI on.
