# Cold-start mitigation

Render Starter web services scale to zero after ~15 min idle. The first request after that idle window has to pull the image, boot the container, finish the FastAPI lifespan startup, and only then accept traffic. Observed wall-clock for a fresh Ospra boot was 30–90 s, which the user experienced as "the login page hangs for minutes."

This doc captures the three-prong mitigation that landed in this pass and the one operational step that has to happen outside the codebase.

## What was changed

### 1. Lifespan split (`ospra_os/main.py`)

`_run_startup` previously did 17 sequential steps before yielding to uvicorn — DB inits, schedulers, an outbound AliExpress HTTP call, sentiment refresher, ranking jobs, etc. Until that returned, uvicorn did not bind the port.

It is now split into:

- **`_run_startup_critical`** — env validation + the one DB init that handlers genuinely need (`init_database`). Runs serially before the lifespan yields. Typical cost: ~1–2 s.
- **`_run_startup_deferred`** — everything else. Launched as a fire-and-forget `asyncio.create_task` immediately after the critical phase. Failures are logged via a `Task.add_done_callback`; they cannot block the request loop.

On Render Starter this turns a ~30 s blocking startup into a ~2 s one. The deferred phase still runs, just out of the request path.

### 2. AliExpress token-refresh timeout

The deferred phase still calls `check_tokens_on_startup`, which makes an outbound HTTP request to AliExpress. AliExpress is regionally flaky; without a bound it could stall the rest of deferred startup for the full 30 s default `httpx` timeout.

The call is now wrapped:

```python
await asyncio.wait_for(check_tokens_on_startup(), timeout=15.0)
```

…and runs as its own sub-task so a slow response doesn't queue the sentiment refresher behind it. The scheduler itself fires every 12 hours, so missing a startup tick is harmless — the next scheduled tick will retry.

### 3. GitHub Actions keep-alive (`.github/workflows/keep-alive.yml`)

Even with the lifespan fix, the very first request after Render scales to zero pays container-spin-up time (~10 s on Starter). The cheapest way to never see that is to never let Render scale the service down.

A new workflow pings `/health` every 10 minutes. Render's idle timeout is 15 min, so 10 gives one safe "missed run" of headroom. The workflow reads the URL from a repo secret so we can rotate the host without editing the file.

## One-time setup outside the codebase

The keep-alive workflow needs a repo secret to know what to ping:

1. **GitHub repo → Settings → Secrets and variables → Actions → New repository secret**
2. Name: `OSPRA_API_HEALTH_URL`
3. Value: `https://ospra-intelligence-api.onrender.com/health` (or whatever the prod backend URL is)

Once set, the workflow runs every 10 minutes. Confirm it's working from the **Actions** tab — runs should be green, output should show `Ping … → HTTP 200`.

If the workflow logs `OSPRA_API_HEALTH_URL secret is not set — skipping ping.`, the secret was not configured; go back to step 1.

## Rolling back

Any of the three pieces can be disabled independently:

- **Restore the old lifespan**: revert `_run_startup_critical` / `_run_startup_deferred` back to a single `_run_startup`. The git history preserves the original.
- **Disable the keep-alive cron**: delete `.github/workflows/keep-alive.yml`, OR unset the `OSPRA_API_HEALTH_URL` secret (the workflow will no-op and exit 0).
- **Drop the AliExpress timeout**: replace `asyncio.wait_for(check_tokens_on_startup(), timeout=15.0)` with the original `await check_tokens_on_startup()`.

## When to remove the keep-alive cron

If the project moves to a Render plan that doesn't scale to zero (Standard, ~$25/mo as of 2026-04), the cron becomes redundant. Delete the workflow rather than leave it running pointlessly — every 10 min × 24h × 30d = 4,320 free CI minutes/month consumed for nothing.

## Frontend awareness

`frontend/src/components/auth/LoginForm.jsx` already polls `/health` and shows a "Server waking up…" indicator while the backend is booting. With this mitigation in place, that indicator should fire approximately never. If it starts firing again, check:

1. Is the GitHub Actions cron still green? (Actions tab)
2. Is `OSPRA_API_HEALTH_URL` still pointing at the right host?
3. Did Render spin up a new region or rotate the URL?
